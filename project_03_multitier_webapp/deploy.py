"""
PROJECT 3 — Multi-tier Web App Deployment
Services: EC2 (frontend + backend), RDS MySQL (database), ALB

Architecture:
  Internet → ALB → EC2 App Servers → RDS MySQL

What this does:
  1. Creates 2 Security Groups: one for web/app EC2, one for RDS
  2. Creates an RDS MySQL instance (db.t3.micro)
  3. Creates a Launch Template with a Flask app that queries RDS
  4. Creates an ALB + Target Group
  5. Creates an Auto Scaling Group (min=1, desired=2, max=4)
"""

import sys, os, base64, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p03-multitier"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
DB_NAME    = "capstonedb"
DB_USER    = "admin"


def get_user_data(rds_endpoint: str) -> str:
    script = f"""#!/bin/bash
yum update -y
yum install -y python3 python3-pip
pip3 install flask pymysql

INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
AZ=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)

cat > /home/ec2-user/app.py <<'PYEOF'
from flask import Flask, jsonify
import pymysql, os, socket

app = Flask(__name__)

DB_HOST = "{rds_endpoint}"
DB_USER = "{DB_USER}"
DB_PASS = "{DB_PASSWORD}"
DB_NAME = "{DB_NAME}"

@app.route("/")
def home():
    try:
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS,
                               database=DB_NAME, connect_timeout=3)
        conn.close()
        db_status = "Connected"
        db_color  = "#22c55e"
    except Exception as e:
        db_status = f"Error: {{e}}"
        db_color  = "#ef4444"

    instance_id = os.popen("curl -s http://169.254.169.254/latest/meta-data/instance-id").read()
    az = os.popen("curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone").read()

    return f'''<!DOCTYPE html>
<html>
<head>
  <title>Project 3 - Multi-tier App</title>
  <style>
    body{{{{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;
         display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}}}
    .card{{{{background:#1e293b;border-radius:16px;padding:40px;max-width:600px;text-align:center}}}}
    h1{{{{color:#a78bfa}}}} .badge{{{{background:#7c3aed;color:#fff;border-radius:999px;
        padding:4px 14px;display:inline-block;margin:4px}}}}
    .db{{{{color:{{db_color}};font-weight:bold}}}}
  </style>
</head>
<body>
  <div class="card">
    <h1>Project 3 - Multi-tier Web App</h1>
    <p><b>Frontend + Backend (Flask) + Database (RDS MySQL)</b></p>
    <hr style="border-color:#334155;margin:20px 0">
    <p>Instance: <span class="badge">{{instance_id}}</span></p>
    <p>Zone: <span class="badge">{{az}}</span></p>
    <p>DB Host: <span class="badge">{rds_endpoint}</span></p>
    <p>DB Status: <span class="db">{{db_status}}</span></p>
  </div>
</body>
</html>'''

@app.route("/health")
def health():
    return jsonify({{"status": "ok", "instance": socket.gethostname()}})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
PYEOF

python3 /home/ec2-user/app.py &
"""
    return script


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 3 — Multi-tier Web App")
    print("="*60)

    ec2  = boto3_client("ec2")
    rds  = boto3_client("rds")
    elb  = boto3_client("elbv2")
    asg  = boto3_client("autoscaling")

    vpc_id, subnet_ids = get_default_vpc_and_subnets()
    info(f"VPC: {vpc_id}")

    # ── Security Groups ──────────────────────────────────────────────────────
    web_sg_id = create_security_group(
        f"{PROJECT}-web-sg", "Web Tier Security Group", vpc_id,
        [
            {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
             "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
            {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
             "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
        ],
    )
    db_sg_id = create_security_group(
        f"{PROJECT}-db-sg", "DB Tier Security Group", vpc_id,
        [
            {"IpProtocol": "tcp", "FromPort": 3306, "ToPort": 3306,
             "UserIdGroupPairs": [{"GroupId": web_sg_id}]},
        ],
    )

    # ── RDS Subnet Group ─────────────────────────────────────────────────────
    try:
        rds.create_db_subnet_group(
            DBSubnetGroupName=f"{PROJECT}-subnet-grp",
            DBSubnetGroupDescription="Capstone P3 DB Subnet Group",
            SubnetIds=subnet_ids,
        )
        ok("RDS Subnet Group created")
    except Exception as e:
        warn(f"Subnet group: {e}")

    # ── RDS MySQL Instance ───────────────────────────────────────────────────
    info("Creating RDS MySQL instance (this takes 5-10 min)...")
    rds_id = f"{PROJECT}-rds"
    try:
        rds.create_db_instance(
            DBInstanceIdentifier=rds_id,
            DBInstanceClass="db.t3.micro",
            Engine="mysql",
            EngineVersion="8.0",
            MasterUsername=DB_USER,
            MasterUserPassword=DB_PASSWORD,
            DBName=DB_NAME,
            AllocatedStorage=20,
            VpcSecurityGroupIds=[db_sg_id],
            DBSubnetGroupName=f"{PROJECT}-subnet-grp",
            PubliclyAccessible=False,
            MultiAZ=False,
            StorageType="gp2",
            Tags=get_tags(PROJECT),
        )
        ok(f"RDS instance creation started")
        waiter_msg("RDS instance to be available (~5-10 min)")
        rds_waiter = rds.get_waiter("db_instance_available")
        rds_waiter.wait(DBInstanceIdentifier=rds_id,
                        WaiterConfig={"Delay": 30, "MaxAttempts": 40})
    except rds.exceptions.DBInstanceAlreadyExistsFault:
        warn(f"RDS '{rds_id}' already exists — reusing it")
        # Still wait if it's not yet available
        db_info = rds.describe_db_instances(DBInstanceIdentifier=rds_id)["DBInstances"][0]
        if db_info["DBInstanceStatus"] != "available":
            waiter_msg("RDS instance to be available")
            rds.get_waiter("db_instance_available").wait(
                DBInstanceIdentifier=rds_id,
                WaiterConfig={"Delay": 30, "MaxAttempts": 40}
            )

    rds_info     = rds.describe_db_instances(DBInstanceIdentifier=rds_id)
    rds_endpoint = rds_info["DBInstances"][0]["Endpoint"]["Address"]
    ok(f"RDS available at: {rds_endpoint}")

    # ── Launch Template with Flask App ───────────────────────────────────────
    user_data = get_user_data(rds_endpoint)
    lt = ec2.create_launch_template(
        LaunchTemplateName=f"{PROJECT}-lt",
        LaunchTemplateData={
            "ImageId": AMI_ID,
            "InstanceType": INSTANCE_TYPE,
            "KeyName": KEY_PAIR_NAME,
            "SecurityGroupIds": [web_sg_id],
            "UserData": base64.b64encode(user_data.encode()).decode(),
            "TagSpecifications": [{"ResourceType": "instance", "Tags": get_tags(PROJECT)}],
        },
    )
    lt_id = lt["LaunchTemplate"]["LaunchTemplateId"]
    ok(f"Launch Template: {lt_id}")

    # ── ALB ──────────────────────────────────────────────────────────────────
    alb_resp = elb.create_load_balancer(
        Name=f"{PROJECT}-alb",
        Subnets=subnet_ids,
        SecurityGroups=[web_sg_id],
        Scheme="internet-facing",
        Type="application",
        Tags=get_tags(PROJECT),
    )
    alb_arn = alb_resp["LoadBalancers"][0]["LoadBalancerArn"]
    alb_dns = alb_resp["LoadBalancers"][0]["DNSName"]

    tg_resp = elb.create_target_group(
        Name=f"{PROJECT}-tg",
        Protocol="HTTP", Port=80,
        VpcId=vpc_id,
        HealthCheckPath="/health",
        TargetType="instance",
    )
    tg_arn = tg_resp["TargetGroups"][0]["TargetGroupArn"]
    elb.create_listener(
        LoadBalancerArn=alb_arn, Protocol="HTTP", Port=80,
        DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}],
    )
    ok(f"ALB + TG + Listener ready")

    # ── Auto Scaling Group ───────────────────────────────────────────────────
    asg.create_auto_scaling_group(
        AutoScalingGroupName=f"{PROJECT}-asg",
        LaunchTemplate={"LaunchTemplateId": lt_id, "Version": "$Latest"},
        MinSize=1, MaxSize=4, DesiredCapacity=2,
        VPCZoneIdentifier=",".join(subnet_ids),
        TargetGroupARNs=[tg_arn],
        HealthCheckType="ELB",
        HealthCheckGracePeriod=180,
        Tags=[{**t, "ResourceId": f"{PROJECT}-asg",
               "ResourceType": "auto-scaling-group", "PropagateAtLaunch": True}
              for t in get_tags(PROJECT)],
    )
    ok("Auto Scaling Group created")

    save_state(STATE_FILE, {
        "alb_arn": alb_arn, "tg_arn": tg_arn,
        "asg_name": f"{PROJECT}-asg", "lt_id": lt_id,
        "web_sg_id": web_sg_id, "db_sg_id": db_sg_id,
        "rds_id": f"{PROJECT}-rds",
        "rds_subnet_group": f"{PROJECT}-subnet-grp",
        "alb_dns": alb_dns,
    })

    print(f"\n  Deployment Complete!\n  URL: http://{alb_dns}\n")


if __name__ == "__main__":
    deploy()

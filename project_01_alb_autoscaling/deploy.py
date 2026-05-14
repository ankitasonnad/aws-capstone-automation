"""
╔══════════════════════════════════════════════════════════╗
║  PROJECT 1 — Scalable Web App with ALB + Auto Scaling   ║
║  Services: EC2 · Application Load Balancer · ASG        ║
╚══════════════════════════════════════════════════════════╝

What this does:
  1. Creates a Security Group that allows HTTP (80) traffic
  2. Launches a Launch Template with a simple Apache web server
  3. Creates an Application Load Balancer (ALB)
  4. Creates a Target Group and ALB Listener on port 80
  5. Creates an Auto Scaling Group (min=1, desired=2, max=4)
     that registers instances with the ALB Target Group
  6. Saves all resource IDs to state.json for cleanup
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT = "capstone-p01-alb"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

# ── User-data script that installs Apache & shows instance metadata ──────────
USER_DATA = """#!/bin/bash
yum update -y
yum install -y httpd
systemctl start httpd
systemctl enable httpd
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
AZ=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)
cat > /var/www/html/index.html <<EOF
<!DOCTYPE html>
<html>
<head>
  <title>Project 1 – ALB + Auto Scaling</title>
  <style>
    body{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;
         display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .card{background:#1e293b;border-radius:16px;padding:40px;max-width:500px;
          box-shadow:0 20px 40px rgba(0,0,0,.4);text-align:center}
    h1{color:#38bdf8;margin-bottom:8px}
    .badge{background:#0ea5e9;color:#fff;border-radius:999px;
           padding:4px 14px;font-size:.85rem;display:inline-block;margin:8px 4px}
  </style>
</head>
<body>
  <div class="card">
    <h1>🚀 Project 1</h1>
    <h2>ALB + Auto Scaling</h2>
    <p>Served by <span class="badge">$INSTANCE_ID</span></p>
    <p>Zone: <span class="badge">$AZ</span></p>
    <p style="color:#94a3b8;margin-top:20px">Refresh to see traffic distributed across instances</p>
  </div>
</body>
</html>
EOF
"""

import base64

def deploy():
    print("\n" + "="*60)
    print("  🚀  Deploying Project 1 — ALB + Auto Scaling")
    print("="*60)

    ec2  = boto3_client("ec2")
    elb  = boto3_client("elbv2")
    asg  = boto3_client("autoscaling")

    vpc_id, subnet_ids = get_default_vpc_and_subnets()
    info(f"VPC: {vpc_id}  |  Subnets: {subnet_ids}")

    # ── 1. Security Groups ───────────────────────────────────────────────────
    alb_sg_id = create_security_group(
        f"{PROJECT}-alb-sg", "ALB Security Group", vpc_id,
        [{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
    )
    ec2_sg_id = create_security_group(
        f"{PROJECT}-ec2-sg", "EC2 Security Group", vpc_id,
        [
            {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
             "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
            {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
             "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
        ],
    )

    # ── 2. Launch Template ───────────────────────────────────────────────────
    lt_resp = ec2.create_launch_template(
        LaunchTemplateName=f"{PROJECT}-lt",
        LaunchTemplateData={
            "ImageId": AMI_ID,
            "InstanceType": INSTANCE_TYPE,
            "KeyName": KEY_PAIR_NAME,
            "SecurityGroupIds": [ec2_sg_id],
            "UserData": base64.b64encode(USER_DATA.encode()).decode(),
            "TagSpecifications": [{
                "ResourceType": "instance",
                "Tags": get_tags(PROJECT),
            }],
        },
    )
    lt_id = lt_resp["LaunchTemplate"]["LaunchTemplateId"]
    ok(f"Launch Template: {lt_id}")

    # ── 3. Application Load Balancer ─────────────────────────────────────────
    alb_resp = elb.create_load_balancer(
        Name=f"{PROJECT}-alb",
        Subnets=subnet_ids,
        SecurityGroups=[alb_sg_id],
        Scheme="internet-facing",
        Type="application",
        IpAddressType="ipv4",
        Tags=get_tags(PROJECT),
    )
    alb_arn = alb_resp["LoadBalancers"][0]["LoadBalancerArn"]
    alb_dns = alb_resp["LoadBalancers"][0]["DNSName"]
    ok(f"ALB ARN: {alb_arn}")

    # ── 4. Target Group ──────────────────────────────────────────────────────
    tg_resp = elb.create_target_group(
        Name=f"{PROJECT}-tg",
        Protocol="HTTP",
        Port=80,
        VpcId=vpc_id,
        HealthCheckProtocol="HTTP",
        HealthCheckPath="/",
        HealthCheckIntervalSeconds=30,
        HealthyThresholdCount=2,
        UnhealthyThresholdCount=5,
        TargetType="instance",
    )
    tg_arn = tg_resp["TargetGroups"][0]["TargetGroupArn"]
    ok(f"Target Group: {tg_arn}")

    # ── 5. ALB Listener ──────────────────────────────────────────────────────
    elb.create_listener(
        LoadBalancerArn=alb_arn,
        Protocol="HTTP",
        Port=80,
        DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}],
    )
    ok("ALB Listener created on port 80")

    # ── 6. Auto Scaling Group ────────────────────────────────────────────────
    asg.create_auto_scaling_group(
        AutoScalingGroupName=f"{PROJECT}-asg",
        LaunchTemplate={"LaunchTemplateId": lt_id, "Version": "$Latest"},
        MinSize=1,
        MaxSize=4,
        DesiredCapacity=2,
        VPCZoneIdentifier=",".join(subnet_ids),
        TargetGroupARNs=[tg_arn],
        HealthCheckType="ELB",
        HealthCheckGracePeriod=120,
        Tags=[{**t, "ResourceId": f"{PROJECT}-asg",
               "ResourceType": "auto-scaling-group", "PropagateAtLaunch": True}
              for t in get_tags(PROJECT)],
    )
    ok("Auto Scaling Group created (min=1, desired=2, max=4)")

    # ── 7. Scaling Policies ──────────────────────────────────────────────────
    asg.put_scaling_policy(
        AutoScalingGroupName=f"{PROJECT}-asg",
        PolicyName=f"{PROJECT}-scale-out",
        PolicyType="TargetTrackingScaling",
        TargetTrackingConfiguration={
            "PredefinedMetricSpecification": {
                "PredefinedMetricType": "ASGAverageCPUUtilization"
            },
            "TargetValue": 70.0,
        },
    )
    ok("Scaling policy set: scale out at 70% CPU")

    # ── Save State ───────────────────────────────────────────────────────────
    state = {
        "alb_arn": alb_arn,
        "tg_arn": tg_arn,
        "asg_name": f"{PROJECT}-asg",
        "lt_id": lt_id,
        "alb_sg_id": alb_sg_id,
        "ec2_sg_id": ec2_sg_id,
        "alb_dns": alb_dns,
    }
    save_state(STATE_FILE, state)

    print("\n" + "="*60)
    print(f"  🎉  Deployment Complete!")
    print(f"  🌐  URL: http://{alb_dns}")
    print("  ⏳  ALB takes ~2–3 minutes to become active")
    print("="*60 + "\n")


if __name__ == "__main__":
    deploy()

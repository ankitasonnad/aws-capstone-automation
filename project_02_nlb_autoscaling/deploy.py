"""
PROJECT 2 — Scalable Web App with NLB + Auto Scaling
Services: EC2, Network Load Balancer, Auto Scaling Group
"""

import sys, os, base64
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p02-nlb"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

USER_DATA = """#!/bin/bash
yum update -y
amazon-linux-extras install nginx1 -y
systemctl start nginx
systemctl enable nginx
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
AZ=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)
cat > /usr/share/nginx/html/index.html <<EOF
<!DOCTYPE html>
<html>
<head>
  <title>Project 2 - NLB + Auto Scaling</title>
  <style>
    body{font-family:Arial,sans-serif;background:#0d1117;color:#c9d1d9;
         display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .card{background:#161b22;border:1px solid #30363d;border-radius:16px;
          padding:40px;max-width:500px;text-align:center}
    h1{color:#58a6ff}
    .badge{background:#1f6feb;color:#fff;border-radius:999px;
           padding:4px 14px;font-size:.85rem;display:inline-block;margin:4px}
  </style>
</head>
<body>
  <div class="card">
    <h1>Project 2 - NLB + Auto Scaling</h1>
    <p>Instance: <span class="badge">$INSTANCE_ID</span></p>
    <p>Zone: <span class="badge">$AZ</span></p>
    <p>NLB handles millions of requests per second with ultra-low latency</p>
  </div>
</body>
</html>
EOF
"""


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 2 - NLB + Auto Scaling")
    print("="*60)

    ec2 = boto3_client("ec2")
    elb = boto3_client("elbv2")
    asg_client = boto3_client("autoscaling")

    vpc_id, subnet_ids = get_default_vpc_and_subnets()
    info(f"VPC: {vpc_id}")

    sg_id = create_security_group(
        f"{PROJECT}-sg", "NLB EC2 Security Group", vpc_id,
        [
            {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
             "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
            {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
             "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
        ],
    )

    lt = ec2.create_launch_template(
        LaunchTemplateName=f"{PROJECT}-lt",
        LaunchTemplateData={
            "ImageId": AMI_ID,
            "InstanceType": INSTANCE_TYPE,
            "KeyName": KEY_PAIR_NAME,
            "SecurityGroupIds": [sg_id],
            "UserData": base64.b64encode(USER_DATA.encode()).decode(),
            "TagSpecifications": [{"ResourceType": "instance", "Tags": get_tags(PROJECT)}],
        },
    )
    lt_id = lt["LaunchTemplate"]["LaunchTemplateId"]
    ok(f"Launch Template: {lt_id}")

    nlb_resp = elb.create_load_balancer(
        Name=f"{PROJECT}-nlb",
        Subnets=subnet_ids,
        Scheme="internet-facing",
        Type="network",
        IpAddressType="ipv4",
        Tags=get_tags(PROJECT),
    )
    nlb_arn = nlb_resp["LoadBalancers"][0]["LoadBalancerArn"]
    nlb_dns = nlb_resp["LoadBalancers"][0]["DNSName"]
    ok(f"NLB ARN: {nlb_arn}")

    tg_resp = elb.create_target_group(
        Name=f"{PROJECT}-tg",
        Protocol="TCP",
        Port=80,
        VpcId=vpc_id,
        HealthCheckProtocol="TCP",
        HealthCheckIntervalSeconds=30,
        HealthyThresholdCount=3,
        UnhealthyThresholdCount=3,
        TargetType="instance",
    )
    tg_arn = tg_resp["TargetGroups"][0]["TargetGroupArn"]
    ok(f"Target Group: {tg_arn}")

    elb.create_listener(
        LoadBalancerArn=nlb_arn,
        Protocol="TCP",
        Port=80,
        DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}],
    )
    ok("NLB Listener created on TCP:80")

    asg_client.create_auto_scaling_group(
        AutoScalingGroupName=f"{PROJECT}-asg",
        LaunchTemplate={"LaunchTemplateId": lt_id, "Version": "$Latest"},
        MinSize=1, MaxSize=6, DesiredCapacity=2,
        VPCZoneIdentifier=",".join(subnet_ids),
        TargetGroupARNs=[tg_arn],
        HealthCheckType="EC2",
        HealthCheckGracePeriod=90,
        Tags=[{**t, "ResourceId": f"{PROJECT}-asg",
               "ResourceType": "auto-scaling-group", "PropagateAtLaunch": True}
              for t in get_tags(PROJECT)],
    )
    ok("Auto Scaling Group: min=1, desired=2, max=6")

    asg_client.put_scaling_policy(
        AutoScalingGroupName=f"{PROJECT}-asg",
        PolicyName=f"{PROJECT}-cpu-policy",
        PolicyType="TargetTrackingScaling",
        TargetTrackingConfiguration={
            "PredefinedMetricSpecification": {"PredefinedMetricType": "ASGAverageCPUUtilization"},
            "TargetValue": 60.0,
        },
    )
    ok("Scaling policy: scale at 60% CPU")

    save_state(STATE_FILE, {
        "nlb_arn": nlb_arn, "tg_arn": tg_arn,
        "asg_name": f"{PROJECT}-asg", "lt_id": lt_id,
        "sg_id": sg_id, "nlb_dns": nlb_dns,
    })

    print(f"\n  Deployment Complete!\n  URL: http://{nlb_dns}\n")


if __name__ == "__main__":
    deploy()

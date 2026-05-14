"""
PROJECT 6 — Automated Cost Optimizer
Services: AWS Lambda, CloudWatch, EC2

What this does:
  1. Creates an IAM role for the Lambda function
  2. Deploys a Lambda function that:
     - Identifies EC2 instances tagged 'Environment=dev' that have been
       running for more than N hours
     - Stops those instances automatically
  3. Creates a CloudWatch Events rule to trigger Lambda on schedule
  4. Creates a CloudWatch alarm for high CPU utilization on EC2

The Lambda function logic:
  - Lists all running EC2 instances
  - Checks uptime and tags
  - Stops instances with 'AutoStop=true' tag that run > 8 hours
"""

import sys, os, json, zipfile, io, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p06-cost-opt"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

LAMBDA_CODE = '''
import boto3
import json
from datetime import datetime, timezone, timedelta

def lambda_handler(event, context):
    ec2 = boto3.client("ec2")
    stopped = []
    
    # Find instances with AutoStop=true tag
    filters = [
        {"Name": "instance-state-name", "Values": ["running"]},
        {"Name": "tag:AutoStop",         "Values": ["true"]},
    ]
    
    reservations = ec2.describe_instances(Filters=filters)["Reservations"]
    now = datetime.now(timezone.utc)
    
    for res in reservations:
        for inst in res["Instances"]:
            instance_id   = inst["InstanceId"]
            launch_time   = inst["LaunchTime"]
            running_hours = (now - launch_time).total_seconds() / 3600
            
            # Stop if running more than 8 hours
            if running_hours >= 8:
                print(f"Stopping {instance_id} (running {running_hours:.1f} hrs)")
                ec2.stop_instances(InstanceIds=[instance_id])
                stopped.append(instance_id)
    
    # Find unattached EBS volumes and log them
    volumes = ec2.describe_volumes(
        Filters=[{"Name": "status", "Values": ["available"]}]
    )["Volumes"]
    
    unused_volumes = [v["VolumeId"] for v in volumes]
    
    result = {
        "stopped_instances": stopped,
        "unused_volumes_found": unused_volumes,
        "stopped_count": len(stopped),
        "timestamp": now.isoformat(),
    }
    
    print(json.dumps(result, indent=2))
    return result
'''

TRUST_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
})

LAMBDA_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["ec2:DescribeInstances", "ec2:StopInstances",
                       "ec2:DescribeVolumes"],
            "Resource": "*",
        },
        {
            "Effect": "Allow",
            "Action": ["logs:CreateLogGroup", "logs:CreateLogStream",
                       "logs:PutLogEvents"],
            "Resource": "*",
        },
    ],
})


def make_lambda_zip() -> bytes:
    """Package lambda_function.py into a zip in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("lambda_function.py", LAMBDA_CODE)
    return buf.getvalue()


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 6 — Automated Cost Optimizer")
    print("="*60)

    iam     = boto3_client("iam")
    lmb     = boto3_client("lambda")
    events  = boto3_client("events")
    cw      = boto3_client("cloudwatch")

    # ── IAM Role for Lambda ──────────────────────────────────────────────────
    role_name = f"{PROJECT}-lambda-role"
    try:
        role_resp = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=TRUST_POLICY,
            Tags=get_tags(PROJECT),
        )
        role_arn = role_resp["Role"]["Arn"]
        ok(f"Lambda IAM Role: {role_arn}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
        warn(f"Role already exists: {role_arn}")

    # Inline policy
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=f"{PROJECT}-policy",
        PolicyDocument=LAMBDA_POLICY,
    )
    ok("IAM policy attached")

    info("Waiting 10s for IAM propagation...")
    time.sleep(10)

    # ── Lambda Function ──────────────────────────────────────────────────────
    fn_name = f"{PROJECT}-fn"
    zip_bytes = make_lambda_zip()
    try:
        fn_resp = lmb.create_function(
            FunctionName=fn_name,
            Runtime="python3.11",
            Role=role_arn,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": zip_bytes},
            Description="Auto-stops EC2 instances tagged AutoStop=true after 8 hours",
            Timeout=60,
            MemorySize=128,
            Tags={t["Key"]: t["Value"] for t in get_tags(PROJECT)},
        )
        fn_arn = fn_resp["FunctionArn"]
        ok(f"Lambda Function: {fn_arn}")
    except lmb.exceptions.ResourceConflictException:
        lmb.update_function_code(FunctionName=fn_name, ZipFile=zip_bytes)
        fn_arn = lmb.get_function(FunctionName=fn_name)["Configuration"]["FunctionArn"]
        warn(f"Lambda already exists, code updated: {fn_arn}")

    # ── CloudWatch Events Rule (runs every hour) ──────────────────────────────
    rule_name = f"{PROJECT}-schedule"
    rule_resp = events.put_rule(
        Name=rule_name,
        ScheduleExpression="rate(1 hour)",
        State="ENABLED",
        Description="Trigger cost optimizer Lambda every hour",
    )
    rule_arn = rule_resp["RuleArn"]
    ok(f"CloudWatch Events Rule: {rule_arn}")

    # Grant Events permission to invoke Lambda
    try:
        lmb.add_permission(
            FunctionName=fn_name,
            StatementId=f"{PROJECT}-events-permission",
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=rule_arn,
        )
    except lmb.exceptions.ResourceConflictException:
        pass

    # Add Lambda as target of the rule
    events.put_targets(
        Rule=rule_name,
        Targets=[{"Id": "CostOptimizerTarget", "Arn": fn_arn}],
    )
    ok("Lambda target added to CloudWatch Events rule")

    # ── CloudWatch Alarm for High CPU ─────────────────────────────────────────
    cw.put_metric_alarm(
        AlarmName=f"{PROJECT}-high-cpu-alarm",
        AlarmDescription="Alert when EC2 average CPU > 80%",
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Statistic="Average",
        Period=300,
        EvaluationPeriods=2,
        Threshold=80.0,
        ComparisonOperator="GreaterThanThreshold",
        TreatMissingData="notBreaching",
    )
    ok("CloudWatch Alarm created: CPU > 80%")

    # ── Test invoke Lambda immediately ────────────────────────────────────────
    info("Running Lambda function to test it...")
    import base64
    invoke_resp = lmb.invoke(FunctionName=fn_name, InvocationType="RequestResponse")
    payload = invoke_resp["Payload"].read()
    print(f"\n  Lambda test result:\n{json.dumps(json.loads(payload), indent=4)}")

    save_state(STATE_FILE, {
        "role_name": role_name,
        "fn_name": fn_name,
        "fn_arn": fn_arn,
        "rule_name": rule_name,
        "alarm_name": f"{PROJECT}-high-cpu-alarm",
    })

    print(f"\n  Deployment Complete!")
    print(f"  Lambda runs every hour to stop idle instances\n")


if __name__ == "__main__":
    deploy()

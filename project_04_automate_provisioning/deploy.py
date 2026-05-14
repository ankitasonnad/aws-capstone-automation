"""
PROJECT 4 — Automate AWS Resource Provisioning
Services: IAM, EC2, S3, boto3

What this does:
  1. Creates an IAM role with S3 and EC2 read policies
  2. Creates an IAM user and attaches a policy
  3. Creates an S3 bucket and uploads a sample file
  4. Launches an EC2 instance with the IAM role attached
  5. Lists all created resources and saves state
"""

import sys, os, json, base64
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p04-provision"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
BUCKET_NAME = f"{PROJECT}-bucket-{__import__('time').strftime('%Y%m%d%H%M%S')}"

TRUST_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "ec2.amazonaws.com"},
        "Action": "sts:AssumeRole"
    }]
})

USER_DATA = """#!/bin/bash
yum update -y
yum install -y python3 aws-cli
echo "Instance provisioned via boto3 automation" > /tmp/provisioned.txt
aws s3 cp /tmp/provisioned.txt s3://{bucket}/provisioned.txt --region {region}
""".format(bucket=BUCKET_NAME, region=AWS_REGION)


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 4 — Automate AWS Resource Provisioning")
    print("="*60)

    iam = boto3_client("iam")
    ec2 = boto3_client("ec2")
    s3  = boto3_client("s3")

    # ── 1. IAM Role ──────────────────────────────────────────────────────────
    role_name = f"{PROJECT}-role"
    try:
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=TRUST_POLICY,
            Description="Capstone Project 4 EC2 Role",
            Tags=get_tags(PROJECT),
        )
        ok(f"IAM Role created: {role_name}")
    except iam.exceptions.EntityAlreadyExistsException:
        warn(f"Role '{role_name}' already exists")

    for policy_arn in [
        "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
        "arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess",
    ]:
        iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        ok(f"Attached policy: {policy_arn.split('/')[-1]}")

    # ── 2. IAM Instance Profile ──────────────────────────────────────────────
    profile_name = f"{PROJECT}-profile"
    try:
        iam.create_instance_profile(InstanceProfileName=profile_name)
        iam.add_role_to_instance_profile(
            InstanceProfileName=profile_name, RoleName=role_name)
        ok(f"Instance Profile created: {profile_name}")
        import time; time.sleep(10)  # propagation delay
    except Exception as e:
        warn(f"Instance Profile: {e}")

    # ── 3. IAM User ──────────────────────────────────────────────────────────
    user_name = f"{PROJECT}-user"
    try:
        iam.create_user(UserName=user_name, Tags=get_tags(PROJECT))
        iam.attach_user_policy(
            UserName=user_name,
            PolicyArn="arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
        )
        ok(f"IAM User created: {user_name}")
    except iam.exceptions.EntityAlreadyExistsException:
        warn(f"User '{user_name}' already exists")

    # ── 4. S3 Bucket ─────────────────────────────────────────────────────────
    try:
        if AWS_REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
            )
        ok(f"S3 Bucket created: {BUCKET_NAME}")

        # Block public access
        s3.put_public_access_block(
            Bucket=BUCKET_NAME,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True, "IgnorePublicAcls": True,
                "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
            },
        )

        # Upload sample file
        sample_content = json.dumps({
            "project": "Capstone P4",
            "created_by": "boto3 automation",
            "bucket": BUCKET_NAME,
        }, indent=2)
        s3.put_object(Bucket=BUCKET_NAME, Key="README.json",
                      Body=sample_content.encode())
        ok("Uploaded README.json to S3")
    except Exception as e:
        warn(f"S3: {e}")

    # ── 5. EC2 Instance ──────────────────────────────────────────────────────
    vpc_id, subnet_ids = get_default_vpc_and_subnets()
    sg_id = create_security_group(
        f"{PROJECT}-sg", "P4 Instance SG", vpc_id,
        [{"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
    )

    instances = ec2.run_instances(
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_PAIR_NAME,
        MinCount=1, MaxCount=1,
        SecurityGroupIds=[sg_id],
        SubnetId=subnet_ids[0],
        IamInstanceProfile={"Name": profile_name},
        UserData=USER_DATA,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": get_tags(PROJECT, {"Name": f"{PROJECT}-instance"}),
        }],
    )
    instance_id = instances["Instances"][0]["InstanceId"]
    ok(f"EC2 Instance launched: {instance_id}")

    # ── List all resources ────────────────────────────────────────────────────
    print("\n  Resources provisioned:")
    print(f"    IAM Role:     {role_name}")
    print(f"    IAM User:     {user_name}")
    print(f"    S3 Bucket:    s3://{BUCKET_NAME}")
    print(f"    EC2 Instance: {instance_id}")

    save_state(STATE_FILE, {
        "role_name": role_name,
        "profile_name": profile_name,
        "user_name": user_name,
        "bucket": BUCKET_NAME,
        "instance_id": instance_id,
        "sg_id": sg_id,
    })
    print("\n  Deployment Complete!\n")


if __name__ == "__main__":
    deploy()

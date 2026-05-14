"""
🔧 Shared AWS Configuration & Helper Utilities
Used across all 15 capstone projects.
"""

import boto3
import time
import json
import sys

# ─────────────────────────────────────────────
#  ✏️  EDIT THESE VALUES BEFORE RUNNING
# ─────────────────────────────────────────────
AWS_REGION       = "ap-south-1"             # Mumbai region (auto-detected)
KEY_PAIR_NAME    = "pratik-aws-key"          # Your existing key pair
AMI_ID           = "ami-090eaa8ecb757149c"   # Amazon Linux 2 (ap-south-1, latest)
INSTANCE_TYPE    = "t3.micro"              # Free tier eligible in ap-south-1
DB_PASSWORD      = "CapstonePass123!"   # Used for RDS instances
# ─────────────────────────────────────────────

# Common tags applied to every resource
def get_tags(project_name: str, extra: dict = None) -> list:
    tags = [
        {"Key": "Project",     "Value": project_name},
        {"Key": "ManagedBy",   "Value": "boto3-capstone"},
        {"Key": "Environment", "Value": "demo"},
    ]
    if extra:
        for k, v in extra.items():
            tags.append({"Key": k, "Value": v})
    return tags


def ecs_tags(project_name: str) -> list:
    """ECS/CodeBuild use lowercase key/value instead of Key/Value."""
    return [
        {"key": "Project",     "value": project_name},
        {"key": "ManagedBy",   "value": "boto3-capstone"},
        {"key": "Environment", "value": "demo"},
    ]


def boto3_client(service: str):
    """Return a boto3 client for the given service."""
    return boto3.client(service, region_name=AWS_REGION)


def boto3_resource(service: str):
    """Return a boto3 resource for the given service."""
    return boto3.resource(service, region_name=AWS_REGION)


def waiter_msg(action: str):
    """Print a spinner-like wait message."""
    print(f"  ⏳  Waiting for {action} …", flush=True)


def ok(msg: str):
    print(f"  ✅  {msg}")


def info(msg: str):
    print(f"  ℹ️   {msg}")


def warn(msg: str):
    print(f"  ⚠️   {msg}", file=sys.stderr)


def get_default_vpc_and_subnets() -> tuple:
    """Return (vpc_id, [subnet_id, ...]) for the default VPC."""
    ec2 = boto3_client("ec2")
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    if not vpcs["Vpcs"]:
        raise RuntimeError("No default VPC found. Create one in the AWS console.")
    vpc_id = vpcs["Vpcs"][0]["VpcId"]
    subnets = ec2.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )
    subnet_ids = [s["SubnetId"] for s in subnets["Subnets"]]
    return vpc_id, subnet_ids


def create_security_group(name: str, description: str, vpc_id: str,
                           ingress_rules: list) -> str:
    """Create a security group and return its ID."""
    ec2 = boto3_client("ec2")
    try:
        sg = ec2.create_security_group(
            GroupName=name,
            Description=description,
            VpcId=vpc_id,
        )
        sg_id = sg["GroupId"]
        ec2.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=ingress_rules)
        ok(f"Security Group created: {sg_id}")
        return sg_id
    except ec2.exceptions.ClientError as e:
        if "already exists" in str(e):
            sgs = ec2.describe_security_groups(
                Filters=[{"Name": "group-name", "Values": [name]}]
            )
            sg_id = sgs["SecurityGroups"][0]["GroupId"]
            warn(f"Security Group '{name}' already exists: {sg_id}")
            return sg_id
        raise


def delete_security_group(sg_id: str):
    ec2 = boto3_client("ec2")
    try:
        ec2.delete_security_group(GroupId=sg_id)
        ok(f"Security Group {sg_id} deleted.")
    except Exception as e:
        warn(f"Could not delete SG {sg_id}: {e}")


def save_state(filename: str, state: dict):
    """Save resource IDs to a JSON file for later cleanup."""
    with open(filename, "w") as f:
        json.dump(state, f, indent=2)
    info(f"State saved to {filename}")


def load_state(filename: str) -> dict:
    """Load previously saved resource IDs."""
    try:
        with open(filename) as f:
            return json.load(f)
    except FileNotFoundError:
        warn(f"State file '{filename}' not found. Nothing to destroy.")
        sys.exit(0)

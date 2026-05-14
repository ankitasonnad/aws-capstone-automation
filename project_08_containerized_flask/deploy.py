"""
PROJECT 8 — Containerized Flask Application
Services: Amazon ECR, Amazon ECS (Fargate)

What this does:
  1. Creates an ECR repository
  2. Builds and pushes a Docker image for the Flask app
     (uses local Docker daemon — must be running)
  3. Creates an ECS Cluster (Fargate)
  4. Creates a Task Definition with the Flask container
  5. Creates an ECS Service running 2 tasks
  6. Creates an ALB to expose the ECS service

Prerequisites: Docker must be installed and running locally
"""

import sys, os, json, subprocess, base64, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p08-flask"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

FLASK_APP = '''from flask import Flask, jsonify
import os, socket

app = Flask(__name__)

@app.route("/")
def home():
    return """<!DOCTYPE html>
<html>
<head>
  <title>Project 8 - Containerized Flask</title>
  <style>
    body{font-family:Arial,sans-serif;background:#1a1a2e;color:#eee;
         display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .card{background:#16213e;border-radius:16px;padding:40px;text-align:center;max-width:500px}
    h1{color:#e94560}
    .badge{background:#0f3460;color:#e94560;border-radius:999px;
           padding:4px 14px;display:inline-block;margin:4px}
  </style>
</head>
<body>
  <div class="card">
    <h1>Project 8</h1>
    <h2>Containerized Flask App</h2>
    <p>Running on ECS Fargate with Docker</p>
    <p>Host: <span class="badge">""" + socket.gethostname() + """</span></p>
  </div>
</body>
</html>"""

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "host": socket.gethostname()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
'''

DOCKERFILE = """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 5000
CMD ["python", "app.py"]
"""

REQUIREMENTS = "flask==3.0.0\n"


def build_and_push_image(ecr_uri: str, region: str) -> str:
    """Build Docker image locally and push to ECR."""
    app_dir = os.path.dirname(__file__)

    # Write Docker files
    with open(os.path.join(app_dir, "app.py"), "w") as f:
        f.write(FLASK_APP)
    with open(os.path.join(app_dir, "Dockerfile"), "w") as f:
        f.write(DOCKERFILE)
    with open(os.path.join(app_dir, "requirements.txt"), "w") as f:
        f.write(REQUIREMENTS)

    image_tag = f"{ecr_uri}:latest"

    # Get ECR login token
    ecr = boto3_client("ecr")
    token = ecr.get_authorization_token()
    auth = token["authorizationData"][0]
    decoded = base64.b64decode(auth["authorizationToken"]).decode()
    user, password = decoded.split(":", 1)
    registry = auth["proxyEndpoint"]

    # Docker login
    subprocess.run(
        ["docker", "login", "-u", user, "-p", password, registry],
        check=True, capture_output=True,
    )

    # Docker build
    subprocess.run(
        ["docker", "build", "-t", image_tag, app_dir],
        check=True,
    )
    ok(f"Docker image built: {image_tag}")

    # Docker push
    subprocess.run(["docker", "push", image_tag], check=True)
    ok(f"Image pushed to ECR: {image_tag}")

    return image_tag


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 8 — Containerized Flask App (ECR+ECS)")
    print("="*60)

    ecr  = boto3_client("ecr")
    ecs  = boto3_client("ecs")
    iam  = boto3_client("iam")
    elb  = boto3_client("elbv2")
    ec2  = boto3_client("ec2")

    # ── ECR Repository ────────────────────────────────────────────────────────
    try:
        repo = ecr.create_repository(
            repositoryName=f"{PROJECT}-repo",
            tags=get_tags(PROJECT),
        )
        ecr_uri = repo["repository"]["repositoryUri"]
        ok(f"ECR Repo: {ecr_uri}")
    except ecr.exceptions.RepositoryAlreadyExistsException:
        repo = ecr.describe_repositories(repositoryNames=[f"{PROJECT}-repo"])
        ecr_uri = repo["repositories"][0]["repositoryUri"]
        warn(f"ECR repo exists: {ecr_uri}")

    # ── Build & Push Docker Image ─────────────────────────────────────────────
    try:
        image_tag = build_and_push_image(ecr_uri, AWS_REGION)
    except Exception as e:
        warn(f"Docker build failed: {e}")
        warn("Ensure Docker is running. Using placeholder image URI.")
        image_tag = f"{ecr_uri}:latest"

    # ── ECS Task Execution Role ───────────────────────────────────────────────
    role_name = f"{PROJECT}-task-exec-role"
    trust = json.dumps({"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Service": "ecs-tasks.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }]})
    try:
        role_arn = iam.create_role(
            RoleName=role_name, AssumeRolePolicyDocument=trust)["Role"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
    )
    ok(f"ECS Task Role: {role_arn}")
    time.sleep(8)

    # ── ECS Cluster ───────────────────────────────────────────────────────────
    cluster_resp = ecs.create_cluster(
        clusterName=f"{PROJECT}-cluster",
        capacityProviders=["FARGATE"],
        tags=ecs_tags(PROJECT),
    )
    cluster_arn = cluster_resp["cluster"]["clusterArn"]
    ok(f"ECS Cluster: {cluster_arn}")

    # ── Task Definition ───────────────────────────────────────────────────────
    td_resp = ecs.register_task_definition(
        family=f"{PROJECT}-task",
        networkMode="awsvpc",
        requiresCompatibilities=["FARGATE"],
        cpu="256",
        memory="512",
        runtimePlatform={"cpuArchitecture": "ARM64", "operatingSystemFamily": "LINUX"},
        executionRoleArn=role_arn,
        containerDefinitions=[{
            "name": "flask-app",
            "image": image_tag,
            "portMappings": [{"containerPort": 5000, "protocol": "tcp"}],
            "essential": True,
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": f"/ecs/{PROJECT}",
                    "awslogs-region": AWS_REGION,
                    "awslogs-stream-prefix": "flask",
                    "awslogs-create-group": "true",
                },
            },
        }],
        tags=ecs_tags(PROJECT),
    )
    td_arn = td_resp["taskDefinition"]["taskDefinitionArn"]
    ok(f"Task Definition: {td_arn}")

    # ── VPC + Security Group ──────────────────────────────────────────────────
    vpc_id, subnet_ids = get_default_vpc_and_subnets()
    sg_id = create_security_group(
        f"{PROJECT}-sg", "Flask ECS SG", vpc_id,
        [{"IpProtocol": "tcp", "FromPort": 5000, "ToPort": 5000,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
         {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
    )

    # ── ALB ───────────────────────────────────────────────────────────────────
    alb_resp = elb.create_load_balancer(
        Name=f"{PROJECT}-alb",
        Subnets=subnet_ids,
        SecurityGroups=[sg_id],
        Scheme="internet-facing",
        Type="application",
        Tags=get_tags(PROJECT),
    )
    alb_arn = alb_resp["LoadBalancers"][0]["LoadBalancerArn"]
    alb_dns = alb_resp["LoadBalancers"][0]["DNSName"]

    tg_resp = elb.create_target_group(
        Name=f"{PROJECT}-tg",
        Protocol="HTTP", Port=5000, VpcId=vpc_id,
        TargetType="ip",
        HealthCheckPath="/health",
    )
    tg_arn = tg_resp["TargetGroups"][0]["TargetGroupArn"]

    elb.create_listener(
        LoadBalancerArn=alb_arn, Protocol="HTTP", Port=80,
        DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}],
    )
    ok("ALB created")

    # ── ECS Service ───────────────────────────────────────────────────────────
    try:
        ecs.create_service(
            cluster=cluster_arn,
            serviceName=f"{PROJECT}-service",
            taskDefinition=td_arn,
            desiredCount=2,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": subnet_ids,
                    "securityGroups": [sg_id],
                    "assignPublicIp": "ENABLED",
                }
            },
            loadBalancers=[{
                "targetGroupArn": tg_arn,
                "containerName": "flask-app",
                "containerPort": 5000,
            }],
            tags=ecs_tags(PROJECT),
        )
        ok(f"ECS Service created with 2 Fargate tasks")
    except ecs.exceptions.InvalidParameterException as e:
        if "Creation of service was not idempotent" in str(e):
            ecs.update_service(
                cluster=cluster_arn,
                service=f"{PROJECT}-service",
                taskDefinition=td_arn,
                desiredCount=2,
                forceNewDeployment=True,
            )
            ok(f"ECS Service updated with new task definition")
        else:
            raise

    save_state(STATE_FILE, {
        "cluster_arn": cluster_arn,
        "service_name": f"{PROJECT}-service",
        "td_arn": td_arn,
        "ecr_repo": f"{PROJECT}-repo",
        "alb_arn": alb_arn, "tg_arn": tg_arn, "sg_id": sg_id,
        "role_name": role_name, "alb_dns": alb_dns,
    })

    print(f"\n  Deployment Complete!")
    print(f"  URL: http://{alb_dns}  (available in ~3 min)")
    print(f"  Tasks: ECS Fargate x2\n")


if __name__ == "__main__":
    deploy()

"""
PROJECT 10 — Containerized Node.js Application
Services: Amazon ECR, Amazon ECS (Fargate)

What this does:
  1. Creates an ECR repository for the Node.js image
  2. Generates a production Node.js Express app with a styled dashboard
  3. Builds a Docker image and pushes to ECR (requires local Docker)
  4. Creates ECS Cluster, Task Definition, and Service on Fargate
  5. Creates an ALB to expose the service publicly
"""

import sys, os, json, subprocess, base64, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p10-nodejs"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

NODEJS_APP = r"""const express = require('express');
const os = require('os');
const app = express();
const PORT = process.env.PORT || 3000;

app.get('/', (req, res) => {
  res.send(`<!DOCTYPE html>
<html>
<head>
  <title>Project 10 - Containerized Node.js</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0;
           display: flex; align-items: center; justify-content: center; min-height: 100vh; }
    .card { background: #1e293b; border-radius: 20px; padding: 48px;
            max-width: 540px; text-align: center; box-shadow: 0 25px 50px rgba(0,0,0,.4); }
    h1 { font-size: 2.5rem; color: #f59e0b; margin-bottom: 8px; }
    h2 { color: #94a3b8; font-weight: 400; margin-bottom: 32px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 24px 0; }
    .stat { background: #0f172a; border-radius: 12px; padding: 16px; }
    .stat-label { color: #64748b; font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; }
    .stat-value { color: #f59e0b; font-size: 1.1rem; font-weight: 600; margin-top: 4px; }
    .badge { background: #78350f; color: #fcd34d; border-radius: 999px;
             padding: 6px 18px; display: inline-block; font-size: .9rem; }
  </style>
</head>
<body>
  <div class="card">
    <h1>⚡ Project 10</h1>
    <h2>Containerized Node.js on ECS Fargate</h2>
    <div class="grid">
      <div class="stat">
        <div class="stat-label">Hostname</div>
        <div class="stat-value">${os.hostname().substring(0,12)}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Node.js</div>
        <div class="stat-value">${process.version}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Platform</div>
        <div class="stat-value">${os.platform()}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Uptime</div>
        <div class="stat-value">${Math.floor(process.uptime())}s</div>
      </div>
    </div>
    <span class="badge">ECS Fargate · Docker · ECR</span>
  </div>
</body>
</html>`);
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', host: os.hostname(), uptime: process.uptime() });
});

app.listen(PORT, () => console.log(`Server listening on port ${PORT}`));
"""

PKG_JSON = json.dumps({
    "name": "capstone-nodejs",
    "version": "1.0.0",
    "main": "app.js",
    "dependencies": {"express": "^4.18.2"},
    "scripts": {"start": "node app.js"},
}, indent=2)

DOCKERFILE = """FROM node:18-alpine
WORKDIR /app
COPY package.json .
RUN npm install --production
COPY app.js .
EXPOSE 3000
CMD ["node", "app.js"]
"""


def build_and_push(ecr_uri: str) -> str:
    app_dir = os.path.dirname(__file__)
    for fname, content in [("app.js", NODEJS_APP), ("package.json", PKG_JSON),
                            ("Dockerfile", DOCKERFILE)]:
        with open(os.path.join(app_dir, fname), "w") as f:
            f.write(content)

    image_tag = f"{ecr_uri}:latest"
    ecr = boto3_client("ecr")
    token = ecr.get_authorization_token()["authorizationData"][0]
    decoded = base64.b64decode(token["authorizationToken"]).decode()
    user, password = decoded.split(":", 1)

    subprocess.run(["docker", "login", "-u", user, "-p", password,
                    token["proxyEndpoint"]], check=True, capture_output=True)
    subprocess.run(["docker", "build", "-t", image_tag, app_dir], check=True)
    subprocess.run(["docker", "push", image_tag], check=True)
    ok(f"Image pushed: {image_tag}")
    return image_tag


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 10 — Containerized Node.js (ECR+ECS)")
    print("="*60)

    ecr = boto3_client("ecr")
    ecs = boto3_client("ecs")
    iam = boto3_client("iam")
    elb = boto3_client("elbv2")

    # ── ECR Repo ──────────────────────────────────────────────────────────────
    try:
        repo = ecr.create_repository(repositoryName=f"{PROJECT}-repo",
                                     tags=get_tags(PROJECT))
        ecr_uri = repo["repository"]["repositoryUri"]
    except ecr.exceptions.RepositoryAlreadyExistsException:
        ecr_uri = ecr.describe_repositories(
            repositoryNames=[f"{PROJECT}-repo"])["repositories"][0]["repositoryUri"]
    ok(f"ECR URI: {ecr_uri}")

    # ── Build & Push ──────────────────────────────────────────────────────────
    try:
        image_tag = build_and_push(ecr_uri)
    except Exception as e:
        warn(f"Docker build skipped: {e}")
        image_tag = f"{ecr_uri}:latest"

    # ── ECS Execution Role ────────────────────────────────────────────────────
    role_name = f"{PROJECT}-exec-role"
    trust = json.dumps({"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Service": "ecs-tasks.amazonaws.com"},
        "Action": "sts:AssumeRole"}]})
    try:
        role_arn = iam.create_role(RoleName=role_name,
                                   AssumeRolePolicyDocument=trust)["Role"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
    iam.attach_role_policy(RoleName=role_name,
                           PolicyArn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy")
    ok(f"Exec Role: {role_arn}")
    time.sleep(8)

    # ── ECS Cluster ───────────────────────────────────────────────────────────
    cluster_arn = ecs.create_cluster(
        clusterName=f"{PROJECT}-cluster",
        capacityProviders=["FARGATE"],
        tags=ecs_tags(PROJECT),
    )["cluster"]["clusterArn"]
    ok(f"Cluster: {cluster_arn}")

    # ── Task Definition ───────────────────────────────────────────────────────
    td_arn = ecs.register_task_definition(
        family=f"{PROJECT}-task",
        networkMode="awsvpc",
        requiresCompatibilities=["FARGATE"],
        cpu="256", memory="512",
        runtimePlatform={"cpuArchitecture": "ARM64", "operatingSystemFamily": "LINUX"},
        executionRoleArn=role_arn,
        containerDefinitions=[{
            "name": "nodejs-app",
            "image": image_tag,
            "portMappings": [{"containerPort": 3000, "protocol": "tcp"}],
            "essential": True,
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": f"/ecs/{PROJECT}",
                    "awslogs-region": AWS_REGION,
                    "awslogs-stream-prefix": "nodejs",
                    "awslogs-create-group": "true",
                },
            },
        }],
        tags=ecs_tags(PROJECT),
    )["taskDefinition"]["taskDefinitionArn"]
    ok(f"Task Definition: {td_arn}")

    # ── VPC & SG ──────────────────────────────────────────────────────────────
    vpc_id, subnet_ids = get_default_vpc_and_subnets()
    sg_id = create_security_group(
        f"{PROJECT}-sg", "Node ECS SG", vpc_id,
        [{"IpProtocol": "tcp", "FromPort": 3000, "ToPort": 3000,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
         {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
    )

    # ── ALB ───────────────────────────────────────────────────────────────────
    alb_arn = elb.create_load_balancer(
        Name=f"{PROJECT}-alb", Subnets=subnet_ids,
        SecurityGroups=[sg_id], Scheme="internet-facing", Type="application",
        Tags=get_tags(PROJECT),
    )["LoadBalancers"][0]["LoadBalancerArn"]

    alb_dns = elb.describe_load_balancers(
        LoadBalancerArns=[alb_arn])["LoadBalancers"][0]["DNSName"]

    tg_arn = elb.create_target_group(
        Name=f"{PROJECT}-tg", Protocol="HTTP", Port=3000, VpcId=vpc_id,
        TargetType="ip", HealthCheckPath="/health",
    )["TargetGroups"][0]["TargetGroupArn"]

    elb.create_listener(LoadBalancerArn=alb_arn, Protocol="HTTP", Port=80,
                        DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}])
    ok("ALB ready")

    # ── ECS Service ───────────────────────────────────────────────────────────
    ecs.create_service(
        cluster=cluster_arn, serviceName=f"{PROJECT}-service",
        taskDefinition=td_arn, desiredCount=2, launchType="FARGATE",
        networkConfiguration={"awsvpcConfiguration": {
            "subnets": subnet_ids, "securityGroups": [sg_id],
            "assignPublicIp": "ENABLED"}},
        loadBalancers=[{"targetGroupArn": tg_arn, "containerName": "nodejs-app",
                        "containerPort": 3000}],
        tags=ecs_tags(PROJECT),
    )
    ok("ECS Service: 2 Fargate tasks")

    save_state(STATE_FILE, {
        "cluster_arn": cluster_arn, "service_name": f"{PROJECT}-service",
        "td_arn": td_arn, "ecr_repo": f"{PROJECT}-repo",
        "alb_arn": alb_arn, "tg_arn": tg_arn, "sg_id": sg_id,
        "role_name": role_name, "alb_dns": alb_dns,
    })

    print(f"\n  Deployment Complete!\n  URL: http://{alb_dns}\n")


if __name__ == "__main__":
    deploy()

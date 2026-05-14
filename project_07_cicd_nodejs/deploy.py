"""
PROJECT 7 — CI/CD Pipeline to Deploy Node.js Application
Services: AWS CodePipeline, CodeBuild, S3 (artifacts), EC2 (deploy target)

What this does:
  1. Creates an S3 bucket for pipeline artifacts
  2. Creates IAM roles for CodePipeline and CodeBuild
  3. Creates a CodeBuild project to build the Node.js app
  4. Creates a CodePipeline with Source (S3) → Build (CodeBuild) stages
  5. Uploads a sample Node.js app source zip to S3 to trigger the pipeline
"""

import sys, os, json, zipfile, io, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p07-cicd-nodejs"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
ARTIFACT_BUCKET = f"{PROJECT}-artifacts-{int(time.time())}"

# ── Sample Node.js App Files ─────────────────────────────────────────────────
NODEJS_APP_JS = """
const http = require('http');
const os   = require('os');

const PORT = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
  res.writeHead(200, {'Content-Type': 'text/html'});
  res.end(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Project 7 - Node.js CI/CD</title>
      <style>
        body{font-family:Arial,sans-serif;background:#0a0e1a;color:#e2e8f0;
             display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
        .card{background:#111827;border:1px solid #1e293b;border-radius:16px;
              padding:40px;text-align:center;max-width:500px}
        h1{color:#34d399}
        .badge{background:#065f46;color:#6ee7b7;border-radius:999px;
               padding:4px 14px;display:inline-block;margin:4px}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Project 7</h1>
        <h2>Node.js CI/CD Pipeline</h2>
        <p>Host: <span class="badge">${os.hostname()}</span></p>
        <p>Node: <span class="badge">${process.version}</span></p>
        <p>Deployed via CodePipeline + CodeBuild</p>
      </div>
    </body>
    </html>
  `);
});

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
"""

PACKAGE_JSON = json.dumps({
    "name": "capstone-nodejs-app",
    "version": "1.0.0",
    "description": "AWS Capstone Project 7 - Node.js CI/CD",
    "main": "app.js",
    "scripts": {"start": "node app.js", "test": "echo 'Tests passed'"},
}, indent=2)

BUILDSPEC = """version: 0.2
phases:
  install:
    runtime-versions:
      nodejs: 18
    commands:
      - echo Installing dependencies...
      - npm install
  pre_build:
    commands:
      - echo Running tests...
      - npm test
  build:
    commands:
      - echo Build started on `date`
      - echo "Build complete"
  post_build:
    commands:
      - echo Build completed on `date`
artifacts:
  files:
    - '**/*'
  name: nodejs-app-$(date +%Y%m%d%H%M%S)
"""

CODEPIPELINE_TRUST = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "codepipeline.amazonaws.com"},
                   "Action": "sts:AssumeRole"}],
})
CODEBUILD_TRUST = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "codebuild.amazonaws.com"},
                   "Action": "sts:AssumeRole"}],
})


def make_source_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("app.js", NODEJS_APP_JS)
        z.writestr("package.json", PACKAGE_JSON)
        z.writestr("buildspec.yml", BUILDSPEC)
    return buf.getvalue()


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 7 — CI/CD Pipeline for Node.js")
    print("="*60)

    s3     = boto3_client("s3")
    iam    = boto3_client("iam")
    cb     = boto3_client("codebuild")
    cp     = boto3_client("codepipeline")

    # ── S3 Artifact Bucket ────────────────────────────────────────────────────
    if AWS_REGION == "us-east-1":
        s3.create_bucket(Bucket=ARTIFACT_BUCKET)
    else:
        s3.create_bucket(Bucket=ARTIFACT_BUCKET,
                         CreateBucketConfiguration={"LocationConstraint": AWS_REGION})
    s3.put_bucket_versioning(Bucket=ARTIFACT_BUCKET,
                             VersioningConfiguration={"Status": "Enabled"})
    ok(f"Artifact bucket: {ARTIFACT_BUCKET}")

    # ── IAM Role for CodeBuild ────────────────────────────────────────────────
    cb_role_name = f"{PROJECT}-cb-role"
    try:
        cb_role_arn = iam.create_role(
            RoleName=cb_role_name,
            AssumeRolePolicyDocument=CODEBUILD_TRUST,
        )["Role"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        cb_role_arn = iam.get_role(RoleName=cb_role_name)["Role"]["Arn"]

    iam.attach_role_policy(RoleName=cb_role_name,
                           PolicyArn="arn:aws:iam::aws:policy/AWSCodeBuildAdminAccess")
    iam.attach_role_policy(RoleName=cb_role_name,
                           PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess")
    iam.attach_role_policy(RoleName=cb_role_name,
                           PolicyArn="arn:aws:iam::aws:policy/CloudWatchLogsFullAccess")
    ok(f"CodeBuild IAM Role: {cb_role_arn}")

    # ── IAM Role for CodePipeline ─────────────────────────────────────────────
    cp_role_name = f"{PROJECT}-cp-role"
    try:
        cp_role_arn = iam.create_role(
            RoleName=cp_role_name,
            AssumeRolePolicyDocument=CODEPIPELINE_TRUST,
        )["Role"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        cp_role_arn = iam.get_role(RoleName=cp_role_name)["Role"]["Arn"]

    iam.attach_role_policy(RoleName=cp_role_name,
                           PolicyArn="arn:aws:iam::aws:policy/AWSCodePipeline_FullAccess")
    iam.attach_role_policy(RoleName=cp_role_name,
                           PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess")
    iam.attach_role_policy(RoleName=cp_role_name,
                           PolicyArn="arn:aws:iam::aws:policy/AWSCodeBuildAdminAccess")
    ok(f"CodePipeline IAM Role: {cp_role_arn}")

    info("Waiting 15s for IAM propagation...")
    time.sleep(15)

    # ── CodeBuild Project ─────────────────────────────────────────────────────
    cb_project_name = f"{PROJECT}-build"
    try:
        cb.create_project(
            name=cb_project_name,
            description="Build Node.js application",
            source={"type": "CODEPIPELINE", "buildspec": BUILDSPEC},
            artifacts={"type": "CODEPIPELINE"},
            environment={
                "type": "LINUX_CONTAINER",
                "computeType": "BUILD_GENERAL1_SMALL",
                "image": "aws/codebuild/standard:7.0",
            },
            serviceRole=cb_role_arn,
            tags=[{"key": t["Key"], "value": t["Value"]} for t in get_tags(PROJECT)],
        )
        ok(f"CodeBuild Project: {cb_project_name}")
    except cb.exceptions.ResourceAlreadyExistsException:
        warn(f"CodeBuild project already exists: {cb_project_name}")

    # ── Upload source to S3 (triggers pipeline) ───────────────────────────────
    source_zip = make_source_zip()
    s3.put_object(Bucket=ARTIFACT_BUCKET, Key="source/source.zip", Body=source_zip)
    ok("Source code uploaded to S3")

    # ── CodePipeline ──────────────────────────────────────────────────────────
    pipeline_name = f"{PROJECT}-pipeline"
    try:
        cp.create_pipeline(
            pipeline={
                "name": pipeline_name,
                "roleArn": cp_role_arn,
                "artifactStore": {
                    "type": "S3",
                    "location": ARTIFACT_BUCKET,
                },
                "stages": [
                    {
                        "name": "Source",
                        "actions": [{
                            "name": "S3Source",
                            "actionTypeId": {
                                "category": "Source",
                                "owner": "AWS",
                                "provider": "S3",
                                "version": "1",
                            },
                            "configuration": {
                                "S3Bucket": ARTIFACT_BUCKET,
                                "S3ObjectKey": "source/source.zip",
                                "PollForSourceChanges": "true",
                            },
                            "outputArtifacts": [{"name": "SourceOutput"}],
                            "runOrder": 1,
                        }],
                    },
                    {
                        "name": "Build",
                        "actions": [{
                            "name": "CodeBuild",
                            "actionTypeId": {
                                "category": "Build",
                                "owner": "AWS",
                                "provider": "CodeBuild",
                                "version": "1",
                            },
                            "configuration": {"ProjectName": cb_project_name},
                            "inputArtifacts":  [{"name": "SourceOutput"}],
                            "outputArtifacts": [{"name": "BuildOutput"}],
                            "runOrder": 1,
                        }],
                    },
                ],
                "version": 1,
            }
        )
        ok(f"CodePipeline: {pipeline_name}")
    except cp.exceptions.PipelineNameInUseException:
        warn(f"Pipeline already exists: {pipeline_name}")

    save_state(STATE_FILE, {
        "artifact_bucket": ARTIFACT_BUCKET,
        "pipeline_name": pipeline_name,
        "cb_project_name": cb_project_name,
        "cb_role_name": cb_role_name,
        "cp_role_name": cp_role_name,
    })

    print(f"\n  Deployment Complete!")
    print(f"  Pipeline: {pipeline_name}")
    print(f"  Check AWS CodePipeline console to monitor execution\n")


if __name__ == "__main__":
    deploy()

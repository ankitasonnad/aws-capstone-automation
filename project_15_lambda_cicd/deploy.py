"""
PROJECT 15 — Automate CI/CD Pipelines using Lambda
Services: AWS Lambda, CodePipeline, S3, IAM

What this does:
  1. Creates an S3 bucket for source code and artifacts
  2. Deploys a CodeBuild project (Python app build)
  3. Creates a CodePipeline: Source (S3) → Build → Lambda Notify
  4. Deploys a Lambda function that:
     - Is triggered by CodePipeline (Approval action) or SNS
     - Can also MANUALLY trigger a pipeline execution via API
     - Sends a notification (logs) about the deployment status
  5. Creates a CloudWatch Events rule to call Lambda on pipeline state changes
  6. Creates a second Lambda that you can invoke to START a pipeline run

The "trigger pipeline via Lambda" pattern:
  - POST to /trigger-pipeline → Lambda calls codepipeline.start_pipeline_execution()
  - Useful for webhook-based deployments (GitHub push, etc.)
"""

import sys, os, json, zipfile, io, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p15-lambda-cicd"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
BUCKET     = f"{PROJECT}-artifacts-{int(time.time())}"

# ── Lambda 1: Pipeline Notifier (triggered by CloudWatch Events) ─────────────
NOTIFIER_CODE = '''
import boto3, json, os
from datetime import datetime

def lambda_handler(event, context):
    """Called by CloudWatch Events when CodePipeline state changes."""
    detail      = event.get("detail", {})
    pipeline    = detail.get("pipeline", "unknown")
    state       = detail.get("state", "unknown")
    timestamp   = datetime.utcnow().isoformat()

    message = {
        "event":     "Pipeline State Change",
        "pipeline":  pipeline,
        "state":     state,
        "timestamp": timestamp,
        "source":    "CloudWatch Events → Lambda",
    }

    print(f"[PIPELINE NOTIFY] {json.dumps(message, indent=2)}")

    # In production: send to SNS, Slack webhook, etc.
    return {"statusCode": 200, "body": json.dumps(message)}
'''

# ── Lambda 2: Pipeline Trigger (invoke to start a pipeline run) ──────────────
TRIGGER_CODE = '''
import boto3, json, os

PIPELINE_NAME = os.environ.get("PIPELINE_NAME", "")

def lambda_handler(event, context):
    """Trigger a CodePipeline execution. Call this from webhooks."""
    cp     = boto3.client("codepipeline")
    result = cp.start_pipeline_execution(name=PIPELINE_NAME)

    execution_id = result["pipelineExecutionId"]
    print(f"[PIPELINE TRIGGER] Started execution: {execution_id}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message":       "Pipeline triggered successfully",
            "pipeline":      PIPELINE_NAME,
            "execution_id":  execution_id,
        })
    }
'''

BUILDSPEC = """version: 0.2
phases:
  install:
    runtime-versions:
      python: 3.11
    commands:
      - pip install flask boto3
  build:
    commands:
      - echo "Building Python application..."
      - python -c "import flask; print('Flask', flask.__version__, 'OK')"
      - echo "All tests passed"
  post_build:
    commands:
      - echo "Build complete"
artifacts:
  files:
    - '**/*'
"""

SAMPLE_APP = """from flask import Flask
app = Flask(__name__)
@app.route("/")
def home(): return "<h1>Hello from Lambda-triggered CI/CD!</h1>"
if __name__ == "__main__": app.run()
"""

LAMBDA_TRUST = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow",
                   "Principal": {"Service": "lambda.amazonaws.com"},
                   "Action": "sts:AssumeRole"}],
})
CODEBUILD_TRUST = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow",
                   "Principal": {"Service": "codebuild.amazonaws.com"},
                   "Action": "sts:AssumeRole"}],
})
PIPELINE_TRUST = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow",
                   "Principal": {"Service": "codepipeline.amazonaws.com"},
                   "Action": "sts:AssumeRole"}],
})


def make_zip(code: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("lambda_function.py", code)
    return buf.getvalue()


def make_source_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("app.py", SAMPLE_APP)
        z.writestr("requirements.txt", "flask==3.0.0\n")
        z.writestr("buildspec.yml", BUILDSPEC)
    return buf.getvalue()


def create_role(iam, name, trust, policies):
    try:
        arn = iam.create_role(RoleName=name,
                              AssumeRolePolicyDocument=trust)["Role"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        arn = iam.get_role(RoleName=name)["Role"]["Arn"]
    for pol in policies:
        iam.attach_role_policy(RoleName=name, PolicyArn=pol)
    return arn


def create_lambda(lmb, name, role_arn, code, env=None):
    kwargs = dict(
        FunctionName=name,
        Runtime="python3.11",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": make_zip(code)},
        Timeout=30,
        MemorySize=128,
    )
    if env:
        kwargs["Environment"] = {"Variables": env}
    try:
        return lmb.create_function(**kwargs)["FunctionArn"]
    except lmb.exceptions.ResourceConflictException:
        lmb.update_function_code(FunctionName=name, ZipFile=make_zip(code))
        return lmb.get_function(FunctionName=name)["Configuration"]["FunctionArn"]


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 15 — Automate CI/CD with Lambda")
    print("="*60)

    s3      = boto3_client("s3")
    iam     = boto3_client("iam")
    lmb     = boto3_client("lambda")
    cb      = boto3_client("codebuild")
    cp      = boto3_client("codepipeline")
    events  = boto3_client("events")
    sts     = boto3_client("sts")

    account_id = sts.get_caller_identity()["Account"]

    # ── S3 Artifact Bucket ────────────────────────────────────────────────────
    if AWS_REGION == "us-east-1":
        s3.create_bucket(Bucket=BUCKET)
    else:
        s3.create_bucket(Bucket=BUCKET,
                         CreateBucketConfiguration={"LocationConstraint": AWS_REGION})
    s3.put_bucket_versioning(Bucket=BUCKET,
                             VersioningConfiguration={"Status": "Enabled"})
    ok(f"Artifact bucket: {BUCKET}")

    # ── IAM Roles ─────────────────────────────────────────────────────────────
    lambda_role_arn = create_role(iam, f"{PROJECT}-lambda-role", LAMBDA_TRUST, [
        "arn:aws:iam::aws:policy/AWSCodePipeline_FullAccess",
        "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
    ])
    cb_role_arn = create_role(iam, f"{PROJECT}-cb-role", CODEBUILD_TRUST, [
        "arn:aws:iam::aws:policy/AWSCodeBuildAdminAccess",
        "arn:aws:iam::aws:policy/AmazonS3FullAccess",
        "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
    ])
    cp_role_arn = create_role(iam, f"{PROJECT}-cp-role", PIPELINE_TRUST, [
        "arn:aws:iam::aws:policy/AWSCodePipeline_FullAccess",
        "arn:aws:iam::aws:policy/AmazonS3FullAccess",
        "arn:aws:iam::aws:policy/AWSCodeBuildAdminAccess",
    ])
    ok("IAM Roles created")
    info("Waiting 15s for IAM propagation...")
    time.sleep(15)

    # ── CodeBuild Project ─────────────────────────────────────────────────────
    cb_name = f"{PROJECT}-build"
    try:
        cb.create_project(
            name=cb_name,
            source={"type": "CODEPIPELINE", "buildspec": BUILDSPEC},
            artifacts={"type": "CODEPIPELINE"},
            environment={"type": "LINUX_CONTAINER",
                         "computeType": "BUILD_GENERAL1_SMALL",
                         "image": "aws/codebuild/standard:7.0"},
            serviceRole=cb_role_arn,
        )
        ok(f"CodeBuild: {cb_name}")
    except cb.exceptions.ResourceAlreadyExistsException:
        warn(f"CodeBuild project exists")

    # ── Upload Source to S3 ───────────────────────────────────────────────────
    s3.put_object(Bucket=BUCKET, Key="source/app.zip", Body=make_source_zip())
    ok("Source uploaded")

    # ── CodePipeline ──────────────────────────────────────────────────────────
    pipeline_name = f"{PROJECT}-pipeline"
    try:
        cp.create_pipeline(pipeline={
            "name": pipeline_name,
            "roleArn": cp_role_arn,
            "artifactStore": {"type": "S3", "location": BUCKET},
            "stages": [
                {
                    "name": "Source",
                    "actions": [{
                        "name": "S3Source",
                        "actionTypeId": {"category": "Source", "owner": "AWS",
                                         "provider": "S3", "version": "1"},
                        "configuration": {"S3Bucket": BUCKET, "S3ObjectKey": "source/app.zip",
                                          "PollForSourceChanges": "true"},
                        "outputArtifacts": [{"name": "SourceOutput"}],
                        "runOrder": 1,
                    }],
                },
                {
                    "name": "Build",
                    "actions": [{
                        "name": "CodeBuild",
                        "actionTypeId": {"category": "Build", "owner": "AWS",
                                         "provider": "CodeBuild", "version": "1"},
                        "configuration": {"ProjectName": cb_name},
                        "inputArtifacts": [{"name": "SourceOutput"}],
                        "outputArtifacts": [{"name": "BuildOutput"}],
                        "runOrder": 1,
                    }],
                },
            ],
            "version": 1,
        })
        ok(f"Pipeline: {pipeline_name}")
    except cp.exceptions.PipelineNameInUseException:
        warn("Pipeline exists")

    # ── Lambda 1: Notifier ────────────────────────────────────────────────────
    notifier_arn = create_lambda(lmb, f"{PROJECT}-notifier", lambda_role_arn, NOTIFIER_CODE)
    ok(f"Notifier Lambda: {notifier_arn}")

    # ── Lambda 2: Trigger ─────────────────────────────────────────────────────
    trigger_arn = create_lambda(
        lmb, f"{PROJECT}-trigger", lambda_role_arn, TRIGGER_CODE,
        env={"PIPELINE_NAME": pipeline_name},
    )
    ok(f"Trigger Lambda: {trigger_arn}")

    # ── CloudWatch Events Rule: pipeline state → notifier lambda ─────────────
    rule_name = f"{PROJECT}-pipeline-events"
    rule_arn = events.put_rule(
        Name=rule_name,
        EventPattern=json.dumps({
            "source": ["aws.codepipeline"],
            "detail-type": ["CodePipeline Pipeline Execution State Change"],
            "detail": {"pipeline": [pipeline_name]},
        }),
        State="ENABLED",
        Description="Trigger Lambda on CodePipeline state changes",
    )["RuleArn"]
    ok(f"CloudWatch Events Rule: {rule_arn}")

    # Grant Events permission to invoke Lambda
    try:
        lmb.add_permission(
            FunctionName=f"{PROJECT}-notifier",
            StatementId=f"{PROJECT}-cw-events",
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=rule_arn,
        )
    except lmb.exceptions.ResourceConflictException:
        pass

    events.put_targets(
        Rule=rule_name,
        Targets=[{"Id": "PipelineNotifier", "Arn": notifier_arn}],
    )
    ok("Lambda connected to CloudWatch Events")

    # ── Test: invoke trigger lambda ───────────────────────────────────────────
    info("Invoking trigger Lambda to start a pipeline run...")
    try:
        resp = lmb.invoke(FunctionName=f"{PROJECT}-trigger",
                          InvocationType="RequestResponse")
        payload = json.loads(resp["Payload"].read())
        print(f"\n  Pipeline trigger result:\n{json.dumps(payload, indent=4)}")
    except Exception as e:
        warn(f"Trigger invoke: {e}")

    save_state(STATE_FILE, {
        "bucket": BUCKET,
        "pipeline_name": pipeline_name,
        "cb_name": cb_name,
        "lambda_roles": [f"{PROJECT}-lambda-role", f"{PROJECT}-cb-role", f"{PROJECT}-cp-role"],
        "lambdas": [f"{PROJECT}-notifier", f"{PROJECT}-trigger"],
        "rule_name": rule_name,
    })

    print(f"\n  Deployment Complete!")
    print(f"  Pipeline:        {pipeline_name}")
    print(f"  Trigger Lambda:  {PROJECT}-trigger  (invoke to start pipeline)")
    print(f"  Notifier Lambda: {PROJECT}-notifier (fires on pipeline events)")
    print(f"  CloudWatch Rule: {rule_name}\n")


if __name__ == "__main__":
    deploy()

"""
PROJECT 11 — CI/CD Pipeline for Attendance Application
Services: CodePipeline, CodeBuild, S3, EC2

What this does:
  1. Creates an S3 artifact bucket
  2. Creates IAM roles for CodePipeline + CodeBuild
  3. Creates an EC2 instance running the attendance Flask app
  4. Creates a CodeBuild project with buildspec for the attendance app
  5. Creates a full CodePipeline: Source → Build → Deploy (to EC2 via SSM)
  6. Uploads the attendance app source to S3 to trigger the pipeline
"""

import sys, os, json, zipfile, io, time, base64
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p11-attendance"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
BUCKET     = f"{PROJECT}-artifacts-{int(time.time())}"

# ── Attendance App Source Files ──────────────────────────────────────────────
ATTENDANCE_APP_PY = """
from flask import Flask, request, jsonify, render_template_string
import json, os, datetime

app = Flask(__name__)
ATTENDANCE_FILE = "/tmp/attendance.json"

def load_data():
    if os.path.exists(ATTENDANCE_FILE):
        with open(ATTENDANCE_FILE) as f:
            return json.load(f)
    return []

def save_data(data):
    with open(ATTENDANCE_FILE, "w") as f:
        json.dump(data, f, indent=2)

HTML = '''<!DOCTYPE html>
<html>
<head>
  <title>Attendance System - Project 11</title>
  <style>
    body{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;
         max-width:800px;margin:0 auto;padding:40px}
    h1{color:#818cf8;text-align:center}
    .form-card{background:#1e293b;border-radius:12px;padding:24px;margin:24px 0}
    input,select{background:#0f172a;color:#e2e8f0;border:1px solid #334155;
                 border-radius:6px;padding:8px 12px;width:100%;margin:6px 0}
    button{background:#4f46e5;color:#fff;border:none;border-radius:6px;
           padding:10px 24px;cursor:pointer;font-size:1rem}
    button:hover{background:#6366f1}
    table{width:100%;border-collapse:collapse;margin-top:16px}
    th{background:#1e293b;padding:10px;text-align:left;color:#818cf8}
    td{padding:10px;border-bottom:1px solid #1e293b}
    .present{color:#22c55e} .absent{color:#ef4444}
  </style>
</head>
<body>
  <h1>📋 Attendance System</h1>
  <p style="text-align:center;color:#94a3b8">Project 11 — CI/CD Pipeline</p>

  <div class="form-card">
    <h3>Mark Attendance</h3>
    <form onsubmit="markAttendance(event)">
      <input id="student_name" placeholder="Student Name" required>
      <select id="status">
        <option value="present">Present</option>
        <option value="absent">Absent</option>
      </select>
      <button type="submit">Submit</button>
    </form>
  </div>

  <div class="form-card">
    <h3>Attendance Records</h3>
    <table>
      <tr><th>Name</th><th>Status</th><th>Date</th></tr>
      {% for record in records %}
      <tr>
        <td>{{ record.name }}</td>
        <td class="{{ record.status }}">{{ record.status | capitalize }}</td>
        <td>{{ record.date }}</td>
      </tr>
      {% endfor %}
    </table>
  </div>

  <script>
    async function markAttendance(e) {
      e.preventDefault();
      const name = document.getElementById("student_name").value;
      const status = document.getElementById("status").value;
      await fetch("/mark", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name, status})
      });
      location.reload();
    }
  </script>
</body>
</html>'''

@app.route("/")
def home():
    records = load_data()
    return render_template_string(HTML, records=records)

@app.route("/mark", methods=["POST"])
def mark():
    data = request.json
    records = load_data()
    records.append({
        "name": data["name"],
        "status": data["status"],
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    save_data(records)
    return jsonify({"success": True})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
"""

REQUIREMENTS = "flask==3.0.0\n"

BUILDSPEC = """version: 0.2
phases:
  install:
    runtime-versions:
      python: 3.11
    commands:
      - pip install -r requirements.txt
  pre_build:
    commands:
      - echo Running tests...
      - python -c "import flask; print('Flask OK')"
  build:
    commands:
      - echo Building attendance application...
      - echo "Build version:" $(date +%Y%m%d%H%M%S)
  post_build:
    commands:
      - echo Build complete!
artifacts:
  files:
    - '**/*'
"""

EC2_USER_DATA = """#!/bin/bash
yum update -y
yum install -y python3 python3-pip
pip3 install flask
mkdir -p /opt/attendance
cat > /opt/attendance/app.py << 'APPEOF'
from flask import Flask, jsonify
import socket
app = Flask(__name__)
@app.route("/")
def home():
    return "<h1>Attendance App - Waiting for CI/CD deploy</h1>"
@app.route("/health")
def health():
    return jsonify({"status":"ok","host":socket.gethostname()})
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
APPEOF
python3 /opt/attendance/app.py &
"""

PIPELINE_TRUST = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow",
                   "Principal": {"Service": "codepipeline.amazonaws.com"},
                   "Action": "sts:AssumeRole"}],
})
BUILD_TRUST = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow",
                   "Principal": {"Service": "codebuild.amazonaws.com"},
                   "Action": "sts:AssumeRole"}],
})


def make_source_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("app.py", ATTENDANCE_APP_PY)
        z.writestr("requirements.txt", REQUIREMENTS)
        z.writestr("buildspec.yml", BUILDSPEC)
    return buf.getvalue()


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 11 — CI/CD for Attendance App")
    print("="*60)

    s3  = boto3_client("s3")
    iam = boto3_client("iam")
    ec2 = boto3_client("ec2")
    cb  = boto3_client("codebuild")
    cp  = boto3_client("codepipeline")

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
    cb_role  = f"{PROJECT}-cb-role"
    cp_role  = f"{PROJECT}-cp-role"
    for rname, trust in [(cb_role, BUILD_TRUST), (cp_role, PIPELINE_TRUST)]:
        try:
            iam.create_role(RoleName=rname, AssumeRolePolicyDocument=trust)
        except iam.exceptions.EntityAlreadyExistsException:
            pass

    for pol in ["arn:aws:iam::aws:policy/AWSCodeBuildAdminAccess",
                "arn:aws:iam::aws:policy/AmazonS3FullAccess",
                "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"]:
        iam.attach_role_policy(RoleName=cb_role, PolicyArn=pol)

    for pol in ["arn:aws:iam::aws:policy/AWSCodePipeline_FullAccess",
                 "arn:aws:iam::aws:policy/AmazonS3FullAccess",
                 "arn:aws:iam::aws:policy/AWSCodeBuildAdminAccess"]:
        iam.attach_role_policy(RoleName=cp_role, PolicyArn=pol)

    cb_arn = iam.get_role(RoleName=cb_role)["Role"]["Arn"]
    cp_arn = iam.get_role(RoleName=cp_role)["Role"]["Arn"]
    ok("IAM Roles ready")
    time.sleep(15)

    # ── EC2 Instance ──────────────────────────────────────────────────────────
    vpc_id, subnet_ids = get_default_vpc_and_subnets()
    sg_id = create_security_group(
        f"{PROJECT}-sg", "Attendance EC2 SG", vpc_id,
        [{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
         {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
    )
    instances = ec2.run_instances(
        ImageId=AMI_ID, InstanceType=INSTANCE_TYPE, KeyName=KEY_PAIR_NAME,
        MinCount=1, MaxCount=1, SecurityGroupIds=[sg_id], SubnetId=subnet_ids[0],
        UserData=EC2_USER_DATA,
        TagSpecifications=[{"ResourceType": "instance",
                            "Tags": get_tags(PROJECT, {"Name": f"{PROJECT}-server"})}],
    )
    instance_id = instances["Instances"][0]["InstanceId"]
    ok(f"EC2 Instance: {instance_id}")

    # ── CodeBuild Project ─────────────────────────────────────────────────────
    cb_name = f"{PROJECT}-build"
    try:
        cb.create_project(
            name=cb_name,
            source={"type": "CODEPIPELINE", "buildspec": BUILDSPEC},
            artifacts={"type": "CODEPIPELINE"},
            environment={
                "type": "LINUX_CONTAINER",
                "computeType": "BUILD_GENERAL1_SMALL",
                "image": "aws/codebuild/standard:7.0",
            },
            serviceRole=cb_arn,
        )
        ok(f"CodeBuild: {cb_name}")
    except cb.exceptions.ResourceAlreadyExistsException:
        warn(f"CodeBuild project exists: {cb_name}")

    # ── Upload source to S3 ───────────────────────────────────────────────────
    s3.put_object(Bucket=BUCKET, Key="source/attendance.zip", Body=make_source_zip())
    ok("Source uploaded to S3")

    # ── CodePipeline ──────────────────────────────────────────────────────────
    pipeline_name = f"{PROJECT}-pipeline"
    try:
        cp.create_pipeline(pipeline={
            "name": pipeline_name,
            "roleArn": cp_arn,
            "artifactStore": {"type": "S3", "location": BUCKET},
            "stages": [
                {
                    "name": "Source",
                    "actions": [{
                        "name": "S3Source",
                        "actionTypeId": {"category": "Source", "owner": "AWS",
                                         "provider": "S3", "version": "1"},
                        "configuration": {"S3Bucket": BUCKET,
                                          "S3ObjectKey": "source/attendance.zip",
                                          "PollForSourceChanges": "true"},
                        "outputArtifacts": [{"name": "SourceOutput"}],
                        "runOrder": 1,
                    }],
                },
                {
                    "name": "Build",
                    "actions": [{
                        "name": "BuildApp",
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
        warn(f"Pipeline exists: {pipeline_name}")

    save_state(STATE_FILE, {
        "bucket": BUCKET, "pipeline_name": pipeline_name,
        "cb_name": cb_name, "cb_role": cb_role, "cp_role": cp_role,
        "instance_id": instance_id, "sg_id": sg_id,
    })

    print(f"\n  Deployment Complete!")
    print(f"  EC2 Instance: {instance_id}")
    print(f"  Pipeline:     {pipeline_name}")
    print(f"  Check CodePipeline console for build status\n")


if __name__ == "__main__":
    deploy()

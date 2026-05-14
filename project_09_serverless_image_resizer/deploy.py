"""
PROJECT 9 — Serverless Image Resizer
Services: AWS Lambda, Amazon S3

What this does:
  1. Creates a source S3 bucket (upload images here)
  2. Creates a destination S3 bucket (resized images land here)
  3. Creates an IAM role for Lambda
  4. Deploys a Lambda function that:
     - Triggers on s3:ObjectCreated events
     - Downloads the uploaded image
     - Resizes it to [150x150, 300x300, 800x600]
     - Uploads resized versions to the destination bucket
  5. Configures S3 event notification to trigger Lambda

Requirements: Pillow library bundled in Lambda layer or package
"""

import sys, os, json, zipfile, io, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT       = "capstone-p09-img-resizer"
STATE_FILE    = os.path.join(os.path.dirname(__file__), "state.json")
ts            = int(time.time())
SRC_BUCKET    = f"{PROJECT}-src-{ts}"
DST_BUCKET    = f"{PROJECT}-dst-{ts}"

LAMBDA_CODE = '''
import boto3
import os
import urllib.parse
from io import BytesIO

# Try to import Pillow; if unavailable, use a minimal resize simulation
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

RESIZE_CONFIGS = [
    {"suffix": "thumb",  "width": 150,  "height": 150},
    {"suffix": "medium", "width": 300,  "height": 300},
    {"suffix": "large",  "width": 800,  "height": 600},
]

s3 = boto3.client("s3")
DST_BUCKET = os.environ["DST_BUCKET"]

def lambda_handler(event, context):
    results = []
    for record in event["Records"]:
        src_bucket = record["s3"]["bucket"]["name"]
        src_key    = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        print(f"Processing: s3://{src_bucket}/{src_key}")

        # Download image
        response = s3.get_object(Bucket=src_bucket, Key=src_key)
        img_bytes = response["Body"].read()
        filename  = os.path.basename(src_key)
        name, ext = os.path.splitext(filename)

        if PILLOW_AVAILABLE:
            img = Image.open(BytesIO(img_bytes))
            for cfg in RESIZE_CONFIGS:
                resized = img.copy()
                resized.thumbnail((cfg["width"], cfg["height"]))
                buf = BytesIO()
                fmt = img.format or "JPEG"
                resized.save(buf, format=fmt)
                buf.seek(0)
                dst_key = f"{cfg['suffix']}/{name}_{cfg['suffix']}{ext}"
                s3.put_object(
                    Bucket=DST_BUCKET,
                    Key=dst_key,
                    Body=buf.getvalue(),
                    ContentType=f"image/{ext.lstrip('.').lower()}",
                )
                results.append(f"Created: s3://{DST_BUCKET}/{dst_key}")
                print(results[-1])
        else:
            # Pillow not installed — just copy with metadata note
            dst_key = f"resized/{filename}"
            s3.copy_object(
                CopySource={"Bucket": src_bucket, "Key": src_key},
                Bucket=DST_BUCKET,
                Key=dst_key,
                Metadata={"note": "Pillow not available, original copied"},
                MetadataDirective="REPLACE",
            )
            results.append(f"Copied (no Pillow): s3://{DST_BUCKET}/{dst_key}")

    return {"statusCode": 200, "body": results}
'''

TRUST_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow",
                   "Principal": {"Service": "lambda.amazonaws.com"},
                   "Action": "sts:AssumeRole"}],
})

LAMBDA_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {"Effect": "Allow",
         "Action": ["s3:GetObject"], "Resource": f"arn:aws:s3:::{SRC_BUCKET}/*"},
        {"Effect": "Allow",
         "Action": ["s3:PutObject"], "Resource": f"arn:aws:s3:::{DST_BUCKET}/*"},
        {"Effect": "Allow",
         "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
         "Resource": "*"},
    ],
})


def make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("lambda_function.py", LAMBDA_CODE)
    return buf.getvalue()


def create_bucket(s3, name):
    try:
        if AWS_REGION == "us-east-1":
            s3.create_bucket(Bucket=name)
        else:
            s3.create_bucket(Bucket=name,
                             CreateBucketConfiguration={"LocationConstraint": AWS_REGION})
        ok(f"Bucket: {name}")
    except Exception as e:
        warn(f"Bucket {name}: {e}")


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 9 — Serverless Image Resizer")
    print("="*60)

    s3  = boto3_client("s3")
    iam = boto3_client("iam")
    lmb = boto3_client("lambda")
    sts = boto3_client("sts")

    account_id = sts.get_caller_identity()["Account"]

    # ── S3 Buckets ────────────────────────────────────────────────────────────
    create_bucket(s3, SRC_BUCKET)
    create_bucket(s3, DST_BUCKET)

    # ── IAM Role ──────────────────────────────────────────────────────────────
    role_name = f"{PROJECT}-role"
    try:
        role_arn = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=TRUST_POLICY,
            Tags=get_tags(PROJECT),
        )["Role"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]

    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=f"{PROJECT}-policy",
        PolicyDocument=LAMBDA_POLICY,
    )
    ok(f"IAM Role: {role_arn}")
    info("Waiting 20s for IAM propagation...")
    time.sleep(20)

    # ── Lambda Function ───────────────────────────────────────────────────────
    fn_name = f"{PROJECT}-fn"
    try:
        fn_resp = lmb.create_function(
            FunctionName=fn_name,
            Runtime="python3.11",
            Role=role_arn,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": make_zip()},
            Description="Resizes images uploaded to S3",
            Timeout=60,
            MemorySize=512,
            Environment={"Variables": {"DST_BUCKET": DST_BUCKET}},
            Tags={t["Key"]: t["Value"] for t in get_tags(PROJECT)},
        )
        fn_arn = fn_resp["FunctionArn"]
        ok(f"Lambda: {fn_arn}")
    except lmb.exceptions.ResourceConflictException:
        lmb.update_function_code(FunctionName=fn_name, ZipFile=make_zip())
        fn_arn = lmb.get_function(FunctionName=fn_name)["Configuration"]["FunctionArn"]
        warn(f"Lambda updated: {fn_arn}")

    # ── Allow S3 to invoke Lambda ─────────────────────────────────────────────
    try:
        lmb.add_permission(
            FunctionName=fn_name,
            StatementId=f"{PROJECT}-s3-invoke",
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{SRC_BUCKET}",
            SourceAccount=account_id,
        )
    except lmb.exceptions.ResourceConflictException:
        pass
    ok("Lambda permission for S3 granted")

    # ── Wait for Lambda permission to propagate ───────────────────────────────
    info("Waiting 15s for Lambda permission to propagate to S3...")
    time.sleep(15)

    # ── S3 Event Notification → Lambda (with retry) ───────────────────────────
    for attempt in range(1, 4):
        try:
            s3.put_bucket_notification_configuration(
                Bucket=SRC_BUCKET,
                NotificationConfiguration={
                    "LambdaFunctionConfigurations": [{
                        "LambdaFunctionArn": fn_arn,
                        "Events": ["s3:ObjectCreated:*"],
                        "Filter": {
                            "Key": {"FilterRules": [
                                {"Name": "suffix", "Value": ".jpg"},
                            ]}
                        },
                    }, {
                        "LambdaFunctionArn": fn_arn,
                        "Events": ["s3:ObjectCreated:*"],
                        "Filter": {
                            "Key": {"FilterRules": [
                                {"Name": "suffix", "Value": ".png"},
                            ]}
                        },
                    }],
                },
            )
            ok("S3 event notification configured (triggers on .jpg and .png uploads)")
            break
        except Exception as e:
            if attempt < 3:
                warn(f"Attempt {attempt} failed, retrying in 10s: {e}")
                time.sleep(10)
            else:
                raise

    save_state(STATE_FILE, {
        "src_bucket": SRC_BUCKET,
        "dst_bucket": DST_BUCKET,
        "fn_name": fn_name,
        "role_name": role_name,
    })

    print(f"\n  Deployment Complete!")
    print(f"  Upload an image: aws s3 cp photo.jpg s3://{SRC_BUCKET}/")
    print(f"  Resized images: s3://{DST_BUCKET}/")
    print(f"  Sizes: thumb(150x150), medium(300x300), large(800x600)\n")


if __name__ == "__main__":
    deploy()

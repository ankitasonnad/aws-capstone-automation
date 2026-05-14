"""Cleanup — Project 5: S3 Static Hosting"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def destroy():
    state = load_state(STATE_FILE)
    s3 = boto3_client("s3")
    bucket = state["bucket"]

    print(f"\n  Deleting bucket: {bucket}")
    try:
        # Delete all objects
        objects = s3.list_objects_v2(Bucket=bucket)
        for obj in objects.get("Contents", []):
            s3.delete_object(Bucket=bucket, Key=obj["Key"])
            ok(f"Deleted: {obj['Key']}")
        s3.delete_bucket(Bucket=bucket)
        ok(f"Bucket {bucket} deleted")
    except Exception as e:
        warn(str(e))

    os.remove(STATE_FILE)
    print("\n  Cleanup complete!\n")

if __name__ == "__main__":
    destroy()

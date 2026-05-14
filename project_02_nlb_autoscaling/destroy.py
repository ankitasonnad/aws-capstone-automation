"""
Cleanup — Project 2: NLB + Auto Scaling
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def destroy():
    state = load_state(STATE_FILE)
    ec2   = boto3_client("ec2")
    elb   = boto3_client("elbv2")
    asg   = boto3_client("autoscaling")

    print("\n  Destroying Project 2 resources...")

    try:
        asg.delete_auto_scaling_group(
            AutoScalingGroupName=state["asg_name"], ForceDelete=True)
        ok(f"ASG deleted"); time.sleep(15)
    except Exception as e:
        warn(str(e))

    try:
        ec2.delete_launch_template(LaunchTemplateId=state["lt_id"])
        ok("Launch Template deleted")
    except Exception as e:
        warn(str(e))

    try:
        listeners = elb.describe_listeners(LoadBalancerArn=state["nlb_arn"])
        for l in listeners["Listeners"]:
            elb.delete_listener(ListenerArn=l["ListenerArn"])
        elb.delete_load_balancer(LoadBalancerArn=state["nlb_arn"])
        ok("NLB deleted"); time.sleep(10)
    except Exception as e:
        warn(str(e))

    try:
        elb.delete_target_group(TargetGroupArn=state["tg_arn"])
        ok("Target Group deleted")
    except Exception as e:
        warn(str(e))

    time.sleep(15)
    # Wait for EC2 instances to fully terminate before deleting SGs
    info("Waiting 90s for EC2 instances to terminate before SG cleanup...")
    time.sleep(90)
    for sg in [state["sg_id"]]:
        for attempt in range(1, 5):
            try:
                ec2.delete_security_group(GroupId=sg)
                ok(f"Security Group {sg} deleted")
                break
            except Exception as e:
                if attempt < 4:
                    warn(f"SG still in use, retry {attempt}/3 in 30s...")
                    time.sleep(30)
                else:
                    warn(f"Could not delete SG {sg} (EC2 still terminating — will auto-clean in ~5 min)")
    os.remove(STATE_FILE)
    print("\n  Cleanup complete!\n")

if __name__ == "__main__":
    destroy()

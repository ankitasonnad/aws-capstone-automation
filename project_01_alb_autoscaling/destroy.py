"""
Cleanup — Project 1: ALB + Auto Scaling
Deletes: ASG → Launch Template → Listener → ALB → Target Group → Security Groups
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
PROJECT    = "capstone-p01-alb"

def destroy():
    state = load_state(STATE_FILE)
    ec2   = boto3_client("ec2")
    elb   = boto3_client("elbv2")
    asg   = boto3_client("autoscaling")

    print("\n  Destroying Project 1 resources...")

    # 1. Delete ASG
    try:
        asg.delete_auto_scaling_group(
            AutoScalingGroupName=state["asg_name"], ForceDelete=True)
        ok(f"ASG {state['asg_name']} deleted")
        time.sleep(15)
    except Exception as e:
        warn(str(e))

    # 2. Delete Launch Template
    try:
        ec2.delete_launch_template(LaunchTemplateId=state["lt_id"])
        ok(f"Launch Template {state['lt_id']} deleted")
    except Exception as e:
        warn(str(e))

    # 3. Delete ALB Listener & ALB
    try:
        listeners = elb.describe_listeners(LoadBalancerArn=state["alb_arn"])
        for l in listeners["Listeners"]:
            elb.delete_listener(ListenerArn=l["ListenerArn"])
        elb.delete_load_balancer(LoadBalancerArn=state["alb_arn"])
        ok("ALB deleted")
        time.sleep(10)
    except Exception as e:
        warn(str(e))

    # 4. Delete Target Group
    try:
        elb.delete_target_group(TargetGroupArn=state["tg_arn"])
        ok("Target Group deleted")
    except Exception as e:
        warn(str(e))

    # 5. Delete Security Groups
    time.sleep(15)
    for sg_key in ["alb_sg_id", "ec2_sg_id"]:
        if sg_key in state:
            delete_security_group(state[sg_key])

    os.remove(STATE_FILE)
    print("\n  Cleanup complete!\n")

if __name__ == "__main__":
    destroy()

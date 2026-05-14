"""Cleanup — Project 10: Containerized Node.js (ECR + ECS)"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def destroy():
    state = load_state(STATE_FILE)
    ecs   = boto3_client("ecs")
    ecr   = boto3_client("ecr")
    elb   = boto3_client("elbv2")
    iam   = boto3_client("iam")

    print("\n  Destroying Project 10 resources...")

    try:
        ecs.update_service(cluster=state["cluster_arn"],
                           service=state["service_name"], desiredCount=0)
        time.sleep(10)
        ecs.delete_service(cluster=state["cluster_arn"],
                           service=state["service_name"], force=True)
        ok("ECS Service deleted")
    except Exception as e:
        warn(str(e))

    try:
        ecs.delete_cluster(cluster=state["cluster_arn"])
        ok("ECS Cluster deleted")
    except Exception as e:
        warn(str(e))

    try:
        ecs.deregister_task_definition(taskDefinition=state["td_arn"])
        ok("Task Definition deregistered")
    except Exception as e:
        warn(str(e))

    try:
        listeners = elb.describe_listeners(LoadBalancerArn=state["alb_arn"])
        for l in listeners["Listeners"]:
            elb.delete_listener(ListenerArn=l["ListenerArn"])
        elb.delete_load_balancer(LoadBalancerArn=state["alb_arn"])
        ok("ALB deleted"); time.sleep(10)
        elb.delete_target_group(TargetGroupArn=state["tg_arn"])
    except Exception as e:
        warn(str(e))

    try:
        ecr.delete_repository(repositoryName=state["ecr_repo"], force=True)
        ok("ECR Repo deleted")
    except Exception as e:
        warn(str(e))

    time.sleep(15)
    delete_security_group(state["sg_id"])

    try:
        attached = iam.list_attached_role_policies(RoleName=state["role_name"])
        for p in attached["AttachedPolicies"]:
            iam.detach_role_policy(RoleName=state["role_name"], PolicyArn=p["PolicyArn"])
        iam.delete_role(RoleName=state["role_name"])
        ok("IAM Role deleted")
    except Exception as e:
        warn(str(e))

    os.remove(STATE_FILE)
    print("\n  Cleanup complete!\n")

if __name__ == "__main__":
    destroy()

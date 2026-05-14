"""
🚀 AWS Capstone Projects — Master Runner
Run all 15 projects in sequence (for testing purposes)
"""
import subprocess, sys, os

PROJECTS = [
    ("project_01_alb_autoscaling",     "ALB + Auto Scaling"),
    ("project_02_nlb_autoscaling",     "NLB + Auto Scaling"),
    ("project_03_multitier_webapp",    "Multi-tier Web App"),
    ("project_04_automate_provisioning","Automate Provisioning"),
    ("project_05_s3_static_hosting",   "S3 Static Hosting"),
    ("project_06_cost_optimizer",      "Automated Cost Optimizer"),
    ("project_07_cicd_nodejs",         "CI/CD Node.js Pipeline"),
    ("project_08_containerized_flask", "Containerized Flask (ECR+ECS)"),
    ("project_09_serverless_image_resizer","Serverless Image Resizer"),
    ("project_10_containerized_nodejs", "Containerized Node.js"),
    ("project_11_cicd_attendance",     "CI/CD Attendance App"),
    ("project_12_bus_booking_app",     "Bus Booking Application"),
    ("project_13_lamp_hosting",        "LAMP Stack Hosting"),
    ("project_14_lemp_hosting",        "LEMP Stack Hosting"),
    ("project_15_lambda_cicd",         "Lambda CI/CD Automation"),
]

BASE_DIR = os.path.dirname(__file__)


def run_project(project_dir: str, name: str, action: str = "deploy"):
    """Run deploy.py or destroy.py for a project."""
    script = os.path.join(BASE_DIR, project_dir, f"{action}.py")
    print(f"\n{'='*60}")
    print(f"  {'▶' if action == 'deploy' else '🗑'} {name}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, script],
        cwd=os.path.join(BASE_DIR, project_dir)
    )
    return result.returncode == 0


def deploy_all():
    print("\n🚀 Deploying All 15 AWS Capstone Projects")
    print("=" * 60)
    results = []
    for project_dir, name in PROJECTS:
        success = run_project(project_dir, name, "deploy")
        results.append((name, "✅" if success else "❌"))

    print("\n📊 Deployment Summary:")
    for name, status in results:
        print(f"  {status}  {name}")


def destroy_all():
    print("\n🗑  Cleaning Up All 15 AWS Capstone Projects")
    print("=" * 60)
    # Destroy in reverse order
    for project_dir, name in reversed(PROJECTS):
        run_project(project_dir, name, "destroy")
    print("\n✅ All resources cleaned up!")


def deploy_one(number: int):
    """Deploy a single project by number (1-15)."""
    if 1 <= number <= 15:
        project_dir, name = PROJECTS[number - 1]
        run_project(project_dir, name, "deploy")
    else:
        print(f"Invalid project number. Choose 1-15.")


def destroy_one(number: int):
    """Destroy a single project by number (1-15)."""
    if 1 <= number <= 15:
        project_dir, name = PROJECTS[number - 1]
        run_project(project_dir, name, "destroy")
    else:
        print(f"Invalid project number. Choose 1-15.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""
Usage:
  python run_all.py deploy          # Deploy all 15 projects
  python run_all.py destroy         # Destroy all resources
  python run_all.py deploy <N>      # Deploy single project (1-15)
  python run_all.py destroy <N>     # Destroy single project (1-15)

Projects:
""")
        for i, (_, name) in enumerate(PROJECTS, 1):
            print(f"  {i:2d}. {name}")
    elif sys.argv[1] == "deploy":
        if len(sys.argv) == 3:
            deploy_one(int(sys.argv[2]))
        else:
            deploy_all()
    elif sys.argv[1] == "destroy":
        if len(sys.argv) == 3:
            destroy_one(int(sys.argv[2]))
        else:
            destroy_all()
    else:
        print(f"Unknown command: {sys.argv[1]}. Use 'deploy' or 'destroy'.")

"""
PROJECT 12 — Deploy Bus Booking Application
Services: EC2, RDS MySQL, Application Load Balancer

A full real-world bus booking web application:
  - Flask backend with booking API
  - RDS MySQL for storing bookings
  - ALB for traffic distribution
  - 2 EC2 instances behind the ALB

Features:
  - Browse routes
  - Book seats
  - View booking confirmation
"""

import sys, os, base64, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p12-busbooking"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
DB_NAME    = "busdb"
DB_USER    = "busadmin"

APP_CODE = '''
from flask import Flask, request, jsonify, render_template_string
import pymysql, os, socket

app = Flask(__name__)

DB_CONFIG = {
    "host":   os.environ.get("DB_HOST", "localhost"),
    "user":   os.environ.get("DB_USER", "busadmin"),
    "password": os.environ.get("DB_PASS", "CapstonePass123!"),
    "database": "busdb",
    "connect_timeout": 5,
}

def get_db():
    return pymysql.connect(**DB_CONFIG)

def init_db():
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100),
                route VARCHAR(100),
                seats INT,
                travel_date DATE,
                booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return str(e)

HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>BusBook - Project 12</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0}
    nav{background:#1e3a5f;padding:16px 40px;display:flex;
        align-items:center;justify-content:space-between}
    nav h1{color:#38bdf8;font-size:1.5rem}
    .hero{background:linear-gradient(135deg,#1e3a5f,#0f172a);
          padding:60px 40px;text-align:center}
    .hero h2{font-size:2.5rem;color:#38bdf8;margin-bottom:12px}
    .container{max-width:900px;margin:40px auto;padding:0 20px}
    .card{background:#1e293b;border-radius:16px;padding:32px;margin-bottom:24px}
    .card h3{color:#38bdf8;margin-bottom:20px;font-size:1.3rem}
    .route-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}
    .route-card{background:#0f172a;border:1px solid #334155;border-radius:12px;
                padding:20px;cursor:pointer;transition:.2s}
    .route-card:hover{border-color:#38bdf8;transform:translateY(-2px)}
    .route-name{font-weight:600;color:#e2e8f0;margin-bottom:4px}
    .route-price{color:#22c55e;font-size:1.1rem}
    label{display:block;color:#94a3b8;margin-bottom:4px;font-size:.9rem}
    input,select{width:100%;background:#0f172a;color:#e2e8f0;
                 border:1px solid #334155;border-radius:8px;
                 padding:10px;margin-bottom:16px}
    button{background:#0ea5e9;color:#fff;border:none;border-radius:8px;
           padding:12px 32px;cursor:pointer;font-size:1rem;font-weight:600}
    button:hover{background:#38bdf8}
    .success{background:#065f46;color:#6ee7b7;padding:16px;border-radius:8px;margin-top:16px}
    table{width:100%;border-collapse:collapse}
    th{background:#0f172a;padding:12px;text-align:left;color:#38bdf8}
    td{padding:12px;border-bottom:1px solid #1e293b;color:#94a3b8}
    .badge{background:#1e3a5f;color:#38bdf8;border-radius:999px;
           padding:2px 10px;font-size:.8rem}
  </style>
</head>
<body>
  <nav>
    <h1>🚌 BusBook</h1>
    <span class="badge">Project 12 — EC2 + RDS + ALB</span>
  </nav>

  <div class="hero">
    <h2>Book Your Bus Ticket</h2>
    <p style="color:#94a3b8">Simple, fast, and reliable bus booking system</p>
    <p style="color:#64748b;font-size:.9rem;margin-top:8px">
      Served by: {{ host }}
    </p>
  </div>

  <div class="container">
    <div class="card">
      <h3>🗺️ Available Routes</h3>
      <div class="route-grid">
        <div class="route-card" onclick="selectRoute('Mumbai - Pune')">
          <div class="route-name">Mumbai → Pune</div>
          <div class="route-price">₹350</div>
          <div style="color:#64748b;font-size:.85rem">3.5 hours</div>
        </div>
        <div class="route-card" onclick="selectRoute('Bangalore - Mysore')">
          <div class="route-name">Bangalore → Mysore</div>
          <div class="route-price">₹250</div>
          <div style="color:#64748b;font-size:.85rem">2.5 hours</div>
        </div>
        <div class="route-card" onclick="selectRoute('Delhi - Agra')">
          <div class="route-name">Delhi → Agra</div>
          <div class="route-price">₹450</div>
          <div style="color:#64748b;font-size:.85rem">4 hours</div>
        </div>
        <div class="route-card" onclick="selectRoute('Chennai - Pondicherry')">
          <div class="route-name">Chennai → Pondicherry</div>
          <div class="route-price">₹300</div>
          <div style="color:#64748b;font-size:.85rem">3 hours</div>
        </div>
      </div>
    </div>

    <div class="card">
      <h3>📝 Booking Form</h3>
      <form onsubmit="submitBooking(event)">
        <label>Passenger Name</label>
        <input id="name" placeholder="Your full name" required>
        <label>Route</label>
        <input id="route" placeholder="Select a route above or type manually" required>
        <label>Travel Date</label>
        <input type="date" id="travel_date" required>
        <label>Number of Seats</label>
        <input type="number" id="seats" min="1" max="10" value="1" required>
        <button type="submit">Confirm Booking</button>
      </form>
      <div id="result"></div>
    </div>

    <div class="card">
      <h3>📋 Recent Bookings</h3>
      <table>
        <tr><th>Name</th><th>Route</th><th>Seats</th><th>Date</th></tr>
        {% for b in bookings %}
        <tr>
          <td>{{ b[1] }}</td>
          <td>{{ b[2] }}</td>
          <td>{{ b[3] }}</td>
          <td>{{ b[4] }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
  </div>

  <script>
    function selectRoute(r) { document.getElementById("route").value = r; }
    async function submitBooking(e) {
      e.preventDefault();
      const resp = await fetch("/book", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          name: document.getElementById("name").value,
          route: document.getElementById("route").value,
          seats: document.getElementById("seats").value,
          travel_date: document.getElementById("travel_date").value,
        })
      });
      const data = await resp.json();
      document.getElementById("result").innerHTML =
        data.success
          ? '<div class="success">✅ Booking confirmed! ID: ' + data.id + '</div>'
          : '<div style="color:#ef4444">Error: ' + data.error + '</div>';
      setTimeout(() => location.reload(), 2000);
    }
  </script>
</body>
</html>
"""

@app.route("/")
def home():
    db_ok = init_db()
    bookings = []
    if db_ok is True:
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM bookings ORDER BY booked_at DESC LIMIT 10")
            bookings = cur.fetchall()
            conn.close()
        except Exception:
            pass
    return render_template_string(HTML, bookings=bookings, host=socket.gethostname())

@app.route("/book", methods=["POST"])
def book():
    data = request.json
    try:
        init_db()
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO bookings (name, route, seats, travel_date) VALUES (%s,%s,%s,%s)",
            (data["name"], data["route"], data["seats"], data["travel_date"])
        )
        conn.commit()
        booking_id = cur.lastrowid
        conn.close()
        return jsonify({"success": True, "id": booking_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "host": socket.gethostname()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
'''


def get_user_data(db_host):
    return f"""#!/bin/bash
yum update -y
yum install -y python3 python3-pip
pip3 install flask pymysql

mkdir -p /opt/busbooking

cat > /opt/busbooking/app.py << 'APPEOF'
{APP_CODE}
APPEOF

export DB_HOST="{db_host}"
export DB_USER="{DB_USER}"
export DB_PASS="{DB_PASSWORD}"

nohup python3 /opt/busbooking/app.py > /var/log/busbooking.log 2>&1 &
"""


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 12 — Bus Booking App (EC2+RDS+ALB)")
    print("="*60)

    ec2  = boto3_client("ec2")
    rds  = boto3_client("rds")
    elb  = boto3_client("elbv2")
    asg  = boto3_client("autoscaling")

    vpc_id, subnet_ids = get_default_vpc_and_subnets()

    # ── Security Groups ───────────────────────────────────────────────────────
    web_sg = create_security_group(
        f"{PROJECT}-web-sg", "Bus App Web SG", vpc_id,
        [{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
         {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
    )
    db_sg = create_security_group(
        f"{PROJECT}-db-sg", "Bus App DB SG", vpc_id,
        [{"IpProtocol": "tcp", "FromPort": 3306, "ToPort": 3306,
          "UserIdGroupPairs": [{"GroupId": web_sg}]}],
    )

    # ── RDS Subnet Group + MySQL ──────────────────────────────────────────────
    try:
        rds.create_db_subnet_group(
            DBSubnetGroupName=f"{PROJECT}-subnet-grp",
            DBSubnetGroupDescription="Bus booking DB subnet group",
            SubnetIds=subnet_ids,
        )
    except Exception as e:
        warn(f"Subnet group: {e}")

    info("Creating RDS MySQL instance (~5-10 min)...")
    rds.create_db_instance(
        DBInstanceIdentifier=f"{PROJECT}-rds",
        DBInstanceClass="db.t3.micro",
        Engine="mysql",
        EngineVersion="8.0",
        MasterUsername=DB_USER,
        MasterUserPassword=DB_PASSWORD,
        DBName=DB_NAME,
        AllocatedStorage=20,
        VpcSecurityGroupIds=[db_sg],
        DBSubnetGroupName=f"{PROJECT}-subnet-grp",
        PubliclyAccessible=False,
        MultiAZ=False,
        StorageType="gp2",
        Tags=get_tags(PROJECT),
    )

    waiter_msg("RDS MySQL instance")
    rds.get_waiter("db_instance_available").wait(
        DBInstanceIdentifier=f"{PROJECT}-rds",
        WaiterConfig={"Delay": 30, "MaxAttempts": 40})
    db_host = rds.describe_db_instances(
        DBInstanceIdentifier=f"{PROJECT}-rds")["DBInstances"][0]["Endpoint"]["Address"]
    ok(f"RDS ready: {db_host}")

    # ── Launch Template ───────────────────────────────────────────────────────
    lt = ec2.create_launch_template(
        LaunchTemplateName=f"{PROJECT}-lt",
        LaunchTemplateData={
            "ImageId": AMI_ID, "InstanceType": INSTANCE_TYPE, "KeyName": KEY_PAIR_NAME,
            "SecurityGroupIds": [web_sg],
            "UserData": base64.b64encode(get_user_data(db_host).encode()).decode(),
            "TagSpecifications": [{"ResourceType": "instance", "Tags": get_tags(PROJECT)}],
        },
    )
    lt_id = lt["LaunchTemplate"]["LaunchTemplateId"]
    ok(f"Launch Template: {lt_id}")

    # ── ALB + Target Group ────────────────────────────────────────────────────
    alb_resp = elb.create_load_balancer(
        Name=f"{PROJECT}-alb", Subnets=subnet_ids, SecurityGroups=[web_sg],
        Scheme="internet-facing", Type="application", Tags=get_tags(PROJECT))
    alb_arn = alb_resp["LoadBalancers"][0]["LoadBalancerArn"]
    alb_dns = alb_resp["LoadBalancers"][0]["DNSName"]

    tg_arn = elb.create_target_group(
        Name=f"{PROJECT}-tg", Protocol="HTTP", Port=80, VpcId=vpc_id,
        HealthCheckPath="/health", TargetType="instance",
    )["TargetGroups"][0]["TargetGroupArn"]

    elb.create_listener(LoadBalancerArn=alb_arn, Protocol="HTTP", Port=80,
                        DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}])
    ok("ALB ready")

    # ── Auto Scaling Group ────────────────────────────────────────────────────
    asg.create_auto_scaling_group(
        AutoScalingGroupName=f"{PROJECT}-asg",
        LaunchTemplate={"LaunchTemplateId": lt_id, "Version": "$Latest"},
        MinSize=1, MaxSize=4, DesiredCapacity=2,
        VPCZoneIdentifier=",".join(subnet_ids),
        TargetGroupARNs=[tg_arn],
        HealthCheckType="ELB",
        HealthCheckGracePeriod=180,
        Tags=[{**t, "ResourceId": f"{PROJECT}-asg",
               "ResourceType": "auto-scaling-group", "PropagateAtLaunch": True}
              for t in get_tags(PROJECT)],
    )
    ok("Auto Scaling Group: 2 instances")

    save_state(STATE_FILE, {
        "alb_arn": alb_arn, "tg_arn": tg_arn, "asg_name": f"{PROJECT}-asg",
        "lt_id": lt_id, "web_sg": web_sg, "db_sg": db_sg,
        "rds_id": f"{PROJECT}-rds", "subnet_group": f"{PROJECT}-subnet-grp",
        "alb_dns": alb_dns,
    })

    print(f"\n  Deployment Complete!")
    print(f"  URL: http://{alb_dns}")
    print(f"  DB:  {db_host}")
    print(f"  Booking app will be ready in ~3-4 minutes\n")


if __name__ == "__main__":
    deploy()

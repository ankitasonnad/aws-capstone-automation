"""
PROJECT 13 — LAMP Application Hosting
LAMP = Linux + Apache + MySQL + PHP
Services: EC2, RDS MySQL

What this does:
  1. Creates a Security Group for the EC2 instance (HTTP 80, SSH 22)
  2. Creates a DB Security Group for RDS (MySQL 3306, from EC2 SG only)
  3. Creates an RDS MySQL 8.0 instance (db.t3.micro)
  4. Launches an EC2 instance with:
     - Apache HTTP server
     - PHP 8.1
     - mysqli PHP extension
     - A sample PHP app that connects to RDS
  5. Returns the public IP of the LAMP server
"""

import sys, os, base64, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p13-lamp"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
DB_NAME    = "lampdb"
DB_USER    = "lampuser"


def get_user_data(rds_host: str) -> str:
    return f"""#!/bin/bash
# ── Install LAMP Stack ───────────────────────────────────
yum update -y
yum install -y httpd

# Install PHP 8.1 via amazon-linux-extras
amazon-linux-extras enable php8.1
yum clean metadata
yum install -y php php-mysqlnd php-fpm php-opcache php-xml php-gd php-mbstring

# ── Start Services ───────────────────────────────────────
systemctl start httpd
systemctl enable httpd
systemctl start php-fpm
systemctl enable php-fpm

# ── Create PHP Application ───────────────────────────────
mkdir -p /var/www/html

cat > /var/www/html/index.php << 'PHPEOF'
<?php
$db_host = "{rds_host}";
$db_user = "{DB_USER}";
$db_pass = "{DB_PASSWORD}";
$db_name = "{DB_NAME}";

$conn = new mysqli($db_host, $db_user, $db_pass, $db_name, 3306, null, MYSQLI_CLIENT_SSL);
if ($conn->connect_error) {{
    $db_status = "Error: " . $conn->connect_error;
    $db_color  = "#ef4444";
}} else {{
    // Create demo table
    $conn->query("CREATE TABLE IF NOT EXISTS visitors (
        id INT AUTO_INCREMENT PRIMARY KEY,
        ip VARCHAR(50),
        visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )");
    $conn->query("INSERT INTO visitors (ip) VALUES ('" . $_SERVER["REMOTE_ADDR"] . "')");
    $count_result = $conn->query("SELECT COUNT(*) as cnt FROM visitors");
    $count = $count_result->fetch_assoc()["cnt"];
    $db_status = "Connected ✓ | Visitors: $count";
    $db_color  = "#22c55e";
    $conn->close();
}}
?>
<!DOCTYPE html>
<html>
<head>
  <title>Project 13 – LAMP Stack</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:Arial,sans-serif;background:#1a0a00;color:#fed7aa;
         display:flex;align-items:center;justify-content:center;min-height:100vh}}
    .card{{background:#292416;border:1px solid #92400e;border-radius:16px;
           padding:48px;max-width:600px;text-align:center}}
    h1{{color:#f97316;font-size:2.5rem;margin-bottom:8px}}
    h2{{color:#fed7aa;font-weight:400;margin-bottom:32px}}
    .lamp{{display:flex;justify-content:center;gap:16px;margin-bottom:32px}}
    .l{{background:#1c2233;color:#60a5fa;border-radius:8px;
        padding:12px 20px;font-weight:700;font-size:1.1rem}}
    .db{{font-weight:bold;color:{rds_host and "#22c55e" or "#ef4444"}}}
    .info{{background:#0f172a;border-radius:8px;padding:16px;
           margin-top:20px;text-align:left}}
    .info p{{margin:6px 0;color:#94a3b8;font-size:.9rem}}
    .info span{{color:#f97316}}
  </style>
</head>
<body>
  <div class="card">
    <h1>🔥 Project 13</h1>
    <h2>LAMP Application Hosting</h2>
    <div class="lamp">
      <div class="l">L<br><small>Linux</small></div>
      <div class="l">A<br><small>Apache</small></div>
      <div class="l">M<br><small>MySQL</small></div>
      <div class="l">P<br><small>PHP</small></div>
    </div>
    <p class="db"><?php echo $db_status; ?></p>
    <div class="info">
      <p>Server: <span><?php echo gethostname(); ?></span></p>
      <p>PHP Version: <span><?php echo phpversion(); ?></span></p>
      <p>DB Host: <span><?php echo $db_host; ?></span></p>
      <p>Remote IP: <span><?php echo $_SERVER["REMOTE_ADDR"]; ?></span></p>
    </div>
  </div>
</body>
</html>
PHPEOF

# ── Set Permissions ──────────────────────────────────────
chown -R apache:apache /var/www/html
chmod -R 755 /var/www/html
"""


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 13 — LAMP Stack (Linux+Apache+MySQL+PHP)")
    print("="*60)

    ec2 = boto3_client("ec2")
    rds = boto3_client("rds")

    vpc_id, subnet_ids = get_default_vpc_and_subnets()

    # ── Security Groups ───────────────────────────────────────────────────────
    web_sg = create_security_group(
        f"{PROJECT}-web-sg", "LAMP Web SG", vpc_id,
        [{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
         {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
    )
    db_sg = create_security_group(
        f"{PROJECT}-db-sg", "LAMP DB SG", vpc_id,
        [{"IpProtocol": "tcp", "FromPort": 3306, "ToPort": 3306,
          "UserIdGroupPairs": [{"GroupId": web_sg}]}],
    )

    # ── RDS ───────────────────────────────────────────────────────────────────
    try:
        rds.create_db_subnet_group(
            DBSubnetGroupName=f"{PROJECT}-subnet-grp",
            DBSubnetGroupDescription="LAMP DB subnet",
            SubnetIds=subnet_ids,
        )
    except Exception as e:
        warn(f"Subnet group: {e}")

    info("Creating RDS MySQL (~5-10 min)...")
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
        Tags=get_tags(PROJECT),
    )

    waiter_msg("RDS")
    rds.get_waiter("db_instance_available").wait(
        DBInstanceIdentifier=f"{PROJECT}-rds",
        WaiterConfig={"Delay": 30, "MaxAttempts": 40})
    rds_host = rds.describe_db_instances(
        DBInstanceIdentifier=f"{PROJECT}-rds")["DBInstances"][0]["Endpoint"]["Address"]
    ok(f"RDS: {rds_host}")

    # ── EC2 with LAMP ─────────────────────────────────────────────────────────
    user_data = get_user_data(rds_host)
    instances = ec2.run_instances(
        ImageId=AMI_ID, InstanceType=INSTANCE_TYPE, KeyName=KEY_PAIR_NAME,
        MinCount=1, MaxCount=1,
        SecurityGroupIds=[web_sg], SubnetId=subnet_ids[0],
        UserData=user_data,
        TagSpecifications=[{"ResourceType": "instance",
                            "Tags": get_tags(PROJECT, {"Name": f"{PROJECT}-server"})}],
    )
    instance_id = instances["Instances"][0]["InstanceId"]
    ok(f"EC2 launched: {instance_id}")

    info("Waiting for public IP...")
    waiter = ec2.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id])
    inst_info = ec2.describe_instances(InstanceIds=[instance_id])
    public_ip = inst_info["Reservations"][0]["Instances"][0].get("PublicIpAddress", "N/A")
    ok(f"Public IP: {public_ip}")

    save_state(STATE_FILE, {
        "instance_id": instance_id,
        "web_sg": web_sg, "db_sg": db_sg,
        "rds_id": f"{PROJECT}-rds",
        "subnet_group": f"{PROJECT}-subnet-grp",
        "public_ip": public_ip,
    })

    print(f"\n  Deployment Complete!")
    print(f"  URL: http://{public_ip}/")
    print(f"  Stack: Linux + Apache + MySQL + PHP")
    print(f"  (LAMP takes ~2 min to initialize on first boot)\n")


if __name__ == "__main__":
    deploy()

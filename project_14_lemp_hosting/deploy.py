"""
PROJECT 14 — LEMP Application Hosting
LEMP = Linux + Nginx + MySQL + PHP
Services: EC2, RDS MySQL

Key difference from LAMP: Uses Nginx as webserver (faster, event-driven)
+ PHP-FPM for handling PHP requests (non-blocking)

What this does:
  1. Creates Security Groups for web (80/22) and DB (3306)
  2. Creates RDS MySQL instance
  3. Launches EC2 with Nginx + PHP-FPM + connects to RDS
  4. Deploys a sample PHP application
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p14-lemp"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
DB_NAME    = "lempdb"
DB_USER    = "lempuser"


def get_user_data(rds_host: str) -> str:
    return f"""#!/bin/bash
# ── Install LEMP Stack ───────────────────────────────────
yum update -y

# Nginx
amazon-linux-extras install nginx1 -y
systemctl start nginx
systemctl enable nginx

# PHP 8.1 + FPM
amazon-linux-extras enable php8.1
yum clean metadata
yum install -y php php-fpm php-mysqlnd php-opcache php-xml php-gd php-mbstring

# Configure PHP-FPM to use Unix socket
sed -i 's|^listen = .*|listen = /run/php-fpm/www.sock|' /etc/php-fpm.d/www.conf
sed -i 's|^listen.owner = .*|listen.owner = nginx|' /etc/php-fpm.d/www.conf
sed -i 's|^listen.group = .*|listen.group = nginx|' /etc/php-fpm.d/www.conf
sed -i 's|^user = .*|user = nginx|' /etc/php-fpm.d/www.conf
sed -i 's|^group = .*|group = nginx|' /etc/php-fpm.d/www.conf

systemctl start php-fpm
systemctl enable php-fpm

# ── Configure Nginx ───────────────────────────────────────
cat > /etc/nginx/conf.d/lemp.conf << 'NGINXEOF'
server {{
    listen 80;
    server_name _;
    root /var/www/lemp;
    index index.php index.html;

    location / {{
        try_files $uri $uri/ =404;
    }}

    location ~ \\.php$ {{
        fastcgi_pass unix:/run/php-fpm/www.sock;
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
    }}
}}
NGINXEOF

# Remove default server block
rm -f /etc/nginx/conf.d/default.conf

# ── Create Application ────────────────────────────────────
mkdir -p /var/www/lemp
chown -R nginx:nginx /var/www/lemp

cat > /var/www/lemp/index.php << 'PHPEOF'
<?php
$db_host = "{rds_host}";
$db_user = "{DB_USER}";
$db_pass = "{DB_PASSWORD}";
$db_name = "{DB_NAME}";

mysqli_report(MYSQLI_REPORT_OFF);
$conn = new mysqli($db_host, $db_user, $db_pass, $db_name);
if ($conn->connect_error) {{
    $status = "DB Error: " . $conn->connect_error;
    $color = "#ef4444";
    $visits = 0;
}} else {{
    $conn->query("CREATE TABLE IF NOT EXISTS page_visits (
        id INT AUTO_INCREMENT PRIMARY KEY,
        page VARCHAR(100) DEFAULT '/',
        ip VARCHAR(50),
        visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )");
    $conn->query("INSERT INTO page_visits (ip) VALUES ('" . $_SERVER["REMOTE_ADDR"] . "')");
    $result = $conn->query("SELECT COUNT(*) as cnt FROM page_visits");
    $visits = $result->fetch_assoc()["cnt"];
    $status = "Connected ✓";
    $color  = "#22c55e";
    $conn->close();
}}

$hostname = gethostname();
$nginx_v  = shell_exec("nginx -v 2>&1");
$php_v    = phpversion();
?>
<!DOCTYPE html>
<html>
<head>
  <title>Project 14 – LEMP Stack</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:Arial,sans-serif;background:#0a1628;color:#cdd6f4;
         display:flex;align-items:center;justify-content:center;min-height:100vh}}
    .card{{background:#1e2a3a;border:1px solid #313244;border-radius:16px;
           padding:48px;max-width:640px;text-align:center}}
    h1{{color:#89b4fa;font-size:2.5rem;margin-bottom:8px}}
    h2{{color:#cdd6f4;font-weight:400;margin-bottom:32px}}
    .stack{{display:flex;justify-content:center;gap:16px;margin-bottom:32px}}
    .s{{background:#11111b;color:#89b4fa;border-radius:8px;
        padding:12px 20px;font-weight:700;font-size:1.1rem;min-width:70px}}
    .info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;text-align:left}}
    .info-item{{background:#11111b;border-radius:8px;padding:16px}}
    .info-label{{color:#6c7086;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}}
    .info-value{{color:#cdd6f4;font-weight:600;margin-top:4px;font-size:.95rem}}
    .db-status{{font-weight:bold;margin-bottom:24px;font-size:1.1rem}}
    .nginx-badge{{background:#1e3a5f;color:#89b4fa;border-radius:999px;
                  padding:4px 14px;font-size:.85rem;display:inline-block;margin-top:16px}}
  </style>
</head>
<body>
  <div class="card">
    <h1>🌊 Project 14</h1>
    <h2>LEMP Application Hosting</h2>
    <div class="stack">
      <div class="s">L<br><small>Linux</small></div>
      <div class="s">E<br><small>Nginx</small></div>
      <div class="s">M<br><small>MySQL</small></div>
      <div class="s">P<br><small>PHP</small></div>
    </div>
    <p class="db-status" style="color:<?php echo $color; ?>">
      Database: <?php echo $status; ?>
    </p>
    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">Server</div>
        <div class="info-value"><?php echo $hostname; ?></div>
      </div>
      <div class="info-item">
        <div class="info-label">Total Visits</div>
        <div class="info-value"><?php echo $visits; ?></div>
      </div>
      <div class="info-item">
        <div class="info-label">PHP Version</div>
        <div class="info-value"><?php echo $php_v; ?></div>
      </div>
      <div class="info-item">
        <div class="info-label">DB Host</div>
        <div class="info-value" style="font-size:.75rem"><?php echo $db_host; ?></div>
      </div>
    </div>
    <div class="nginx-badge">Powered by Nginx + PHP-FPM</div>
  </div>
</body>
</html>
PHPEOF

chown nginx:nginx /var/www/lemp/index.php

# ── Reload Nginx ─────────────────────────────────────────
nginx -t && systemctl reload nginx
"""


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 14 — LEMP Stack (Linux+Nginx+MySQL+PHP)")
    print("="*60)

    ec2 = boto3_client("ec2")
    rds = boto3_client("rds")

    vpc_id, subnet_ids = get_default_vpc_and_subnets()

    # ── Security Groups ───────────────────────────────────────────────────────
    web_sg = create_security_group(
        f"{PROJECT}-web-sg", "LEMP Web SG", vpc_id,
        [{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
         {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
          "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
    )
    db_sg = create_security_group(
        f"{PROJECT}-db-sg", "LEMP DB SG", vpc_id,
        [{"IpProtocol": "tcp", "FromPort": 3306, "ToPort": 3306,
          "UserIdGroupPairs": [{"GroupId": web_sg}]}],
    )

    # ── RDS ───────────────────────────────────────────────────────────────────
    try:
        rds.create_db_subnet_group(
            DBSubnetGroupName=f"{PROJECT}-subnet-grp",
            DBSubnetGroupDescription="LEMP DB subnet",
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

    # ── EC2 with LEMP ─────────────────────────────────────────────────────────
    import base64
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
    ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
    public_ip = ec2.describe_instances(
        InstanceIds=[instance_id])["Reservations"][0]["Instances"][0].get(
        "PublicIpAddress", "N/A")
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
    print(f"  Stack: Linux + Nginx + MySQL(RDS) + PHP-FPM")
    print(f"  (Takes ~3 min for LEMP to initialize)\n")


if __name__ == "__main__":
    deploy()

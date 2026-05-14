"""
PROJECT 5 — Use SDK to Automate Static Web Hosting on S3
Services: Amazon S3, boto3

What this does:
  1. Creates an S3 bucket with a unique name
  2. Disables the Block Public Access settings
  3. Enables static website hosting
  4. Attaches a public-read bucket policy
  5. Uploads a full HTML website (index.html + error.html + CSS)
  6. Prints the public website URL
"""

import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

PROJECT    = "capstone-p05-s3hosting"
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
BUCKET_NAME = f"{PROJECT}-{int(time.time())}"

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Project 5 — S3 Static Hosting</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <nav class="navbar">
    <div class="logo">☁️ AWS Capstone</div>
    <ul>
      <li><a href="#about">About</a></li>
      <li><a href="#features">Features</a></li>
      <li><a href="#stack">Stack</a></li>
    </ul>
  </nav>

  <header class="hero">
    <div class="hero-content">
      <span class="badge">Project 5</span>
      <h1>S3 Static Website<br><span class="gradient-text">Hosting</span></h1>
      <p>Deployed automatically using Python + boto3 SDK.<br>
         No manual console clicks — fully scripted.</p>
      <a href="#features" class="btn">Explore Features</a>
    </div>
    <div class="cloud-animation">
      <div class="cloud c1">☁️</div>
      <div class="cloud c2">☁️</div>
      <div class="cloud c3">⛅</div>
    </div>
  </header>

  <section id="about" class="section">
    <h2>What is this?</h2>
    <p>This static website is hosted on <strong>Amazon S3</strong> and
       was deployed entirely through a Python boto3 script.
       No AWS Console interaction was required.</p>
  </section>

  <section id="features" class="section features-grid">
    <div class="feat-card">
      <div class="feat-icon">🚀</div>
      <h3>One-command Deploy</h3>
      <p>Run <code>python deploy.py</code> to create the bucket, configure hosting, and upload all files.</p>
    </div>
    <div class="feat-card">
      <div class="feat-icon">🌍</div>
      <h3>Global CDN-Ready</h3>
      <p>S3 static hosting supports CloudFront for worldwide low-latency delivery.</p>
    </div>
    <div class="feat-card">
      <div class="feat-icon">💰</div>
      <h3>Cost-Effective</h3>
      <p>Pay only for storage and bandwidth. Free tier covers 5 GB/month.</p>
    </div>
    <div class="feat-card">
      <div class="feat-icon">🔒</div>
      <h3>Secure by Default</h3>
      <p>Fine-grained bucket policies control exactly who can read your content.</p>
    </div>
  </section>

  <section id="stack" class="section">
    <h2>Tech Stack</h2>
    <div class="stack-list">
      <span class="tag">Amazon S3</span>
      <span class="tag">Python 3</span>
      <span class="tag">boto3</span>
      <span class="tag">HTML5 + CSS3</span>
      <span class="tag">Static Hosting</span>
    </div>
  </section>

  <footer>
    <p>🎓 AWS Capstone Project 5 — Deployed with boto3</p>
  </footer>
</body>
</html>
"""

STYLE_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Inter', sans-serif;
  background: #0a0e1a;
  color: #e2e8f0;
  overflow-x: hidden;
}

/* Navbar */
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 60px;
  background: rgba(10,14,26,.9);
  backdrop-filter: blur(10px);
  position: sticky;
  top: 0;
  z-index: 100;
  border-bottom: 1px solid #1e293b;
}
.logo { font-size: 1.4rem; font-weight: 800; color: #38bdf8; }
.navbar ul { list-style: none; display: flex; gap: 32px; }
.navbar a { color: #94a3b8; text-decoration: none; transition: color .2s; }
.navbar a:hover { color: #38bdf8; }

/* Hero */
.hero {
  position: relative;
  min-height: 90vh;
  display: flex;
  align-items: center;
  padding: 0 60px;
  overflow: hidden;
  background: radial-gradient(ellipse at 70% 50%, #0e3055 0%, #0a0e1a 70%);
}
.hero-content { position: relative; z-index: 2; max-width: 600px; }
.badge {
  background: #1e40af;
  color: #93c5fd;
  font-size: .85rem;
  font-weight: 600;
  padding: 4px 14px;
  border-radius: 999px;
  display: inline-block;
  margin-bottom: 20px;
}
h1 { font-size: 3.5rem; font-weight: 800; line-height: 1.1; margin-bottom: 20px; }
.gradient-text {
  background: linear-gradient(135deg, #38bdf8, #818cf8);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.hero p { font-size: 1.15rem; color: #94a3b8; line-height: 1.7; margin-bottom: 32px; }
.btn {
  display: inline-block;
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: #fff;
  padding: 14px 32px;
  border-radius: 12px;
  text-decoration: none;
  font-weight: 600;
  transition: transform .2s, box-shadow .2s;
}
.btn:hover { transform: translateY(-2px); box-shadow: 0 10px 30px rgba(14,165,233,.3); }

/* Cloud animation */
.cloud-animation {
  position: absolute;
  right: 60px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 5rem;
  opacity: .15;
}
.cloud { animation: float 6s ease-in-out infinite; }
.c1 { animation-delay: 0s; }
.c2 { animation-delay: 2s; }
.c3 { animation-delay: 4s; }
@keyframes float {
  0%,100% { transform: translateY(0); }
  50% { transform: translateY(-20px); }
}

/* Section */
.section { padding: 80px 60px; max-width: 1100px; margin: 0 auto; }
.section h2 { font-size: 2rem; font-weight: 700; margin-bottom: 24px; color: #f1f5f9; }

/* Features Grid */
.features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 24px; }
.feat-card {
  background: #111827;
  border: 1px solid #1e293b;
  border-radius: 16px;
  padding: 32px;
  transition: transform .2s, border-color .2s;
}
.feat-card:hover { transform: translateY(-4px); border-color: #38bdf8; }
.feat-icon { font-size: 2rem; margin-bottom: 16px; }
.feat-card h3 { font-size: 1.1rem; margin-bottom: 10px; }
.feat-card p { color: #94a3b8; font-size: .9rem; line-height: 1.6; }
code { background: #1e293b; padding: 2px 6px; border-radius: 4px; font-size: .85rem; }

/* Stack */
.stack-list { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; }
.tag {
  background: #1e293b;
  border: 1px solid #334155;
  color: #93c5fd;
  padding: 6px 16px;
  border-radius: 999px;
  font-size: .9rem;
}

/* Footer */
footer {
  text-align: center;
  padding: 40px;
  color: #475569;
  border-top: 1px solid #1e293b;
}
"""

ERROR_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>404 — Page Not Found</title>
  <style>
    body{font-family:Arial,sans-serif;background:#0a0e1a;color:#e2e8f0;
         display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center}
    h1{font-size:5rem;color:#ef4444}
    p{color:#94a3b8}
    a{color:#38bdf8}
  </style>
</head>
<body>
  <div>
    <h1>404</h1>
    <h2>Page Not Found</h2>
    <p>The page you're looking for doesn't exist.</p>
    <p><a href="/">← Go Home</a></p>
  </div>
</body>
</html>
"""


def deploy():
    print("\n" + "="*60)
    print("  Deploying Project 5 — S3 Static Website Hosting")
    print("="*60)

    s3 = boto3_client("s3")

    # ── Create Bucket ────────────────────────────────────────────────────────
    try:
        if AWS_REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
            )
        ok(f"Bucket created: {BUCKET_NAME}")
    except Exception as e:
        warn(f"Bucket creation: {e}"); return

    # ── Disable Block Public Access ──────────────────────────────────────────
    s3.delete_public_access_block(Bucket=BUCKET_NAME)
    ok("Block public access disabled")

    # ── Enable Static Website Hosting ────────────────────────────────────────
    s3.put_bucket_website(
        Bucket=BUCKET_NAME,
        WebsiteConfiguration={
            "IndexDocument": {"Suffix": "index.html"},
            "ErrorDocument": {"Key": "error.html"},
        },
    )
    ok("Static website hosting enabled")

    # ── Bucket Policy (public read) ──────────────────────────────────────────
    policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{BUCKET_NAME}/*",
        }],
    })
    s3.put_bucket_policy(Bucket=BUCKET_NAME, Policy=policy)
    ok("Public read policy applied")

    # ── Upload Files ─────────────────────────────────────────────────────────
    files = [
        ("index.html", INDEX_HTML, "text/html"),
        ("style.css",  STYLE_CSS,  "text/css"),
        ("error.html", ERROR_HTML, "text/html"),
    ]
    for key, content, content_type in files:
        s3.put_object(
            Bucket=BUCKET_NAME, Key=key,
            Body=content.encode(), ContentType=content_type,
        )
        ok(f"Uploaded: {key}")

    # S3 website endpoint format varies by region:
    # us-east-1 → s3-website-us-east-1.amazonaws.com (dash)
    # all others → s3-website.REGION.amazonaws.com (dot)
    if AWS_REGION == "us-east-1":
        website_url = f"http://{BUCKET_NAME}.s3-website-us-east-1.amazonaws.com"
    else:
        website_url = f"http://{BUCKET_NAME}.s3-website.{AWS_REGION}.amazonaws.com"

    save_state(STATE_FILE, {"bucket": BUCKET_NAME, "url": website_url})

    print("\n" + "="*60)
    print(f"  Deployment Complete!")
    print(f"  URL: {website_url}")
    print("="*60 + "\n")


if __name__ == "__main__":
    deploy()

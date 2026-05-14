from flask import Flask, jsonify
import os, socket

app = Flask(__name__)

@app.route("/")
def home():
    return """<!DOCTYPE html>
<html>
<head>
  <title>Project 8 - Containerized Flask</title>
  <style>
    body{font-family:Arial,sans-serif;background:#1a1a2e;color:#eee;
         display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .card{background:#16213e;border-radius:16px;padding:40px;text-align:center;max-width:500px}
    h1{color:#e94560}
    .badge{background:#0f3460;color:#e94560;border-radius:999px;
           padding:4px 14px;display:inline-block;margin:4px}
  </style>
</head>
<body>
  <div class="card">
    <h1>Project 8</h1>
    <h2>Containerized Flask App</h2>
    <p>Running on ECS Fargate with Docker</p>
    <p>Host: <span class="badge">""" + socket.gethostname() + """</span></p>
  </div>
</body>
</html>"""

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "host": socket.gethostname()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

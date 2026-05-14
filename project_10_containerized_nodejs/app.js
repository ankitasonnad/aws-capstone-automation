const express = require('express');
const os = require('os');
const app = express();
const PORT = process.env.PORT || 3000;

app.get('/', (req, res) => {
  res.send(`<!DOCTYPE html>
<html>
<head>
  <title>Project 10 - Containerized Node.js</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0;
           display: flex; align-items: center; justify-content: center; min-height: 100vh; }
    .card { background: #1e293b; border-radius: 20px; padding: 48px;
            max-width: 540px; text-align: center; box-shadow: 0 25px 50px rgba(0,0,0,.4); }
    h1 { font-size: 2.5rem; color: #f59e0b; margin-bottom: 8px; }
    h2 { color: #94a3b8; font-weight: 400; margin-bottom: 32px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 24px 0; }
    .stat { background: #0f172a; border-radius: 12px; padding: 16px; }
    .stat-label { color: #64748b; font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; }
    .stat-value { color: #f59e0b; font-size: 1.1rem; font-weight: 600; margin-top: 4px; }
    .badge { background: #78350f; color: #fcd34d; border-radius: 999px;
             padding: 6px 18px; display: inline-block; font-size: .9rem; }
  </style>
</head>
<body>
  <div class="card">
    <h1>⚡ Project 10</h1>
    <h2>Containerized Node.js on ECS Fargate</h2>
    <div class="grid">
      <div class="stat">
        <div class="stat-label">Hostname</div>
        <div class="stat-value">${os.hostname().substring(0,12)}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Node.js</div>
        <div class="stat-value">${process.version}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Platform</div>
        <div class="stat-value">${os.platform()}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Uptime</div>
        <div class="stat-value">${Math.floor(process.uptime())}s</div>
      </div>
    </div>
    <span class="badge">ECS Fargate · Docker · ECR</span>
  </div>
</body>
</html>`);
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', host: os.hostname(), uptime: process.uptime() });
});

app.listen(PORT, () => console.log(`Server listening on port ${PORT}`));

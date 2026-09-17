const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const PORT = 3000;
const PUBLIC_DIR = path.join(__dirname, 'frontend');

const MIME_TYPES = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.js': 'text/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon'
};

let backendProcess = null;

// Checks if the FastAPI backend on port 8000 is already active
function checkBackend(callback) {
  let finished = false;
  const finish = (result) => {
    if (!finished) {
      finished = true;
      callback(result);
    }
  };

  const req = http.get('http://127.0.0.1:8000/docs', (res) => {
    finish(res.statusCode < 500);
  });
  req.on('error', () => finish(false));
  req.setTimeout(1500, () => {
    req.destroy();
    finish(false);
  });
}

// Spawns the FastAPI backend automatically if not already running
function startBackend() {
  let backendDir = __dirname;
  if (fs.existsSync(path.join(__dirname, 'backend', 'main.py'))) {
    backendDir = __dirname;
  } else if (fs.existsSync(path.join(__dirname, 'SIH backend', 'maharashtra-skill-intelligence-main', 'backend', 'main.py'))) {
    backendDir = path.join(__dirname, 'SIH backend', 'maharashtra-skill-intelligence-main');
  }

  const userProfile = process.env.USERPROFILE || '';
  const uvCandidate = path.join(userProfile, '.local', 'bin', 'uv.exe');
  const uvCmd = fs.existsSync(uvCandidate) ? uvCandidate : 'uv';

  const args = [
    'run',
    '--with', 'fastapi',
    '--with', 'uvicorn',
    '--with', 'pydantic',
    '--with', 'pandas',
    '--with', 'numpy',
    '--with', 'scikit-learn',
    '--with', 'joblib',
    'python',
    '-m', 'uvicorn',
    'backend.main:app',
    '--host', '127.0.0.1',
    '--port', '8000'
  ];

  console.log('[Backend] Starting FastAPI backend on http://127.0.0.1:8000 ...');
  backendProcess = spawn(uvCmd, args, {
    cwd: backendDir,
    stdio: 'inherit'
  });

  backendProcess.on('error', (err) => {
    console.error('[Backend] Could not launch backend automatically:', err.message);
  });

  backendProcess.on('exit', (code, signal) => {
    if (code !== null && code !== 0) {
      console.log(`[Backend] Process exited with code ${code}`);
    }
    backendProcess = null;
  });
}

function ensureBackend() {
  checkBackend((isRunning) => {
    if (isRunning) {
      console.log('[Backend] FastAPI backend is already active on http://127.0.0.1:8000');
    } else {
      startBackend();
    }
  });
}

function cleanup() {
  if (backendProcess) {
    try {
      backendProcess.kill();
    } catch (_) {}
  }
}

process.on('SIGINT', () => { cleanup(); process.exit(); });
process.on('SIGTERM', () => { cleanup(); process.exit(); });
process.on('exit', cleanup);

const server = http.createServer((req, res) => {
  // Reverse proxy API requests to FastAPI backend
  if (req.url.startsWith('/api/')) {
    const proxyReq = http.request({
      hostname: '127.0.0.1',
      port: 8000,
      path: req.url,
      method: req.method,
      headers: { ...req.headers, host: '127.0.0.1:8000' }
    }, (proxyRes) => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res, { end: true });
    });
    proxyReq.on('error', (err) => {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ detail: 'FastAPI backend unavailable', error: err.message }));
    });
    req.pipe(proxyReq, { end: true });
    return;
  }

  let reqPath = req.url.split('?')[0];
  if (reqPath === '/') reqPath = '/index.html';

  const filePath = path.join(PUBLIC_DIR, reqPath);

  fs.readFile(filePath, (err, content) => {
    if (err) {
      if (err.code === 'ENOENT') {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('404 Not Found');
      } else {
        res.writeHead(500, { 'Content-Type': 'text/plain' });
        res.end(`Server Error: ${err.code}`);
      }
    } else {
      const ext = path.extname(filePath).toLowerCase();
      const contentType = MIME_TYPES[ext] || 'application/octet-stream';
      res.writeHead(200, { 'Content-Type': contentType });
      res.end(content);
    }
  });
});

server.listen(PORT, () => {
  console.log(`Frontend running at http://localhost:${PORT}/`);
  ensureBackend();
});

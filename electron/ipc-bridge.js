// IPC Bridge for Electron ↔ Python communication
// Replaces HTTP-based Flask communication with direct IPC

const { spawn } = require('child_process');
const path = require('path');
const readline = require('readline');

class IPCBridge {
  constructor() {
    this.pythonProcess = null;
    this.requestQueue = new Map();
    this.requestId = 0;
    this.isReady = false;
    this.startPython();
  }

  startPython() {
    const appDir = path.join(__dirname, '..');
    const pythonDir = path.join(appDir, 'app', 'python');
    const appPy = path.join(pythonDir, 'app_ipc.py');
    
    const isWin = process.platform === 'win32';
    const venvPath = isWin 
      ? path.join(appDir, 'venv', 'Scripts', 'python.exe')
      : path.join(appDir, 'venv', 'bin', 'python3');
    
    const fs = require('fs');
    const pythonPath = fs.existsSync(venvPath) ? venvPath : (isWin ? 'python' : 'python3');
    
    console.log('[IPC] Starting Python process:', pythonPath);
    
    const env = {
      ...process.env,
      PYTHONPATH: pythonDir,
      PYTHONUNBUFFERED: '1' // Ensure unbuffered output
    };
    
    this.pythonProcess = spawn(pythonPath, [appPy], {
      cwd: appDir,
      env: env,
      stdio: ['pipe', 'pipe', 'pipe']
    });
    
    // Setup readline for stdout
    const rl = readline.createInterface({
      input: this.pythonProcess.stdout,
      crlfDelay: Infinity
    });
    
    rl.on('line', (line) => {
      // Only try to parse lines that look like JSON (start with { or [)
      const trimmed = line.trim();
      if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      try {
        const response = JSON.parse(line);
        this.handleResponse(response);
      } catch (e) {
          // Only log if it actually looked like JSON but failed to parse
          if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            console.error('[IPC] Failed to parse JSON response:', line.substring(0, 100), e.message);
          }
        }
      } else {
        // Non-JSON line (likely debug output) - log to stderr equivalent
        // Don't spam console, only log if it's not empty
        if (trimmed.length > 0 && !trimmed.match(/^[=\-]+$/)) {
          // Suppress separator lines and empty lines
        }
      }
    });
    
    // Handle stderr
    this.pythonProcess.stderr.on('data', (data) => {
      console.log('[Python]', data.toString());
    });
    
    this.pythonProcess.on('error', (err) => {
      console.error('[IPC] Python process error:', err);
      this.isReady = false;
    });
    
    this.pythonProcess.on('exit', (code) => {
      console.log('[IPC] Python process exited with code:', code);
      this.isReady = false;
      
      // Reject all pending requests
      for (const [id, { reject }] of this.requestQueue.entries()) {
        reject(new Error('Python process exited'));
      }
      this.requestQueue.clear();
      
      // Restart after 2 seconds if it crashed
      if (code !== 0) {
        setTimeout(() => {
          console.log('[IPC] Restarting Python process...');
          this.startPython();
        }, 2000);
      }
    });
    
    // Handle stdin errors
    this.pythonProcess.stdin.on('error', (err) => {
      console.error('[IPC] stdin error:', err);
      this.isReady = false;
    });
    
    // Wait for Python process to signal it's ready
    // Python prints "Ready to receive requests" when initialized
    let readyCheckAttempts = 0;
    const maxReadyChecks = 30; // Wait up to 30 seconds
    
    const checkReady = setInterval(() => {
      readyCheckAttempts++;
      
      // Check if Python process is still running
      if (!this.pythonProcess || this.pythonProcess.killed) {
        clearInterval(checkReady);
        this.isReady = false;
        return;
      }
      
      // Mark as ready after Python has had time to initialize
      // We check stderr for initialization messages
      if (readyCheckAttempts >= 3) { // Give it at least 3 seconds
        this.isReady = true;
        clearInterval(checkReady);
        console.log('[IPC] Python process ready');
      }
      
      if (readyCheckAttempts >= maxReadyChecks) {
        clearInterval(checkReady);
        console.warn('[IPC] Python process ready check timeout');
        // Mark as ready anyway to avoid blocking forever
        this.isReady = true;
      }
    }, 1000);
  }

  handleResponse(response) {
    const { id, data, error } = response;
    
    if (this.requestQueue.has(id)) {
      const { resolve, reject } = this.requestQueue.get(id);
      this.requestQueue.delete(id);
      
      if (error) {
        reject(new Error(error));
      } else {
        resolve(data);
      }
    }
  }

  async sendRequest(method, path, body = null, headers = {}) {
    return new Promise((resolve, reject) => {
      // Wait for Python process to be ready (with timeout)
      const waitForReady = (attempts = 0) => {
        if (this.isReady && this.pythonProcess && !this.pythonProcess.killed) {
          // Process is ready, send request
          this._sendRequestInternal(method, path, body, headers, resolve, reject);
        } else if (attempts < 50) { // Wait up to 50 seconds
          setTimeout(() => waitForReady(attempts + 1), 1000);
        } else {
          reject(new Error('Python process not ready after timeout'));
        }
      };
      
      waitForReady();
    });
  }
  
  _sendRequestInternal(method, path, body, headers, resolve, reject) {
    const id = ++this.requestId;
    
    // Check if process and stdin are still valid
    if (!this.pythonProcess || this.pythonProcess.killed || !this.pythonProcess.stdin || this.pythonProcess.stdin.destroyed) {
      reject(new Error('Python process or stdin stream is not available'));
      return;
    }
    
    // Store promise resolvers
    this.requestQueue.set(id, { resolve, reject });
    
    // Create request object
    const request = {
      id,
      method,
      path,
      body,
      headers
    };
    
    // Send to Python via stdin
    const requestJson = JSON.stringify(request) + '\n';
    
    try {
      const writeResult = this.pythonProcess.stdin.write(requestJson, (err) => {
        if (err) {
          this.requestQueue.delete(id);
          reject(new Error(`Failed to write to Python process: ${err.message}`));
        }
      });
      
      // If write returns false, the stream is full - wait for drain
      if (writeResult === false) {
        this.pythonProcess.stdin.once('drain', () => {
          // Stream drained, request already sent
        });
      }
    } catch (err) {
      this.requestQueue.delete(id);
      reject(new Error(`Error writing to Python process: ${err.message}`));
      
      // If stream is destroyed, restart the process
      if (err.code === 'ERR_STREAM_DESTROYED' || err.message.includes('destroyed')) {
        console.error('[IPC] Stream destroyed, restarting Python process...');
        this.isReady = false;
        setTimeout(() => {
          this.startPython();
        }, 2000);
      }
    }
    
    // Timeout after 30 seconds
    setTimeout(() => {
      if (this.requestQueue.has(id)) {
        this.requestQueue.delete(id);
        reject(new Error('Request timeout'));
      }
    }, 30000);
  }

  stop() {
    if (this.pythonProcess) {
      this.pythonProcess.kill();
      this.pythonProcess = null;
    }
    this.isReady = false;
    this.requestQueue.clear();
  }
}

module.exports = IPCBridge;


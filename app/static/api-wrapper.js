/**
 * API Wrapper - Replaces fetch() calls with IPC communication
 * This allows the app to work without HTTP server (native feel)
 */

(function() {
  'use strict';
  
  const isElectron = window.electronAPI && window.electronAPI.isElectron;
  
  // Store original fetch for fallback
  const originalFetch = window.fetch;
  
  // API wrapper function
  async function apiFetch(url, options = {}) {
    // If not in Electron, use original fetch
    if (!isElectron) {
      return originalFetch(url, options);
    }
    
    // Extract method, path, body, headers from fetch options
    const method = options.method || 'GET';
    const path = url.startsWith('/') ? url : new URL(url).pathname;
    const body = options.body ? JSON.parse(options.body) : null;
    const headers = {};
    
    if (options.headers) {
      Object.keys(options.headers).forEach(key => {
        headers[key] = options.headers[key];
      });
    }
    
    // Call IPC bridge
    try {
      const response = await window.electronAPI.apiRequest(method, path, body, headers);
      
      // Convert to fetch-like Response object
      return {
        ok: response.status >= 200 && response.status < 300,
        status: response.status,
        statusText: response.status >= 200 && response.status < 300 ? 'OK' : 'Error',
        headers: new Headers(response.headers || {}),
        json: async () => response.data,
        text: async () => typeof response.data === 'string' ? response.data : JSON.stringify(response.data),
        blob: async () => new Blob([JSON.stringify(response.data)]),
        arrayBuffer: async () => new ArrayBuffer(0),
        clone: function() { return this; }
      };
    } catch (error) {
      // Return error response
      return {
        ok: false,
        status: 500,
        statusText: 'Internal Error',
        headers: new Headers(),
        json: async () => ({ error: error.message }),
        text: async () => error.message,
        blob: async () => new Blob([error.message]),
        arrayBuffer: async () => new ArrayBuffer(0),
        clone: function() { return this; }
      };
    }
  }
  
  // Replace fetch for API calls only
  window.fetch = function(url, options) {
    // Only intercept /api/ calls
    if (typeof url === 'string' && url.includes('/api/')) {
      return apiFetch(url, options);
    }
    
    // For non-API calls, use original fetch
    return originalFetch(url, options);
  };
  
  // Expose API helper
  window.api = {
    get: (path, headers) => apiFetch(path, { method: 'GET', headers }),
    post: (path, body, headers) => apiFetch(path, { 
      method: 'POST', 
      body: JSON.stringify(body),
      headers: { 'Content-Type': 'application/json', ...headers }
    }),
    put: (path, body, headers) => apiFetch(path, { 
      method: 'PUT', 
      body: JSON.stringify(body),
      headers: { 'Content-Type': 'application/json', ...headers }
    }),
    delete: (path, headers) => apiFetch(path, { method: 'DELETE', headers })
  };
  
  console.log('✅ API Wrapper loaded - IPC mode:', isElectron);
})();


/**
 * Sentinel — API Client
 * Communicates with the FastAPI backend (Person 3).
 */

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
export const WS_BASE = API_BASE.replace(/^http/, 'ws');

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText || `HTTP ${res.status}` }));
    let msg = `HTTP ${res.status}`;
    if (typeof err.error === 'string') {
      msg = err.error;
    } else if (typeof err.detail === 'string') {
      msg = err.detail;
    } else if (err.error?.message && typeof err.error.message === 'string') {
      msg = err.error.message;
    } else if (err.detail?.message && typeof err.detail.message === 'string') {
      msg = err.detail.message;
    } else if (Array.isArray(err.detail)) {
      msg = err.detail.map((d) => d.msg || d.message || JSON.stringify(d)).join('; ');
    } else if (err.message && typeof err.message === 'string') {
      msg = err.message;
    }
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  /** GET /health */
  health() {
    return request('GET', '/health');
  },

  /** POST /impact/explain */
  explainImpact(payload) {
    return request('POST', '/impact/explain', payload);
  },

  /** POST /impact/verify */
  verifyCitations(payload) {
    return request('POST', '/impact/verify', payload);
  },

  /** POST /ask */
  ask(payload) {
    return request('POST', '/ask', payload);
  },

  /** POST /fix/propose */
  proposeFix(payload) {
    return request('POST', '/fix/propose', payload);
  },

  /** POST /validate */
  validate(payload) {
    return request('POST', '/validate', payload);
  },

  /** POST /projects/connect */
  connectProject(payload) {
    return request('POST', '/projects/connect', payload);
  },

  /** GET /projects/files */
  listFiles(dirPath = '') {
    const q = dirPath ? `?dir_path=${encodeURIComponent(dirPath)}` : '';
    return request('GET', `/projects/files${q}`);
  },

  /** GET /projects/file/content */
  readFile(filePath) {
    return request('GET', `/projects/file/content?path=${encodeURIComponent(filePath)}`);
  },

  /** Local code-intelligence routes; `/projects` remains compatible with the IDE. */
  projectImpact(payload) {
    return request('POST', '/projects/impact', payload);
  },

  searchProject(query, limit = 8) {
    return request('GET', `/projects/search?query=${encodeURIComponent(query)}&limit=${limit}`);
  },
};

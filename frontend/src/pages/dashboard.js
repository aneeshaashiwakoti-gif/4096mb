/** Sentinel control room — local connection and live index health. */
import { api } from '../api.js';
import { showToast } from '../components/index.js';

export function renderDashboard() {
  return `
    <div class="page-header">
      <p class="eyebrow">CODEBASE INTELLIGENCE</p>
      <h1 class="page-title">Sentinel control room</h1>
      <p class="page-subtitle">Codebase ingestion &amp; chunking for semantic search and drift-aware auditing.</p>
    </div>
    <div class="control-grid">
      <section class="card card-lg connection-card">
        <div class="card-header"><span class="card-heading">API connection</span><span class="badge badge-success" id="connection-state">CHECKING</span></div>
        <p class="text-secondary">Connect a real local repository. Scanning, parsing, and indexing remain on this machine.</p>
        <div class="connection-row"><input id="project-root" class="input" value="N:\\HackbattleVIT\\sentinel_demo_project" aria-label="Local project path"/><button id="btn-connect-project" class="btn btn-primary">Connect</button></div>
        <div class="offline-strip"><span><strong>Local project mode</strong><small>Only bounded, redacted retrieved evidence reaches an LLM.</small></span><span class="live-switch"></span></div>
      </section>
      <section class="card card-lg health-card">
        <div class="card-header"><span class="card-heading">Health monitor</span><button id="btn-refresh-health" class="btn btn-secondary btn-sm">↻ Refresh</button></div>
        <div class="health-grid" id="dashboard-metrics"><div class="loading-overlay"><span class="loading-spinner"></span></div></div>
      </section>
    </div>
    <section class="card card-lg pipeline-card">
      <div class="card-header"><span class="card-heading">Ingestion &amp; chunking pipeline</span><span class="pipeline-state">⌁ <span id="pipeline-state">READY</span></span></div>
      <div class="pipeline-metrics" id="pipeline-metrics"><div class="loading-overlay"><span class="loading-spinner"></span></div></div>
      <div id="language-breakdown" class="language-breakdown"></div>
    </section>`;
}

export async function initDashboard() {
  const connect = async () => {
    const path = document.getElementById('project-root')?.value.trim();
    if (!path) return showToast('Enter a local project path', 'error');
    try { await api.connectProject({ path }); showToast('Project connected and indexed', 'success'); await loadDashboard(); }
    catch (error) { showToast(error.message, 'error'); }
  };
  document.getElementById('btn-connect-project')?.addEventListener('click', connect);
  document.getElementById('btn-refresh-health')?.addEventListener('click', loadDashboard);
  await loadDashboard();
}

async function loadDashboard() {
  const state = document.getElementById('connection-state');
  try {
    const [health, status] = await Promise.all([api.health(), api.indexStatus().catch(() => null)]);
    if (state) state.textContent = health.status === 'ok' ? 'ONLINE' : 'DEGRADED';
    document.getElementById('dashboard-metrics').innerHTML = `
      <div class="health-metric"><span>RETRIEVAL</span><strong>${status?.project ? 'ready' : 'standby'}</strong></div>
      <div class="health-metric"><span>CHUNKS</span><strong>${status?.chunk_count ?? '—'}</strong></div>
      <div class="health-metric"><span>EMBEDDINGS</span><strong>${status?.embedding_status || 'local'}</strong></div>
      <div class="health-metric"><span>LLM PROVIDER</span><strong>${health.llm_provider || 'offline'}</strong></div>`;
    document.getElementById('pipeline-metrics').innerHTML = `
      <div><span>FILES PARSED</span><strong>${status?.file_count ?? '—'}</strong></div><div><span>CHUNKS INDEXED</span><strong>${status?.chunk_count ?? '—'}</strong></div><div><span>AST PARSED</span><strong>${status?.tree_sitter_files ?? '—'}</strong></div><div><span>INDEX STATE</span><strong>${status?.status || 'idle'}</strong></div>`;
    const counts = status?.language_counts || {};
    document.getElementById('language-breakdown').innerHTML = Object.entries(counts).slice(0, 5).map(([language, count]) => `<div><span>${language}</span><i><b style="width:${Math.min(100, count * 12)}%"></b></i><em>${count} files</em></div>`).join('') || '<p class="text-secondary">Connect a project to display indexed language coverage.</p>';
  } catch (error) {
    if (state) state.textContent = 'OFFLINE';
    const metrics = document.getElementById('dashboard-metrics');
    if (metrics) metrics.innerHTML = '<div class="text-secondary">Backend unavailable. Start Sentinel at http://127.0.0.1:8000.</div>';
  }
}

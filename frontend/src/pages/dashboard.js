/**
 * Sentinel — Dashboard Page
 */

import { api } from '../api.js';
import { icons } from '../icons.js';
import { renderMetricCard, showToast } from '../components/index.js';

export function renderDashboard() {
  return `
    <div class="page-header">
      <h1 class="page-title">Dashboard</h1>
      <p class="page-subtitle">Sentinel — Codebase Intelligence overview</p>
    </div>

    <div class="grid-4" id="dashboard-metrics">
      <div class="card">
        <div class="loading-overlay" style="padding: var(--space-6);">
          <span class="loading-spinner"></span>
        </div>
      </div>
      <div class="card">
        <div class="loading-overlay" style="padding: var(--space-6);">
          <span class="loading-spinner"></span>
        </div>
      </div>
      <div class="card">
        <div class="loading-overlay" style="padding: var(--space-6);">
          <span class="loading-spinner"></span>
        </div>
      </div>
      <div class="card">
        <div class="loading-overlay" style="padding: var(--space-6);">
          <span class="loading-spinner"></span>
        </div>
      </div>
    </div>

    <div style="margin-top: var(--space-8);">
      <div class="grid-2">
        <div class="card card-lg">
          <div class="card-header">
            <div class="card-header-left">
              <div class="card-icon">${icons.impact}</div>
              <span class="card-heading">Quick Actions</span>
            </div>
          </div>
          <div class="stack" style="gap: var(--space-3);">
            <a href="#/impact" class="quick-action-item">
              <div class="card-icon">${icons.impact}</div>
              <div>
                <div style="font-weight: 500; font-size: var(--text-body-sm);">Analyze Impact</div>
                <div class="text-secondary">Explain change impact with risk scoring</div>
              </div>
              <span class="chain-arrow" style="margin-left:auto;">${icons.arrowRight}</span>
            </a>
            <a href="#/ask" class="quick-action-item">
              <div class="card-icon">${icons.ask}</div>
              <div>
                <div style="font-weight: 500; font-size: var(--text-body-sm);">Ask Sentinel</div>
                <div class="text-secondary">Query your codebase with AI grounding</div>
              </div>
              <span class="chain-arrow" style="margin-left:auto;">${icons.arrowRight}</span>
            </a>
            <a href="#/fix" class="quick-action-item">
              <div class="card-icon">${icons.fix}</div>
              <div>
                <div style="font-weight: 500; font-size: var(--text-body-sm);">Propose Fix</div>
                <div class="text-secondary">Generate evidence-grounded code fixes</div>
              </div>
              <span class="chain-arrow" style="margin-left:auto;">${icons.arrowRight}</span>
            </a>
          </div>
        </div>

        <div class="card card-lg">
          <div class="card-header">
            <div class="card-header-left">
              <div class="card-icon success">${icons.checkCircle}</div>
              <span class="card-heading">System Information</span>
            </div>
          </div>
          <div id="system-info" class="stack" style="gap: var(--space-4);">
            <div class="loading-overlay" style="padding: var(--space-6);">
              <span class="loading-spinner"></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <style>
      .quick-action-item {
        display: flex;
        align-items: center;
        gap: var(--space-4);
        padding: var(--space-4);
        border-radius: var(--radius-lg);
        border: 1px solid var(--color-border);
        transition: border-color var(--transition-fast), background var(--transition-fast);
        cursor: pointer;
      }
      .quick-action-item:hover {
        border-color: var(--color-accent);
        background: var(--color-accent-light);
      }
    </style>
  `;
}

export async function initDashboard() {
  try {
    const health = await api.health();

    const metricsGrid = document.getElementById('dashboard-metrics');
    if (metricsGrid) {
      metricsGrid.innerHTML = `
        ${renderMetricCard('Status', health.status === 'ok' ? '● Online' : '○ Offline', 'Backend health', icons.checkCircle, health.status === 'ok' ? 'success' : 'error')}
        ${renderMetricCard('Version', `v${health.version}`, 'Engine version', icons.info, '')}
        ${renderMetricCard('Mode', health.demo_mode ? 'Demo' : 'Production', health.demo_mode ? 'Deterministic mock responses' : 'Live LLM', icons.sparkle, '')}
        ${renderMetricCard('Model', health.model, `Provider: ${health.llm_provider}`, icons.sentinel, '')}
      `;
    }

    const systemInfo = document.getElementById('system-info');
    if (systemInfo) {
      systemInfo.innerHTML = `
        <div class="info-row">
          <span class="text-secondary">API Endpoints</span>
          <span style="font-weight: 500;">6 active</span>
        </div>
        <div class="info-row">
          <span class="text-secondary">LLM Provider</span>
          <span class="tag">${health.llm_provider}</span>
        </div>
        <div class="info-row">
          <span class="text-secondary">Active Model</span>
          <span class="tag">${health.model}</span>
        </div>
        <div class="info-row">
          <span class="text-secondary">Demo Mode</span>
          <span class="badge ${health.demo_mode ? 'badge-accent' : 'badge-success'}">${health.demo_mode ? 'Enabled' : 'Disabled'}</span>
        </div>
        <div class="info-row">
          <span class="text-secondary">CORS Origins</span>
          <span style="font-size: var(--text-small); color: var(--color-text-muted);">localhost:3000, 5173</span>
        </div>

        <style>
          .info-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: var(--space-2) 0;
          }
          .info-row + .info-row {
            border-top: 1px solid var(--color-border);
            padding-top: var(--space-3);
          }
        </style>
      `;
    }

    showToast('Backend connected successfully', 'success');
  } catch (err) {
    const metricsGrid = document.getElementById('dashboard-metrics');
    if (metricsGrid) {
      metricsGrid.innerHTML = `
        <div class="card" style="grid-column: 1 / -1;">
          <div class="empty-state" style="padding: var(--space-8);">
            ${icons.alertTriangle}
            <h3>Backend Unavailable</h3>
            <p>Could not connect to the Sentinel backend at port 8000. Start the server with: <code>python -m uvicorn app.main:app --reload</code></p>
          </div>
        </div>
      `;
    }
    showToast('Backend connection failed', 'error');
  }
}

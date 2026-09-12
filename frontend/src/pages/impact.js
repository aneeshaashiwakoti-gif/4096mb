/**
 * Sentinel — Impact Analysis Page
 */

import { api } from '../api.js';
import { icons } from '../icons.js';
import { demoImpactPayload } from '../demo.js';
import {
  renderRiskBadge,
  renderConfidenceBadge,
  renderCodeViewer,
  renderClaim,
  renderImpactChain,
  renderFactorList,
  renderLoading,
  renderEmptyState,
  showToast,
  escapeHtml,
} from '../components/index.js';

export function renderImpactPage() {
  return `
    <div class="page-header">
      <div class="row" style="justify-content: space-between;">
        <div>
          <h1 class="page-title">Impact Analysis</h1>
          <p class="page-subtitle">Explain code change impact with deterministic risk scoring</p>
        </div>
        <div class="row">
          <button class="btn btn-secondary" id="btn-load-demo-impact">${icons.sparkle} Load Demo</button>
          <button class="btn btn-primary" id="btn-run-impact">${icons.impact} Analyze Impact</button>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card card-lg">
        <div class="card-header">
          <span class="card-heading">Input — Change Context</span>
          <span class="ai-indicator">${icons.sparkle} AI-Grounded</span>
        </div>
        <div class="input-group" style="margin-bottom: var(--space-4);">
          <label class="input-label">Payload (JSON)</label>
          <textarea class="input" id="impact-input" rows="18" placeholder='Paste the ImpactAnalysisInput JSON...' style="font-family: var(--font-code); font-size: var(--text-code); min-height: 360px;"></textarea>
        </div>
      </div>

      <div class="card card-lg" id="impact-result">
        ${renderEmptyState('No analysis yet', 'Load the demo payload or paste your own, then click Analyze Impact.')}
      </div>
    </div>
  `;
}

export function initImpactPage() {
  const input = document.getElementById('impact-input');
  const resultContainer = document.getElementById('impact-result');
  const btnDemo = document.getElementById('btn-load-demo-impact');
  const btnRun = document.getElementById('btn-run-impact');

  btnDemo?.addEventListener('click', () => {
    input.value = JSON.stringify(demoImpactPayload, null, 2);
    showToast('Demo payload loaded', 'success');
  });

  btnRun?.addEventListener('click', async () => {
    let payload;
    try {
      payload = JSON.parse(input.value);
    } catch {
      showToast('Invalid JSON payload', 'error');
      return;
    }

    resultContainer.innerHTML = renderLoading('Analyzing impact...');
    btnRun.disabled = true;

    try {
      const result = await api.explainImpact(payload);
      resultContainer.innerHTML = renderImpactResult(result);
      showToast('Impact analysis complete', 'success');
    } catch (err) {
      resultContainer.innerHTML = renderEmptyState('Analysis Failed', err.message);
      showToast(err.message, 'error');
    } finally {
      btnRun.disabled = false;
    }
  });
}

function renderImpactResult(r) {
  return `
    <div class="card-header">
      <span class="card-heading">Analysis Result</span>
      <div class="row" style="gap: var(--space-3);">
        ${renderRiskBadge(r.risk?.level)}
        ${renderConfidenceBadge(r.confidence)}
      </div>
    </div>

    <!-- Summary -->
    <div style="margin-bottom: var(--space-6);">
      <p class="text-body" style="line-height: var(--leading-relaxed);">${escapeHtml(r.summary)}</p>
    </div>

    <!-- Impact Type -->
    <div style="margin-bottom: var(--space-5);">
      <span class="badge badge-accent">${escapeHtml(r.impact_type)}</span>
    </div>

    <!-- Risk Factors -->
    ${r.risk?.factors?.length ? `
      <div style="margin-bottom: var(--space-6);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Risk Factors</h3>
        ${renderFactorList(r.risk.factors)}
      </div>
    ` : ''}

    <!-- Root Cause -->
    ${r.root_cause ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Root Cause</h3>
        <div class="row" style="margin-bottom: var(--space-2); gap: var(--space-2);">
          <span class="tag">${escapeHtml(r.root_cause.file)}:${r.root_cause.line}</span>
          ${r.root_cause.symbol ? `<span class="tag">${escapeHtml(r.root_cause.symbol)}</span>` : ''}
        </div>
        <p class="text-body" style="font-size: var(--text-body-sm);">${escapeHtml(r.root_cause.reason)}</p>
      </div>
    ` : ''}

    <!-- Impact Chain -->
    ${r.impact_chain?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Impact Chain</h3>
        ${renderImpactChain(r.impact_chain)}
      </div>
    ` : ''}

    <!-- Direct Impacts -->
    ${r.direct_impacts?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Direct Impacts</h3>
        <div class="stack" style="gap: var(--space-3);">
          ${r.direct_impacts.map(di => `
            <div class="claim-item">
              <span class="claim-icon" style="color: var(--color-error);">${icons.alertTriangle}</span>
              <div class="claim-body">
                <div class="row" style="gap: var(--space-2); margin-bottom: var(--space-1);">
                  <span class="tag">${escapeHtml(di.file)}</span>
                  ${di.symbol ? `<span class="tag">${escapeHtml(di.symbol)}</span>` : ''}
                  ${di.line_range ? `<span class="text-muted">Lines ${di.line_range}</span>` : ''}
                </div>
                <p class="claim-statement">${escapeHtml(di.reason)}</p>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    ` : ''}

    <!-- Indirect Impacts -->
    ${r.indirect_impacts?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Indirect Impacts</h3>
        <div class="stack" style="gap: var(--space-3);">
          ${r.indirect_impacts.map(ii => `
            <div class="claim-item">
              <span class="claim-icon" style="color: var(--color-warning);">${icons.link}</span>
              <div class="claim-body">
                <div class="row" style="gap: var(--space-2); margin-bottom: var(--space-1);">
                  <span class="tag">${escapeHtml(ii.file)}</span>
                  ${ii.symbol ? `<span class="tag">${escapeHtml(ii.symbol)}</span>` : ''}
                </div>
                <p class="claim-statement">${escapeHtml(ii.reason)}</p>
                ${ii.path?.length ? `<div class="impact-chain" style="margin-top: var(--space-2);">${ii.path.map((p, i) => `${i > 0 ? `<span class="chain-arrow">${icons.arrowRight}</span>` : ''}<span class="chain-node" style="font-size: 11px; padding: 3px 8px;">${escapeHtml(p)}</span>`).join('')}</div>` : ''}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    ` : ''}

    <!-- Claims -->
    ${r.claims?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Verified Claims</h3>
        <div class="stack" style="gap: var(--space-3);">
          ${r.claims.map(c => renderClaim(c)).join('')}
        </div>
      </div>
    ` : ''}

    <!-- Recommended Actions -->
    ${r.recommended_actions?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Recommended Actions</h3>
        ${renderFactorList(r.recommended_actions)}
      </div>
    ` : ''}

    <!-- Uncertainties -->
    ${r.uncertainties?.length ? `
      <div class="card-divider"></div>
      <div>
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Uncertainties</h3>
        ${renderFactorList(r.uncertainties)}
      </div>
    ` : ''}
  `;
}

/**
 * Sentinel — Validation & Re-analysis Page
 */

import { api } from '../api.js';
import { icons } from '../icons.js';
import { demoValidatePayload } from '../demo.js';
import {
  renderConfidenceBadge,
  renderLoading,
  renderEmptyState,
  showToast,
  escapeHtml,
} from '../components/index.js';

export function renderValidationPage() {
  return `
    <div class="page-header">
      <div class="row" style="justify-content: space-between;">
        <div>
          <h1 class="page-title">Validation & Re-analysis</h1>
          <p class="page-subtitle">Verify regression resolution and ensure no new risks are introduced</p>
        </div>
        <div class="row">
          <button class="btn btn-secondary" id="btn-load-demo-val">${icons.sparkle} Load Demo</button>
          <button class="btn btn-primary" id="btn-run-val">${icons.validate} Validate Fix</button>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card card-lg">
        <div class="card-header">
          <span class="card-heading">Post-Fix Evidence & Context</span>
          <span class="ai-indicator">${icons.checkCircle} Re-analysis</span>
        </div>

        <div class="stack" style="gap: var(--space-4);">
          <div class="input-group">
            <label class="input-label" for="val-original">Original Impact Analysis (JSON)</label>
            <textarea
              class="input"
              id="val-original"
              rows="8"
              placeholder="Paste original ImpactAnalysisInput JSON..."
              style="font-family: var(--font-code); font-size: var(--text-code); min-height: 160px;"
            ></textarea>
          </div>

          <div class="input-group">
            <label class="input-label" for="val-evidence">New Post-Fix Evidence (JSON)</label>
            <textarea
              class="input"
              id="val-evidence"
              rows="6"
              placeholder="Paste post-fix EvidenceSnippet array JSON..."
              style="font-family: var(--font-code); font-size: var(--text-code); min-height: 120px;"
            ></textarea>
          </div>

          <div class="input-group">
            <label class="input-label" for="val-tests">Test Results (JSON, optional)</label>
            <textarea
              class="input"
              id="val-tests"
              rows="3"
              placeholder='{ "passed": true }'
              style="font-family: var(--font-code); font-size: var(--text-code); min-height: 60px;"
            ></textarea>
          </div>
        </div>
      </div>

      <div class="card card-lg" id="val-result">
        ${renderEmptyState('No Validation Run', 'Load the demo verification payload or submit post-fix evidence to re-analyze.')}
      </div>
    </div>
  `;
}

export function initValidationPage() {
  const originalInput = document.getElementById('val-original');
  const evidenceInput = document.getElementById('val-evidence');
  const testsInput = document.getElementById('val-tests');
  const resultContainer = document.getElementById('val-result');
  const btnDemo = document.getElementById('btn-load-demo-val');
  const btnRun = document.getElementById('btn-run-val');

  btnDemo?.addEventListener('click', () => {
    originalInput.value = JSON.stringify(demoValidatePayload.original_analysis, null, 2);
    evidenceInput.value = JSON.stringify(demoValidatePayload.new_evidence, null, 2);
    testsInput.value = JSON.stringify(demoValidatePayload.test_results, null, 2);
    showToast('Demo validation payload loaded', 'success');
  });

  btnRun?.addEventListener('click', async () => {
    let originalAnalysis, newEvidence, testResults;

    try {
      originalAnalysis = JSON.parse(originalInput.value.trim());
    } catch {
      showToast('Invalid JSON in Original Analysis', 'error');
      return;
    }

    try {
      newEvidence = JSON.parse(evidenceInput.value.trim() || '[]');
    } catch {
      showToast('Invalid JSON in New Evidence', 'error');
      return;
    }

    if (testsInput.value.trim()) {
      try {
        testResults = JSON.parse(testsInput.value.trim());
      } catch {
        showToast('Invalid JSON in Test Results', 'error');
        return;
      }
    }

    const payload = {
      original_analysis: originalAnalysis,
      new_evidence: newEvidence,
      test_results: testResults || undefined,
    };

    resultContainer.innerHTML = renderLoading('Performing post-fix validation & regression check...');
    btnRun.disabled = true;

    try {
      const response = await api.validate(payload);
      resultContainer.innerHTML = renderValidationResult(response);
      showToast('Validation analysis complete', 'success');
    } catch (err) {
      resultContainer.innerHTML = renderEmptyState('Validation Failed', err.message);
      showToast(err.message, 'error');
    } finally {
      btnRun.disabled = false;
    }
  });
}

function renderValidationResult(r) {
  const statusCls =
    r.status === 'VERIFIED'
      ? 'badge-success'
      : r.status === 'PARTIALLY_VERIFIED'
      ? 'badge-warning'
      : 'badge-error';

  return `
    <div class="card-header">
      <div class="row" style="gap: var(--space-3);">
        <span class="card-heading">Validation Outcome</span>
        <span class="badge ${statusCls}">${escapeHtml(r.status)}</span>
      </div>
      <div class="row" style="gap: var(--space-3);">
        ${renderConfidenceBadge(r.confidence)}
      </div>
    </div>

    <!-- Summary -->
    <div style="margin-bottom: var(--space-6);">
      <p class="text-body" style="line-height: var(--leading-relaxed);">${escapeHtml(r.summary)}</p>
    </div>

    <!-- Resolved Issues -->
    ${r.resolved_issues?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3); color: var(--color-success); display: flex; align-items: center; gap: var(--space-2);">
          ${icons.checkCircle} Resolved Issues (${r.resolved_issues.length})
        </h3>
        <div class="stack" style="gap: var(--space-2);">
          ${r.resolved_issues.map(iss => `
            <div class="claim-item">
              <span class="claim-icon verified">${icons.check}</span>
              <div class="claim-body">
                <span class="claim-statement">${escapeHtml(iss)}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    ` : ''}

    <!-- Remaining Issues -->
    ${r.remaining_issues?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3); color: var(--color-warning); display: flex; align-items: center; gap: var(--space-2);">
          ${icons.alertTriangle} Remaining Issues (${r.remaining_issues.length})
        </h3>
        <div class="stack" style="gap: var(--space-2);">
          ${r.remaining_issues.map(iss => `
            <div class="claim-item">
              <span class="claim-icon" style="color: var(--color-warning);">${icons.alertTriangle}</span>
              <div class="claim-body">
                <span class="claim-statement">${escapeHtml(iss)}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    ` : ''}

    <!-- New Risks -->
    ${r.new_risks?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3); color: var(--color-error); display: flex; align-items: center; gap: var(--space-2);">
          ${icons.xCircle} New Risks Detected (${r.new_risks.length})
        </h3>
        <div class="stack" style="gap: var(--space-2);">
          ${r.new_risks.map(risk => `
            <div class="claim-item">
              <span class="claim-icon" style="color: var(--color-error);">${icons.xCircle}</span>
              <div class="claim-body">
                <span class="claim-statement">${escapeHtml(risk)}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    ` : ''}
  `;
}

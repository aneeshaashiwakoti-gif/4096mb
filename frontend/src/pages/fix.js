/**
 * Sentinel — Fix Proposals Page
 */

import { api } from '../api.js';
import { icons } from '../icons.js';
import { demoFixPayload } from '../demo.js';
import {
  renderConfidenceBadge,
  renderDiffViewer,
  renderFactorList,
  renderLoading,
  renderEmptyState,
  showToast,
  escapeHtml,
} from '../components/index.js';

export function renderFixPage() {
  return `
    <div class="page-header">
      <div class="row" style="justify-content: space-between;">
        <div>
          <h1 class="page-title">Fix Proposals</h1>
          <p class="page-subtitle">Non-destructive, citation-backed safe code rewrites</p>
        </div>
        <div class="row">
          <button class="btn btn-secondary" id="btn-load-demo-fix">${icons.sparkle} Load Demo</button>
          <button class="btn btn-primary" id="btn-run-fix">${icons.fix} Propose Fix</button>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card card-lg">
        <div class="card-header">
          <span class="card-heading">Fix Request Parameters</span>
          <span class="ai-indicator">${icons.sparkle} Safe Rewrite</span>
        </div>

        <div class="stack" style="gap: var(--space-4);">
          <div class="input-group">
            <label class="input-label" for="fix-instruction">Fix Instruction</label>
            <textarea
              class="input"
              id="fix-instruction"
              rows="3"
              placeholder="e.g. Update payment.py to use attribute access instead of dictionary subscript for the CartTotal return type."
              style="min-height: 80px;"
            ></textarea>
          </div>

          <div class="grid-2" style="gap: var(--space-4);">
            <div class="input-group">
              <label class="input-label" for="fix-target-file">Target File (optional)</label>
              <input
                type="text"
                class="input"
                id="fix-target-file"
                placeholder="e.g. payment.py"
              />
            </div>
            <div class="input-group">
              <label class="input-label" for="fix-constraints">Constraints (comma-separated)</label>
              <input
                type="text"
                class="input"
                id="fix-constraints"
                placeholder="Preserve existing behavior, Do not modify public API"
              />
            </div>
          </div>

          <div class="input-group">
            <label class="input-label" for="fix-context">Impact Context (JSON)</label>
            <textarea
              class="input"
              id="fix-context"
              rows="12"
              placeholder="ImpactAnalysisInput JSON for the affected codebase..."
              style="font-family: var(--font-code); font-size: var(--text-code); min-height: 220px;"
            ></textarea>
          </div>
        </div>
      </div>

      <div class="card card-lg" id="fix-result">
        ${renderEmptyState('No Fix Proposed', 'Load the demo fix request or specify instructions and click Propose Fix.')}
      </div>
    </div>
  `;
}

export function initFixPage() {
  const instructionInput = document.getElementById('fix-instruction');
  const targetFileInput = document.getElementById('fix-target-file');
  const constraintsInput = document.getElementById('fix-constraints');
  const contextInput = document.getElementById('fix-context');
  const resultContainer = document.getElementById('fix-result');
  const btnDemo = document.getElementById('btn-load-demo-fix');
  const btnRun = document.getElementById('btn-run-fix');

  btnDemo?.addEventListener('click', () => {
    instructionInput.value = demoFixPayload.instruction;
    targetFileInput.value = demoFixPayload.target_file || '';
    constraintsInput.value = (demoFixPayload.constraints || []).join(', ');
    contextInput.value = JSON.stringify(demoFixPayload.impact_analysis, null, 2);
    showToast('Demo fix request loaded', 'success');
  });

  btnRun?.addEventListener('click', async () => {
    const instruction = instructionInput.value.trim();
    if (!instruction) {
      showToast('Please specify a fix instruction', 'error');
      return;
    }

    let impactAnalysis;
    try {
      impactAnalysis = JSON.parse(contextInput.value.trim());
    } catch {
      showToast('Invalid JSON in Impact Analysis context', 'error');
      return;
    }

    const constraints = constraintsInput.value
      ? constraintsInput.value.split(',').map((s) => s.trim()).filter(Boolean)
      : [];

    const payload = {
      instruction,
      constraints,
      impact_analysis: impactAnalysis,
      evidence: impactAnalysis.evidence || [],
      target_file: targetFileInput.value.trim() || undefined,
    };

    resultContainer.innerHTML = renderLoading('Generating safe code rewrite proposal...');
    btnRun.disabled = true;

    try {
      const response = await api.proposeFix(payload);
      resultContainer.innerHTML = renderFixResult(response);
      showToast('Fix proposal generated', 'success');

      // Add copy button listener
      const btnCopy = document.getElementById('btn-copy-diff');
      if (btnCopy && response.diff) {
        btnCopy.addEventListener('click', () => {
          navigator.clipboard.writeText(response.diff);
          showToast('Unified diff copied to clipboard', 'success');
        });
      }
    } catch (err) {
      resultContainer.innerHTML = renderEmptyState('Fix Generation Failed', err.message);
      showToast(err.message, 'error');
    } finally {
      btnRun.disabled = false;
    }
  });
}

function renderFixResult(r) {
  const statusColor =
    r.status === 'PROPOSED' ? 'badge-success' : r.status === 'NEEDS_CLARIFICATION' ? 'badge-warning' : 'badge-error';

  return `
    <div class="card-header">
      <div class="row" style="gap: var(--space-3);">
        <span class="card-heading">Proposal</span>
        <span class="badge ${statusColor}">${escapeHtml(r.status)}</span>
      </div>
      <div class="row" style="gap: var(--space-3);">
        ${renderConfidenceBadge(r.confidence)}
        ${r.diff ? `<button class="btn btn-secondary btn-sm" id="btn-copy-diff">${icons.check} Copy Diff</button>` : ''}
      </div>
    </div>

    <!-- Summary -->
    <div style="margin-bottom: var(--space-6);">
      <p class="text-body" style="line-height: var(--leading-relaxed);">${escapeHtml(r.summary)}</p>
      ${r.message ? `<div class="claim-item" style="margin-top: var(--space-3);"><span class="claim-icon" style="color: var(--color-warning);">${icons.info}</span><div class="claim-body"><span class="claim-statement">${escapeHtml(r.message)}</span></div></div>` : ''}
    </div>

    <!-- Unified Diff -->
    ${r.diff ? `
      <div style="margin-bottom: var(--space-6);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Unified Diff</h3>
        ${renderDiffViewer(r.changes?.[0]?.file || 'patch.diff', r.diff)}
      </div>
    ` : ''}

    <!-- Changes Breakdown -->
    ${r.changes?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Changes Breakdown (${r.changes.length})</h3>
        <div class="stack" style="gap: var(--space-4);">
          ${r.changes.map(ch => `
            <div class="claim-item" style="flex-direction: column; align-items: stretch; gap: var(--space-2);">
              <div class="row" style="justify-content: space-between;">
                <span class="tag" style="font-weight: 600;">${escapeHtml(ch.file)}: lines ${ch.start_line}–${ch.end_line}</span>
                <span class="text-muted" style="font-size: 12px;">Replacement chunk</span>
              </div>
              <p class="text-body-sm text-secondary">${escapeHtml(ch.reason)}</p>
              ${ch.citations?.length ? `
                <div class="row" style="gap: var(--space-2); margin-top: var(--space-1);">
                  <span class="text-muted" style="font-size: 11px;">Citations:</span>
                  ${ch.citations.map(c => `<span class="tag" style="font-size: 11px;">${escapeHtml(c.file)}:${c.start_line || ''}</span>`).join('')}
                </div>
              ` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    ` : ''}

    <!-- Assumptions -->
    ${r.assumptions?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Assumptions</h3>
        ${renderFactorList(r.assumptions)}
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

    <div class="card-divider"></div>
    <div class="row" style="justify-content: space-between; align-items: center;">
      <span class="text-secondary" style="font-size: var(--text-small);">Ready to verify this fix against the codebase?</span>
      <a href="#/validation" class="btn btn-secondary btn-sm">${icons.validate} Go to Validation</a>
    </div>
  `;
}

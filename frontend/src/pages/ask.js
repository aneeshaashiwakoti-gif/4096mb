/**
 * Sentinel — Ask Assistant Page
 */

import { api } from '../api.js';
import { icons } from '../icons.js';
import { demoAskPayload } from '../demo.js';
import {
  renderConfidenceBadge,
  renderClaim,
  renderFactorList,
  renderDiffViewer,
  renderLoading,
  renderEmptyState,
  showToast,
  escapeHtml,
} from '../components/index.js';

export function renderAskPage() {
  return `
    <div class="page-header ask-page-header">
      <div class="row" style="justify-content: space-between;">
        <div>
          <p class="eyebrow">RETRIEVAL · EVIDENCE · REASONING</p>
          <h1 class="page-title">Semantic code search</h1>
          <p class="page-subtitle">Query the indexed repository in plain language. Every answer is grounded in retrieved chunks with verifiable file and line citations.</p>
        </div>
        <div class="row">
          <button class="btn btn-secondary" id="btn-load-demo-ask">${icons.sparkle} Load Demo</button>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card card-lg">
        <div class="card-header">
          <span class="card-heading">Ask the connected repository</span>
          <span class="ai-indicator">${icons.sparkle} Grounded Q&A</span>
        </div>

        <div class="stack" style="gap: var(--space-4);">
          <div class="input-group">
            <label class="input-label" for="ask-question">QUESTION</label>
            <textarea
              class="input"
              id="ask-question"
              rows="3"
              placeholder="Ask about any function, dependency, or behaviour…"
              style="min-height: 80px;"
            ></textarea>
          </div>

          <div>
            <span class="text-secondary" style="font-size: var(--text-small); display: block; margin-bottom: var(--space-2);">Suggested Queries:</span>
            <div class="row" style="flex-wrap: wrap; gap: var(--space-2);" id="ask-suggestions">
              <button class="tag chip-btn" data-query="Why does payment.py break after the cart.py change?">Why does payment.py break?</button>
              <button class="tag chip-btn" data-query="What dependencies call calculate_total?">Dependencies of calculate_total?</button>
              <button class="tag chip-btn" data-query="What is the safest way to update payment.py?">Safest fix for payment.py?</button>
            </div>
          </div>

          <div class="input-group">
            <label class="input-label" for="ask-context">ADVANCED: IMPACT CONTEXT JSON (OPTIONAL)</label>
            <textarea
              class="input"
              id="ask-context"
              rows="10"
              placeholder="Optional ImpactAnalysisInput JSON for repository context..."
              style="font-family: var(--font-code); font-size: var(--text-code); min-height: 200px;"
            ></textarea>
          </div>

          <div class="input-group">
            <label class="input-label" for="ask-constraints">Constraints (one per line, optional)</label>
            <input
              type="text"
              class="input"
              id="ask-constraints"
              placeholder="e.g. Preserve existing behavior, Do not break public API"
            />
          </div>

          <button class="btn btn-primary" id="btn-run-ask" style="width: 100%;">
            ${icons.send} Ask Sentinel
          </button>
        </div>
      </div>

      <div class="card card-lg" id="ask-result">
        ${renderEmptyState('Ask a question', 'Select a suggested query or load the demo context to inspect grounded reasoning.')}
      </div>
    </div>

    <style>
      .chip-btn {
        background: var(--color-bg);
        border: 1px solid var(--color-border);
        cursor: pointer;
        padding: 4px 10px;
        transition: background var(--transition-fast), border-color var(--transition-fast);
      }
      .chip-btn:hover {
        background: var(--color-accent-light);
        border-color: var(--color-accent);
        color: var(--color-accent);
      }
    </style>
  `;
}

export function initAskPage() {
  const questionInput = document.getElementById('ask-question');
  const contextInput = document.getElementById('ask-context');
  const constraintsInput = document.getElementById('ask-constraints');
  const resultContainer = document.getElementById('ask-result');
  const btnDemo = document.getElementById('btn-load-demo-ask');
  const btnRun = document.getElementById('btn-run-ask');
  const suggestions = document.getElementById('ask-suggestions');

  btnDemo?.addEventListener('click', () => {
    questionInput.value = demoAskPayload.question;
    contextInput.value = JSON.stringify(demoAskPayload.impact_context, null, 2);
    constraintsInput.value = (demoAskPayload.constraints || []).join(', ');
    showToast('Demo query loaded', 'success');
  });

  suggestions?.addEventListener('click', (e) => {
    const btn = e.target.closest('.chip-btn');
    if (!btn) return;
    questionInput.value = btn.dataset.query;
    if (!contextInput.value.trim()) {
      contextInput.value = JSON.stringify(demoAskPayload.impact_context, null, 2);
    }
  });

  btnRun?.addEventListener('click', async () => {
    const question = questionInput.value.trim();
    if (!question) {
      showToast('Please enter a question', 'error');
      return;
    }

    let impactContext = null;
    if (contextInput.value.trim()) {
      try {
        impactContext = JSON.parse(contextInput.value.trim());
      } catch {
        showToast('Invalid JSON in Impact Context', 'error');
        return;
      }
    }

    const constraints = constraintsInput.value
      ? constraintsInput.value.split(',').map((s) => s.trim()).filter(Boolean)
      : [];

    const payload = {
      question,
      project_id: impactContext?.project_id || 'demo-project',
      impact_context: impactContext,
      evidence: impactContext?.evidence || [],
      constraints,
    };

    resultContainer.innerHTML = renderLoading('Consulting codebase intelligence...');
    btnRun.disabled = true;

    try {
      const response = await api.ask(payload);
      resultContainer.innerHTML = renderAskResult(response);
      showToast('Response received', 'success');
    } catch (err) {
      resultContainer.innerHTML = renderEmptyState('Query Failed', err.message);
      showToast(err.message, 'error');
    } finally {
      btnRun.disabled = false;
    }
  });
}

function renderAskResult(res) {
  return `
    <div class="card-header">
      <span class="card-heading">Sentinel Response</span>
      <div class="row" style="gap: var(--space-3);">
        ${renderConfidenceBadge(res.confidence)}
      </div>
    </div>

    <!-- Answer Body -->
    <div style="margin-bottom: var(--space-6);">
      <div class="text-body" style="line-height: var(--leading-relaxed); white-space: pre-wrap;">${escapeHtml(res.answer)}</div>
    </div>

    <!-- Citations -->
    ${res.citations?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Code Citations</h3>
        <div class="stack" style="gap: var(--space-2);">
          ${res.citations.map(c => `
            <div class="claim-item" style="padding: var(--space-2) var(--space-3);">
              <span class="claim-icon verified">${icons.file}</span>
              <div class="claim-body">
                <div class="row" style="gap: var(--space-2); align-items: baseline;">
                  <span class="tag" style="font-weight: 500;">${escapeHtml(c.file)}${c.start_line ? `:${c.start_line}-${c.end_line}` : ''}</span>
                  ${c.symbol ? `<span class="tag">${escapeHtml(c.symbol)}</span>` : ''}
                  ${c.verified ? '<span class="badge badge-success" style="font-size: 11px;">Verified</span>' : ''}
                </div>
                ${c.snippet ? `<div style="font-family: var(--font-code); font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; background: var(--color-bg); padding: 4px 8px; border-radius: var(--radius-sm);">${escapeHtml(c.snippet)}</div>` : ''}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    ` : ''}

    <!-- Claims -->
    ${res.claims?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Grounded Claims</h3>
        <div class="stack" style="gap: var(--space-3);">
          ${res.claims.map(c => renderClaim(c)).join('')}
        </div>
      </div>
    ` : ''}

    <!-- Recommended Actions -->
    ${res.recommended_actions?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Recommended Actions</h3>
        ${renderFactorList(res.recommended_actions)}
      </div>
    ` : ''}

    <!-- Uncertainties -->
    ${res.uncertainties?.length ? `
      <div class="card-divider"></div>
      <div style="margin-bottom: var(--space-5);">
        <h3 class="card-heading" style="margin-bottom: var(--space-3);">Uncertainties & Assumptions</h3>
        ${renderFactorList(res.uncertainties)}
      </div>
    ` : ''}

    <!-- Fix Proposal Attachment -->
    ${res.fix_proposal ? `
      <div class="card-divider"></div>
      <div>
        <div class="card-header" style="margin-bottom: var(--space-3);">
          <h3 class="card-heading">Attached Fix Proposal</h3>
          <span class="badge badge-accent">${escapeHtml(res.fix_proposal.status)}</span>
        </div>
        <p class="text-body-sm" style="margin-bottom: var(--space-3);">${escapeHtml(res.fix_proposal.summary)}</p>
        ${res.fix_proposal.diff ? renderDiffViewer(res.fix_proposal.changes?.[0]?.file || 'patch.diff', res.fix_proposal.diff) : ''}
      </div>
    ` : ''}
  `;
}

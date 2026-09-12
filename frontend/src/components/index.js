/**
 * Sentinel — Reusable UI Components
 */

import { icons } from '../icons.js';

/* ────────────────────────────────────────────
   Risk Badge
   ──────────────────────────────────────────── */

export function renderRiskBadge(level) {
  const cls = (level || 'UNKNOWN').toLowerCase();
  return `<span class="risk-badge risk-${cls}"><span class="risk-dot"></span>${level || 'UNKNOWN'}</span>`;
}

/* ────────────────────────────────────────────
   Confidence Badge
   ──────────────────────────────────────────── */

export function renderConfidenceBadge(level) {
  const cls = (level || 'LOW').toLowerCase();
  return `<span class="confidence-badge confidence-${cls}"><span class="confidence-dot"></span>Confidence: ${level || 'LOW'}</span>`;
}

/* ────────────────────────────────────────────
   Code Viewer
   ──────────────────────────────────────────── */

export function renderCodeViewer(file, startLine, code, highlightedLines = []) {
  const lines = code.split('\n');
  const linesHtml = lines.map((line, i) => {
    const lineNum = startLine + i;
    const isHighlighted = highlightedLines.includes(lineNum);
    return `<div class="code-line${isHighlighted ? ' highlighted' : ''}">
      <span class="code-line-number">${lineNum}</span>
      <span class="code-line-content">${escapeHtml(line)}</span>
    </div>`;
  }).join('');

  return `<div class="code-viewer">
    <div class="code-viewer-header">
      <span class="code-viewer-file">${icons.file} ${escapeHtml(file)}</span>
      <span class="text-muted">Lines ${startLine}–${startLine + lines.length - 1}</span>
    </div>
    <div class="code-viewer-body">${linesHtml}</div>
  </div>`;
}

/* ────────────────────────────────────────────
   Diff Viewer
   ──────────────────────────────────────────── */

export function renderDiffViewer(file, diff) {
  if (!diff) return '';

  const lines = diff.split('\n');
  const linesHtml = lines.map(line => {
    let cls = 'context';
    let marker = ' ';
    if (line.startsWith('+') && !line.startsWith('+++')) {
      cls = 'added';
      marker = '+';
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      cls = 'removed';
      marker = '−';
    } else if (line.startsWith('@@')) {
      cls = 'context';
      marker = '@';
    }
    return `<div class="diff-line ${cls}">
      <span class="diff-line-marker">${marker}</span>
      <span class="diff-line-content">${escapeHtml(line)}</span>
    </div>`;
  }).join('');

  return `<div class="diff-viewer">
    <div class="diff-header">${icons.file} ${escapeHtml(file)}</div>
    <div class="diff-body">${linesHtml}</div>
  </div>`;
}

/* ────────────────────────────────────────────
   Claim Card
   ──────────────────────────────────────────── */

export function renderClaim(claim) {
  const isVerified = claim.verified || (claim.citations && claim.citations.every(c => c.verified));
  const iconClass = isVerified ? 'verified' : 'unverified';
  const icon = isVerified ? icons.checkCircle : icons.info;
  const categoryBadge = `<span class="badge badge-${claim.category === 'FACT' ? 'success' : claim.category === 'ASSUMPTION' ? 'warning' : 'muted'}">${claim.category}</span>`;

  const citationsHtml = (claim.citations || []).map(cit =>
    `<span class="tag">${escapeHtml(cit.file)}${cit.start_line ? `:${cit.start_line}` : ''}${cit.verified ? ' ✓' : ''}</span>`
  ).join(' ');

  return `<div class="claim-item">
    <span class="claim-icon ${iconClass}">${icon}</span>
    <div class="claim-body">
      <div class="claim-statement">${escapeHtml(claim.statement)}</div>
      <div class="claim-meta">${categoryBadge} ${citationsHtml}</div>
    </div>
  </div>`;
}

/* ────────────────────────────────────────────
   Impact Chain
   ──────────────────────────────────────────── */

export function renderImpactChain(chain) {
  if (!chain || chain.length === 0) return '';

  const nodes = chain.map((node, i) =>
    `${i > 0 ? `<span class="chain-arrow">${icons.arrowRight}</span>` : ''}<span class="chain-node">${escapeHtml(node)}</span>`
  ).join('');

  return `<div class="impact-chain">${nodes}</div>`;
}

/* ────────────────────────────────────────────
   Metric Card
   ──────────────────────────────────────────── */

export function renderMetricCard(label, value, sub, iconHtml = '', colorClass = '') {
  return `<div class="card">
    <div class="card-header-left">
      ${iconHtml ? `<div class="card-icon ${colorClass}">${iconHtml}</div>` : ''}
      <span class="card-heading">${escapeHtml(label)}</span>
    </div>
    <div class="metric-card">
      <div class="metric-value">${value}</div>
      ${sub ? `<div class="metric-sub">${escapeHtml(sub)}</div>` : ''}
    </div>
  </div>`;
}

/* ────────────────────────────────────────────
   Factor List
   ──────────────────────────────────────────── */

export function renderFactorList(items) {
  if (!items || items.length === 0) return '<p class="text-muted">None</p>';
  return items.map(item =>
    `<div class="factor-item"><span class="factor-bullet"></span><span>${escapeHtml(item)}</span></div>`
  ).join('');
}

/* ────────────────────────────────────────────
   Empty State
   ──────────────────────────────────────────── */

export function renderEmptyState(title, description, iconHtml = icons.info) {
  return `<div class="empty-state">
    ${iconHtml}
    <h3>${escapeHtml(title)}</h3>
    <p>${escapeHtml(description)}</p>
  </div>`;
}

/* ────────────────────────────────────────────
   Loading
   ──────────────────────────────────────────── */

export function renderLoading(message = 'Analyzing...') {
  return `<div class="loading-overlay">
    <span class="loading-spinner"></span>
    <span>${escapeHtml(message)}</span>
  </div>`;
}

/* ────────────────────────────────────────────
   Toast
   ──────────────────────────────────────────── */

let toastContainer = null;

export function showToast(message, type = 'success') {
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 200ms ease';
    setTimeout(() => toast.remove(), 200);
  }, 3500);
}

/* ────────────────────────────────────────────
   Helpers
   ──────────────────────────────────────────── */

export function escapeHtml(str) {
  if (typeof str !== 'string') return String(str ?? '');
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;' };
  return str.replace(/[&<>"']/g, c => map[c]);
}

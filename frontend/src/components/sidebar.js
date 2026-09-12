/**
 * Sentinel — Sidebar Component
 */

import { icons } from '../icons.js';

export const navItems = [
  { id: 'dashboard', path: '#/dashboard', label: 'Dashboard', icon: icons.dashboard },
  { id: 'impact', path: '#/impact', label: 'Impact Analysis', icon: icons.impact },
  { id: 'ask', path: '#/ask', label: 'Ask Sentinel', icon: icons.ask },
  { id: 'fix', path: '#/fix', label: 'Fix Proposals', icon: icons.fix },
  { id: 'validation', path: '#/validation', label: 'Validation', icon: icons.validate },
];

export function renderSidebar(currentPath = '#/dashboard') {
  const normPath = currentPath === '#/' || currentPath === '' ? '#/dashboard' : currentPath;

  const navLinks = navItems
    .map((item) => {
      const isActive = normPath.startsWith(item.path);
      return `
        <a href="${item.path}" class="sidebar-item ${isActive ? 'active' : ''}" data-nav="${item.id}" aria-label="${item.label}">
          ${item.icon}
          <span class="sidebar-tooltip">${item.label}</span>
        </a>
      `;
    })
    .join('');

  return `
    <aside class="sidebar" id="app-sidebar">
      <a href="#/dashboard" class="sidebar-logo" title="Sentinel — Codebase Intelligence" aria-label="Sentinel Logo">
        ${icons.sentinel}
      </a>
      <nav class="sidebar-nav" aria-label="Main Navigation">
        ${navLinks}
      </nav>
      <div class="sidebar-bottom">
        <div class="sidebar-status" id="sidebar-status-dot" title="Backend: Checking status..."></div>
      </div>
    </aside>
  `;
}

export function updateSidebarActive(currentPath) {
  const normPath = currentPath === '#/' || currentPath === '' ? '#/dashboard' : currentPath;
  const items = document.querySelectorAll('.sidebar-item');
  items.forEach((el) => {
    const href = el.getAttribute('href');
    if (normPath.startsWith(href)) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });
}

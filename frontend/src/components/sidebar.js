/**
 * Sentinel — Sidebar Component
 */

import { icons } from '../icons.js';

export const navItems = [
  { id: 'dashboard', path: '#/dashboard', label: 'Overview', icon: icons.dashboard },
  { id: 'ask', path: '#/ask', label: 'Ask', icon: icons.ask },
  { id: 'impact', path: '#/impact', label: 'Impact', icon: icons.impact },
  { id: 'fix', path: '#/fix', label: 'Fix', icon: icons.fix },
];

export function renderSidebar(currentPath = '#/dashboard') {
  const normPath = currentPath === '#/' || currentPath === '' ? '#/dashboard' : currentPath;

  const navLinks = navItems
    .map((item) => {
      const isActive = normPath.startsWith(item.path);
      return `
        <a href="${item.path}" class="sidebar-item ${isActive ? 'active' : ''}" data-nav="${item.id}" aria-label="${item.label}">
          <span>${item.label}</span>
        </a>
      `;
    })
    .join('');

  return `
    <header class="sidebar" id="app-sidebar">
      <a href="#/dashboard" class="sidebar-logo" title="Sentinel — Codebase Intelligence" aria-label="Sentinel Logo">
        ${icons.sentinel}<span>SENTINEL</span>
      </a>
      <nav class="sidebar-nav" aria-label="Main Navigation">
        ${navLinks}
      </nav>
      <div class="sidebar-bottom">
        <div class="sidebar-status" id="sidebar-status-dot" title="Backend: Checking status..."></div><span>LIVE</span>
      </div>
    </header>
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

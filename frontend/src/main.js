/**
 * Sentinel — Codebase Intelligence
 * Application Entrypoint & Router
 */

import './styles/variables.css';
import './styles/reset.css';
import './styles/base.css';
import './styles/components.css';
import './styles/layout.css';
import './styles/workspace.css';

import { renderSidebar, updateSidebarActive } from './components/sidebar.js';
import { renderIde, initIde } from './pages/ide.js';
import { renderImpactPage, initImpactPage } from './pages/impact.js';
import { renderAskPage, initAskPage } from './pages/ask.js';
import { renderFixPage, initFixPage } from './pages/fix.js';
import { renderValidationPage, initValidationPage } from './pages/validation.js';
import { api } from './api.js';

const routes = {
  '': { render: renderIde, init: initIde },
  '#/': { render: renderIde, init: initIde },
  '#/dashboard': { render: renderIde, init: initIde },
  '#/impact': { render: renderImpactPage, init: initImpactPage },
  '#/ask': { render: renderAskPage, init: initAskPage },
  '#/fix': { render: renderFixPage, init: initFixPage },
  '#/validation': { render: renderValidationPage, init: initValidationPage },
};

function initApp() {
  const appEl = document.getElementById('app');
  if (!appEl) return;

  const currentHash = window.location.hash || '#/dashboard';

  appEl.innerHTML = `
    ${renderSidebar(currentHash)}
    <main class="main-content" id="main-content">
      <div id="page-container"></div>
    </main>
  `;

  navigate(currentHash);
  checkBackendHealth();
}

async function checkBackendHealth() {
  const statusDot = document.getElementById('sidebar-status-dot');
  if (!statusDot) return;

  try {
    const res = await api.health();
    if (res.status === 'ok') {
      statusDot.className = 'sidebar-status';
      statusDot.title = `Backend: Online (v${res.version}, ${res.demo_mode ? 'Demo' : 'Live'})`;
    } else {
      statusDot.className = 'sidebar-status offline';
      statusDot.title = 'Backend: Degraded';
    }
  } catch {
    statusDot.className = 'sidebar-status offline';
    statusDot.title = 'Backend: Offline';
  }
}

function navigate(hash) {
  const routeKey = hash.split('?')[0];
  const route = routes[routeKey] || routes['#/dashboard'];

  const pageContainer = document.getElementById('page-container');
  if (pageContainer && route) {
    pageContainer.innerHTML = route.render();
    updateSidebarActive(routeKey);

    // Run page-specific logic
    if (typeof route.init === 'function') {
      try {
        route.init();
      } catch (err) {
        console.error('Error initializing page:', err);
      }
    }
  }

  window.scrollTo(0, 0);
}

window.addEventListener('hashchange', () => {
  navigate(window.location.hash);
});

// Start app on DOMContentLoaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

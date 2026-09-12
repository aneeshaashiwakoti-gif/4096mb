import { api, WS_BASE } from '../api.js';
import { icons } from '../icons.js';
import { showToast } from '../components/index.js';

let activeWs = null;

export function renderIde() {
  return `
    <div class="workspace-layout">
      <!-- Top Bar (Optional, can be left blank or used for quick actions) -->
      
      <div class="workspace-body">
        <!-- Sidebar: Project Explorer -->
        <aside class="project-explorer">
          <div class="explorer-header">
            <span>PROJECT</span>
            <div>
              <button id="btn-demo-project" class="btn-icon" title="Open Demo Project" style="margin-right: 4px;">${icons.sparkle || '☆'}</button>
              <button id="btn-connect-project" class="btn-icon" title="Connect Local Project">${icons.plus}</button>
            </div>
          </div>
          <div class="explorer-content" id="file-tree">
            <div class="empty-state">No project connected.</div>
          </div>
        </aside>
        
        <!-- Main: Code Editor -->
        <main class="editor-area">
          <div class="editor-tabs">
            <div class="editor-tab active" id="active-file-tab">Welcome to Sentinel</div>
          </div>
          <div class="editor-content">
            <pre><code id="code-viewer-content" style="display:block; padding: 20px;">
Welcome to Sentinel — Codebase Intelligence.
Please connect a local project to begin.
            </code></pre>
          </div>
        </main>
        
        <!-- Right Sidebar: Sentinel AI -->
        <aside class="ai-sidebar">
          <div class="ai-header">SENTINEL AI</div>
          <div class="ai-chat" id="chat-container">
            <div class="chat-message system">
              I am Sentinel. I can explain code changes, analyze impact, and propose fixes based on actual repository evidence.
            </div>
          </div>
          <div class="ai-input-area">
            <input type="text" id="ai-chat-input" placeholder="Ask Sentinel..." />
          </div>
        </aside>
      </div>

      <!-- Bottom Bar: Status / Impact -->
      <footer class="status-bar">
        <div class="status-left" id="impact-graph">
          ● CONNECTED
        </div>
        <div class="status-right" id="system-status">
          <button id="btn-toggle-theme" class="btn-outline">Toggle Theme</button>
        </div>
      </footer>
    </div>
  `;
}

export async function initIde() {
  document.getElementById('btn-connect-project')?.addEventListener('click', async () => {
    const path = prompt("Enter local project path:");
    if (path) {
      await connectAndLoad(path);
    }
  });

  document.getElementById('btn-demo-project')?.addEventListener('click', async () => {
    // Assuming backend runs with cwd as n:\HackbattleVIT
    await connectAndLoad('n:\\HackbattleVIT\\sentinel_demo_project');
  });

  async function connectAndLoad(path) {
    try {
      await api.connectProject({ path });
      showToast("Project connected", "success");
      loadFiles();
      connectWebSocket();
    } catch (e) {
      showToast(e.message, "error");
    }
  }
  
  document.getElementById('btn-toggle-theme')?.addEventListener('click', () => {
    document.body.classList.toggle('white-mode');
  });

  const chatInput = document.getElementById('ai-chat-input');
  if (chatInput) {
    chatInput.addEventListener('keypress', async (e) => {
      if (e.key === 'Enter' && chatInput.value.trim()) {
        const query = chatInput.value.trim();
        chatInput.value = '';
        addChatMessage(query, 'user');
        
        try {
           const currentFile = document.getElementById('active-file-tab')?.innerText || '';
           const res = await api.ask({
             question: query,
             query: query,
             context: { current_file: currentFile },
             current_file: currentFile,
           });
           const reply = res.answer || res.response || res.message || JSON.stringify(res);
           addChatMessage(reply, 'ai');
        } catch (err) {
           addChatMessage(err.message, 'error');
        }
      }
    });
  }
}

async function loadFiles(dirPath = '') {
  try {
    const res = await api.listFiles(dirPath);
    const tree = document.getElementById('file-tree');
    if (!tree) return;
    
    let html = '';
    res.files.forEach(f => {
      const icon = f.type === 'dir' ? icons.folder : icons.file;
      html += `<div class="file-item" data-path="${f.path}" data-type="${f.type}">
        <span class="file-icon">${icon}</span>
        <span class="file-name">${f.name}</span>
      </div>`;
    });
    tree.innerHTML = html;
    
    // Add click listeners
    tree.querySelectorAll('.file-item').forEach(el => {
      el.addEventListener('click', async (e) => {
        const path = el.getAttribute('data-path');
        const type = el.getAttribute('data-type');
        if (type === 'file') {
          await openFile(path);
        } else {
          // simple expand logic could go here
        }
      });
    });
  } catch (e) {
    console.error("Failed to list files", e);
  }
}

async function openFile(path) {
  try {
    const res = await api.readFile(path);
    const tab = document.getElementById('active-file-tab');
    if (tab) tab.innerText = path;
    
    const viewer = document.getElementById('code-viewer-content');
    if (viewer) {
      viewer.textContent = res.content;
      // highlight changed lines visually if there's an active change
    }
  } catch (e) {
    showToast("Failed to read file", "error");
  }
}

function connectWebSocket() {
  if (activeWs) activeWs.close();
  const wsUrl = `${WS_BASE}/projects/ws`;
  activeWs = new WebSocket(wsUrl);
  
  activeWs.onopen = () => {
    activeWs.send(JSON.stringify({type: 'watch'}));
  };
  
  activeWs.onmessage = async (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'file_event') {
      showToast(`File changed: ${msg.file}`, 'info');
      document.getElementById('impact-graph').innerText = `● LIVE CHANGE: ${msg.file}`;
      
      // Auto reload if currently viewed
      const activeFile = document.getElementById('active-file-tab')?.innerText;
      if (activeFile === msg.file) {
        await openFile(msg.file);
      }
      
      // Trigger Analyzer/Impact backend logic here in real product
      try {
         const context = msg.impact || await api.projectImpact({ file: msg.file, change_type: "MODIFIED" });
         const res = await api.explainImpact(context);
         addChatMessage(`Impact detected for ${msg.file}. ${res.summary}`, 'system');
      } catch (err) {
         console.error(err);
      }
    }
  };
}

function addChatMessage(text, role) {
  const container = document.getElementById('chat-container');
  if (!container) return;
  
  const el = document.createElement('div');
  el.className = `chat-message ${role}`;
  el.textContent = text;
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
}

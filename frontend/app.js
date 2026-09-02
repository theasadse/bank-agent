// =========================================================
// State Management
// =========================================================
const state = {
  activeTab: 'tab-chat',
  chatHistory: [],
  selectedProvider: localStorage.getItem('soc_provider') || 'auto',
  groqApiKey: localStorage.getItem('soc_groq_key') || '',
  geminiApiKey: localStorage.getItem('soc_gemini_key') || '',
  isFiler: true,
  selectedFile: null,
  isStreaming: false,
  currentSessionId: null,
  isDarkMode: localStorage.getItem('soc_theme') === 'dark'
};

// =========================================================
// DOM Elements
// =========================================================
const elements = {
  navTabs: document.querySelectorAll('.nav-tab'),
  tabPanes: document.querySelectorAll('.tab-pane'),
  activeProviderLabel: document.getElementById('active-provider-label'),
  providerStatusBadge: document.getElementById('provider-status-badge'),
  quickProviderSelect: document.getElementById('quick-provider-select'),

  // Theme
  themeToggleBtn: document.getElementById('theme-toggle-btn'),
  themeToggleIcon: document.getElementById('theme-toggle-icon'),

  // Chat
  chatForm: document.getElementById('chat-form'),
  chatInput: document.getElementById('chat-input'),
  chatSendBtn: document.getElementById('chat-send-btn'),
  chatClearBtn: document.getElementById('chat-clear-btn'),
  chatContainer: document.getElementById('chat-messages-container'),
  promptChips: document.querySelectorAll('.prompt-chip'),
  sidebarDocCount: document.getElementById('sidebar-doc-count'),
  sidebarDocStats: document.getElementById('sidebar-doc-stats'),
  sidebarDocName: document.getElementById('sidebar-doc-name'),
  voiceInputBtn: document.getElementById('voice-input-btn'),

  // History Panel
  historySessionList: document.getElementById('history-session-list'),
  historyCountBadge: document.getElementById('history-count-badge'),
  newSessionBtn: document.getElementById('new-session-btn'),

  // Compare
  presetBtns: document.querySelectorAll('.preset-btn'),
  runCompareBtn: document.getElementById('run-compare-btn'),
  compareResultArea: document.getElementById('compare-result-area'),

  // Calculator
  calcPresetSelect: document.getElementById('calc-preset-select'),
  calcServiceName: document.getElementById('calc-service-name'),
  calcBaseFee: document.getElementById('calc-base-fee'),
  calcTxAmount: document.getElementById('calc-tx-amount'),
  calcFedRate: document.getElementById('calc-fed-rate'),
  calcIntlRate: document.getElementById('calc-intl-rate'),
  filerBtnTrue: document.getElementById('filer-btn-true'),
  filerBtnFalse: document.getElementById('filer-btn-false'),
  calcSubmitBtn: document.getElementById('calc-submit-btn'),
  receiptServiceTitle: document.getElementById('receipt-service-title'),
  receiptBaseVal: document.getElementById('receipt-base-val'),
  receiptFedVal: document.getElementById('receipt-fed-val'),
  receiptIntlRow: document.getElementById('receipt-intl-row'),
  receiptIntlVal: document.getElementById('receipt-intl-val'),
  receiptWhtRow: document.getElementById('receipt-wht-row'),
  receiptWhtVal: document.getElementById('receipt-wht-val'),
  receiptTotalVal: document.getElementById('receipt-total-val'),
  receiptStepsList: document.getElementById('receipt-steps-list'),
  receiptStatutoryNote: document.getElementById('receipt-statutory-note'),
  receiptCopyBtn: document.getElementById('receipt-copy-btn'),
  receiptDownloadBtn: document.getElementById('receipt-download-btn'),

  // Vault
  pdfDropZone: document.getElementById('pdf-drop-zone'),
  pdfFileInput: document.getElementById('pdf-file-input'),
  browsePdfBtn: document.getElementById('browse-pdf-btn'),
  chosenFileName: document.getElementById('chosen-file-name'),
  uploadPdfBtn: document.getElementById('upload-pdf-btn'),
  resetSampleBtn: document.getElementById('reset-sample-btn'),
  uploadProgressBox: document.getElementById('upload-progress-box'),
  uploadProgressFill: document.getElementById('upload-progress-fill'),
  uploadProgressStatus: document.getElementById('upload-progress-status'),
  useDoclingToggle: document.getElementById('use-docling-toggle'),
  indexedDocsList: document.getElementById('indexed-docs-list'),
  refreshDocsBtn: document.getElementById('refresh-docs-btn'),

  // Modals
  settingsModal: document.getElementById('settings-modal'),
  openSettingsBtn: document.getElementById('open-settings-btn'),
  closeSettingsBtn: document.getElementById('close-settings-btn'),
  saveSettingsBtn: document.getElementById('save-settings-btn'),
  groqKeyInput: document.getElementById('groq-api-key-input'),
  geminiKeyInput: document.getElementById('gemini-api-key-input'),
  providerRadios: document.querySelectorAll('input[name="provider-choice"]'),
  modalOllamaStatus: document.getElementById('modal-ollama-status'),
  modalChromaStatus: document.getElementById('modal-chroma-status'),

  // Citation Modal
  citationModal: document.getElementById('citation-modal'),
  closeCitationBtn: document.getElementById('close-citation-btn'),
  dismissCitationBtn: document.getElementById('dismiss-citation-btn'),
  citModalDoc: document.getElementById('cit-modal-doc'),
  citModalPage: document.getElementById('cit-modal-page'),
  citModalSection: document.getElementById('cit-modal-section'),
  citModalScore: document.getElementById('cit-modal-score'),
  citModalSnippet: document.getElementById('cit-modal-snippet')
};

// =========================================================
// INITIALIZATION
// =========================================================

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initNavigation();
  initSettings();
  initChat();
  initHistory();
  initComparator();
  initCalculator();
  initVault();
  initVoiceInput();
  checkSystemHealth();
  loadDocuments();
  loadSessionHistory();
});

// =========================================================
// FEATURE 1: DARK / LIGHT MODE TOGGLE
// =========================================================

function initTheme() {
  applyTheme(state.isDarkMode);
  if (elements.themeToggleBtn) {
    elements.themeToggleBtn.addEventListener('click', toggleTheme);
  }
}

function toggleTheme() {
  state.isDarkMode = !state.isDarkMode;
  localStorage.setItem('soc_theme', state.isDarkMode ? 'dark' : 'light');
  applyTheme(state.isDarkMode);
}

function applyTheme(isDark) {
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  if (elements.themeToggleIcon) {
    elements.themeToggleIcon.className = isDark ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
  }
  if (elements.themeToggleBtn) {
    elements.themeToggleBtn.title = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';
  }
}

// =========================================================
// FEATURE 2: CHAT SESSION PERSISTENCE & HISTORY
// =========================================================

const SESSION_STORAGE_KEY = 'soc_chat_sessions';
const MAX_SESSIONS = 20;

function generateSessionId() {
  return 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7);
}

function getSessions() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveSessions(sessions) {
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sessions));
}

function saveCurrentSession() {
  if (!state.currentSessionId || state.chatHistory.length === 0) return;
  const sessions = getSessions();
  const messagesHtml = elements.chatContainer.innerHTML;
  const firstUserMsg = state.chatHistory.find(h => h.role === 'user');
  const title = firstUserMsg
    ? firstUserMsg.content.slice(0, 55) + (firstUserMsg.content.length > 55 ? '\u2026' : '')
    : 'Tariff Consultation';

  const existingIndex = sessions.findIndex(s => s.id === state.currentSessionId);
  const sessionData = {
    id: state.currentSessionId,
    title,
    timestamp: Date.now(),
    history: state.chatHistory,
    messagesHtml
  };

  if (existingIndex >= 0) {
    sessions[existingIndex] = sessionData;
  } else {
    sessions.unshift(sessionData);
  }

  if (sessions.length > MAX_SESSIONS) sessions.length = MAX_SESSIONS;
  saveSessions(sessions);
  renderSessionHistory();
}

function restoreSession(sessionId) {
  const sessions = getSessions();
  const session = sessions.find(s => s.id === sessionId);
  if (!session) return;

  saveCurrentSession();

  state.currentSessionId = session.id;
  state.chatHistory = session.history || [];
  elements.chatContainer.innerHTML = session.messagesHtml || '';

  // Re-attach citation pill click handlers
  elements.chatContainer.querySelectorAll('.citation-pill').forEach(pill => {
    const citData = {
      document_name: pill.dataset.doc,
      page_number: pill.dataset.page,
      section_title: pill.dataset.section,
      score: pill.dataset.score,
      snippet: pill.dataset.snippet
    };
    pill.addEventListener('click', () => openCitationModal(citData));
  });

  // Re-attach copy handlers on restored messages
  elements.chatContainer.querySelectorAll('.copy-msg-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      const bubble = this.closest('.message-bubble');
      const plainText = bubble?.querySelector('.bubble-content')?.innerText || '';
      navigator.clipboard.writeText(plainText).then(() => {
        this.classList.add('copied');
        this.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
        showToast('Response copied to clipboard', 'success');
        setTimeout(() => {
          this.classList.remove('copied');
          this.innerHTML = '<i class="fa-solid fa-copy"></i> Copy';
        }, 2500);
      }).catch(() => showToast('Copy failed', 'error'));
    });
  });

  renderSessionHistory();
  scrollToBottom();
  showToast('Session restored', 'info', 'fa-clock-rotate-left');
}

function deleteSession(sessionId, event) {
  if (event) event.stopPropagation();
  const sessions = getSessions().filter(s => s.id !== sessionId);
  saveSessions(sessions);
  if (state.currentSessionId === sessionId) {
    startNewSession();
  } else {
    renderSessionHistory();
  }
}

function startNewSession() {
  saveCurrentSession();
  state.currentSessionId = generateSessionId();
  state.chatHistory = [];
  elements.chatContainer.innerHTML = `
    <div class="message-row assistant">
      <div class="avatar-box"><i class="fa-solid fa-building-columns"></i></div>
      <div class="message-bubble">
        <div class="bubble-header">
          <span class="sender-name">Bank SOC AI Assistant</span>
          <span class="provider-pill">Official Tariff Guide</span>
        </div>
        <div class="bubble-content markdown-body">
          <p>Welcome! I am your <strong>Bank Schedule of Charges (SOC) & Fee Assistant</strong>. Ask me anything about card charges, account maintenance, transfer fees, or tax rules.</p>
          <ul>
            <li>💳 <strong>Debit & Credit Cards</strong>: Annual fees, replacement charges, ATM withdrawal & POS limits.</li>
            <li>💸 <strong>Fund Transfers & IBFT</strong>: Free monthly limits, charges, and Raast transfers.</li>
            <li>⚖️ <strong>Waiver Rules & Footnotes</strong>: Balance thresholds and spend criteria that waive annual fees.</li>
            <li>🧾 <strong>Tax & FED Breakdown</strong>: Provincial sales tax / FED (16%) and filer vs non-filer withholding tax.</li>
          </ul>
          <p class="text-muted">Type your banking question below or click any topic on the left to begin.</p>
        </div>
      </div>
    </div>
  `;
  renderSessionHistory();
  elements.chatInput?.focus();
}

function initHistory() {
  if (!state.currentSessionId) {
    state.currentSessionId = generateSessionId();
  }
  if (elements.newSessionBtn) {
    elements.newSessionBtn.addEventListener('click', startNewSession);
  }
}

function loadSessionHistory() {
  renderSessionHistory();
}

function renderSessionHistory() {
  const sessions = getSessions();
  const badge = elements.historyCountBadge;
  if (badge) badge.textContent = `${sessions.length} session${sessions.length !== 1 ? 's' : ''}`;

  if (!elements.historySessionList) return;

  if (sessions.length === 0) {
    elements.historySessionList.innerHTML = '<div class="history-empty-state">No saved sessions yet. Start chatting!</div>';
    return;
  }

  elements.historySessionList.innerHTML = sessions.map(sess => {
    const dateStr = formatRelativeTime(sess.timestamp);
    const isActive = sess.id === state.currentSessionId;
    const msgCount = (sess.history || []).filter(h => h.role === 'user').length;
    return `
      <div class="history-session-item ${isActive ? 'active-session' : ''}"
           onclick="handleRestoreSession('${escapeHtml(sess.id)}')">
        <i class="fa-solid fa-message history-session-icon"></i>
        <div class="history-session-info">
          <div class="history-session-title">${escapeHtml(sess.title)}</div>
          <div class="history-session-time">${dateStr} &middot; ${msgCount} msg${msgCount !== 1 ? 's' : ''}</div>
        </div>
        <button class="history-session-delete"
                onclick="handleDeleteSession('${escapeHtml(sess.id)}', event)"
                title="Delete session">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    `;
  }).join('');
}

function formatRelativeTime(timestamp) {
  const diff = Date.now() - timestamp;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

window.handleRestoreSession = restoreSession;
window.handleDeleteSession = deleteSession;

// =========================================================
// TOAST NOTIFICATION SYSTEM
// =========================================================

function showToast(message, type = 'info', icon = null) {
  const iconMap = { success: 'fa-circle-check', error: 'fa-triangle-exclamation', info: 'fa-circle-info' };
  const iconClass = icon || iconMap[type] || 'fa-circle-info';

  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast-notification toast-${type}`;
  toast.innerHTML = `<i class="fa-solid ${iconClass}"></i><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast-fade-out');
    toast.addEventListener('animationend', () => toast.remove());
  }, 3200);
}

// =========================================================
// VOICE INPUT (SPEECH RECOGNITION)
// =========================================================

function initVoiceInput() {
  if (!elements.voiceInputBtn) return;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    elements.voiceInputBtn.style.display = 'none';
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  let isListening = false;

  elements.voiceInputBtn.addEventListener('click', () => {
    if (isListening) {
      recognition.stop();
      return;
    }
    recognition.start();
  });

  recognition.onstart = () => {
    isListening = true;
    elements.voiceInputBtn.innerHTML = '<i class="fa-solid fa-microphone-slash" style="color:var(--accent-rose)"></i>';
    elements.voiceInputBtn.title = 'Listening\u2026 click to stop';
    showToast('Listening\u2026 speak your banking question', 'info', 'fa-microphone');
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    elements.chatInput.value = transcript;
    elements.chatInput.focus();
    showToast('Voice captured \u2014 press Send to submit', 'success', 'fa-microphone');
  };

  recognition.onend = () => {
    isListening = false;
    elements.voiceInputBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    elements.voiceInputBtn.title = 'Voice Input (click to speak)';
  };

  recognition.onerror = (event) => {
    isListening = false;
    elements.voiceInputBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    showToast(`Voice error: ${event.error}`, 'error');
  };
}

// =========================================================
// NAVIGATION
// =========================================================

function initNavigation() {
  elements.navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetId = tab.getAttribute('data-target');
      state.activeTab = targetId;

      elements.navTabs.forEach(t => t.classList.remove('active'));
      elements.tabPanes.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add('active');
    });
  });
}

// =========================================================
// SETTINGS & HEALTH
// =========================================================

function initSettings() {
  if (elements.quickProviderSelect) {
    elements.quickProviderSelect.value = state.selectedProvider;
    elements.quickProviderSelect.addEventListener('change', (e) => {
      state.selectedProvider = e.target.value;
      localStorage.setItem('soc_provider', state.selectedProvider);
      elements.providerRadios.forEach(r => {
        r.checked = (r.value === state.selectedProvider);
      });
      updateProviderBadge();
    });
  }

  elements.openSettingsBtn.addEventListener('click', () => {
    if (elements.groqKeyInput) elements.groqKeyInput.value = state.groqApiKey;
    if (elements.geminiKeyInput) elements.geminiKeyInput.value = state.geminiApiKey;
    elements.providerRadios.forEach(r => {
      r.checked = (r.value === state.selectedProvider);
    });
    elements.settingsModal.style.display = 'flex';
  });

  elements.closeSettingsBtn.addEventListener('click', () => {
    elements.settingsModal.style.display = 'none';
  });

  elements.saveSettingsBtn.addEventListener('click', () => {
    const chosen = Array.from(elements.providerRadios).find(r => r.checked)?.value || 'auto';
    state.selectedProvider = chosen;
    if (elements.groqKeyInput) state.groqApiKey = elements.groqKeyInput.value.trim();
    if (elements.geminiKeyInput) state.geminiApiKey = elements.geminiKeyInput.value.trim();

    localStorage.setItem('soc_provider', chosen);
    localStorage.setItem('soc_groq_key', state.groqApiKey);
    localStorage.setItem('soc_gemini_key', state.geminiApiKey);

    if (elements.quickProviderSelect) {
      elements.quickProviderSelect.value = chosen;
    }

    updateProviderBadge();
    elements.settingsModal.style.display = 'none';
    checkSystemHealth();
    showToast('Settings saved successfully', 'success');
  });
}

let latestHealthData = null;

async function checkSystemHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) throw new Error('Health check failed');
    const data = await res.json();
    latestHealthData = data;

    if (elements.modalOllamaStatus) {
      elements.modalOllamaStatus.textContent = data.ollama_online
        ? `Online (${data.ollama_models?.join(', ') || 'llama3.2'})`
        : 'Offline';
      elements.modalOllamaStatus.style.color = data.ollama_online ? 'var(--accent-emerald)' : 'var(--accent-rose)';
    }

    if (elements.sidebarDocStats && data.total_chunks > 0) {
      elements.sidebarDocStats.textContent = `${data.indexed_documents} Doc(s) \u2022 ${data.total_chunks} Chunks Indexed`;
    }

    updateProviderBadge(data);
  } catch (e) {
    console.warn('Could not fetch health:', e);
  }
}

function updateProviderBadge(healthData) {
  const data = healthData || latestHealthData || {};
  let label = 'Auto (Groq Cloud \u2194 Ollama)';

  if (state.selectedProvider === 'groq' || (state.selectedProvider === 'auto' && (state.groqApiKey || data.groq_configured))) {
    label = 'Groq Cloud (GPT-OSS 120B / Fast)';
  } else if (state.selectedProvider === 'gemini' || (state.selectedProvider === 'auto' && (state.geminiApiKey || data.gemini_configured))) {
    label = 'Google Gemini Flash';
  } else if (state.selectedProvider === 'ollama') {
    label = data.ollama_online ? 'Ollama Local (llama3.2 Online)' : 'Ollama Local (Offline)';
  } else {
    label = data.ollama_online ? 'Ollama Local (llama3.2)' : 'AI Ready (Groq Cloud)';
  }

  if (elements.activeProviderLabel) {
    elements.activeProviderLabel.textContent = label;
  }
}

// =========================================================
// TAB 1: CHAT ASSISTANT
// =========================================================

function initChat() {
  elements.chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = elements.chatInput.value.trim();
    if (!query || state.isStreaming) return;
    submitQuery(query);
  });

  elements.chatClearBtn.addEventListener('click', () => {
    startNewSession();
  });

  elements.promptChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      if (prompt) {
        elements.chatInput.value = prompt;
        submitQuery(prompt);
      }
    });
  });
}

async function submitQuery(queryText) {
  appendUserMessage(queryText);
  elements.chatInput.value = '';
  elements.chatSendBtn.disabled = true;
  state.isStreaming = true;

  const assistantBubble = createAssistantMessagePlaceholder();
  const contentElement = assistantBubble.querySelector('.bubble-content');
  const citationsContainer = assistantBubble.querySelector('.citations-footer');
  const providerPill = assistantBubble.querySelector('.provider-pill');

  let accumulatedMarkdown = '';
  let citationsList = [];

  try {
    const payload = {
      query: queryText,
      history: state.chatHistory,
      provider: state.selectedProvider,
      api_key: state.selectedProvider === 'groq'
        ? state.groqApiKey
        : (state.selectedProvider === 'gemini'
          ? state.geminiApiKey
          : (state.groqApiKey || state.geminiApiKey || null))
    };

    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === 'meta') {
              providerPill.textContent = `${event.provider} (${event.model})`;
              citationsList = event.citations || [];
            } else if (event.type === 'token') {
              accumulatedMarkdown += event.content;
              contentElement.innerHTML = marked.parse(accumulatedMarkdown);
              scrollToBottom();
            } else if (event.type === 'done') {
              break;
            }
          } catch (err) {
            console.error('Error parsing SSE chunk:', err);
          }
        }
      }
    }

    if (citationsList && citationsList.length > 0) {
      renderCitations(citationsContainer, citationsList);
    } else {
      citationsContainer.style.display = 'none';
    }

    // Add copy action bar
    addMessageActionBar(assistantBubble, accumulatedMarkdown);

    state.chatHistory.push({ role: 'user', content: queryText });
    state.chatHistory.push({ role: 'assistant', content: accumulatedMarkdown });

    // Auto-save session after each exchange
    saveCurrentSession();

  } catch (error) {
    console.error('Query error:', error);
    contentElement.innerHTML = `<p class="text-rose"><i class="fa-solid fa-triangle-exclamation"></i> Error: ${escapeHtml(error.message)}</p>`;
    showToast(`Query failed: ${error.message}`, 'error');
  } finally {
    state.isStreaming = false;
    elements.chatSendBtn.disabled = false;
    scrollToBottom();
  }
}

function appendUserMessage(text) {
  const row = document.createElement('div');
  row.className = 'message-row user';
  row.innerHTML = `
    <div class="avatar-box"><i class="fa-solid fa-user"></i></div>
    <div class="message-bubble">
      <div class="bubble-header">
        <span class="sender-name">You</span>
      </div>
      <div class="bubble-content markdown-body">
        <p>${escapeHtml(text)}</p>
      </div>
    </div>
  `;
  elements.chatContainer.appendChild(row);
  scrollToBottom();
}

function createAssistantMessagePlaceholder() {
  const row = document.createElement('div');
  row.className = 'message-row assistant';
  row.innerHTML = `
    <div class="avatar-box"><i class="fa-solid fa-robot"></i></div>
    <div class="message-bubble">
      <div class="bubble-header">
        <span class="sender-name">Apex SOC Compliance Agent</span>
        <span class="provider-pill">Reasoning...</span>
      </div>
      <div class="bubble-content markdown-body">
        <p><em>Analyzing Schedule of Charges tables and footnote rules...</em></p>
      </div>
      <div class="citations-footer">
        <div class="citations-label"><i class="fa-solid fa-bookmark text-cyan"></i> Verified SOC Citations:</div>
        <div class="citation-pills-container"></div>
      </div>
    </div>
  `;
  elements.chatContainer.appendChild(row);
  scrollToBottom();
  return row;
}

// =========================================================
// FEATURE 3A: COPY BUTTON ON AI MESSAGES
// =========================================================

function addMessageActionBar(bubbleRow, markdownText) {
  const bubble = bubbleRow.querySelector('.message-bubble');
  if (!bubble) return;

  const actionsBar = document.createElement('div');
  actionsBar.className = 'message-actions-bar';
  actionsBar.innerHTML = '<button class="btn-msg-action copy-msg-btn" title="Copy response text"><i class="fa-solid fa-copy"></i> Copy</button>';
  bubble.appendChild(actionsBar);

  actionsBar.querySelector('.copy-msg-btn').addEventListener('click', function() {
    const plainText = markdownText || (bubble.querySelector('.bubble-content')?.innerText || '');
    navigator.clipboard.writeText(plainText).then(() => {
      this.classList.add('copied');
      this.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
      showToast('Response copied to clipboard', 'success');
      setTimeout(() => {
        this.classList.remove('copied');
        this.innerHTML = '<i class="fa-solid fa-copy"></i> Copy';
      }, 2500);
    }).catch(() => {
      showToast('Copy failed \u2014 try selecting text manually', 'error');
    });
  });
}

function renderCitations(container, citations) {
  container.style.display = 'block';
  const pillsContainer = container.querySelector('.citation-pills-container');
  pillsContainer.innerHTML = '';

  citations.forEach(cit => {
    const pill = document.createElement('button');
    pill.className = 'citation-pill';
    pill.dataset.doc = cit.document_name || '';
    pill.dataset.page = cit.page_number || '';
    pill.dataset.section = cit.section_title || '';
    pill.dataset.score = cit.score || '';
    pill.dataset.snippet = cit.snippet || '';
    pill.innerHTML = `<i class="fa-solid fa-file-pdf"></i><span>Page ${cit.page_number}: ${escapeHtml(cit.section_title)}</span>`;
    pill.addEventListener('click', () => openCitationModal(cit));
    pillsContainer.appendChild(pill);
  });
}

function openCitationModal(cit) {
  elements.citModalDoc.textContent = cit.document_name || 'Apex_International_Bank_SOC_2025.pdf';
  elements.citModalPage.textContent = `Page ${cit.page_number}`;
  elements.citModalSection.textContent = cit.section_title;
  elements.citModalScore.textContent = cit.score ? `Relevance: ${Math.round(cit.score * 100)}%` : 'Direct Source';
  elements.citModalSnippet.textContent = cit.snippet;
  elements.citationModal.style.display = 'flex';
}

elements.closeCitationBtn?.addEventListener('click', () => { elements.citationModal.style.display = 'none'; });
elements.dismissCitationBtn?.addEventListener('click', () => { elements.citationModal.style.display = 'none'; });

function scrollToBottom() {
  elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
}

// =========================================================
// TAB 2: VARIANT COMPARATOR
// =========================================================

function initComparator() {
  let selectedCategory = 'debit_cards';
  let selectedItems = ['VISA Classic Debit Card', 'VISA Gold / Pehchaan Debit Card', 'VISA Platinum Debit Card', 'VISA Signature Debit Card', 'PayPak Classic Debit Card'];

  elements.presetBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      elements.presetBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedCategory = btn.getAttribute('data-category');
      selectedItems = btn.getAttribute('data-items').split(',').map(s => s.trim());
    });
  });

  elements.runCompareBtn.addEventListener('click', async () => {
    elements.compareResultArea.innerHTML = `
      <div class="empty-state">
        <i class="fa-solid fa-arrows-split-up-and-left fa-spin text-cyan"></i>
        <p>Retrieving SOC chunks and building comparative matrix with footnotes in PKR (Rs.)...</p>
      </div>
    `;

    try {
      const res = await fetch('/api/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: selectedCategory,
          items: selectedItems,
          provider: state.selectedProvider,
          api_key: state.selectedProvider === 'groq'
            ? state.groqApiKey
            : (state.selectedProvider === 'gemini'
              ? state.geminiApiKey
              : (state.groqApiKey || state.geminiApiKey || null))
        })
      });

      if (!res.ok) throw new Error('Comparison failed');
      const data = await res.json();
      renderComparisonResult(data);
    } catch (e) {
      elements.compareResultArea.innerHTML = `
        <div class="empty-state">
          <i class="fa-solid fa-triangle-exclamation text-rose"></i>
          <p class="text-rose">Failed to generate comparison: ${escapeHtml(e.message)}</p>
        </div>
      `;
      showToast(`Comparison failed: ${e.message}`, 'error');
    }
  });
}

function renderComparisonResult(data) {
  let tableHtml = '<div class="matrix-table-container"><table class="matrix-table"><thead><tr><th>Product Feature / Fee</th>';
  data.items.forEach(it => { tableHtml += `<th>${escapeHtml(it)}</th>`; });
  tableHtml += '</tr></thead><tbody>';

  if (data.matrix && data.matrix.length > 0) {
    data.matrix.forEach(row => {
      tableHtml += `<tr><td>${escapeHtml(row.feature_name)}</td>`;
      data.items.forEach(it => { tableHtml += `<td>${escapeHtml(row.values[it] || 'N/A')}</td>`; });
      tableHtml += '</tr>';
    });
  }
  tableHtml += '</tbody></table></div>';

  let recommendationHtml = '';
  if (data.recommendation) {
    recommendationHtml = `
      <div class="comparison-recommendation">
        <h4><i class="fa-solid fa-award"></i> Compliance &amp; Value Analysis:</h4>
        <p>${escapeHtml(data.recommendation)}</p>
      </div>
    `;
  }

  let footnotesHtml = '';
  if (data.footnotes_and_waivers && data.footnotes_and_waivers.length > 0) {
    footnotesHtml = `
      <div class="comparison-footnotes-box">
        <h4><i class="fa-solid fa-asterisk"></i> Footnote Waivers &amp; Statutory Rules:</h4>
        <ul>
          ${data.footnotes_and_waivers.map(fn => `<li>${escapeHtml(fn)}</li>`).join('')}
        </ul>
      </div>
    `;
  }

  // FEATURE 3B: Export bar
  const exportBar = '<div class="compare-export-bar"><button class="btn-export" id="export-csv-btn"><i class="fa-solid fa-file-csv"></i> Export as CSV</button></div>';

  elements.compareResultArea.innerHTML =
    `<h3 style="font-family:var(--font-heading);margin-bottom:1rem;color:var(--accent-cyan);"><i class="fa-solid fa-table-cells"></i> ${escapeHtml(data.title)}</h3>` +
    tableHtml + recommendationHtml + footnotesHtml + exportBar;

  const csvBtn = document.getElementById('export-csv-btn');
  if (csvBtn) {
    csvBtn.addEventListener('click', () => { exportComparisonAsCSV(data); });
  }
}

// =========================================================
// FEATURE 3B: CSV EXPORT FOR COMPARISON TABLE
// =========================================================

function exportComparisonAsCSV(data) {
  if (!data || !data.matrix) { showToast('No data to export', 'error'); return; }

  const header = ['Feature / Fee', ...data.items];
  const rows = data.matrix.map(row => [
    row.feature_name,
    ...data.items.map(it => row.values[it] || 'N/A')
  ]);

  const csvContent = [header, ...rows]
    .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `SOC_Comparison_${data.title.replace(/[^a-z0-9]/gi, '_').slice(0, 40)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Comparison exported as CSV', 'success', 'fa-file-csv');
}

// =========================================================
// TAB 3: TAX & SURCHARGE CALCULATOR
// =========================================================

function initCalculator() {
  elements.filerBtnTrue.addEventListener('click', () => {
    state.isFiler = true;
    elements.filerBtnTrue.classList.add('active');
    elements.filerBtnFalse.classList.remove('active');
    runCalculation();
  });

  elements.filerBtnFalse.addEventListener('click', () => {
    state.isFiler = false;
    elements.filerBtnFalse.classList.add('active');
    elements.filerBtnTrue.classList.remove('active');
    runCalculation();
  });

  elements.calcPresetSelect.addEventListener('change', () => {
    const selected = elements.calcPresetSelect.options[elements.calcPresetSelect.selectedIndex];
    if (selected.value !== 'custom') {
      elements.calcServiceName.value = selected.getAttribute('data-name') || '';
      elements.calcBaseFee.value = selected.getAttribute('data-fee') || '0';
      elements.calcTxAmount.value = selected.getAttribute('data-amount') || '0';
      elements.calcFedRate.value = selected.getAttribute('data-fed') || '16.0';
      elements.calcIntlRate.value = selected.getAttribute('data-markup') || '0';
      runCalculation();
    }
  });

  elements.calcSubmitBtn.addEventListener('click', runCalculation);
  [elements.calcBaseFee, elements.calcTxAmount, elements.calcFedRate, elements.calcIntlRate].forEach(inp => {
    if (inp) inp.addEventListener('input', runCalculation);
  });

  // FEATURE 3C: Receipt copy button
  if (elements.receiptCopyBtn) {
    elements.receiptCopyBtn.addEventListener('click', () => {
      const receiptBox = document.getElementById('calc-result-box');
      if (!receiptBox) return;
      navigator.clipboard.writeText(receiptBox.innerText).then(() => {
        showToast('Receipt copied to clipboard', 'success', 'fa-copy');
      }).catch(() => {
        showToast('Copy failed', 'error');
      });
    });
  }

  // FEATURE 3C: Receipt PNG download
  if (elements.receiptDownloadBtn) {
    elements.receiptDownloadBtn.addEventListener('click', async () => {
      const receiptBox = document.getElementById('calc-result-box');
      if (!receiptBox || typeof html2canvas === 'undefined') {
        showToast('PNG export requires html2canvas', 'error');
        return;
      }
      elements.receiptDownloadBtn.disabled = true;
      elements.receiptDownloadBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Capturing...';
      try {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const bgColor = isDark ? '#1C2128' : '#F8FAFC';
        const canvas = await html2canvas(receiptBox, { backgroundColor: bgColor, scale: 2, useCORS: true });
        const url = canvas.toDataURL('image/png');
        const a = document.createElement('a');
        a.href = url;
        const serviceName = (elements.receiptServiceTitle?.textContent || 'receipt').replace(/[^a-z0-9]/gi, '_').slice(0, 30);
        a.download = `SOC_Receipt_${serviceName}.png`;
        a.click();
        showToast('Receipt saved as PNG', 'success', 'fa-image');
      } catch (err) {
        showToast(`PNG capture failed: ${err.message}`, 'error');
      } finally {
        elements.receiptDownloadBtn.disabled = false;
        elements.receiptDownloadBtn.innerHTML = '<i class="fa-solid fa-image"></i> Save as PNG';
      }
    });
  }
}

async function runCalculation() {
  const baseFee = parseFloat(elements.calcBaseFee.value) || 0;
  const txAmount = parseFloat(elements.calcTxAmount.value) || 0;
  const fedRate = parseFloat(elements.calcFedRate.value) || 0;
  const intlRate = parseFloat(elements.calcIntlRate.value) || 0;
  const serviceName = elements.calcServiceName.value.trim() || 'Banking Service';

  let whtRate = 0.0;
  if (!state.isFiler && txAmount >= 50000) whtRate = 0.6;

  try {
    const res = await fetch('/api/calculate-tax', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        base_fee: baseFee,
        service_name: serviceName,
        fed_rate: fedRate,
        is_filer: state.isFiler,
        wht_rate: whtRate,
        transaction_amount: txAmount,
        intl_markup_rate: intlRate
      })
    });
    if (!res.ok) throw new Error('Calculation error');
    const data = await res.json();
    renderReceipt(data);
  } catch (e) {
    console.error(e);
  }
}

function renderReceipt(data) {
  elements.receiptServiceTitle.textContent = data.service_name;
  elements.receiptBaseVal.textContent = `Rs. ${data.base_fee.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  elements.receiptFedVal.textContent = `+Rs. ${data.fed_amount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

  if (data.intl_markup_amount > 0) {
    elements.receiptIntlRow.style.display = 'flex';
    elements.receiptIntlVal.textContent = `+Rs. ${data.intl_markup_amount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  } else {
    elements.receiptIntlRow.style.display = 'none';
  }

  if (data.wht_amount > 0) {
    elements.receiptWhtRow.style.display = 'flex';
    elements.receiptWhtVal.textContent = `+Rs. ${data.wht_amount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  } else {
    elements.receiptWhtRow.style.display = 'none';
  }

  elements.receiptTotalVal.textContent = `Rs. ${data.total_fee_charged.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  elements.receiptStepsList.innerHTML = data.breakdown_steps.map(s => `<li>${escapeHtml(s)}</li>`).join('');

  if (data.footnote_rule_applied) {
    elements.receiptStatutoryNote.innerHTML = `<i class="fa-solid fa-circle-info"></i> <span>${escapeHtml(data.footnote_rule_applied)}</span>`;
  }
}

// =========================================================
// TAB 4: SOC DOCUMENT VAULT
// =========================================================

function initVault() {
  if (elements.browsePdfBtn) elements.browsePdfBtn.addEventListener('click', () => { elements.pdfFileInput.click(); });
  if (elements.pdfDropZone) elements.pdfDropZone.addEventListener('click', () => { elements.pdfFileInput.click(); });

  if (elements.pdfDropZone) {
    elements.pdfDropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      elements.pdfDropZone.classList.add('dragover');
    });
    elements.pdfDropZone.addEventListener('dragleave', () => {
      elements.pdfDropZone.classList.remove('dragover');
    });
    elements.pdfDropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      elements.pdfDropZone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFileSelected(e.dataTransfer.files[0]);
      }
    });
  }

  if (elements.pdfFileInput) {
    elements.pdfFileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) handleFileSelected(e.target.files[0]);
    });
  }

  if (elements.uploadPdfBtn) elements.uploadPdfBtn.addEventListener('click', uploadSelectedPdf);
  if (elements.resetSampleBtn) elements.resetSampleBtn.addEventListener('click', reindexSampleSoc);
  if (elements.refreshDocsBtn) elements.refreshDocsBtn.addEventListener('click', loadDocuments);
}

function handleFileSelected(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('Please select a valid PDF file', 'error');
    return;
  }
  state.selectedFile = file;
  elements.chosenFileName.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
  elements.uploadPdfBtn.disabled = false;
}

async function uploadSelectedPdf() {
  if (!state.selectedFile) return;
  const formData = new FormData();
  formData.append('file', state.selectedFile);
  if (elements.useDoclingToggle) formData.append('use_docling', elements.useDoclingToggle.checked);

  elements.uploadProgressBox.style.display = 'block';
  elements.uploadPdfBtn.disabled = true;

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }
    const data = await res.json();
    showToast(`Indexed ${data.total_chunks} chunks \u2014 ${data.tables_extracted} tables extracted`, 'success', 'fa-check');
    elements.chosenFileName.textContent = 'No file selected';
    state.selectedFile = null;
    loadDocuments();
    checkSystemHealth();
  } catch (e) {
    showToast(`Upload error: ${e.message}`, 'error');
  } finally {
    elements.uploadProgressBox.style.display = 'none';
    elements.uploadPdfBtn.disabled = true;
  }
}

async function reindexSampleSoc() {
  elements.uploadProgressBox.style.display = 'block';
  elements.uploadProgressStatus.textContent = 'Re-indexing comprehensive 2025 Schedule of Charges PDF...';
  try {
    const res = await fetch('/api/sample-index', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to index sample');
    showToast('Official 2025 SOC PDF re-indexed successfully', 'success');
    loadDocuments();
    checkSystemHealth();
  } catch (e) {
    showToast(`Re-index error: ${e.message}`, 'error');
  } finally {
    elements.uploadProgressBox.style.display = 'none';
  }
}

async function loadDocuments() {
  try {
    const res = await fetch('/api/documents');
    if (!res.ok) return;
    const docs = await res.json();
    renderDocumentList(docs);
  } catch (e) {
    console.error('Error loading documents:', e);
  }
}

function renderDocumentList(docs) {
  if (!docs || docs.length === 0) {
    elements.indexedDocsList.innerHTML = '<div class="empty-state" style="height:120px;"><p>No documents indexed yet.</p></div>';
    return;
  }

  elements.indexedDocsList.innerHTML = docs.map(doc => `
    <div class="doc-item-row">
      <div class="doc-item-left">
        <div class="doc-badge-icon"><i class="fa-solid fa-file-pdf"></i></div>
        <div>
          <div class="doc-item-title">${escapeHtml(doc.document_name)}</div>
          <div class="doc-item-meta">
            <span><i class="fa-solid fa-file-lines"></i> ${doc.total_pages} Pages</span>
            <span>&bull;</span>
            <span><i class="fa-solid fa-cubes"></i> ${doc.total_chunks} Chunks in ChromaDB</span>
          </div>
        </div>
      </div>
      <button class="btn-danger-icon" onclick="deleteDoc('${escapeHtml(doc.document_name)}')" title="Delete from index">
        <i class="fa-solid fa-trash-can"></i>
      </button>
    </div>
  `).join('');

  if (elements.sidebarDocCount) elements.sidebarDocCount.textContent = `${docs.length} Doc${docs.length > 1 ? 's' : ''}`;
  if (elements.sidebarDocName && docs[0]) elements.sidebarDocName.textContent = docs[0].document_name;
}

window.deleteDoc = async function(docName) {
  if (!confirm(`Remove '${docName}' from the vector database?`)) return;
  try {
    const res = await fetch(`/api/documents/${encodeURIComponent(docName)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
    showToast(`'${docName}' removed from index`, 'success', 'fa-trash-can');
    loadDocuments();
    checkSystemHealth();
  } catch (e) {
    showToast(`Delete error: ${e.message}`, 'error');
  }
};

// =========================================================
// HELPERS
// =========================================================

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

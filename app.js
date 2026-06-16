/**
 * Convers — Frontend Application Logic
 *
 * Features:
 *  - Dynamic scenario selection (from sessionStorage)
 *  - Challenge accept flow (reads sessionStorage 'convers_challenge')
 *  - Session start with retry logic + loading state
 *  - SSE streaming chat with typing indicator
 *  - Voice recording via MediaRecorder → /api/voice/transcribe
 *  - Session timer & turn counter
 *  - Full feedback modal with 5 category scores + animated ring
 *  - PDF export via jsPDF (dynamically loaded)
 *  - Resume builder via Groq LLM
 *  - Challenge friend: create shareable codes
 *  - History save + gamification update on session end
 *  - Grammar highlight on user bubbles (filler + capitalisation)
 *  - Keyboard shortcuts (Enter, Shift+Enter, Ctrl+M)
 */

// ── Config ──────────────────────────────────────────────────────────────────
const API_BASE = window.location.origin + '/api';

// ── State ───────────────────────────────────────────────────────────────────
let sessionId = null;
let isGenerating = false;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let timerInterval = null;
let sessionStartTime = null;
let turnCount = 0;
let scenarioType = 'hr_interview';
let scenarioConfig = {};
let sessionLanguage = 'en';
let conversationHistory = [];
const authToken = localStorage.getItem('convers_token') || '';
const authHeaders = authToken
  ? { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken }
  : { 'Content-Type': 'application/json' };

// ── DOM Refs ────────────────────────────────────────────────────────────────
const chatContainer  = document.getElementById('chat-container');
const messageInput   = document.getElementById('message-input');
const sendBtn        = document.getElementById('send-btn');
const endSessionBtn  = document.getElementById('end-session-btn');
const sessionStatus  = document.getElementById('session-status');
const scenarioLabel  = document.getElementById('scenario-label');
const timerDisplay   = document.getElementById('session-timer');
const turnDisplay    = document.getElementById('turn-count');
const micBtn         = document.getElementById('mic-btn');
const micIcon        = document.getElementById('mic-icon');
const micRing        = document.getElementById('mic-ring');
const initLoader     = document.getElementById('init-loader');

// ── Scenario Labels ─────────────────────────────────────────────────────────
const SCENARIO_LABELS = {
  hr_interview: '🧑‍💼 HR Interview',
  upsc_test: '🏛️ UPSC Mock',
  customer_support: '📞 Support',
  public_speaking: '🎤 Speaking',
  english_practice: '🌐 English',
  custom: '✨ Custom',
};

// ══════════════════════════════════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════════════════════════════════

(async function boot() {
  // First check if this is a challenge accept flow
  const savedChallenge = sessionStorage.getItem('convers_challenge');
  if (savedChallenge) {
    try {
      const challenge = JSON.parse(savedChallenge);
      scenarioType = challenge.scenario_type || 'hr_interview';
      scenarioConfig = challenge.scenario_config || {};
      sessionLanguage = scenarioConfig.language || 'en';
      sessionStorage.removeItem('convers_challenge'); // consume it
    } catch (e) { /* ignore */ }
  }

  // Then check normal scenario selection (overrides challenge if both present)
  const saved = sessionStorage.getItem('convers_scenario');
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      scenarioType = parsed.scenario_type || scenarioType;
      scenarioConfig = parsed.scenario_config || scenarioConfig;
      sessionLanguage = parsed.language || sessionLanguage;
    } catch (e) { /* defaults */ }
  }
  if (scenarioLabel) scenarioLabel.textContent = SCENARIO_LABELS[scenarioType] || scenarioType;
  await initSession();
})();


// ══════════════════════════════════════════════════════════════════════════════
// SESSION MANAGEMENT
// ══════════════════════════════════════════════════════════════════════════════

async function initSession() {
  try {
    const response = await fetchWithRetry(`${API_BASE}/session/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_type: scenarioType,
        scenario_config: scenarioConfig,
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    sessionId = data.session_id;

    // Remove loader, show chat
    if (initLoader) initLoader.remove();

    // Show opening message
    appendMessage(data.opening_message, 'ai');
    conversationHistory.push({ role: 'assistant', content: data.opening_message });
    turnCount = 1;
    updateTurnDisplay();

    // Update status
    setStatus('active', 'Session Active');
    endSessionBtn.classList.remove('hidden');
    endSessionBtn.classList.add('flex');
    sendBtn.disabled = false;

    // Start timer
    startTimer();

  } catch (err) {
    console.error('Session start failed:', err);
    if (initLoader) {
      initLoader.innerHTML = `
        <span class="material-symbols-outlined text-5xl text-red-400">error</span>
        <p class="text-white/60 text-sm">Could not connect to the backend.</p>
        <button onclick="location.reload()" class="mt-2 px-6 py-2 bg-white/10 hover:bg-white/20 text-white rounded-full text-sm transition">Retry</button>
      `;
    }
  }
}


// ══════════════════════════════════════════════════════════════════════════════
// CHAT — SEND & STREAM
// ══════════════════════════════════════════════════════════════════════════════

async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || !sessionId || isGenerating) return;

  // UI: show user bubble
  appendMessage(text, 'user');
  messageInput.value = '';
  messageInput.style.height = 'auto';
  isGenerating = true;
  sendBtn.disabled = true;

  // UI: show typing indicator
  const typingEl = showTypingIndicator();

  // Create empty AI bubble (hidden until first chunk)
  const aiBubble = createBubble('ai');
  aiBubble.style.display = 'none';

  try {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message: text }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let firstChunk = true;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n').filter(l => l.startsWith('data: '));

      for (const line of lines) {
        const payload = line.slice(6);
        if (payload === '[DONE]') continue;

        if (firstChunk) {
          typingEl.remove();
          aiBubble.style.display = '';
          firstChunk = false;
        }
        aiBubble.textContent += payload;
        scrollToBottom();
      }
    }

    // If no content came through at all
    if (firstChunk) {
      typingEl.remove();
      aiBubble.style.display = '';
      aiBubble.textContent = "I'm sorry, I'm temporarily unable to respond. Please try again.";
    }

    // Track history
    conversationHistory.push({ role: 'user', content: text });
    conversationHistory.push({ role: 'assistant', content: aiBubble.textContent });
    turnCount++;
    updateTurnDisplay();

  } catch (err) {
    console.error('Chat error:', err);
    typingEl.remove();
    aiBubble.style.display = '';
    aiBubble.innerHTML = `
      <span class="text-red-300">Failed to get response.</span>
      <button onclick="retryLast()" class="ml-2 underline text-primary-container text-xs">Retry</button>
    `;
  } finally {
    isGenerating = false;
    sendBtn.disabled = false;
    messageInput.focus();
  }
}

let lastUserMessage = '';
function retryLast() {
  // Remove the AI error bubble AND the user bubble (last 2 wrappers)
  const bubbles = chatContainer.querySelectorAll('.msg-wrapper');
  if (bubbles.length >= 2) {
    bubbles[bubbles.length - 1].remove();  // error bubble (AI)
    bubbles[bubbles.length - 2].remove();  // user message bubble
    // Also undo the history push for the user message
    conversationHistory.splice(-1, 1);
    turnCount = Math.max(0, turnCount - 1);
    updateTurnDisplay();
  } else if (bubbles.length === 1) {
    bubbles[0].remove();
  }
  messageInput.value = lastUserMessage;
  sendMessage();
}


// ══════════════════════════════════════════════════════════════════════════════
// VOICE RECORDING
// ══════════════════════════════════════════════════════════════════════════════

async function toggleRecording() {
  if (isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(audioChunks, { type: 'audio/webm' });
      await transcribeAudio(blob);
    };

    mediaRecorder.start();
    isRecording = true;
    micIcon.textContent = 'stop';
    micBtn.classList.add('text-red-400');
    micBtn.classList.remove('text-white/60');
    micRing.classList.remove('hidden');
  } catch (err) {
    console.error('Mic access denied:', err);
    alert('Microphone access is required for voice input. Please allow it in your browser settings.');
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  isRecording = false;
  micIcon.textContent = 'mic';
  micBtn.classList.remove('text-red-400');
  micBtn.classList.add('text-white/60');
  micRing.classList.add('hidden');
}

async function transcribeAudio(blob) {
  setStatus('processing', 'Transcribing...');
  const formData = new FormData();
  formData.append('audio', blob, 'recording.webm');

  try {
    const response = await fetch(`${API_BASE}/voice/transcribe`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) throw new Error(`Transcription HTTP ${response.status}`);
    const data = await response.json();

    if (data.text && data.text.trim()) {
      messageInput.value = data.text.trim();
      messageInput.dispatchEvent(new Event('input'));
      setStatus('active', 'Session Active');
      // Auto-send after transcription
      sendMessage();
    } else {
      setStatus('active', 'Session Active');
      alert('Could not understand the audio. Please try again.');
    }
  } catch (err) {
    console.error('Transcription failed:', err);
    setStatus('active', 'Session Active');
    alert('Voice transcription failed. Make sure the backend is running with Whisper enabled.');
  }
}


// ══════════════════════════════════════════════════════════════════════════════
// END SESSION & FEEDBACK
// ══════════════════════════════════════════════════════════════════════════════

async function endSession() {
  if (!sessionId || isGenerating) return;

  setStatus('processing', 'Analyzing...');
  endSessionBtn.disabled = true;
  stopTimer();

  try {
    // Generate feedback BEFORE ending session
    const fbResponse = await fetch(`${API_BASE}/feedback/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });

    let feedback = null;
    if (fbResponse.ok) {
      feedback = await fbResponse.json();
    }

    // End session
    const endResponse = await fetch(`${API_BASE}/session/end`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });

    let endData = {};
    if (endResponse.ok) {
      endData = await endResponse.json();
    }

    setStatus('ended', 'Session Ended');

    // Save session to database
    const elapsed = getElapsedSeconds();
    let savedResult = null;
    try {
      const saveResp = await fetch(`${API_BASE}/history/save`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({
          session_id: sessionId,
          scenario_type: scenarioType,
          scenario_config: scenarioConfig,
          history: conversationHistory,
          feedback: feedback || {},
          overall_score: feedback?.overall_score || 0,
          total_turns: turnCount,
          duration_seconds: elapsed,
          difficulty: scenarioConfig.difficulty || 'intermediate',
          language: sessionLanguage,
        }),
      });
      if (saveResp.ok) savedResult = await saveResp.json();
    } catch (e) { console.warn('Session save failed:', e); }

    if (feedback) {
      showFeedbackModal(feedback, endData, savedResult);
    }

  } catch (err) {
    console.error('End session error:', err);
    setStatus('error', 'Error ending session');
    endSessionBtn.disabled = false;
  }
}

function showFeedbackModal(data, endData, savedResult) {
  const modal = document.getElementById('feedback-modal');
  modal.classList.remove('hidden');

  // Overall score
  const overall = data.overall_score || 0;
  document.getElementById('fb-overall').textContent = overall;

  // Animate score ring (264 = full circumference)
  const ring = document.getElementById('fb-score-ring');
  const offset = 264 - (264 * (overall / 10));
  setTimeout(() => { ring.style.transition = 'stroke-dashoffset 1s ease'; ring.style.strokeDashoffset = offset; }, 100);

  // Stats
  document.getElementById('fb-turns').textContent = endData.total_turns || turnCount;
  document.getElementById('fb-fillers').textContent = data.ml_stats?.total_fillers ?? '--';
  document.getElementById('fb-duration').textContent = formatTime(endData.duration_seconds || getElapsedSeconds());

  // Categories
  const catContainer = document.getElementById('fb-categories');
  catContainer.innerHTML = '';
  const catIcons = {
    communication: 'forum', confidence: 'psychology', grammar: 'spellcheck',
    vocabulary: 'dictionary', relevance: 'target',
  };
  const catColors = {
    communication: '#64cefb', confidence: '#a78bfa', grammar: '#34d399',
    vocabulary: '#fbbf24', relevance: '#f472b6',
  };

  if (data.categories) {
    for (const [key, val] of Object.entries(data.categories)) {
      const score = val.score || 0;
      const pct = Math.min(100, score * 10);
      catContainer.innerHTML += `
        <div class="flex items-center gap-3">
          <span class="material-symbols-outlined text-[18px]" style="color:${catColors[key] || '#64cefb'}">${catIcons[key] || 'check_circle'}</span>
          <div class="flex-1">
            <div class="flex justify-between items-center mb-1">
              <span class="text-white/80 text-xs font-medium capitalize">${key}</span>
              <span class="text-white/50 text-xs">${score}/10</span>
            </div>
            <div class="w-full bg-white/10 rounded-full h-1.5">
              <div class="h-1.5 rounded-full transition-all duration-700" style="width:${pct}%; background:${catColors[key] || '#64cefb'}"></div>
            </div>
            <p class="text-white/40 text-[10px] mt-0.5">${val.feedback || ''}</p>
          </div>
        </div>`;
    }
  }

  // Strengths
  const strengthsList = document.getElementById('fb-strengths');
  strengthsList.innerHTML = '';
  (data.strengths || []).forEach(s => {
    const li = document.createElement('li');
    li.className = 'flex items-start gap-1.5';
    li.innerHTML = `<span class="text-green-400 text-xs mt-0.5">✓</span><span>${s}</span>`;
    strengthsList.appendChild(li);
  });

  // Improvements
  const improvementsList = document.getElementById('fb-improvements');
  improvementsList.innerHTML = '';
  (data.improvements || []).forEach(s => {
    const li = document.createElement('li');
    li.className = 'flex items-start gap-1.5';
    li.innerHTML = `<span class="text-orange-400 text-xs mt-0.5">→</span><span>${s}</span>`;
    improvementsList.appendChild(li);
  });

  // AI Narrative
  document.getElementById('fb-narrative').textContent = data.ai_narrative || 'No detailed feedback available.';

  // ── New Feature Buttons ──
  const actionsArea = document.getElementById('fb-extra-actions');
  if (actionsArea) {
    let html = '';

    // Points earned
    if (savedResult?.points_earned) {
      html += `<div class="text-center py-2 px-4 bg-purple-500/15 border border-purple-500/20 rounded-xl"><span class="text-purple-400 font-bold text-lg">+${savedResult.points_earned}</span><span class="text-white/40 text-xs ml-1">points earned</span></div>`;
    }

    // New badges
    if (savedResult?.gamification?.new_badges?.length) {
      savedResult.gamification.new_badges.forEach(b => {
        html += `<div class="text-center py-2 px-4 bg-yellow-500/15 border border-yellow-500/20 rounded-xl"><span class="text-yellow-400 text-sm font-semibold">🏅 New Badge: ${b}</span></div>`;
      });
    }

    // Difficulty progression
    if (overall >= 7.5 && scenarioConfig.difficulty) {
      const nextDiff = { junior: 'intermediate', intermediate: 'senior', senior: 'expert' };
      const next = nextDiff[scenarioConfig.difficulty];
      if (next) {
        html += `<div class="text-center py-2 px-4 bg-green-500/15 border border-green-500/20 rounded-xl"><span class="text-green-400 text-sm">⬆️ Great job! Try <strong>${next}</strong> difficulty next.</span></div>`;
      }
    }

    // Action buttons
    html += `<div class="flex flex-wrap gap-2 justify-center">`;
    html += `<button onclick="exportPDF()" class="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-white/70 transition"><span class="material-symbols-outlined text-[16px]">picture_as_pdf</span>Export PDF</button>`;
    html += `<button onclick="generateResume(this)" class="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-white/70 transition"><span class="material-symbols-outlined text-[16px]">description</span>Build Resume</button>`;

    if (authToken && savedResult?.session_db_id) {
      html += `<button onclick="createChallenge(${savedResult.session_db_id})" class="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-white/70 transition"><span class="material-symbols-outlined text-[16px]">sports_esports</span>Challenge Friend</button>`;
    }

    if (authToken) {
      html += `<a href="dashboard.html" class="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-white/70 transition no-underline"><span class="material-symbols-outlined text-[16px]">dashboard</span>Dashboard</a>`;
    }
    html += `</div>`;

    actionsArea.innerHTML = html;
  }

  // Store feedback data globally for PDF/resume
  window._lastFeedback = data;
  window._lastEndData = endData;
}


// ══════════════════════════════════════════════════════════════════════════════
// UI HELPERS
// ══════════════════════════════════════════════════════════════════════════════

function appendMessage(text, role) {
  const wrapper = document.createElement('div');
  wrapper.className = `msg-wrapper flex w-full ${role === 'user' ? 'justify-end' : 'justify-start'} msg-animate`;

  const bubble = document.createElement('div');
  bubble.className = `max-w-[85%] md:max-w-[75%] px-4 py-3 text-sm leading-relaxed ${role === 'user' ? 'chat-bubble-user font-medium' : 'chat-bubble-ai'}`;
  bubble.textContent = text;

  if (role === 'user') {
    lastUserMessage = text;
    highlightGrammarIssues(bubble, text);
  }

  wrapper.appendChild(bubble);
  chatContainer.appendChild(wrapper);
  scrollToBottom();
  return bubble;
}

function createBubble(role) {
  const wrapper = document.createElement('div');
  wrapper.className = `msg-wrapper flex w-full justify-start msg-animate`;

  const bubble = document.createElement('div');
  bubble.className = 'max-w-[85%] md:max-w-[75%] px-4 py-3 text-sm leading-relaxed chat-bubble-ai';

  wrapper.appendChild(bubble);
  chatContainer.appendChild(wrapper);
  scrollToBottom();
  return bubble;
}

function showTypingIndicator() {
  const wrapper = document.createElement('div');
  wrapper.className = 'msg-wrapper flex w-full justify-start msg-animate';
  wrapper.id = 'typing-indicator';

  wrapper.innerHTML = `
    <div class="chat-bubble-ai px-5 py-4 flex items-center gap-1.5">
      <div class="w-2 h-2 rounded-full bg-white/40 typing-dot"></div>
      <div class="w-2 h-2 rounded-full bg-white/40 typing-dot"></div>
      <div class="w-2 h-2 rounded-full bg-white/40 typing-dot"></div>
    </div>
  `;

  chatContainer.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function setStatus(state, text) {
  const colors = {
    active: 'bg-green-400',
    processing: 'bg-yellow-400 animate-pulse',
    error: 'bg-red-400',
    ended: 'bg-white/30',
  };
  sessionStatus.innerHTML = `<span class="inline-block w-2 h-2 rounded-full ${colors[state] || 'bg-white/30'} mr-1"></span>${text}`;
}

function updateTurnDisplay() {
  if (turnDisplay) turnDisplay.textContent = turnCount;
}

// ── Timer ───────────────────────────────────────────────────────────────────

function startTimer() {
  sessionStartTime = Date.now();
  timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
    if (timerDisplay) timerDisplay.textContent = formatTime(elapsed);
  }, 1000);
}

function stopTimer() {
  if (timerInterval) clearInterval(timerInterval);
}

function getElapsedSeconds() {
  if (!sessionStartTime) return 0;
  return Math.floor((Date.now() - sessionStartTime) / 1000);
}

function formatTime(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = Math.floor(totalSeconds % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// ── Auto-resize textarea ────────────────────────────────────────────────────

messageInput.addEventListener('input', function () {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 128) + 'px';
  sendBtn.disabled = !this.value.trim() || isGenerating;
});

// ── Fetch with retry ────────────────────────────────────────────────────────

async function fetchWithRetry(url, options, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      return await fetch(url, options);
    } catch (err) {
      if (i === retries - 1) throw err;
      await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// EVENT LISTENERS
// ══════════════════════════════════════════════════════════════════════════════

sendBtn.addEventListener('click', sendMessage);

messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

endSessionBtn.addEventListener('click', endSession);

micBtn.addEventListener('click', toggleRecording);

// Global keyboard shortcuts
document.addEventListener('keydown', (e) => {
  // Ctrl+M → toggle mic
  if (e.ctrlKey && e.key === 'm') {
    e.preventDefault();
    toggleRecording();
  }
  // Ctrl+E → end session (with confirm so it's not accidental)
  if (e.ctrlKey && e.key === 'e' && sessionId && !isGenerating) {
    e.preventDefault();
    if (confirm('End this session and view your feedback?')) {
      endSession();
    }
  }
});


// ══════════════════════════════════════════════════════════════════════════════
// PDF EXPORT (client-side using jsPDF)
// ══════════════════════════════════════════════════════════════════════════════

async function exportPDF() {
  // Dynamically load jsPDF
  if (!window.jspdf) {
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.2/jspdf.umd.min.js';
    document.head.appendChild(script);
    await new Promise(r => script.onload = r);
  }

  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();
  const fb = window._lastFeedback || {};
  const ed = window._lastEndData || {};

  let y = 20;
  doc.setFontSize(20);
  doc.setTextColor(0, 86, 113);
  doc.text('Convers — Session Report', 20, y); y += 12;

  doc.setFontSize(10);
  doc.setTextColor(100, 100, 100);
  doc.text(`Scenario: ${SCENARIO_LABELS[scenarioType] || scenarioType}  |  ${new Date().toLocaleDateString()}`, 20, y); y += 8;
  doc.text(`Turns: ${turnCount}  |  Duration: ${formatTime(getElapsedSeconds())}  |  Language: ${sessionLanguage}`, 20, y); y += 12;

  doc.setFontSize(28); doc.setTextColor(0, 0, 0);
  doc.text(`${fb.overall_score || 0}/10`, 20, y); y += 12;

  // Categories
  if (fb.categories) {
    doc.setFontSize(12); doc.setTextColor(0, 86, 113);
    doc.text('Category Scores', 20, y); y += 7;
    doc.setFontSize(10); doc.setTextColor(60, 60, 60);
    for (const [k, v] of Object.entries(fb.categories)) {
      doc.text(`• ${k}: ${v.score}/10 — ${v.feedback || ''}`, 24, y); y += 6;
      if (y > 270) { doc.addPage(); y = 20; }
    }
    y += 4;
  }

  // Strengths
  if (fb.strengths?.length) {
    doc.setFontSize(12); doc.setTextColor(0, 128, 0);
    doc.text('Strengths', 20, y); y += 7;
    doc.setFontSize(10); doc.setTextColor(60, 60, 60);
    fb.strengths.forEach(s => { doc.text(`✓ ${s}`, 24, y); y += 6; if(y>270){doc.addPage();y=20;} });
    y += 4;
  }

  // Improvements
  if (fb.improvements?.length) {
    doc.setFontSize(12); doc.setTextColor(200, 120, 0);
    doc.text('Areas to Improve', 20, y); y += 7;
    doc.setFontSize(10); doc.setTextColor(60, 60, 60);
    fb.improvements.forEach(s => { doc.text(`→ ${s}`, 24, y); y += 6; if(y>270){doc.addPage();y=20;} });
    y += 4;
  }

  // Narrative
  if (fb.ai_narrative) {
    doc.setFontSize(12); doc.setTextColor(0, 86, 113);
    doc.text('AI Coach Feedback', 20, y); y += 7;
    doc.setFontSize(9); doc.setTextColor(60, 60, 60);
    const lines = doc.splitTextToSize(fb.ai_narrative, 170);
    lines.forEach(l => { doc.text(l, 24, y); y += 5; if(y>270){doc.addPage();y=20;} });
  }

  doc.save(`convers-report-${Date.now()}.pdf`);
}


// ══════════════════════════════════════════════════════════════════════════════
// RESUME BUILDER
// ══════════════════════════════════════════════════════════════════════════════

async function generateResume(btnEl) {
  const btn = btnEl || document.querySelector('[onclick*="generateResume"]');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="animate-spin material-symbols-outlined text-[16px]">progress_activity</span> Generating...';
  }

  try {
    const resp = await fetch(`${API_BASE}/resume/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        history: conversationHistory,
        job_role: scenarioConfig.job_role || 'Software Engineer',
      }),
    });

    if (!resp.ok) throw new Error('Resume generation failed');
    const data = await resp.json();

    // Show in a new modal
    const m = document.createElement('div');
    m.className = 'fixed inset-0 z-[70] bg-black/85 backdrop-blur-sm flex items-center justify-center p-4';
    m.innerHTML = `
      <div style="background:rgba(30,30,30,0.95);border:1px solid rgba(62,72,78,0.6);backdrop-filter:blur(12px);" class="max-w-2xl w-full rounded-3xl p-6 max-h-[85vh] overflow-y-auto">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-xl font-bold text-white flex items-center gap-2"><span class="material-symbols-outlined text-primary-container">description</span>Resume Bullet Points</h2>
          <button onclick="this.closest('.fixed').remove()" class="text-white/40 hover:text-white"><span class="material-symbols-outlined">close</span></button>
        </div>
        <div class="prose prose-invert text-sm leading-relaxed text-white/80 whitespace-pre-wrap">${data.resume_bullets}</div>
        <button onclick="navigator.clipboard.writeText(this.parentElement.querySelector('.prose').textContent);this.textContent='Copied!'" class="mt-4 px-4 py-2 bg-primary-container text-on-primary-container rounded-lg text-sm font-semibold">Copy to Clipboard</button>
      </div>`;
    document.body.appendChild(m);
  } catch (e) {
    alert('Resume generation failed: ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span class="material-symbols-outlined text-[16px]">description</span>Build Resume';
    }
  }
}


// ══════════════════════════════════════════════════════════════════════════════
// CHALLENGE FRIEND
// ══════════════════════════════════════════════════════════════════════════════

async function createChallenge(sessionDbId) {
  try {
    const resp = await fetch(`${API_BASE}/history/challenge/create?session_db_id=${sessionDbId}`, {
      method: 'POST',
      headers: authHeaders,
    });
    if (!resp.ok) throw new Error('Failed');
    const data = await resp.json();

    const m = document.createElement('div');
    m.className = 'fixed inset-0 z-[70] bg-black/85 backdrop-blur-sm flex items-center justify-center p-4';
    m.innerHTML = `
      <div style="background:rgba(30,30,30,0.95);border:1px solid rgba(62,72,78,0.6);backdrop-filter:blur(12px);" class="max-w-sm w-full rounded-3xl p-6 text-center">
        <span class="material-symbols-outlined text-5xl text-primary-container mb-3">sports_esports</span>
        <h2 class="text-xl font-bold text-white mb-2">Challenge Created!</h2>
        <p class="text-white/50 text-sm mb-4">Share this code with a friend:</p>
        <div class="bg-white/10 rounded-xl p-4 text-3xl font-mono font-bold text-primary-container tracking-[0.3em]">${data.challenge_code}</div>
        <button onclick="navigator.clipboard.writeText('${data.challenge_code}');this.textContent='Copied!'" class="mt-4 px-6 py-2 bg-primary-container text-on-primary-container rounded-lg text-sm font-semibold">Copy Code</button>
        <button onclick="this.closest('.fixed').remove()" class="mt-2 block mx-auto text-white/40 text-sm hover:text-white">Close</button>
      </div>`;
    document.body.appendChild(m);
  } catch (e) {
    alert('Challenge creation failed');
  }
}


// ══════════════════════════════════════════════════════════════════════════════
// GRAMMAR HIGHLIGHTS (underlines grammar issues in user messages)
// ══════════════════════════════════════════════════════════════════════════════

function highlightGrammarIssues(bubbleEl, text) {
  // Common filler/grammar patterns
  const patterns = [
    { regex: /\b(um|uh|hmm|like|you know|basically|actually|literally)\b/gi, cls: 'text-yellow-400 underline decoration-wavy decoration-yellow-400/50', title: 'Filler word' },
    { regex: /\bi\b(?=[^''])/g, cls: 'text-orange-400 underline decoration-wavy decoration-orange-400/50', title: 'Should be capitalized: I' },
  ];

  let html = text;
  patterns.forEach(p => {
    html = html.replace(p.regex, (match) => `<span class="${p.cls}" title="${p.title}">${match}</span>`);
  });

  if (html !== text) {
    bubbleEl.innerHTML = html;
  }
}

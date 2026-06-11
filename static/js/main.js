/* ══════════════════════════════════════════
   SmartSpend AI — main.js
   Handles: theme, sidebar, charts, chat, UI
   ══════════════════════════════════════════ */

// ── Theme Toggle ──────────────────────────
const html = document.documentElement;

function getTheme() {
  // Server is source of truth — html[data-theme] is set by Flask from DB
  // localStorage is only used as instant-apply before page load
  return html.dataset.theme || localStorage.getItem('ss_theme') || 'dark';
}

function setTheme(t) {
  html.dataset.theme = t;
  localStorage.setItem('ss_theme', t);
  // Update toggle button icon
  const btn = document.getElementById('themeToggle');
  if (btn) {
    btn.innerHTML = t === 'dark'
      ? '<i class="fa-solid fa-sun"></i>'
      : '<i class="fa-solid fa-moon"></i>';
    btn.title = t === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode';
  }
  // Persist to server so next page load matches
  fetch('/api/theme/set', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({theme: t})
  }).catch(() => {});
}

// Apply theme from server setting immediately (no flash)
(function() {
  const t = html.dataset.theme || localStorage.getItem('ss_theme') || 'dark';
  html.dataset.theme = t;
  localStorage.setItem('ss_theme', t);
})();

document.addEventListener('DOMContentLoaded', () => {
  // Sync icon to current theme
  setTheme(getTheme());

  // Theme button
  const themeBtn = document.getElementById('themeToggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      setTheme(getTheme() === 'dark' ? 'light' : 'dark');
    });
  }

  // ── Sidebar Mobile Toggle ─────────────────
  const sidebar   = document.getElementById('sidebar');
  const toggler   = document.getElementById('sidebarToggle');
  const overlay   = document.getElementById('sidebarOverlay');

  if (toggler && sidebar) {
    toggler.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      if (overlay) overlay.classList.toggle('show');
    });
  }
  if (overlay) {
    overlay.addEventListener('click', () => {
      sidebar.classList.remove('open');
      overlay.classList.remove('show');
    });
  }

  // ── Auto-dismiss flash messages ───────────
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => el.style.opacity = '0', 4000);
    setTimeout(() => el.remove(), 4400);
  });

  // ── Animate stat numbers ──────────────────
  document.querySelectorAll('.stat-value[data-value]').forEach(el => {
    const target = parseFloat(el.dataset.value);
    const prefix = el.dataset.prefix || '';
    const suffix = el.dataset.suffix || '';
    let start = 0;
    const step = target / 40;
    const timer = setInterval(() => {
      start += step;
      if (start >= target) { start = target; clearInterval(timer); }
      el.textContent = prefix + formatNumber(start) + suffix;
    }, 30);
  });

  // ── Progress bar animations ───────────────
  document.querySelectorAll('.progress-fill[data-width]').forEach(el => {
    setTimeout(() => { el.style.width = el.dataset.width + '%'; }, 200);
  });

  // ── Stagger card animations ───────────────
  document.querySelectorAll('.stat-card, .card').forEach((el, i) => {
    el.style.animationDelay = (i * 0.07) + 's';
  });

});

// ── Number Formatter ──────────────────────
function formatNumber(n) {
  if (n >= 1e7) return (n / 1e7).toFixed(1) + 'Cr';
  if (n >= 1e5) return (n / 1e5).toFixed(1) + 'L';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return Math.round(n).toLocaleString('en-IN');
}

// ── Chart Defaults (dark/light aware) ─────
function getChartColors() {
  const isDark = getTheme() === 'dark';
  return {
    text:    isDark ? '#94a3b8' : '#475569',
    grid:    isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
    tooltip: isDark ? '#1e293b' : '#ffffff',
  };
}

function applyChartDefaults() {
  const c = getChartColors();
  Chart.defaults.color = c.text;
  Chart.defaults.borderColor = c.grid;
  Chart.defaults.plugins.tooltip.backgroundColor = c.tooltip;
  Chart.defaults.plugins.tooltip.titleColor = getTheme() === 'dark' ? '#f1f5f9' : '#1e293b';
  Chart.defaults.plugins.tooltip.bodyColor  = c.text;
  Chart.defaults.plugins.tooltip.borderColor = c.grid;
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 10;
  Chart.defaults.plugins.legend.labels.boxWidth = 12;
  Chart.defaults.plugins.legend.labels.padding = 16;
  Chart.defaults.font.family = "'DM Sans', sans-serif";
}
applyChartDefaults();

// Category colours
const CAT_COLORS = {
  Food:          '#f97316',
  Shopping:      '#a855f7',
  Bills:         '#ef4444',
  Travel:        '#06b6d4',
  Entertainment: '#ec4899',
  Education:     '#3b82f6',
  Health:        '#22c55e',
  Others:        '#94a3b8',
};
function catColor(name) { return CAT_COLORS[name] || '#6366f1'; }

// ── Build Monthly Bar/Line Chart ──────────
function buildMonthlyChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !data || !data.length) return;
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.month),
      datasets: [
        {
          label: 'Income',
          data: data.map(d => d.income),
          backgroundColor: 'rgba(34,197,94,0.7)',
          borderColor: '#22c55e',
          borderWidth: 2,
          borderRadius: 8,
          borderSkipped: false,
        },
        {
          label: 'Expenses',
          data: data.map(d => d.expenses),
          backgroundColor: 'rgba(239,68,68,0.7)',
          borderColor: '#ef4444',
          borderWidth: 2,
          borderRadius: 8,
          borderSkipped: false,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: {
        x: { grid: { display: false } },
        y: {
          grid: { color: getChartColors().grid },
          ticks: { callback: v => '₹' + formatNumber(v) }
        }
      }
    }
  });
}

// ── Build Pie/Doughnut Chart ───────────────
function buildPieChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !data) return;
  const labels = Object.keys(data);
  const values = Object.values(data);
  if (!labels.length) return;
  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: labels.map(catColor),
        borderWidth: 2,
        borderColor: getTheme() === 'dark' ? '#0a0e1a' : '#f0f4ff',
        hoverOffset: 10,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: {
        legend: { position: 'bottom' },
        tooltip: {
          callbacks: {
            label: ctx => ` ₹${ctx.parsed.toLocaleString('en-IN')} (${((ctx.parsed / ctx.dataset.data.reduce((a,b)=>a+b,0))*100).toFixed(1)}%)`
          }
        }
      }
    }
  });
}

// ── Build Line Trend Chart ─────────────────
function buildTrendChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !data || !data.length) return;
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.month),
      datasets: [
        {
          label: 'Income',
          data: data.map(d => d.income),
          borderColor: '#22c55e',
          backgroundColor: 'rgba(34,197,94,0.08)',
          fill: true,
          tension: 0.4,
          pointBackgroundColor: '#22c55e',
          pointRadius: 5,
        },
        {
          label: 'Expenses',
          data: data.map(d => d.expenses),
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239,68,68,0.08)',
          fill: true,
          tension: 0.4,
          pointBackgroundColor: '#ef4444',
          pointRadius: 5,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: {
        x: { grid: { display: false } },
        y: {
          grid: { color: getChartColors().grid },
          ticks: { callback: v => '₹' + formatNumber(v) }
        }
      }
    }
  });
}

// ── AI Chat Widget ─────────────────────────
function toggleChat() {
  const w = document.getElementById('chatWidget');
  if (w) w.classList.toggle('open');
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const msgs  = document.getElementById('chatMessages');
  if (!input || !msgs) return;
  const text = input.value.trim();
  if (!text) return;
  input.value = '';

  // User bubble
  msgs.innerHTML += `<div class="chat-msg user"><span>${escapeHtml(text)}</span></div>`;

  // Thinking bubble
  const thinkId = 'think_' + Date.now();
  msgs.innerHTML += `<div class="chat-msg bot" id="${thinkId}"><span>⏳ Thinking...</span></div>`;
  msgs.scrollTop = msgs.scrollHeight;

  try {
    const res  = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    const el   = document.getElementById(thinkId);
    if (el) el.querySelector('span').textContent = data.reply || '🤖 Sorry, I couldn\'t process that.';
  } catch {
    const el = document.getElementById(thinkId);
    if (el) el.querySelector('span').textContent = '❌ Connection error. Please try again.';
  }
  msgs.scrollTop = msgs.scrollHeight;
}

// ── FAQ Accordion ──────────────────────────
function toggleFaq(el) {
  const item = el.closest('.faq-item');
  document.querySelectorAll('.faq-item.open').forEach(i => { if (i !== item) i.classList.remove('open'); });
  item.classList.toggle('open');
}

// ── Delete Confirmation ────────────────────
function confirmDelete(formId) {
  if (confirm('Are you sure you want to delete this? This cannot be undone.')) {
    document.getElementById(formId).submit();
  }
}

// ── Modal Helpers ──────────────────────────
function openModal(id) {
  document.getElementById(id).classList.add('open');
  document.getElementById(id).style.display = 'flex';
}
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
  document.getElementById(id).style.display = 'none';
}

// ── Utility ───────────────────────────────
function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
/* ─── Global helpers (used by income, budget, etc.) ─── */
function openModal(id) {
  // used by pages OTHER than dashboard
  const m = document.getElementById(id);
  if (!m) return;
  m.style.display = 'flex';
  m.classList.add('open');
  const ov = document.getElementById('modalOverlay');
  if (ov) ov.classList.add('show');
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.style.display = 'none';
  m.classList.remove('open');
  const ov = document.getElementById('modalOverlay');
  if (ov) ov.classList.remove('show');
}
function confirmDelete(formId) {
  if (confirm('Are you sure? This cannot be undone.')) {
    document.getElementById(formId).submit();
  }
}
function toggleFaq(el) {
  const item = el.closest('.faq-item');
  document.querySelectorAll('.faq-item.open').forEach(i => { if(i!==item) i.classList.remove('open'); });
  item.classList.toggle('open');
}

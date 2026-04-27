const POLL_MS = 200;

const POSTURE_LABELS = {
  good:               'GOOD',
  slouching_forward:  'SLOUCHING',
  hyperextended:      'HYPEREXTENDED',
  leaning_right:      'LEANING RIGHT',
  leaning_left:       'LEANING LEFT',
  calibrating:        'CALIBRATING',
  unknown:            '—',
};

const STATE_CLASS = {
  good:              'state-good',
  slouching_forward: 'state-bad',
  hyperextended:     'state-warning',
  leaning_right:     'state-warning',
  leaning_left:      'state-warning',
  calibrating:       'state-calibrating',
  unknown:           'state-unknown',
};

let scoreChart = null;

function formatDuration(s) {
  if (s == null || s === 0) return '—';
  const m   = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}m ${String(sec).padStart(2, '0')}s`;
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function angleToPercent(deg) {
  // maps -30..+30 → 0..100 (%) of gauge track
  return ((clamp(deg, -30, 30) + 30) / 60) * 100;
}

function updateDevices(devices) {
  const roles = ['upper', 'lower'];
  let connectedCount = 0;

  roles.forEach(role => {
    const isConnected = devices[role];
    if (isConnected) connectedCount++;

    const dot    = document.getElementById(`dot-${role}`);
    const status = document.getElementById(`status-${role}`);

    dot.className = 'device-dot ' + (isConnected ? 'connected' : 'searching');
    status.textContent = isConnected ? 'Connected' : 'Searching…';
  });

  // Update banner
  const banner = document.getElementById('connection-banner');
  if (connectedCount === 2) {
    banner.textContent = '2 / 2 Connected';
    banner.className   = 'connection-banner connected';
  } else if (connectedCount === 1) {
    banner.textContent = '1 / 2 Connected';
    banner.className   = 'connection-banner partial';
  } else {
    banner.textContent = 'Searching for sensors…';
    banner.className   = 'connection-banner disconnected';
  }

  // Render log (newest first — flex-direction: column-reverse handles display)
  const logEl = document.getElementById('ble-log');
  logEl.innerHTML = (devices.log ?? []).map(entry =>
    `<span class="log-line"><span class="log-time">${entry.t}</span>${entry.msg}</span>`
  ).join('');
}

async function updateLive() {
  try {
    const [statusRes, sessionRes, devicesRes] = await Promise.all([
      fetch('/api/status'),
      fetch('/api/session/current'),
      fetch('/api/devices'),
    ]);
    const status  = await statusRes.json();
    const session = await sessionRes.json();
    const devices = await devicesRes.json();

    updateDevices(devices);

    // Hero card state class
    const heroCard  = document.getElementById('hero-card');
    const heroLabel = document.getElementById('hero-label');
    const heroSub   = document.getElementById('hero-sub');
    const prevCls   = [...heroCard.classList].find(c => c.startsWith('state-'));
    if (prevCls) heroCard.classList.remove(prevCls);
    heroCard.classList.add(STATE_CLASS[status.posture_state] ?? 'state-unknown');
    heroLabel.textContent = POSTURE_LABELS[status.posture_state] ?? '—';
    heroSub.textContent = status.posture_state === 'calibrating'
      ? 'Sit up straight — calibrating...'
      : 'Current Posture';

    // Angle gauges
    const pitchPct = angleToPercent(status.delta_pitch ?? 0);
    const rollPct  = angleToPercent(status.delta_roll  ?? 0);
    document.getElementById('gauge-pitch').style.left = `${pitchPct}%`;
    document.getElementById('gauge-roll').style.left  = `${rollPct}%`;
    document.getElementById('val-pitch').textContent  = `${(status.delta_pitch ?? 0).toFixed(1)}°`;
    document.getElementById('val-roll').textContent   = `${(status.delta_roll  ?? 0).toFixed(1)}°`;

    // Session stats
    document.getElementById('stat-duration').textContent =
      formatDuration(session.duration_s);
    document.getElementById('stat-good-pct').textContent =
      session.good_pct != null ? `${session.good_pct.toFixed(1)}%` : '—';
    document.getElementById('stat-score').textContent =
      session.score != null ? `${Math.round(session.score)}` : '—';

  } catch (_) {
    // network error — keep displaying last known state
  }
}

async function loadHistory() {
  const res      = await fetch('/api/session/history');
  const sessions = await res.json();

  // Score line chart (newest sessions on the right)
  const ordered = [...sessions].reverse();
  const labels  = ordered.map(s => (s.start_time ?? '').slice(0, 10));
  const scores  = ordered.map(s => s.score ?? 0);
  const pointColors = scores.map(s =>
    s >= 70 ? '#16A34A' : s >= 40 ? '#D97706' : '#DC2626'
  );

  const ctx = document.getElementById('chart-score').getContext('2d');
  if (scoreChart) scoreChart.destroy();
  scoreChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Posture Score',
        data: scores,
        borderColor: '#16A34A',
        backgroundColor: 'rgba(22,163,74,0.08)',
        tension: 0.3,
        pointRadius: 5,
        pointBackgroundColor: pointColors,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: {
          min: 0, max: 100,
          grid: { color: '#F1F5F9' },
          ticks: { color: '#64748B' },
        },
        x: {
          grid: { display: false },
          ticks: { color: '#64748B' },
        },
      },
    },
  });

  // Session table (10 most recent)
  const tbody = document.getElementById('session-tbody');
  tbody.innerHTML = sessions.slice(0, 10).map(s => {
    const score = s.score ?? 0;
    const cls   = score >= 70 ? 'score-good' : score >= 40 ? 'score-warning' : 'score-bad';
    const date  = (s.start_time ?? '').slice(0, 16).replace('T', ' ');
    return `<tr>
      <td>${date}</td>
      <td>${formatDuration(s.duration_s)}</td>
      <td><span class="score-badge ${cls}">${Math.round(score)}</span></td>
      <td>${s.good_pct != null ? s.good_pct.toFixed(1) + '%' : '—'}</td>
    </tr>`;
  }).join('');
}

// ── Nav switching ─────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    const panel = btn.dataset.panel;
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.panel').forEach(p => p.classList.add('hidden'));
    document.getElementById(`panel-${panel}`)?.classList.remove('hidden');
    document.getElementById('panel-title').textContent =
      panel === 'live' ? 'Live Monitor' : 'Session History';
    if (panel === 'history') loadHistory();
  });
});

// ── Re-zero button ────────────────────────────────────────────────────────
document.getElementById('btn-zero').addEventListener('click', async () => {
  await fetch('/api/zero', { method: 'POST' });
});

// ── Retry buttons ─────────────────────────────────────────────────────────
['upper', 'lower'].forEach(role => {
  document.getElementById(`btn-retry-${role}`).addEventListener('click', async () => {
    await fetch(`/api/devices/${role}/retry`, { method: 'POST' });
  });
});

// ── Start polling ─────────────────────────────────────────────────────────
setInterval(updateLive, POLL_MS);
updateLive();

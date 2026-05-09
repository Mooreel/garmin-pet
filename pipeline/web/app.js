const state = {
  config: null,
  bridge: null,
  bridgePayload: null,
  devices: [],
  configHistory: [],
  watch: null,
  uploadSelection: null,
  petdexResults: [],
  petdexSelected: null,
  petdexMode: 'popular',
  petdexError: null,
  petdexRequestId: 0,
  petdexSearchTimer: null,
  uploadRequestId: 0,
  watchPollTimer: null,
  watchPollInFlight: false,
  previewScreen: 'pet',
  previewMessage: '',
  previewAnimationTimer: null,
  previewAnimationStartedAt: Date.now(),
  previewAnimationKey: '',
  petAssetVersion: Date.now(),
  security: {
    ok: false,
    checkedAt: null,
  },
};

const $ = (id) => document.getElementById(id);
const DEVICE_FRAME_ASSET_VERSION = Date.now();

function log(message, payload) {
  const text = payload ? `${message}\n${typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2)}` : message;
  const logPanel = $('log');
  logPanel.textContent = text;
  window.requestAnimationFrame(() => {
    logPanel.scrollTop = logPanel.scrollHeight;
  });
}

const STEP_LABELS = {
  connect: 'Connect',
  upload: 'Pet',
  theme: 'Setup',
  preview: 'Preview',
  build: 'Build',
  deploy: 'Deploy',
};

const STEP_ORDER = Object.keys(STEP_LABELS);
const WATCH_POLL_FAST_MS = 1800;
const WATCH_POLL_READY_MS = 6000;
const WATCH_POLL_HIDDEN_MS = 5000;
const WATCH_POLL_ERROR_MS = 7000;
const PREVIEW_ANIMATION_MS = 180;
const BUTTON_SUCCESS_MS = 760;

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function actionButton(buttonOrId) {
  if (!buttonOrId) return null;
  return typeof buttonOrId === 'string' ? $(buttonOrId) : buttonOrId;
}

function rememberButtonLabel(button) {
  if (button && !button.dataset.idleLabel) {
    button.dataset.idleLabel = button.textContent.trim();
  }
}

function setButtonBusy(buttonOrId, label = 'Working') {
  const button = actionButton(buttonOrId);
  if (!button) return null;
  rememberButtonLabel(button);
  button.classList.remove('buttonSuccess');
  button.classList.add('buttonWorking');
  button.disabled = true;
  button.textContent = label;
  return button;
}

function resetActionButton(buttonOrId, label) {
  const button = actionButton(buttonOrId);
  if (!button) return;
  button.classList.remove('buttonWorking', 'buttonSuccess');
  button.textContent = label || button.dataset.idleLabel || button.textContent;
  button.disabled = false;
}

async function completeButton(buttonOrId, successLabel = 'Done', nextLabel) {
  const button = actionButton(buttonOrId);
  if (!button) return;
  rememberButtonLabel(button);
  button.classList.remove('buttonWorking');
  button.classList.add('buttonSuccess');
  button.disabled = true;
  button.textContent = successLabel;
  await sleep(BUTTON_SUCCESS_MS);
  button.classList.remove('buttonSuccess');
  button.textContent = nextLabel || button.dataset.idleLabel || button.textContent;
  button.disabled = false;
}

function mark(step, kind) {
  document.querySelectorAll('.step').forEach((item) => {
    if (item.dataset.step === step) item.className = `step ${kind}`;
  });
  updateRunMeter();
}

function updateRunMeter() {
  const steps = Array.from(document.querySelectorAll('.step'));
  const done = steps.filter((item) => item.classList.contains('done')).length;
  const active = steps.find((item) => item.classList.contains('active')) || steps.find((item) => item.classList.contains('error'));
  const activeKey = active?.dataset.step || 'connect';
  $('activeStepLabel').textContent = STEP_LABELS[activeKey] || activeKey;
  $('flowMeter').style.width = `${Math.round((done / STEP_ORDER.length) * 100)}%`;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Accept')) headers.set('Accept', 'application/json');
  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    const isHtml = text.trimStart().startsWith('<');
    const message = isHtml
      ? 'Search is waiting for the local pipeline API.'
      : 'The local pipeline API returned invalid data.';
    throw {
      ok: false,
      code: isHtml ? 'api-html' : 'api-invalid-json',
      message,
      detail: isHtml ? `API request returned HTML for ${path}.` : `API request returned invalid JSON for ${path}.`,
    };
  }
  if (!response.ok || payload.ok === false) {
    throw payload;
  }
  return payload;
}

function applyTheme(theme) {
  const root = document.documentElement;
  root.style.setProperty('--device-accent', theme.accent || '#9A6CFF');
  root.style.setProperty('--device-good', theme.good || '#42E76F');
  root.style.setProperty('--device-warn', theme.warn || '#FFA754');
  root.style.setProperty('--device-panel', theme.panel || '#15181D');
  renderWatchPreview();
}

function applyDeviceFrame(device) {
  const frame = device?.frame || state.devices.find((item) => item.id === 'fr265s')?.frame;
  if (!frame) return;
  const screen = frame.screen || {};
  const frameWidth = Number(frame.width) || 571;
  const frameHeight = Number(frame.height) || 785;
  const screenX = Number(screen.x) || 113;
  const screenY = Number(screen.y) || 214;
  const screenWidth = Number(screen.width) || device?.screen?.width || 360;
  const screenHeight = Number(screen.height) || device?.screen?.height || 360;
  const shape = device?.screen?.shape || 'round';
  const watchFrame = $('watchFrame');
  const watchScreen = $('watchScreen');

  watchFrame.style.backgroundImage = 'none';
  watchFrame.style.setProperty('--watch-frame-image', `url("${versionedUrl(frame.image, DEVICE_FRAME_ASSET_VERSION)}")`);
  watchFrame.style.aspectRatio = `${frameWidth} / ${frameHeight}`;
  watchFrame.style.setProperty('--screen-left', `${(screenX / frameWidth) * 100}%`);
  watchFrame.style.setProperty('--screen-top', `${(screenY / frameHeight) * 100}%`);
  watchFrame.style.setProperty('--screen-width', `${(screenWidth / frameWidth) * 100}%`);
  watchFrame.style.setProperty('--screen-height', `${(screenHeight / frameHeight) * 100}%`);
  watchScreen.style.borderRadius = shape === 'round' ? '50%' : '8%';
}

function updateDevicePreview() {
  const selected = state.devices.find((item) => item.id === $('device').value) || state.devices[0];
  if (!selected) return;
  $('deviceName').textContent = selected.name;
  $('deviceSize').textContent = `${selected.screen.width} x ${selected.screen.height} ${selected.screen.shape || 'screen'}`;
  $('sheetWatch').textContent = selected.name;
  applyDeviceFrame(selected);
  renderWatchPreview();
}

function fillConfig(config) {
  state.config = config;
  const theme = config.theme || {};
  $('bridgeUrl').value = config.bridgeUrl || '';
  $('petDisplayName').value = config.petDisplayName || 'Codex Pet';
  $('accent').value = theme.accent || '#9A6CFF';
  $('good').value = theme.good || '#42E76F';
  $('warn').value = theme.warn || '#FFA754';
  $('panel').value = theme.panel || '#111216';
  state.previewMessage = config.petDisplayName ? `${config.petDisplayName} is ready for Codex updates` : 'Latest Codex message appears here';
  $('sheetPet').textContent = $('petDisplayName').value || 'Codex Pet';
  $('sheetBridge').textContent = config.bridgeUrl ? compactUrl(config.bridgeUrl) : 'Not saved';
  applyTheme(theme);
  renderBridgeStatus();
}

function applyConfig(config) {
  fillConfig(config);
  if (config.device) $('device').value = config.device;
  updateDevicePreview();
}

function updateConfigHistory(history) {
  state.configHistory = Array.isArray(history) ? history : [];
  renderConfigHistory();
}

function collectConfig() {
  return {
    device: $('device').value,
    developerKey: state.config?.developerKey || 'build/developer_key.der',
    bridgeMode: 'auto',
    bridgeUrl: state.bridge?.url || $('bridgeUrl').value.trim(),
    petDisplayName: $('petDisplayName').value.trim() || 'Codex Pet',
    theme: {
      surface: '#000000',
      panel: $('panel').value,
      selection: state.config?.theme?.selection || '#251B5F',
      ink: '#FFFFFF',
      subtle: '#A8A6B6',
      accent: $('accent').value,
      review: '#32C8FF',
      good: $('good').value,
      warn: $('warn').value,
    },
  };
}

function compactUrl(value) {
  if (!value) return 'Not saved';
  try {
    const url = new URL(value);
    const token = url.searchParams.has('token') ? '?token=...' : url.search;
    return `${url.protocol}//${url.host}${url.pathname}${token}`;
  } catch {
    return value.length > 42 ? `${value.slice(0, 39)}...` : value;
  }
}

function renderBridgeStatus() {
  if (!$('bridgeMode')) return;
  const bridge = state.bridge || {};
  const port = bridge.port || '';
  const host = bridge.host || '';
  if (bridge.samePort && bridge.lanReachableFromMac === false) {
    $('bridgeMode').textContent = `LAN bridge not reachable on ${host || 'Mac'}${port ? `:${port}` : ''}. Restart with scripts/start.sh.`;
  } else if (bridge.samePort) {
    $('bridgeMode').textContent = `Auto: same server port${port ? ` ${port}` : ''}${host ? ` on ${host}` : ''}. If the watch shows -300, rebuild and check iPhone Local Network/WiFi.`;
  } else {
    $('bridgeMode').textContent = 'Auto bridge endpoint will be generated during build.';
  }
  $('sheetBridge').textContent = $('bridgeUrl').value.trim() ? compactUrl($('bridgeUrl').value.trim()) : 'Auto bridge';
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));
}

function cssColor(value, fallback) {
  const color = String(value || '').trim();
  return /^#[0-9a-f]{6}$/i.test(color) ? color : fallback;
}

function petStillPreviewUrl() {
  return versionedUrl('/resources/images/pet_large_idle_0.png', state.petAssetVersion);
}

function formatHistoryTime(value) {
  if (!value) return 'Saved locally';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function deviceNameFor(id) {
  return state.devices.find((item) => item.id === id)?.name || id || 'Garmin watch';
}

function versionedUrl(url, version) {
  const separator = String(url).includes('?') ? '&' : '?';
  return `${url}${separator}v=${encodeURIComponent(String(version))}`;
}

function selectedDevice() {
  return state.devices.find((item) => item.id === $('device').value) || state.devices[0] || null;
}

function previewConfig() {
  const current = state.config || {};
  const theme = current.theme || {};
  return {
    ...current,
    device: $('device').value || current.device,
    bridgeUrl: $('bridgeUrl').value.trim() || current.bridgeUrl || '',
    petDisplayName: $('petDisplayName').value.trim() || current.petDisplayName || 'Codex Pet',
    theme: {
      ...theme,
      surface: '#000000',
      panel: $('panel').value || theme.panel || '#111216',
      selection: theme.selection || '#251B5F',
      ink: '#FFFFFF',
      subtle: '#A8A6B6',
      accent: $('accent').value || theme.accent || '#9A6CFF',
      review: theme.review || '#32C8FF',
      good: $('good').value || theme.good || '#42E76F',
      warn: $('warn').value || theme.warn || '#FFA754',
    },
  };
}

function previewPayload() {
  const livePayload = state.bridgePayload;
  if (livePayload && Array.isArray(livePayload.messages) && livePayload.messages.length) {
    return {
      summary: livePayload.summary || livePayload.messages[0].body || 'Latest Codex message appears here',
      status: livePayload.status || 'Live from Codex',
      updatedAt: livePayload.updatedAt,
      progress: livePayload.progress,
      assetVersion: state.petAssetVersion,
      petState: livePayload.pet?.state || livePayload.petState || 'review',
      hasSeenTaskPayload: true,
      messages: livePayload.messages,
    };
  }

  const petName = $('petDisplayName').value.trim() || 'Codex Pet';
  const body = state.previewMessage || `${petName} is ready for Codex updates`;
  return {
    summary: body,
    status: state.watch?.accessible ? 'Ready to deploy' : 'Working locally',
    assetVersion: state.petAssetVersion,
    petState: state.security.ok ? 'waving' : 'review',
    messages: [
      {
        title: 'Garmin app',
        body,
        tone: state.security.ok ? 'success' : 'review',
        time: '',
      },
      {
        title: 'Codex bridge',
        body: $('bridgeUrl').value.trim() ? `Bridge set to ${compactUrl($('bridgeUrl').value.trim())}` : 'Bridge URL is not saved yet.',
        tone: state.watch?.accessible ? 'success' : 'info',
        time: '',
      },
      {
        title: 'Build',
        body: state.security.ok ? 'Security check passed. Save and build is enabled.' : 'Run the security check before building the app.',
        tone: state.security.ok ? 'success' : 'warning',
        time: '',
      },
    ],
  };
}

function currentPreviewAnimation(payload) {
  if (state.previewAnimationKey !== payload.petState) {
    state.previewAnimationKey = payload.petState;
    state.previewAnimationStartedAt = Date.now();
  }
  return {
    now: Date.now(),
    startedAt: state.previewAnimationStartedAt,
  };
}

function renderWatchPreview(options = {}) {
  if (!window.GarminPreview || !state.devices.length) return;
  const device = selectedDevice();
  if (!device) return;
  const screens = window.GarminPreview.screens();
  const activeScreen = screens.find((screen) => screen.id === state.previewScreen) || screens[0];
  if (!activeScreen) return;
  state.previewScreen = activeScreen.id;

  const config = previewConfig();
  const payload = previewPayload();
  const animation = currentPreviewAnimation(payload);
  const screenShape = device.screen?.shape || 'round';
  const screenWidth = Number(device.screen?.width) || 360;
  const screenHeight = Number(device.screen?.height) || screenWidth;
  $('previewScreenName').textContent = activeScreen.label;
  $('watchScreen').style.borderRadius = screenShape === 'round' ? '50%' : '8%';
  $('watchScreen').innerHTML = window.GarminPreview.renderScreen({
    device,
    config,
    payload,
    screenId: activeScreen.id,
    slot: 'main',
    animation,
  });

  if (options.skipGallery) return;

  $('screenGallery').innerHTML = screens.map((screen) => {
    const active = screen.id === state.previewScreen;
    const radius = screenShape === 'round' ? '50%' : '8%';
    return `
      <button class="screenCard${active ? ' active' : ''}" type="button" data-screen-id="${escapeHtml(screen.id)}" role="tab" aria-selected="${active ? 'true' : 'false'}" title="${escapeHtml(screen.summary)}">
        <span class="screenCardLabel">${escapeHtml(screen.label)}</span>
        <span class="screenThumb" style="--thumb-aspect:${screenWidth} / ${screenHeight};--thumb-radius:${radius};">
          ${window.GarminPreview.renderScreen({
            device,
            config,
            payload,
            screenId: screen.id,
            slot: `thumb-${screen.id}`,
            animation,
          })}
        </span>
      </button>
    `;
  }).join('');
}

function animatePetPreview() {
  if (!window.GarminPreview || state.previewScreen !== 'pet') return;
  const device = selectedDevice();
  if (!device) return;
  const config = previewConfig();
  const payload = previewPayload();
  const pet = window.GarminPreview.petAnimationState({
    device,
    config,
    payload,
    animation: currentPreviewAnimation(payload),
  });
  const sprite = $('watchScreen').querySelector('[data-pet-sprite="large"]');
  if (!sprite) {
    renderWatchPreview({ skipGallery: true });
    return;
  }
  sprite.setAttribute('href', pet.imageHref);
  sprite.setAttribute('x', pet.petLeft);
  sprite.setAttribute('y', pet.petTop);
}

function setPreviewScreen(id) {
  if (!id) return;
  state.previewScreen = id;
  renderWatchPreview();
}

function startPreviewAnimation() {
  if (state.previewAnimationTimer) return;
  state.previewAnimationTimer = window.setInterval(() => {
    animatePetPreview();
  }, PREVIEW_ANIMATION_MS);
}

function watchStateClass(watch) {
  if (watch?.accessible) return 'ready';
  if (watch?.recognized || watch?.visible) return 'recognized';
  return 'missing';
}

function watchAccessText(watch) {
  if (watch?.accessible && watch?.method === 'mounted-volume') return 'Accessible via USB storage';
  if (watch?.accessible && watch?.method === 'mtp') return 'Accessible via MTP';
  if (watch?.recognized || watch?.visible) return 'Recognized, deploy blocked';
  return 'Not recognized';
}

function updateSecurityGate() {
  const passed = Boolean(state.security.ok);
  $('buildBtn').disabled = !passed;
  $('buildBtn').title = passed ? '' : 'Run the security check before saving and building.';
  if (!passed && $('buildState').textContent !== 'Failed') {
    $('buildState').textContent = 'Security required';
  }
  document.querySelectorAll('#configHistory button[data-action="build"]').forEach((button) => {
    button.disabled = !passed;
    button.title = passed ? '' : 'Run the security check before building a saved recipe.';
  });
  document.querySelectorAll('#configHistory button[data-action="deploy"]').forEach((button) => {
    const allowed = passed && Boolean(state.watch?.accessible);
    button.disabled = !allowed;
    button.title = allowed
      ? ''
      : passed
        ? 'Deploy is enabled once Garmin storage or MTP access is available.'
        : 'Run the security check before building and deploying a saved recipe.';
  });
}

function setSecurityState(ok, output) {
  state.security = {
    ok,
    checkedAt: ok ? new Date().toISOString() : null,
    output,
  };
  $('securityBtn').textContent = ok ? 'Security passed' : 'Run security check';
  $('securityBtn').className = ok ? 'button primary' : 'button secondary';
  if (!ok) $('sheetBuild').textContent = 'Security required';
  updateSecurityGate();
  renderWatchPreview();
}

function invalidateSecurity() {
  if (!state.security.ok) return;
  setSecurityState(false, 'Local inputs changed after the last security check.');
}

function updateDeployAvailability() {
  const accessible = Boolean(state.watch?.accessible);
  $('deployBtn').disabled = !accessible;
  $('deployBtn').title = accessible ? '' : 'Deploy is enabled once Garmin storage or MTP access is available.';
  updateSecurityGate();
}

function renderWatchStatus(watch) {
  state.watch = watch || {};
  const stateClass = watchStateClass(state.watch);
  $('watchBanner').className = `watchBanner ${stateClass}`;
  $('watchBadge').textContent = state.watch.accessible ? 'Ready' : state.watch.recognized || state.watch.visible ? 'Seen' : 'Missing';
  $('watchTitle').textContent = state.watch.headline || 'Garmin status unknown';
  $('watchDetail').textContent = state.watch.message || 'Waiting for automatic watch detection.';
  $('watchAccess').textContent = watchAccessText(state.watch);
  $('sheetWatchAccess').textContent = watchAccessText(state.watch);
  $('watchState').textContent = state.watch.accessible
    ? 'Accessible for deploy'
    : state.watch.recognized || state.watch.visible
      ? 'Recognized, not accessible'
      : 'Not found';
  mark('connect', state.watch.accessible ? 'done' : state.watch.recognized || state.watch.visible ? 'active' : 'error');
  updateDeployAvailability();
}

function watchPollDelay() {
  if (document.hidden) return WATCH_POLL_HIDDEN_MS;
  return state.watch?.accessible ? WATCH_POLL_READY_MS : WATCH_POLL_FAST_MS;
}

function scheduleWatchPoll(delay = watchPollDelay()) {
  window.clearTimeout(state.watchPollTimer);
  state.watchPollTimer = window.setTimeout(() => {
    pollWatchStatus().catch(() => {
      scheduleWatchPoll(WATCH_POLL_ERROR_MS);
    });
  }, delay);
}

async function pollWatchStatus() {
  if (state.watchPollInFlight) {
    scheduleWatchPoll(1000);
    return;
  }

  state.watchPollInFlight = true;
  try {
    const result = await api('/api/watch-status');
    renderWatchStatus(result.watch);
    refreshBridgePayload().catch(() => {});
    if (result.build) {
      $('sheetBuild').textContent = result.build.exists ? 'Existing PRG found' : 'No PRG yet';
    }
    scheduleWatchPoll();
  } finally {
    state.watchPollInFlight = false;
  }
}

async function refreshBridgePayload() {
  const result = await api('/api/bridge-status');
  state.bridge = result.bridge || state.bridge;
  state.bridgePayload = result.payload || null;
  renderBridgeStatus();
  renderWatchPreview();
  return result;
}

async function checkWatchNow() {
  const button = $('watchRefreshBtn');
  setButtonBusy(button, 'Checking');
  try {
    await pollWatchStatus();
    await completeButton(button, 'Ready', 'Check now');
  } finally {
    resetActionButton(button, 'Check now');
  }
}

function startWatchPolling() {
  pollWatchStatus().catch(() => scheduleWatchPoll(WATCH_POLL_ERROR_MS));
}

function renderConfigHistory() {
  const container = $('configHistory');

  if (!state.configHistory.length) {
    updateDeployAvailability();
    container.innerHTML = '<p class="emptyHistory">No saved recipes yet.</p>';
    return;
  }

  updateDeployAvailability();
  container.innerHTML = state.configHistory.map((entry) => {
    const config = entry.config || {};
    const theme = config.theme || {};
    const petName = config.petDisplayName || 'Codex Pet';
    const deviceName = deviceNameFor(config.device);
    const bridge = compactUrl(config.bridgeUrl || '');
    const petPreview = versionedUrl(
      entry.petSnapshot?.previewUrl || `/api/config-history/${encodeURIComponent(entry.id)}/pet-preview`,
      entry.petSnapshot?.id || entry.createdAt || state.petAssetVersion,
    );
    const previewFallback = petStillPreviewUrl();
    const canBuild = Boolean(state.security.ok);
    const canDeploy = canBuild && Boolean(state.watch?.accessible);
    const style = [
      `--recipe-panel:${cssColor(theme.panel, '#111216')}`,
      `--recipe-accent:${cssColor(theme.accent, '#9A6CFF')}`,
      `--recipe-good:${cssColor(theme.good, '#42E76F')}`,
    ].join(';');
    const buildTitle = canBuild ? '' : ' title="Run the security check before building this saved recipe."';
    const deployTitle = canDeploy
      ? ''
      : ` title="${canBuild ? 'Deploy is enabled once Garmin storage or MTP access is available.' : 'Run the security check before building and deploying this saved recipe.'}"`;
    return `
      <article class="configRow" data-id="${escapeHtml(entry.id)}" style="${escapeHtml(style)}">
        <div class="configPreview" aria-hidden="true">
          <span><img src="${escapeHtml(petPreview)}" alt="" loading="lazy" onerror="this.onerror=null;this.src='${escapeHtml(previewFallback)}';" /></span>
        </div>
        <div class="configMeta">
          <strong>${escapeHtml(petName)}</strong>
          <span>${escapeHtml(deviceName)} / ${escapeHtml(bridge)}</span>
          <em>${escapeHtml(formatHistoryTime(entry.createdAt))}</em>
        </div>
        <div class="configActions">
          <button class="button secondary" type="button" data-action="restore">Restore</button>
          <button class="button primary" type="button" data-action="build"${canBuild ? '' : ' disabled'}${buildTitle}>Build</button>
          <button class="button contrast" type="button" data-action="deploy"${canDeploy ? '' : ' disabled'}${deployTitle}>Build & deploy</button>
          <button class="button danger" type="button" data-action="delete">Delete</button>
        </div>
      </article>
    `;
  }).join('');
  updateSecurityGate();
}

function compactNumber(value) {
  const number = Number(value) || 0;
  if (number < 1000) return String(number);
  if (number < 10000) return `${(number / 1000).toFixed(1)}k`;
  return `${Math.round(number / 1000)}k`;
}

function petDexSubtitle(pet) {
  const vibes = Array.isArray(pet.vibes) ? pet.vibes.slice(0, 3).map((item) => `#${item}`).join(' ') : '';
  return [pet.kind, vibes].filter(Boolean).join(' / ');
}

function petDexMetrics(pet) {
  const metrics = pet.metrics || {};
  const parts = [];
  if (metrics.installCount) parts.push(`${compactNumber(metrics.installCount)} installs`);
  if (metrics.likeCount) parts.push(`${compactNumber(metrics.likeCount)} likes`);
  return parts.join(' / ');
}

function petDexInstallCount(pet) {
  const count = Number(pet?.metrics?.installCount) || 0;
  return `${compactNumber(count)} installs`;
}

function petDexErrorMessage(error) {
  if (error?.code === 'api-html') {
    return 'Search is waiting for the local pipeline API. Open the pipeline server page, then try again.';
  }
  if (error?.message) return error.message;
  return 'Petdex search is not reachable right now.';
}

function renderPetDexResults() {
  const container = $('petDexResults');
  container.textContent = '';
  container.className = `petDexResults${state.petdexMode === 'preview' ? ' preview' : ''}`;

  if (state.petdexError) {
    const problem = document.createElement('div');
    problem.className = 'petDexProblem';

    const title = document.createElement('strong');
    title.textContent = state.petdexError.message;
    problem.appendChild(title);

    const detail = document.createElement('span');
    detail.textContent = 'Petdex import needs the local pipeline API so it can fetch and validate remote assets.';
    problem.appendChild(detail);

    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'button secondary';
    retry.textContent = 'Check again';
    retry.addEventListener('click', () => searchPetDex({ force: true }).catch(handleError('upload')));
    problem.appendChild(retry);

    container.appendChild(problem);
    return;
  }

  if (!state.petdexResults.length) {
    const empty = document.createElement('p');
    empty.className = 'petDexEmpty';
    empty.textContent = 'No Petdex pets loaded yet.';
    container.appendChild(empty);
    return;
  }

  const previewMode = state.petdexMode === 'preview';
  const pets = previewMode ? state.petdexResults.slice(0, 4) : state.petdexResults;

  pets.forEach((pet) => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = `petDexCard${state.petdexSelected?.slug === pet.slug ? ' selected' : ''}`;
    card.dataset.slug = pet.slug;

    if (!previewMode) {
      const thumb = document.createElement('span');
      thumb.className = 'petDexThumb';
      if (pet.spritesheetPath) thumb.style.backgroundImage = `url("${pet.spritesheetPath}")`;
      card.appendChild(thumb);
    }

    const body = document.createElement('span');
    body.className = 'petDexBody';

    const name = document.createElement('strong');
    name.textContent = pet.displayName || pet.slug;
    body.appendChild(name);

    if (previewMode) {
      const metricRow = document.createElement('small');
      metricRow.textContent = petDexInstallCount(pet);
      body.appendChild(metricRow);
    } else {
      const subtitle = document.createElement('span');
      subtitle.textContent = petDexSubtitle(pet) || 'Codex pet';
      body.appendChild(subtitle);

      const description = document.createElement('em');
      description.textContent = pet.description || 'Ready to import from Petdex.';
      body.appendChild(description);

      const metrics = petDexMetrics(pet);
      if (metrics) {
        const metricRow = document.createElement('small');
        metricRow.textContent = metrics;
        body.appendChild(metricRow);
      }
    }

    card.appendChild(body);
    card.addEventListener('click', () => setPetDexSelected(pet));
    container.appendChild(card);
  });
}

function setPetDexSelected(pet) {
  state.petdexSelected = pet;
  $('importPetDexBtn').disabled = !pet;
  if (pet) {
    state.uploadSelection = null;
    $('uploadBtn').disabled = true;
    setUploadFeedback('', 'Petdex pet selected. Import it or drop a local package instead.');
    $('selectedPetFile').textContent = `Petdex: ${pet.displayName || pet.slug}`;
    $('sheetPet').textContent = pet.displayName || pet.slug;
    mark('upload', 'active');
  }
  renderPetDexResults();
}

async function searchPetDex(options = {}) {
  const query = $('petDexSearch').value.trim();
  const typing = Boolean(options.typing);
  const preview = typing && Boolean(query);
  const limit = preview ? '4' : '8';
  const requestId = ++state.petdexRequestId;
  const params = new URLSearchParams({
    sort: $('petDexSort').value,
    limit,
  });
  if (query) params.set('q', query);

  state.petdexMode = preview ? 'preview' : query ? 'search' : 'popular';
  state.petdexError = null;
  if (!options.keepButtonLabel) {
    $('petDexSearchBtn').textContent = preview ? 'Search more' : 'Search Petdex';
  }
  $('petDexStatus').textContent = query
    ? preview ? `Finding top Petdex hits for "${query}"...` : `Searching Petdex for "${query}"...`
    : 'Loading popular Petdex pets...';
  try {
    const result = await api(`/api/petdex/search?${params}`);
    if (requestId !== state.petdexRequestId) return;
    state.petdexResults = Array.isArray(result.pets) ? result.pets : [];
    state.petdexError = null;
    if (state.petdexSelected && !state.petdexResults.some((pet) => pet.slug === state.petdexSelected.slug)) {
      state.petdexSelected = null;
      $('importPetDexBtn').disabled = true;
    }
    renderPetDexResults();
    const count = Number(result.total) || state.petdexResults.length;
    if (!state.petdexResults.length) {
      $('petDexStatus').textContent = query ? `No Petdex pets matched "${query}".` : 'No Petdex pets loaded yet.';
    } else if (preview) {
      $('petDexStatus').textContent = `Top ${Math.min(state.petdexResults.length, 4)} hit${state.petdexResults.length === 1 ? '' : 's'} for "${query}". Press Search more for the full list.`;
    } else {
      $('petDexStatus').textContent = `${state.petdexResults.length} shown from ${count} Petdex match${count === 1 ? '' : 'es'}.`;
    }
  } catch (error) {
    if (requestId !== state.petdexRequestId) return;
    state.petdexResults = [];
    state.petdexSelected = null;
    state.petdexError = { message: petDexErrorMessage(error), detail: error.detail || error.message || '' };
    $('importPetDexBtn').disabled = true;
    renderPetDexResults();
    const message = state.petdexError.message;
    $('petDexStatus').textContent = message;
    if (!options.initial) log('Petdex search failed.', state.petdexError.detail || message);
  }
}

async function searchPetDexFromButton() {
  const query = $('petDexSearch').value.trim();
  const button = setButtonBusy('petDexSearchBtn', 'Searching');
  try {
    await searchPetDex({ keepButtonLabel: true });
    await completeButton(button, 'Found', query ? 'Search more' : 'Search Petdex');
  } catch (error) {
    resetActionButton(button, query ? 'Search more' : 'Search Petdex');
    throw error;
  }
}

function fileStem(name) {
  return (name || 'Codex Pet').replace(/\.(zip|webp|json)$/i, '').replace(/[-_]+/g, ' ').trim() || 'Codex Pet';
}

function displayNameFor(selection) {
  return $('petDisplayName').value.trim() || fileStem(selection?.sourceName || selection?.label || 'Codex Pet');
}

function setUploadFeedback(kind, message) {
  const status = $('uploadStatus');
  const zone = $('petDropZone');
  if (!status || !zone) return;
  status.className = `uploadStatus${kind ? ` ${kind}` : ''}`;
  zone.classList.remove('uploading', 'imported', 'error');
  if (kind) zone.classList.add(kind);
  status.textContent = message;
}

function createUploadSelection(files, sourceName = 'selected files') {
  const entries = Array.from(files || [])
    .filter((file) => file && file.name)
    .map((file) => ({
      file,
      path: file.webkitRelativePath || file.relativePath || file.name,
    }));

  if (!entries.length) return null;

  const rootPath = entries[0].path || entries[0].file.name;
  const rootName = rootPath.includes('/') ? rootPath.split('/')[0] : sourceName;
  const label = entries.length === 1 ? entries[0].file.name : `${rootName} (${entries.length} files)`;
  return { files: entries, label, sourceName: rootName };
}

function setUploadSelection(selection) {
  state.uploadSelection = selection;
  if (selection) {
    state.petdexSelected = null;
    $('importPetDexBtn').disabled = true;
    renderPetDexResults();
  }
  if (!selection) {
    $('selectedPetFile').textContent = 'Drop in a package';
    $('uploadBtn').disabled = true;
    setUploadFeedback('', 'Drop a pet to export and preview it automatically.');
    return;
  }
  $('selectedPetFile').textContent = selection.label;
  $('sheetPet').textContent = displayNameFor(selection);
  $('uploadBtn').disabled = false;
  setUploadFeedback('uploading', `Reading ${selection.label}...`);
  mark('upload', 'active');
  renderWatchPreview();
}

async function filesFromEntry(entry, prefix = '') {
  if (entry.isFile) {
    const file = await new Promise((resolve, reject) => entry.file(resolve, reject));
    return [{ file, path: `${prefix}${entry.name}` }];
  }

  if (!entry.isDirectory) return [];

  const reader = entry.createReader();
  const children = [];
  for (;;) {
    const batch = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
    if (!batch.length) break;
    children.push(...batch);
  }

  const nested = await Promise.all(children.map((child) => filesFromEntry(child, `${prefix}${entry.name}/`)));
  return nested.flat();
}

async function selectionFromDrop(dataTransfer) {
  const items = Array.from(dataTransfer.items || []);
  const entries = items
    .map((item) => (typeof item.webkitGetAsEntry === 'function' ? item.webkitGetAsEntry() : null))
    .filter(Boolean);

  if (entries.length) {
    const grouped = await Promise.all(entries.map((entry) => filesFromEntry(entry)));
    const files = grouped.flat();
    const sourceName = entries.length === 1 ? entries[0].name : 'dropped-pet';
    return {
      files,
      label: files.length === 1 ? files[0].file.name : `${sourceName} (${files.length} files)`,
      sourceName,
    };
  }

  return createUploadSelection(Array.from(dataTransfer.files || []), 'dropped files');
}

async function payloadForSelection(selection) {
  const displayName = displayNameFor(selection);
  const single = selection.files.length === 1 ? selection.files[0] : null;
  const singlePath = single?.path || single?.file.name || '';

  if (single && !singlePath.includes('/') && /\.(zip|webp)$/i.test(single.file.name)) {
    return {
      name: single.file.name,
      dataUrl: await readFileAsDataUrl(single.file),
      displayName,
    };
  }

  return {
    name: selection.sourceName || selection.label || displayName,
    displayName,
    files: await Promise.all(
      selection.files.map(async ({ file, path }) => ({
        name: file.name,
        path: path || file.name,
        type: file.type,
        dataUrl: await readFileAsDataUrl(file),
      })),
    ),
  };
}

async function refresh() {
  const status = await api('/api/status');
  state.bridge = status.bridge || null;
  state.devices = status.devices.devices || [];
  $('device').innerHTML = state.devices
    .map((item) => `<option value="${item.id}">${item.name}${item.buildEnabled ? '' : ' - preview only'}</option>`)
    .join('');
  applyConfig({ ...status.config, device: status.config.device || status.devices.default || 'fr265s' });
  renderWatchStatus(status.watch);
  updateConfigHistory(status.configHistory);
  $('sheetBuild').textContent = status.build.exists ? 'Existing PRG found' : 'No PRG yet';
  renderBridgeStatus();
  await refreshBridgePayload();
  log('Pipeline status loaded.', {
    watch: watchAccessText(status.watch),
    bridge: compactUrl(status.bridge?.url || status.config?.bridgeUrl || ''),
    build: status.build.exists,
  });
}

async function saveConfig(event) {
  event.preventDefault();
  const button = event.submitter || $('configForm').querySelector('button[type="submit"]');
  setButtonBusy(button, 'Saving');
  const config = collectConfig();
  try {
    const result = await api('/api/config', {
      method: 'POST',
      body: JSON.stringify(config),
    });
    await completeButton(button, 'Saved', 'Save recipe');
    state.bridge = result.bridge || state.bridge;
    applyConfig(result.config || config);
    updateConfigHistory(result.configHistory);
    state.previewMessage = `${(result.config || config).petDisplayName} configuration saved`;
    renderWatchPreview();
    mark('theme', 'done');
    mark('preview', 'active');
    log('Configuration saved locally. It will be injected only during configured builds.');
  } catch (error) {
    resetActionButton(button, 'Save recipe');
    throw error;
  }
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function uploadPet(selection = state.uploadSelection || createUploadSelection(Array.from($('petFile').files || []))) {
  if (!selection) {
    log('Drop a pet folder, ZIP, spritesheet.webp, or choose files first.');
    setUploadFeedback('', 'Drop a pet folder, ZIP, or spritesheet.webp first.');
    return;
  }
  const requestId = ++state.uploadRequestId;
  const button = setButtonBusy('uploadBtn', 'Exporting');
  mark('upload', 'active');
  $('selectedPetFile').textContent = selection.label;
  $('sheetPet').textContent = displayNameFor(selection);
  state.previewMessage = `Importing ${displayNameFor(selection)}...`;
  setUploadFeedback('uploading', `Exporting frames from ${selection.label}...`);
  renderWatchPreview();
  try {
    const payload = await payloadForSelection(selection);
    const result = await api('/api/pet/upload', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    if (requestId !== state.uploadRequestId) return;
    const petName = result.pet?.displayName || displayNameFor(selection);
    $('petDisplayName').value = petName;
    $('sheetPet').textContent = petName;
    $('selectedPetFile').textContent = petName;
    state.previewMessage = `${petName} is ready on the watch preview`;
    await completeButton(button, 'Exported', 'Re-export selected pet');
    mark('upload', 'done');
    mark('preview', 'done');
    state.petAssetVersion = Date.now();
    invalidateSecurity();
    setUploadFeedback('imported', `${petName} imported. Preview refreshed automatically.`);
    renderWatchPreview();
    log('Pet frames exported.', result.output);
  } catch (error) {
    if (requestId === state.uploadRequestId) {
      setUploadFeedback('error', error.message || 'Pet import failed.');
    }
    resetActionButton(button, 'Re-export selected pet');
    throw error;
  }
}

async function importPetDex() {
  const pet = state.petdexSelected;
  if (!pet) {
    log('Choose a Petdex pet first.');
    return;
  }
  const button = setButtonBusy('importPetDexBtn', 'Importing');
  mark('upload', 'active');
  $('selectedPetFile').textContent = `Petdex: ${pet.displayName || pet.slug}`;
  $('sheetPet').textContent = pet.displayName || pet.slug;
  $('petDisplayName').value = pet.displayName || pet.slug || 'Codex Pet';
  $('petDexStatus').textContent = `Importing ${pet.displayName || pet.slug}...`;
  try {
    const result = await api('/api/petdex/import', {
      method: 'POST',
      body: JSON.stringify({ pet }),
    });
    await completeButton(button, 'Imported', 'Import selected pet');
    mark('upload', 'done');
    mark('preview', 'done');
    $('petDexStatus').textContent = result.message || `Imported ${pet.displayName || pet.slug}.`;
    setUploadFeedback('imported', `${pet.displayName || pet.slug} imported from Petdex. Preview refreshed automatically.`);
    state.petAssetVersion = Date.now();
    invalidateSecurity();
    renderWatchPreview();
    log('Petdex pet imported and frames exported.', result.output);
  } catch (error) {
    resetActionButton(button, 'Import selected pet');
    throw error;
  }
}

async function runSecurity() {
  const button = setButtonBusy('securityBtn', 'Checking');
  mark('build', 'active');
  $('buildState').textContent = 'Checking';
  $('sheetBuild').textContent = 'Checking secrets';
  try {
    const result = await api('/api/security', { method: 'POST', body: '{}' });
    setSecurityState(true, result.output);
    await completeButton(button, 'Passed', 'Security passed');
    $('buildState').textContent = 'Security passed';
    $('sheetBuild').textContent = 'Security passed';
    log('Security check passed.', result.output);
  } catch (error) {
    resetActionButton(button, 'Run security check');
    throw error;
  }
}

async function build() {
  if (!state.security.ok) {
    mark('build', 'error');
    $('buildState').textContent = 'Security required';
    $('sheetBuild').textContent = 'Run security check';
    log('Run the security check before saving and building.');
    return;
  }
  const config = collectConfig();
  const button = setButtonBusy('buildBtn', 'Building');
  mark('build', 'active');
  $('buildState').textContent = 'Saving';
  $('sheetBuild').textContent = 'Saving recipe';
  try {
    const result = await api('/api/build', { method: 'POST', body: JSON.stringify({ config }) });
    await completeButton(button, 'Built', 'Save & build app');
    state.bridge = result.bridge || state.bridge;
    if (result.security) setSecurityState(Boolean(result.security.ok), result.security.output);
    applyConfig(result.config || config);
    updateConfigHistory(result.configHistory);
    mark('build', 'done');
    $('buildState').textContent = 'PRG ready';
    $('sheetBuild').textContent = 'PRG ready';
    log('Configuration saved and build complete.', result.output);
  } catch (error) {
    resetActionButton(button, 'Save & build app');
    throw error;
  }
}

async function deploy() {
  const button = setButtonBusy('deployBtn', 'Deploying');
  mark('deploy', 'active');
  $('deployState').textContent = 'Sending';
  $('sheetBuild').textContent = 'Deploying';
  try {
    const result = await api('/api/deploy', { method: 'POST', body: '{}' });
    await completeButton(button, 'Deployed', 'Deploy latest PRG');
    state.bridge = result.bridge || state.bridge;
    if (result.config) applyConfig(result.config);
    updateConfigHistory(result.configHistory);
    mark('deploy', 'done');
    $('deployState').textContent = 'On watch';
    $('sheetBuild').textContent = 'On watch';
    log('Deploy complete.', result.output);
  } catch (error) {
    resetActionButton(button, 'Deploy latest PRG');
    throw error;
  }
}

async function restoreConfig(id, triggerButton) {
  const button = setButtonBusy(triggerButton, 'Restoring');
  try {
    const result = await api('/api/config/restore', {
      method: 'POST',
      body: JSON.stringify({ id }),
    });
    await completeButton(button, 'Restored', 'Restore');
    state.bridge = result.bridge || state.bridge;
    applyConfig(result.config);
    updateConfigHistory(result.configHistory);
    state.petAssetVersion = Date.now();
    mark('theme', 'done');
    mark('preview', 'active');
    state.previewMessage = `${result.config.petDisplayName} recipe restored`;
    renderWatchPreview();
    const petNote = result.petRestore?.restored ? ' Pet restored with the recipe.' : '';
    log('Configuration restored.', `${result.config.petDisplayName} on ${deviceNameFor(result.config.device)}.${petNote}`);
  } catch (error) {
    resetActionButton(button, 'Restore');
    throw error;
  }
}

async function deleteConfig(id, triggerButton) {
  const entry = state.configHistory.find((item) => String(item.id) === String(id));
  const label = entry?.config?.petDisplayName || entry?.label || 'saved recipe';
  if (!window.confirm(`Delete ${label}?`)) return;
  const button = setButtonBusy(triggerButton, 'Deleting');
  try {
    const result = await api('/api/config/delete', {
      method: 'POST',
      body: JSON.stringify({ id }),
    });
    await completeButton(button, 'Deleted', 'Delete');
    updateConfigHistory(result.configHistory);
    log('Saved recipe deleted.', label);
  } catch (error) {
    resetActionButton(button, 'Delete');
    throw error;
  }
}

async function buildSavedConfig(id, deployAfter = false, triggerButton) {
  if (!state.security.ok) {
    mark('build', 'error');
    $('buildState').textContent = 'Security required';
    $('sheetBuild').textContent = 'Run security check';
    log('Run the security check before building a saved recipe.');
    return;
  }
  const button = setButtonBusy(triggerButton, deployAfter ? 'Deploying' : 'Building');
  mark('build', 'active');
  $('buildState').textContent = 'Loading';
  $('sheetBuild').textContent = deployAfter ? 'Build and deploy' : 'Building saved recipe';
  if (deployAfter) {
    mark('deploy', 'active');
    $('deployState').textContent = 'Queued';
  }

  try {
    const result = await api(deployAfter ? '/api/build-deploy' : '/api/build', {
      method: 'POST',
      body: JSON.stringify({ historyId: id }),
    });
    await completeButton(button, deployAfter ? 'Deployed' : 'Built', deployAfter ? 'Build & deploy' : 'Build');
    if (result.security) setSecurityState(Boolean(result.security.ok), result.security.output);
    applyConfig(result.config);
    updateConfigHistory(result.configHistory);
    state.petAssetVersion = Date.now();
    mark('build', 'done');
    $('buildState').textContent = 'PRG ready';
    if (deployAfter) {
      mark('deploy', 'done');
      $('deployState').textContent = 'On watch';
      $('sheetBuild').textContent = 'On watch';
      log('Saved configuration built and deployed.', result.output);
      return;
    }
    $('sheetBuild').textContent = 'PRG ready';
    log('Saved configuration built.', result.output);
  } catch (error) {
    resetActionButton(button, deployAfter ? 'Build & deploy' : 'Build');
    throw error;
  }
}

function handleError(step) {
  return (error) => {
    if (step) mark(step, 'error');
    if (step === 'build') $('buildState').textContent = 'Failed';
    if (step === 'deploy') $('deployState').textContent = 'Failed';
    const securityOutput = error?.security?.output || error?.security?.message;
    if (error?.security) setSecurityState(false, securityOutput);
    $('sheetBuild').textContent = 'Needs attention';
    log('Step failed.', securityOutput || error.output || error.message || error);
  };
}

$('configForm').addEventListener('submit', (event) => saveConfig(event).catch(handleError('theme')));
$('uploadBtn').addEventListener('click', () => uploadPet().catch(handleError('upload')));
$('importPetDexBtn').addEventListener('click', () => importPetDex().catch(handleError('upload')));
$('petDexSearchBtn').addEventListener('click', () => searchPetDexFromButton().catch(handleError('upload')));
$('petDexSearch').addEventListener('input', () => {
  window.clearTimeout(state.petdexSearchTimer);
  state.petdexSearchTimer = window.setTimeout(() => searchPetDex({ typing: true }), 280);
});
$('petDexSort').addEventListener('change', () => searchPetDex());
$('securityBtn').addEventListener('click', () => runSecurity().catch(handleError('build')));
$('buildBtn').addEventListener('click', () => build().catch(handleError('build')));
$('deployBtn').addEventListener('click', () => deploy().catch(handleError('deploy')));
$('watchRefreshBtn').addEventListener('click', () => checkWatchNow().catch(handleError('connect')));
$('device').addEventListener('change', () => {
  updateDevicePreview();
  invalidateSecurity();
});
$('screenGallery').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-screen-id]');
  if (button) setPreviewScreen(button.dataset.screenId);
});
$('bridgeUrl').addEventListener('input', () => {
  invalidateSecurity();
  renderWatchPreview();
});
$('configHistory').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const row = button.closest('.configRow');
  const id = row?.dataset.id;
  if (!id) return;
  const action = button.dataset.action;
  if (action === 'restore') {
    restoreConfig(id, button).catch(handleError('theme'));
  } else if (action === 'build') {
    buildSavedConfig(id, false, button).catch(handleError('build'));
  } else if (action === 'deploy') {
    buildSavedConfig(id, true, button).catch(handleError('deploy'));
  } else if (action === 'delete') {
    deleteConfig(id, button).catch(handleError('theme'));
  }
});
$('petFile').addEventListener('change', () => {
  const selection = createUploadSelection(Array.from($('petFile').files || []));
  setUploadSelection(selection);
  if (selection) uploadPet(selection).catch(handleError('upload'));
});
$('petFolder').addEventListener('change', () => {
  const selection = createUploadSelection(Array.from($('petFolder').files || []), 'selected folder');
  setUploadSelection(selection);
  if (selection) uploadPet(selection).catch(handleError('upload'));
});
$('folderBtn').addEventListener('click', () => $('petFolder').click());
$('petDropZone').addEventListener('dragenter', (event) => {
  event.preventDefault();
  $('petDropZone').classList.add('dragging');
});
$('petDropZone').addEventListener('dragover', (event) => {
  event.preventDefault();
});
$('petDropZone').addEventListener('dragleave', (event) => {
  if (!$('petDropZone').contains(event.relatedTarget)) {
    $('petDropZone').classList.remove('dragging');
  }
});
$('petDropZone').addEventListener('drop', async (event) => {
  event.preventDefault();
  $('petDropZone').classList.remove('dragging');
  try {
    const selection = await selectionFromDrop(event.dataTransfer);
    setUploadSelection(selection);
    if (selection) uploadPet(selection).catch(handleError('upload'));
  } catch (error) {
    handleError('upload')(error);
  }
});
['accent', 'good', 'warn', 'panel'].forEach((id) => $(id).addEventListener('input', () => {
  applyTheme(collectConfig().theme);
  invalidateSecurity();
}));
$('petDisplayName').addEventListener('input', () => {
  $('sheetPet').textContent = state.uploadSelection ? displayNameFor(state.uploadSelection) : $('petDisplayName').value.trim() || 'Codex Pet';
  state.previewMessage = `${$('sheetPet').textContent} is ready for Codex updates`;
  invalidateSecurity();
  renderWatchPreview();
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    scheduleWatchPoll(WATCH_POLL_HIDDEN_MS);
  } else {
    pollWatchStatus().catch(() => scheduleWatchPoll(WATCH_POLL_ERROR_MS));
  }
});
window.addEventListener('focus', () => {
  pollWatchStatus().catch(() => scheduleWatchPoll(WATCH_POLL_ERROR_MS));
});
window.addEventListener('online', () => {
  pollWatchStatus().catch(() => scheduleWatchPoll(WATCH_POLL_ERROR_MS));
});

refresh().catch(handleError('connect')).finally(startWatchPolling);
startPreviewAnimation();
searchPetDex({ initial: true });

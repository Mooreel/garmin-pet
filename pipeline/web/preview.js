(function () {
  const SCREEN_DEFINITIONS = [
    { id: 'pet', label: 'Pet home', summary: 'Idle companion and latest Codex update' },
    { id: 'tasks', label: 'Task list', summary: 'Swipe view with current task rows' },
    { id: 'details', label: 'Task detail', summary: 'Round-safe selected task detail' },
  ];

  const DEFAULT_MESSAGES = [
    {
      title: 'Garmin app',
      body: 'Building the watch UI, bridge, pet animation frames, and deployment path so the Garmin view mirrors the current Codex task.',
      tone: 'review',
      time: '',
    },
    {
      title: 'Codex bridge',
      body: 'Local API is publishing prompts and status updates to the watch.',
      tone: 'info',
      time: '',
    },
    {
      title: 'Pet frames',
      body: 'Imported sprites are ready for the configured device build.',
      tone: 'success',
      time: '',
    },
  ];

  const LARGE_PET_SIZE = 160;
  const DEFAULT_DETAIL_CHARS = 34;
  const PET_FRAME_COUNT = 8;
  const PET_STATES = ['failed', 'idle', 'jumping', 'review', 'sleeping', 'waving'];

  function screenDefinitions() {
    return SCREEN_DEFINITIONS.map((screen) => ({ ...screen }));
  }

  function escapeXml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&apos;',
    }[char]));
  }

  function number(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function fit(value, maxChars) {
    const text = String(value ?? '').replace(/\s+/g, ' ').trim();
    if (text.length <= maxChars) return text;
    return `${text.slice(0, Math.max(0, maxChars - 1)).trimEnd()}...`;
  }

  function clipText(value, maxChars) {
    return String(value ?? '').replace(/\s+/g, ' ').trim().slice(0, maxChars).trimEnd();
  }

  function wrapFixed(value, chars, maxLines) {
    const text = String(value ?? '').replace(/\s+/g, ' ').trim();
    if (!text) return [''];

    const lines = [];
    let remaining = text;
    while (remaining.length && lines.length < maxLines) {
      if (remaining.length <= chars) {
        lines.push(remaining);
        break;
      }
      let cut = remaining.lastIndexOf(' ', chars);
      if (cut < Math.floor(chars * 0.55)) cut = chars;
      const line = remaining.slice(0, cut).trim();
      lines.push(line);
      remaining = remaining.slice(cut).trim();
    }

    if (remaining.length && lines.length) {
      lines[lines.length - 1] = fit(lines[lines.length - 1], Math.max(4, chars - 1));
    }
    return lines;
  }

  function wrapFixedClipped(value, chars, maxLines) {
    const text = String(value ?? '').replace(/\s+/g, ' ').trim();
    if (!text) return [''];

    const lines = [];
    let remaining = text;
    while (remaining.length && lines.length < maxLines) {
      if (remaining.length <= chars) {
        lines.push(remaining);
        break;
      }
      let cut = remaining.lastIndexOf(' ', chars);
      if (cut < Math.floor(chars * 0.55)) cut = chars;
      lines.push(remaining.slice(0, cut).trim());
      remaining = remaining.slice(cut).trim();
    }
    return lines.length ? lines : [''];
  }

  function profileFor(device) {
    const screen = device?.screen || {};
    const preview = device?.preview || {};
    const width = number(screen.width, 360);
    const height = number(screen.height, width);
    const minSide = Math.min(width, height);
    const shape = preview.shape || screen.shape || 'round';
    return {
      width,
      height,
      minSide,
      shape,
      scale: minSide / 360,
      dotRadius: clamp(Math.round(minSide * 0.011), 3, 5),
      pageDotY: height - 34,
    };
  }

  function themeFor(config) {
    const theme = config?.theme || {};
    return {
      surface: theme.surface || '#000000',
      panel: theme.panel || '#111216',
      selection: theme.selection || '#251B5F',
      divider: '#2A2C35',
      ink: theme.ink || '#FFFFFF',
      subtle: theme.subtle || '#A8A6B6',
      accent: theme.accent || '#9A6CFF',
      review: theme.review || '#32C8FF',
      good: theme.good || '#42E76F',
      warn: theme.warn || '#FFA754',
    };
  }

  function timestamp() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function payloadFor(config, overrides = {}) {
    const petName = config?.petDisplayName || 'Codex Pet';
    const messages = taskMessages(overrides.messages || DEFAULT_MESSAGES).map((message) => ({
      ...message,
      time: message.time || timestamp(),
    }));
    const first = messages[0] || DEFAULT_MESSAGES[0];
    return {
      updatedAt: overrides.updatedAt || timestamp(),
      summary: overrides.summary || `${petName} is ready for Codex updates`,
      status: overrides.status || 'Working locally',
      progress: number(overrides.progress, 72),
      assetVersion: overrides.assetVersion || '0',
      petName,
      petState: overrides.petState || 'review',
      hasNetworkError: Boolean(overrides.hasNetworkError),
      hasSeenTaskPayload: overrides.hasSeenTaskPayload !== false,
      message: first,
      messages,
    };
  }

  function normalizedPetState(payload) {
    const state = String(payload.petState || 'idle').toLowerCase();
    if (state === 'running' || state === 'working' || state === 'listening') return 'review';
    return PET_STATES.includes(state) ? state : 'idle';
  }

  function frameInterval(state) {
    if (state === 'jumping') return 180;
    if (state === 'waving' || state === 'review' || state === 'failed') return 240;
    return 360;
  }

  function animationFrame(state, animation = {}) {
    const now = number(animation.now, Date.now());
    const startedAt = number(animation.startedAt, now);
    const elapsed = Math.max(0, now - startedAt);
    return Math.floor(elapsed / frameInterval(state)) % PET_FRAME_COUNT;
  }

  function petImageFor(state, frame, payload) {
    const version = encodeURIComponent(String(payload.assetVersion || '0'));
    return `/resources/images/pet_large_${state}_${frame}.png?v=${version}`;
  }

  function statusFor(message, payload) {
    if (payload.hasNetworkError) return 'Offline';
    const tone = String(message?.tone || '').toLowerCase();
    if (tone === 'success' || tone === 'done') return 'Done';
    if (tone === 'warning' || tone === 'blocked') return 'Attention';
    if (tone === 'review') return 'Update';
    return payload.hasSeenTaskPayload ? 'Running' : 'Waiting';
  }

  function isDoneMessage(message) {
    const title = String(message?.title || '').toLowerCase();
    const body = String(message?.body || '').toLowerCase();
    const tone = String(message?.tone || '').toLowerCase();
    const eventType = String(message?.eventType || '').toLowerCase();
    return tone === 'success'
      || tone === 'done'
      || title === 'codex done'
      || eventType === 'task_complete'
      || eventType === 'final_answer'
      || title.startsWith('task done')
      || title.startsWith('task complete')
      || title.startsWith('task finished')
      || body.startsWith('task done')
      || body.startsWith('task complete')
      || body.startsWith('task finished');
  }

  function taskMessages(messages) {
    const active = [];
    const done = [];
    (messages || []).forEach((message) => {
      if (isDoneMessage(message)) {
        if (done.length < 2) done.push(message);
      } else {
        active.push(message);
      }
    });
    return active.concat(done);
  }

  function accentFor(theme, message, payload) {
    const tone = String(message?.tone || '').toLowerCase();
    const status = statusFor(message, payload);
    if (status === 'Done' || tone === 'success' || tone === 'done') return theme.good;
    if (status === 'Attention' || status === 'Offline' || tone === 'warning' || tone === 'blocked') return theme.warn;
    if (tone === 'review') return theme.review;
    return theme.accent;
  }

  function textNode(x, y, text, options = {}) {
    const anchor = options.anchor || 'start';
    const weight = options.weight || 700;
    const size = options.size || 14;
    const fill = options.fill || '#FFFFFF';
    const baseline = options.baseline ? ` dominant-baseline="${escapeXml(options.baseline)}"` : '';
    return `<text x="${x}" y="${y}" text-anchor="${anchor}"${baseline} font-family="system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" font-size="${size}" font-weight="${weight}" fill="${escapeXml(fill)}">${escapeXml(text)}</text>`;
  }

  function rect(x, y, width, height, fill, extra = '') {
    return `<rect x="${x}" y="${y}" width="${width}" height="${height}" fill="${escapeXml(fill)}"${extra} />`;
  }

  function circle(cx, cy, radius, fill) {
    return `<circle cx="${cx}" cy="${cy}" r="${radius}" fill="${escapeXml(fill)}" />`;
  }

  function pill(x, y, width, height, fill) {
    const radius = height / 2;
    return [
      rect(x + radius, y, width - height, height, fill),
      circle(x + radius, y + radius, radius, fill),
      circle(x + width - radius, y + radius, radius, fill),
    ].join('');
  }

  function renderHeader(profile, theme, payload) {
    const tiny = clamp(Math.round(16 * profile.scale), 10, 18);
    const statusColor = payload.hasNetworkError ? theme.warn : theme.good;
    return [
      textNode(profile.width / 2, 20, fit(payload.updatedAt, 12), {
        anchor: 'middle',
        size: tiny,
        fill: theme.ink,
        weight: 750,
      }),
      circle(profile.width - 46, 18, profile.dotRadius, statusColor),
    ].join('');
  }

  function runningTaskCount(payload) {
    if (!payload.hasSeenTaskPayload || payload.hasNetworkError) return 0;
    const count = payload.messages.filter((message) => statusFor(message, payload) !== 'Done').length;
    return Math.min(9, count);
  }

  function renderPageDots(profile, theme, active) {
    const startX = profile.width / 2 - 16;
    return [0, 1, 2].map((index) => circle(startX + index * 16, profile.pageDotY, index === active ? 4 : 3, index === active ? theme.accent : theme.subtle)).join('');
  }

  function renderTaskPositionDots(profile, theme, selectedIndex, total) {
    if (total <= 1) return '';
    const dots = Math.min(total, 5);
    const activeDot = total > dots ? Math.round((selectedIndex * (dots - 1)) / Math.max(1, total - 1)) : selectedIndex;
    const spacing = 9;
    const startX = profile.width / 2 - ((dots - 1) * spacing) / 2;
    return Array.from({ length: dots }, (_, index) => circle(startX + index * spacing, profile.pageDotY, index === activeDot ? 3 : 2, index === activeDot ? theme.accent : theme.subtle)).join('');
  }

  function homeLayout(profile) {
    const petTop = profile.height < 340 ? 38 : 45;
    return {
      counterY: petTop + 120,
      messageY: profile.height < 340 ? profile.height - 72 : profile.height - 130,
      petTop,
    };
  }

  function petAnimationState({ device, config, payload, animation }) {
    const profile = profileFor(device);
    const data = payloadFor(config, payload);
    const state = normalizedPetState(data);
    const frame = animationFrame(state, animation);
    const layout = homeLayout(profile);
    return {
      frame,
      imageHref: petImageFor(state, frame, data),
      petLeft: profile.width / 2 - LARGE_PET_SIZE / 2,
      petTop: layout.petTop,
      state,
    };
  }

  function renderPetScreen(profile, theme, payload, animation) {
    const centerX = profile.width / 2;
    const layout = homeLayout(profile);
    const pet = petAnimationState({ device: { screen: profile }, config: {}, payload, animation });
    const textWidth = Math.max(80, profile.width - 82);
    const chars = clamp(Math.floor(textWidth / 11), 14, 26);
    const lines = wrapFixed(payload.message?.body || payload.summary, chars, 2);
    const lineSize = clamp(Math.round(15 * profile.scale), 10, 15);

    return [
      renderHeader(profile, theme, payload),
      `<image data-pet-sprite="large" href="${escapeXml(pet.imageHref)}" x="${pet.petLeft}" y="${pet.petTop}" width="${LARGE_PET_SIZE}" height="${LARGE_PET_SIZE}" preserveAspectRatio="xMidYMid meet" />`,
      textNode(centerX - 108, layout.counterY, `(${runningTaskCount(payload)})`, {
        anchor: 'middle',
        size: clamp(Math.round(20 * profile.scale), 13, 20),
        fill: theme.accent,
        weight: 800,
      }),
      lines.map((line, index) => textNode(centerX, layout.messageY + index * 27, line, {
        anchor: 'middle',
        size: lineSize,
        fill: payload.hasNetworkError ? theme.warn : theme.subtle,
        weight: 650,
      })).join(''),
      renderPageDots(profile, theme, 0),
    ].join('');
  }

  function isBridgeEventTitle(title) {
    return !title || ['Codex', 'Codex done', 'Codex Pet', 'You', 'Bridge offline'].includes(String(title));
  }

  function taskTitle(message, maxChars = 28) {
    const title = String(message?.title || '').trim();
    const body = String(message?.body || '').replace(/\s+/g, ' ').trim();
    if (isBridgeEventTitle(title)) {
      return fit(body || 'Codex task', maxChars);
    }
    return fit(title || body || 'Codex task', maxChars);
  }

  function taskSubtitle(message, payload) {
    return message?.time ? `${message.time}  ${statusFor(message, payload)}` : statusFor(message, payload);
  }

  function renderTaskIcon(x, y, accent, theme, background, message, payload) {
    const status = statusFor(message, payload);
    if (status === 'Done') {
      return [
        circle(x, y, 13, accent),
        `<path d="M ${x - 6} ${y} L ${x - 2} ${y + 5} L ${x + 7} ${y - 6}" fill="none" stroke="${escapeXml(theme.ink)}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />`,
      ].join('');
    }
    if (String(message?.tone || '').toLowerCase() === 'review') {
      return [
        circle(x, y, 13, accent),
        circle(x, y, 10, background),
      ].join('');
    }
    return [
      circle(x - 11, y + 6, 3, accent),
      rect(x - 5, y - 2, 4, 13, accent),
      rect(x + 2, y - 10, 4, 21, accent),
      circle(x + 12, y - 8, 4, accent),
    ].join('');
  }

  function taskPreviewText(message) {
    const body = String(message?.body || '').replace(/\s+/g, ' ').trim();
    return body || taskTitle(message, 28);
  }

  function featureTextNodes(x, y, text, maxChars, theme, maxLines = 2) {
    return wrapFixedClipped(text, maxChars, maxLines).map((line, index) => (
      textNode(x, y + 29 + index * 22, line, {
        size: 15,
        fill: theme.ink,
        weight: 760,
      })
    )).join('');
  }

  function renderFeaturedTask(profile, theme, message, payload, x, y, width, height) {
    const accent = accentFor(theme, message, payload);
    const status = statusFor(message, payload);
    const done = status === 'Done';
    const bg = done ? '#124222' : theme.selection;
    const textChars = clamp(Math.floor((width - 90) / 10), 18, 25);
    const textX = x + 64;
    return [
      pill(x, y, width, height, accent),
      pill(x + 3, y + 3, width - 6, height - 6, bg),
      renderTaskIcon(x + 34, y + height / 2, accent, theme, bg, message, payload),
      featureTextNodes(textX, y, taskPreviewText(message), textChars, theme, 3),
    ].join('');
  }

  function renderContextTaskRow(profile, theme, message, payload, x, y, width, height) {
    const accent = accentFor(theme, message, payload);
    const status = statusFor(message, payload);
    const done = status === 'Done';
    const bg = done ? '#071C10' : theme.panel;
    const tiny = clamp(Math.round(15 * profile.scale), 10, 15);
    const titleChars = clamp(Math.floor((width - 72) / 10), 15, 23);
    return [
      pill(x, y, width, height, bg),
      renderTaskIcon(x + 26, y + height / 2, accent, theme, bg, message, payload),
      textNode(x + 52, y + 33, clipText(taskPreviewText(message), titleChars), {
        size: tiny,
        fill: theme.ink,
        weight: 750,
      }),
    ].join('');
  }

  function contextTaskWidth(profile, slot) {
    if (slot === 0) return profile.width - 112;
    return profile.width - 86;
  }

  function overviewTaskIndexForSlot(messages, selectedIndex, slot) {
    const count = messages.length;
    if (!count) return -1;
    const selected = clamp(selectedIndex, 0, count - 1);
    if (slot === 1) return selected;
    if (slot === 0) return selected > 0 ? selected - 1 : -1;
    if (slot === 2) return selected < count - 1 ? selected + 1 : -1;
    return -1;
  }

  function renderTasksScreen(profile, theme, payload) {
    const rows = [];
    const topIndex = overviewTaskIndexForSlot(payload.messages, 0, 0);
    if (topIndex >= 0) {
      const rowW = contextTaskWidth(profile, 0);
      rows.push(renderContextTaskRow(profile, theme, payload.messages[topIndex], payload, (profile.width - rowW) / 2, 44, rowW, 52));
    }

    const featuredIndex = overviewTaskIndexForSlot(payload.messages, 0, 1);
    if (featuredIndex >= 0) {
      const rowW = profile.width - 46;
      rows.push(renderFeaturedTask(profile, theme, payload.messages[featuredIndex], payload, (profile.width - rowW) / 2, 104, rowW, 98));
    }

    const bottomIndex = overviewTaskIndexForSlot(payload.messages, 0, 2);
    if (bottomIndex >= 0) {
      const rowW = contextTaskWidth(profile, 2);
      rows.push(renderContextTaskRow(profile, theme, payload.messages[bottomIndex], payload, (profile.width - rowW) / 2, 212, rowW, 52));
    }

    return [
      renderHeader(profile, theme, payload),
      rows.length ? rows.join('') : textNode(profile.width / 2, 145, 'No task updates yet', {
        anchor: 'middle',
        size: clamp(Math.round(16 * profile.scale), 10, 16),
        fill: theme.subtle,
      }),
      payload.hasNetworkError ? textNode(profile.width / 2, 254, fit(payload.status, 30), {
        anchor: 'middle',
        size: clamp(Math.round(16 * profile.scale), 10, 16),
        fill: theme.warn,
      }) : '',
      renderTaskPositionDots(profile, theme, 0, payload.messages.length),
    ].join('');
  }

  function detailLines(message, chars = DEFAULT_DETAIL_CHARS) {
    const text = String(message?.body || message?.title || 'No details yet.').replace(/\s+/g, ' ').trim();
    return wrapFixed(text, chars, 80);
  }

  function detailLayout(profile) {
    const inset = clamp(Math.round(profile.width / 9), 34, 54);
    const textY = clamp(Math.round(profile.height / 5), 70, 88);
    const lineHeight = clamp(Math.round(profile.height / 15), 23, 27);
    const visibleLines = clamp(Math.floor((profile.height - textY - 54) / lineHeight), 5, 11);
    const lineChars = clamp(Math.floor((profile.width - inset * 2) / 9), 22, 40);
    return {
      inset,
      lineChars,
      lineHeight,
      railH: profile.height - textY - 76,
      railTop: textY + 8,
      railX: profile.width - inset + 10,
      textX: inset,
      textY,
      visibleLines,
    };
  }

  function renderDetailsScreen(profile, theme, payload) {
    const message = payload.messages[0] || DEFAULT_MESSAGES[0];
    const accent = accentFor(theme, message, payload);
    const tiny = clamp(Math.round(15 * profile.scale), 10, 15);
    const centerX = profile.width / 2;
    const layout = detailLayout(profile);
    const lines = detailLines(message, layout.lineChars);
    const visible = lines.slice(0, layout.visibleLines);
    const thumbH = lines.length > layout.visibleLines
      ? clamp((layout.railH * layout.visibleLines) / lines.length, 24, layout.railH)
      : layout.railH;

    return [
      renderHeader(profile, theme, payload),
      circle(centerX - 76, 48, 4, accent),
      textNode(centerX, 58, fit(taskSubtitle(message, payload), 24), {
        anchor: 'middle',
        size: tiny,
        fill: theme.subtle,
        weight: 750,
      }),
      rect(layout.inset, 64, profile.width - layout.inset * 2, 1, theme.divider),
      visible.map((line, index) => textNode(layout.textX, layout.textY + 16 + index * layout.lineHeight, line, {
        size: tiny,
        fill: theme.ink,
        weight: 700,
      })).join(''),
      lines.length > layout.visibleLines
        ? [
          rect(layout.railX, layout.railTop, 2, layout.railH, theme.divider),
          rect(layout.railX - 2, layout.railTop, 6, thumbH, accent),
        ].join('')
        : '',
      renderPageDots(profile, theme, 2),
    ].join('');
  }

  function renderShell(profile, theme, body, options = {}) {
    const slot = String(options.slot || 'preview').replace(/[^a-z0-9_-]/gi, '-');
    const clipId = `watch-screen-${slot}`;
    const shape = profile.shape === 'round'
      ? `<circle cx="${profile.width / 2}" cy="${profile.height / 2}" r="${profile.minSide / 2}" />`
      : `<rect x="0" y="0" width="${profile.width}" height="${profile.height}" rx="${Math.round(profile.minSide * 0.06)}" />`;

    return `
      <svg class="watchSvg" viewBox="0 0 ${profile.width} ${profile.height}" role="img" aria-label="${escapeXml(options.label || 'Garmin preview')}" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <clipPath id="${clipId}">
            ${shape}
          </clipPath>
          <radialGradient id="${clipId}-glass" cx="30%" cy="18%" r="78%">
            <stop offset="0%" stop-color="#ffffff" stop-opacity="0.12" />
            <stop offset="58%" stop-color="#ffffff" stop-opacity="0" />
            <stop offset="100%" stop-color="#000000" stop-opacity="0.22" />
          </radialGradient>
        </defs>
        <g clip-path="url(#${clipId})">
          ${rect(0, 0, profile.width, profile.height, theme.surface)}
          ${body}
          ${rect(0, 0, profile.width, profile.height, `url(#${clipId}-glass)`)}
        </g>
      </svg>
    `;
  }

  function renderScreen({ device, config, payload, screenId, slot, animation }) {
    const profile = profileFor(device);
    const theme = themeFor(config);
    const data = payloadFor(config, payload);
    const selectedScreen = SCREEN_DEFINITIONS.some((screen) => screen.id === screenId) ? screenId : SCREEN_DEFINITIONS[0].id;
    const body = selectedScreen === 'tasks'
      ? renderTasksScreen(profile, theme, data)
      : selectedScreen === 'details'
        ? renderDetailsScreen(profile, theme, data)
        : renderPetScreen(profile, theme, data, animation);
    const definition = SCREEN_DEFINITIONS.find((screen) => screen.id === selectedScreen) || SCREEN_DEFINITIONS[0];
    return renderShell(profile, theme, body, {
      slot: `${slot || 'preview'}-${selectedScreen}`,
      label: `${definition.label} on ${device?.name || 'Garmin watch'}`,
    });
  }

  window.GarminPreview = {
    petAnimationState,
    screens: screenDefinitions,
    renderScreen,
  };
}());

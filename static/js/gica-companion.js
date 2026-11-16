/* A small, local conversation companion. It never opens a microphone, makes a
 * request, or applies a business change: the existing Gica controller does so. */
(() => {
  'use strict';
  const presence = document.querySelector('[data-romeo-presence]');
  if (!presence || document.querySelector('[data-gica-companion]')) return;
  const owner = document.body.dataset.voiceUser || presence.dataset.gicaUserName || '';
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const state = { active: false, exchanged: false, micActive: false, listening: false, speaking: false, blocked: false, demo: false, phase: '', assistantText: '', userText: '', creation: null };
  let minimized = false, frame = 0, move = null, located = false, disposed = false, choiceSignature = '', submitted = false;
  let lastPosition = { x: 0, y: 0 };
  let manualPosition = null, drag = null, draggedCompactUntil = 0;
  let demoTargetNode = null, demoCompact = false, completionCompact = false;

  const element = (tag, className, text = '') => {
    const node = document.createElement(tag); node.className = className;
    if (text) node.textContent = text;
    return node;
  };
  const button = (className, label) => {
    const node = element('button', className, label); node.type = 'button'; return node;
  };
  const plain = (value, limit) => {
    if (typeof value !== 'string' || value.length > 32768) return '';
    const text = value.normalize('NFC').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/gu, '').replace(/\s+/gu, ' ').trim();
    return text.length > limit ? text.slice(0, limit - 1).trimEnd() + '…' : text;
  };
  const emit = (name, detail = {}) => document.dispatchEvent(new CustomEvent(name, { detail }));
  const shell = element('aside', 'gica-companion');
  shell.dataset.gicaCompanion = '';
  shell.hidden = true;
  shell.setAttribute('aria-label', 'Gica, resumen de la conversación');
  const compact = button('gica-companion-compact', '');
  compact.setAttribute('aria-label', 'Ampliar conversación con Gica');
  compact.setAttribute('aria-controls', 'gica-companion-card');
  compact.setAttribute('aria-expanded', 'false');
  const card = element('section', 'gica-companion-card');
  card.id = 'gica-companion-card';
  card.setAttribute('aria-label', 'Conversación breve con Gica');
  const header = element('header', 'gica-companion-header');
  const avatarSource = presence.querySelector('[data-romeo-home] img')?.getAttribute('src');
  function avatar(className) {
    const holder = element('span', className);
    holder.setAttribute('aria-hidden', 'true');
    if (avatarSource) {
      const img = document.createElement('img'); img.src = avatarSource; img.alt = ''; img.width = 36; img.height = 36; holder.append(img);
    } else holder.textContent = 'G';
    return holder;
  }
  compact.append(avatar('gica-companion-avatar'));
  const compactDot = element('span', 'gica-companion-mic-dot'); compactDot.setAttribute('aria-hidden', 'true'); compact.append(compactDot);
  header.append(avatar('gica-companion-avatar'));
  const identity = element('div', 'gica-companion-identity');
  const name = element('strong', '', 'Gica-1'), status = element('span', 'gica-companion-state', 'Contigo');
  identity.append(name, status); header.append(identity);
  const grip = button('gica-companion-grip', '');
  grip.dataset.gicaCompanionDrag = '';
  grip.setAttribute('aria-label', 'Mover la burbuja de Gica');
  grip.setAttribute('aria-describedby', 'gica-companion-drag-help');
  grip.title = 'Arrastra para mover. Flechas: mover. Inicio: posición automática.';
  const gripIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  gripIcon.setAttribute('viewBox', '0 0 20 20'); gripIcon.setAttribute('aria-hidden', 'true');
  for (const x of [7, 13]) for (const y of [5, 10, 15]) {
    const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    dot.setAttribute('cx', String(x)); dot.setAttribute('cy', String(y)); dot.setAttribute('r', '1.25'); gripIcon.append(dot);
  }
  grip.append(gripIcon); header.append(grip);
  const dragHelp = element('span', 'gica-companion-visually-hidden', 'Arrastra este control para mover la burbuja. Con el teclado, usa las flechas; Inicio restaura la posición automática.');
  dragHelp.id = 'gica-companion-drag-help';
  compact.setAttribute('aria-describedby', dragHelp.id);
  const minimize = button('gica-companion-minimize', '');
  minimize.setAttribute('aria-label', 'Minimizar conversación');
  const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  icon.setAttribute('viewBox', '0 0 20 20'); icon.setAttribute('aria-hidden', 'true');
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'path'); line.setAttribute('d', 'M5 10h10'); icon.append(line); minimize.append(icon); header.append(minimize);
  const question = element('p', 'gica-companion-question');
  question.setAttribute('aria-live', 'polite'); question.setAttribute('aria-atomic', 'true');
  const answer = element('p', 'gica-companion-answer'); answer.hidden = true;
  const options = element('div', 'gica-companion-options'); options.setAttribute('role', 'group'); options.setAttribute('aria-label', 'Respuestas rápidas'); options.hidden = true;
  const otherForm = element('form', 'gica-companion-other'); otherForm.hidden = true;
  let customChoice = null;
  const otherLabel = element('label', '', 'Otra opción'); otherLabel.htmlFor = 'gica-companion-other-answer';
  const otherRow = element('div', 'gica-companion-other-row');
  const otherInput = element('input', ''); otherInput.id = 'gica-companion-other-answer'; otherInput.type = 'text'; otherInput.maxLength = 300;
  otherInput.autocomplete = 'off'; otherInput.placeholder = 'Escribe tu respuesta'; otherInput.setAttribute('aria-describedby', 'gica-companion-other-help');
  const otherSubmit = button('gica-companion-send', 'Responder'); otherSubmit.type = 'submit';
  otherRow.append(otherInput, otherSubmit);
  const otherHelp = element('span', 'gica-companion-other-help', 'Hasta 300 caracteres.'); otherHelp.id = 'gica-companion-other-help';
  otherForm.append(otherLabel, otherRow, otherHelp);
  const footer = element('footer', 'gica-companion-footer');
  const open = button('gica-companion-link', 'Ver conversación');
  const stop = button('gica-companion-stop', 'Apagar mic'); stop.hidden = true;
  footer.append(open, stop); card.append(header, question, answer, options, otherForm, footer); shell.append(compact, card, dragHelp); document.body.append(shell);
  // Text users see the very same controls inside the full conversation. Moving
  // these nodes keeps one set of listeners, IDs, values and stale-click tokens.
  const creationPanel = presence.querySelector('[data-gica-creation]');
  const inlineHost = element('div', 'gica-companion-inline'); inlineHost.hidden = true;
  const creationStatus = creationPanel?.querySelector('[data-gica-creation-status]');
  if (creationStatus) creationStatus.after(inlineHost);
  else creationPanel?.append(inlineHost);

  function routeOptions(full, draftActive) {
    const target = full && draftActive && creationPanel ? inlineHost : card;
    if (options.parentNode !== target) {
      if (target === card) { card.insertBefore(options, footer); card.insertBefore(otherForm, footer); }
      else target.append(options, otherForm);
    }
    inlineHost.hidden = target !== inlineHost || (options.hidden && otherForm.hidden);
  }

  function visible(node) {
    if (!node?.isConnected || node.closest('[hidden]')) return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.right > 0 && rect.top < innerHeight && rect.left < innerWidth;
  }
  function overlap(a, b) {
    return Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  }
  function padded(rect, amount = 10) {
    return { left: rect.left - amount, right: rect.right + amount, top: rect.top - amount, bottom: rect.bottom + amount };
  }
  function viewportBounds(workspace = false) {
    const viewport = window.visualViewport;
    const bounds = { left: (viewport?.offsetLeft || 0) + 12, top: (viewport?.offsetTop || 0) + 12,
      right: (viewport?.offsetLeft || 0) + (viewport?.width || innerWidth) - 12,
      bottom: (viewport?.offsetTop || 0) + (viewport?.height || innerHeight) - 12 };
    if (!workspace) return bounds;
    const topbar = document.querySelector('.app-topbar');
    if (visible(topbar)) bounds.top = Math.max(bounds.top, topbar.getBoundingClientRect().bottom + 10);
    const sidebar = document.querySelector('.sidebar');
    if (visible(sidebar)) {
      const rect = sidebar.getBoundingClientRect();
      if (rect.height > (viewport?.height || innerHeight) * .55 && rect.width < innerWidth * .5) bounds.left = Math.max(bounds.left, rect.right + 12);
      else if (rect.top <= bounds.top) bounds.top = Math.max(bounds.top, rect.bottom + 10);
    }
    return bounds;
  }
  function clamped(point, width = shell.getBoundingClientRect().width, height = shell.getBoundingClientRect().height) {
    const bounds = viewportBounds();
    return { x: Math.max(bounds.left, Math.min(Math.max(bounds.left, bounds.right - width), point.x)),
      y: Math.max(bounds.top, Math.min(Math.max(bounds.top, bounds.bottom - height), point.y)) };
  }
  function place(destination, animate = false) {
    const rect = shell.getBoundingClientRect();
    const from = located ? { x: rect.left, y: rect.top } : destination;
    move?.cancel();
    if (typeof shell.animate === 'function') {
      move = shell.animate([{ transform: `translate(${from.x}px, ${from.y}px)` }, { transform: `translate(${destination.x}px, ${destination.y}px)` }],
        { duration: animate && located && !reduced.matches ? 300 : 0, easing: 'cubic-bezier(.2,.7,.2,1)', fill: 'forwards' });
    } else shell.classList.add('gica-companion-static');
    located = true; lastPosition = { x: destination.x, y: destination.y };
    shell.dataset.position = destination.y < (viewportBounds().top + viewportBounds().bottom) / 2 ? 'top' : 'bottom';
  }
  function position() {
    frame = 0;
    if (disposed || shell.hidden || document.hidden) return;
    const bounds = viewportBounds(!manualPosition || state.demo);
    // A short visual viewport normally means the on-screen keyboard is open.
    shell.classList.toggle('is-short', bounds.bottom - bounds.top < 480);
    const rect = shell.getBoundingClientRect(), width = rect.width, height = rect.height;
    const targetRect = state.demo && visible(demoTargetNode) ? padded(demoTargetNode.getBoundingClientRect(), 20) : null;
    const manualBox = manualPosition ? { left: manualPosition.x, top: manualPosition.y, right: manualPosition.x + width, bottom: manualPosition.y + height } : null;
    // A manual position belongs to the user. During the presentation we only
    // borrow a different place while that position covers the current control.
    if (manualPosition && (!targetRect || overlap(manualBox, targetRect) === 0)) {
      manualPosition = clamped(manualPosition, width, height);
      if (!located || Math.abs(manualPosition.x - lastPosition.x) >= 1 || Math.abs(manualPosition.y - lastPosition.y) >= 1) place(manualPosition);
      return;
    }
    const left = bounds.left, right = Math.max(left, bounds.right - width);
    const top = bounds.top, bottom = Math.max(top, bounds.bottom - height);
    const middleX = Math.max(left, (left + right) / 2), middleY = Math.max(top, (top + bottom) / 2);
    const obstacles = [];
    if (targetRect) obstacles.push({ rect: targetRect, weight: 200 });
    for (const node of document.querySelectorAll('[data-account-menu][open] .account-options, #romeo-presence-details, [open] dialog, dialog[open], [aria-modal="true"]')) {
      if (visible(node) && !shell.contains(node)) obstacles.push({ rect: padded(node.getBoundingClientRect()), weight: 16 });
    }
    const focus = document.activeElement;
    if (focus && focus !== document.body && !shell.contains(focus) && visible(focus)) obstacles.push({ rect: padded(focus.getBoundingClientRect(), 18), weight: 22 });
    for (const node of document.querySelectorAll('main .gica-field-current, main .gica-field-preview, main [data-gica-live-question], main [data-event-select-options]:not([hidden]), main [data-event-date-panel]:not([hidden])')) {
      if (visible(node)) obstacles.push({ rect: padded(node.getBoundingClientRect(), 14), weight: 14 });
    }
    // Stable candidate order keeps Gica near the content, never wandering at random.
    const candidates = [{ x: right, y: bottom }, { x: right, y: top }, { x: left, y: bottom }, { x: left, y: top },
      { x: right, y: middleY }, { x: left, y: middleY }, { x: middleX, y: bottom }, { x: middleX, y: top }];
    let destination;
    if (shell.contains(focus) && located && !state.demo) destination = { x: Math.max(left, Math.min(right, lastPosition.x)), y: Math.max(top, Math.min(bottom, lastPosition.y)) };
    else destination = candidates.map((candidate, index) => {
      const box = { left: candidate.x, top: candidate.y, right: candidate.x + width, bottom: candidate.y + height };
      return { ...candidate, score: obstacles.reduce((sum, obstacle) => sum + overlap(box, obstacle.rect) * obstacle.weight, 0) + index * 5 };
    }).sort((a, b) => a.score - b.score)[0];
    if (state.demo && targetRect && destination && !demoCompact && !minimized) {
      const box = { left: destination.x, top: destination.y, right: destination.x + width, bottom: destination.y + height };
      if (overlap(box, targetRect) > 0) { demoCompact = true; render(); return; }
    }
    if (!destination || (located && Math.abs(destination.x - lastPosition.x) < 1 && Math.abs(destination.y - lastPosition.y) < 1)) return;
    place(destination, true);
  }
  function schedule() { if (!frame && !disposed && !shell.hidden) frame = requestAnimationFrame(position); }
  function cancelDrag() {
    const current = drag; drag = null; shell.classList.remove('is-dragging');
    if (current?.target.hasPointerCapture?.(current.pointerId)) current.target.releasePointerCapture(current.pointerId);
  }
  function setManual(point) {
    manualPosition = clamped(point); shell.dataset.placement = 'manual'; place(manualPosition);
  }
  function resetPosition() {
    cancelDrag(); manualPosition = null; shell.dataset.placement = 'automatic'; schedule();
  }
  function beginDrag(event) {
    if (disposed || shell.hidden || document.hidden || document.body.dataset.voiceUser !== owner ||
        event.button !== 0 || event.isPrimary === false || typeof shell.animate !== 'function') return;
    cancelDrag();
    const rect = shell.getBoundingClientRect();
    drag = { pointerId: event.pointerId, target: event.currentTarget, clientX: event.clientX, clientY: event.clientY,
      x: rect.left, y: rect.top, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function moveDrag(event) {
    if (!drag || drag.pointerId !== event.pointerId || document.body.dataset.voiceUser !== owner) return;
    const dx = event.clientX - drag.clientX, dy = event.clientY - drag.clientY;
    if (!drag.moved && Math.hypot(dx, dy) < 5) return;
    drag.moved = true; shell.classList.add('is-dragging'); event.preventDefault();
    setManual({ x: drag.x + dx, y: drag.y + dy });
  }
  function endDrag(event) {
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.moved && drag.target === compact) draggedCompactUntil = performance.now() + 400;
    cancelDrag();
  }
  function keyboardMove(event) {
    if (disposed || shell.hidden || document.hidden || document.body.dataset.voiceUser !== owner) return;
    if (event.key === 'Home') { event.preventDefault(); resetPosition(); return; }
    const axes = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (!Object.hasOwn(axes, event.key) || typeof shell.animate !== 'function') return;
    event.preventDefault(); cancelDrag();
    const rect = shell.getBoundingClientRect(), step = event.shiftKey ? 32 : 12, axis = axes[event.key];
    setManual({ x: rect.left + axis[0] * step, y: rect.top + axis[1] * step });
  }
  for (const handle of [grip, compact]) {
    handle.addEventListener('pointerdown', beginDrag);
    handle.addEventListener('pointermove', moveDrag);
    handle.addEventListener('pointerup', endDrag);
    handle.addEventListener('pointercancel', endDrag);
    handle.addEventListener('lostpointercapture', endDrag);
    handle.addEventListener('keydown', keyboardMove);
  }
  grip.addEventListener('dblclick', resetPosition);
  function setMinimized(value, focusButton = false) {
    minimized = value; render();
    if (focusButton) (value ? compact : minimize).focus({ preventScroll: true });
  }
  function normalizedCreation(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value) ||
        typeof value.draft_id !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.draft_id) ||
        !Number.isSafeInteger(value.revision) || value.revision < 1 ||
        typeof value.step_key !== 'string' || !/^[a-z_]{1,40}$/.test(value.step_key) ||
        !['collecting', 'review', 'invalid', 'conflict', 'created', 'cancelled', 'expired'].includes(value.status)) return null;
    const choices = [];
    if (value.status === 'collecting' && value.busy !== true && Array.isArray(value.choices)) {
      for (const choice of value.choices.slice(0, 4)) {
        if (!choice || typeof choice.id !== 'string' || !/^[a-z0-9_-]{1,80}$/i.test(choice.id) ||
            !['answer', 'custom'].includes(choice.mode) || typeof choice.value !== 'string' || choice.value.length > 300 ||
            (choice.mode === 'answer' && !choice.value.trim())) continue;
        // Directory suggestions must retain the complete human-readable name:
        // truncating two similar institutions would make a safe choice unclear.
        const directory = /^directory_candidate_[1-3]$/.test(choice.id);
        const label = plain(choice.label, directory ? 160 : 42);
        if (label) choices.push({ id: choice.id, value: choice.value.normalize('NFC').trim(), label, mode: choice.mode });
      }
    }
    return { draft_id: value.draft_id, revision: value.revision, step_key: value.step_key, status: value.status,
      prompt: plain(value.question, 280), choices, disabled: value.busy === true };
  }
  function submit(choice, value, source) {
    const creation = state.creation;
    if (!creation || creation.disabled || state.blocked || submitted || !choice || typeof value !== 'string') return;
    const text = value.normalize('NFC').trim();
    if (!text || text.length > 300 || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(text)) return;
    submitted = true; render();
    const event = new CustomEvent('sparkx:gica-companion-answer', { cancelable: true, detail: {
      draft_id: creation.draft_id, revision: creation.revision, step_key: creation.step_key,
      choice_id: choice.id, value: text, source } });
    document.dispatchEvent(event);
    // Only the controller can acknowledge a current, permitted option. A
    // declined click never leaves a decorative component locked in "saving".
    if (!event.defaultPrevented) { submitted = false; render(); }
  }
  function renderChoices() {
    const creation = state.creation;
    const signature = JSON.stringify(creation && { draft_id: creation.draft_id, revision: creation.revision, step_key: creation.step_key, choices: creation.choices });
    if (signature !== choiceSignature) {
      choiceSignature = signature; submitted = false; options.replaceChildren(); otherForm.hidden = true; otherInput.value = ''; customChoice = null;
      options.classList.toggle('has-directory-candidates', (creation?.choices || []).some((choice) => /^directory_candidate_[1-3]$/.test(choice.id)));
      for (const choice of creation?.choices || []) {
        const control = button('gica-companion-choice', choice.label);
        control.dataset.gicaCompanionChoice = choice.id;
        control.title = choice.label;
        if (/^directory_candidate_[1-3]$/.test(choice.id)) control.classList.add('is-directory-candidate');
        if (choice.mode === 'custom') {
          control.classList.add('is-other'); control.dataset.gicaCompanionOther = '';
          control.addEventListener('click', () => {
            customChoice = choice; otherForm.hidden = !otherForm.hidden;
            const directoryName = choice.id === 'directory_name';
            otherLabel.textContent = directoryName ? (creation.step_key === 'organization' ? 'Nombre de la institución' : 'Nombre de la persona') : 'Otra opción';
            otherInput.placeholder = directoryName ? 'Escribe el nombre' : 'Escribe tu respuesta';
            otherInput.maxLength = directoryName ? 160 : 300;
            otherHelp.textContent = directoryName ? 'Te pediré confirmación antes de registrarlo.' : 'Hasta 300 caracteres.';
            control.setAttribute('aria-expanded', String(!otherForm.hidden)); schedule();
            if (!otherForm.hidden) otherInput.focus({ preventScroll: true });
          });
          control.setAttribute('aria-expanded', 'false'); control.setAttribute('aria-controls', 'gica-companion-other-answer');
        } else control.addEventListener('click', () => submit(choice, choice.value, 'choice'));
        options.append(control);
      }
    }
    options.hidden = !creation || !options.childElementCount;
    for (const control of options.querySelectorAll('button')) control.disabled = submitted || state.blocked || creation?.disabled === true;
    otherInput.disabled = otherSubmit.disabled = submitted || state.blocked || creation?.disabled === true;
  }
  function render() {
    if (document.body.dataset.voiceUser !== owner) { clear(); return; }
    const draftActive = state.creation && ['collecting', 'review', 'invalid', 'conflict'].includes(state.creation.status);
    const requested = (state.active || state.exchanged || draftActive) && !document.hidden && !disposed;
    shell.hidden = !requested;
    if (!requested) { cancelDrag(); cancelAnimationFrame(frame); frame = 0; return; }
    const full = visible(document.getElementById('romeo-presence-details'));
    const compactMode = minimized || full || demoCompact || completionCompact;
    shell.classList.toggle('is-minimized', compactMode);
    shell.classList.toggle('is-listening', state.listening);
    shell.classList.toggle('is-speaking', state.speaking);
    const appearance = presence.dataset.gicaAppearance;
    shell.dataset.appearance = ['ocean', 'slate', 'forest'].includes(appearance) ? appearance : 'ocean';
    compact.hidden = !compactMode; card.hidden = compactMode;
    compact.setAttribute('aria-expanded', String(!compactMode));
    compact.setAttribute('aria-label', 'Ampliar conversación con Gica' + (state.speaking ? '. Gica está hablando.' : state.listening ? '. Escuchando.' : state.active && !state.micActive ? '. Por texto.' : state.active ? '. Esperando audio.' : ''));
    stop.hidden = !state.micActive && !state.demo;
    stop.textContent = state.demo ? 'Detener piloto' : 'Apagar mic';
    const audioLabel = state.listening ? 'Te escucho' : 'Esperando audio';
    const phases = { speaking: 'Gica está hablando', listening: audioLabel, waiting: audioLabel, dictating: audioLabel, transcribing: 'Escribiendo tu respuesta', sending: 'Guardando respuesta', processing: 'Preparando respuesta', holding: 'En espera', paused: 'Micrófono en pausa', off: 'Micrófono apagado' };
    status.textContent = state.demo ? (state.speaking ? 'Piloto · Gica habla' : 'Piloto · mic apagado') : state.creation?.disabled || submitted ? 'Guardando respuesta' : state.active && !state.micActive ? 'Conversación por texto' : phases[state.phase] || (state.micActive ? 'Esperando audio' : 'Puedes responder por voz o clic');
    const prompt = state.demo ? state.assistantText || state.creation?.prompt : state.creation?.prompt || state.assistantText;
    if (question.textContent !== prompt) question.textContent = prompt;
    question.hidden = !prompt;
    const previous = state.userText ? 'Tú: ' + state.userText : '';
    if (answer.textContent !== previous) answer.textContent = previous;
    answer.hidden = !previous;
    renderChoices(); routeOptions(full, draftActive); schedule();
  }
  function clear() {
    cancelDrag(); manualPosition = null; draggedCompactUntil = 0; shell.dataset.placement = 'automatic';
    state.active = state.exchanged = false; state.assistantText = state.userText = ''; state.creation = null; demoTargetNode = null; demoCompact = false; completionCompact = false;
    state.micActive = state.listening = state.speaking = state.blocked = state.demo = false;
    question.textContent = answer.textContent = ''; otherInput.value = ''; options.replaceChildren(); choiceSignature = ''; submitted = false; minimized = false; customChoice = null;
    routeOptions(false, false); inlineHost.hidden = true;
    shell.hidden = true; move?.cancel(); move = null; located = false; cancelAnimationFrame(frame); frame = 0;
  }
  function apply(detail) {
    if (document.body.dataset.voiceUser !== owner) { clear(); return; }
    if (disposed || !detail || typeof detail !== 'object' || Array.isArray(detail) || detail.user !== owner) return;
    if (detail.kind === 'clear') { clear(); return; }
    if (document.hidden) return;
    if (detail.kind === 'voice') {
      if (typeof detail.active !== 'boolean' || typeof detail.micActive !== 'boolean') return;
      if (!state.active && detail.active && detail.phase === 'demo') completionCompact = false;
      if (!state.active && detail.active && !state.creation) {
        try {
          const snapshot = window.SparkXGicaCreation?.presentation?.();
          if (snapshot?.user === owner) {
            const restored = normalizedCreation(snapshot);
            if (restored && ['collecting', 'review', 'invalid', 'conflict'].includes(restored.status)) state.creation = restored;
          }
        } catch (_) { /* Reopening remains possible if a snapshot is unavailable. */ }
      }
      if (state.active && !detail.active) state.exchanged = false;
      state.active = detail.active; state.micActive = detail.micActive;
      state.demo = detail.phase === 'demo';
      state.blocked = detail.blocked === true;
      state.listening = detail.listening === true; state.speaking = detail.speaking === true;
      if (typeof detail.phase === 'string') state.phase = plain(detail.phase, 32);
      if (detail.speaking === true) state.phase = 'speaking';
    } else if (detail.kind === 'exchange') {
      if (typeof detail.assistantText === 'string') state.assistantText = plain(detail.assistantText, 280);
      if (typeof detail.userText === 'string') state.userText = plain(detail.userText, 140);
      if (state.assistantText || state.userText) state.exchanged = true;
    } else if (detail.kind === 'creation') {
      state.creation = normalizedCreation(detail);
      // The controller can re-publish the current snapshot after declining a
      // stale or temporarily blocked click. That must leave the controls usable.
      if (state.creation && !state.creation.disabled) submitted = false;
      if (state.creation && !['collecting', 'review', 'invalid', 'conflict'].includes(state.creation.status)) state.creation = null;
    } else return;
    render();
  }
  document.addEventListener('sparkx:gica-companion-state', (event) => {
    apply(event.detail);
  });
  document.addEventListener('sparkx:gica-demo-target', (event) => {
    if (!state.demo || presence.dataset.gicaDemoActive !== 'true' || event.detail?.user !== owner ||
        !(event.detail.element instanceof Element) || !event.detail.element.isConnected) return;
    demoTargetNode = event.detail.element; demoCompact = false; render();
  });
  document.addEventListener('sparkx:gica-demo-end', (event) => {
    demoTargetNode = null; demoCompact = false;
    if (event.detail?.user === owner && event.detail.completed === true) completionCompact = true;
    render();
  });
  try {
    const initial = window.SparkXGicaCreation?.presentation?.();
    if (initial) apply(initial);
  } catch (_) {
    // The companion is optional; it cannot interrupt the existing controller.
  }
  compact.addEventListener('click', () => {
    if (performance.now() < draggedCompactUntil) return;
    if (visible(document.getElementById('romeo-presence-details'))) { emit('sparkx:gica-companion-open'); return; }
    completionCompact = false; setMinimized(false, true);
  });
  minimize.addEventListener('click', () => setMinimized(true, true));
  open.addEventListener('click', () => emit('sparkx:gica-companion-open'));
  stop.addEventListener('click', () => emit('sparkx:gica-companion-stop'));
  otherForm.addEventListener('submit', (event) => { event.preventDefault(); submit(customChoice, otherInput.value, 'other'); });
  shell.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !minimized) { event.preventDefault(); event.stopPropagation(); setMinimized(true, true); } });
  document.addEventListener('focusin', schedule);
  document.addEventListener('scroll', schedule, { passive: true, capture: true });
  window.addEventListener('resize', schedule, { passive: true });
  window.visualViewport?.addEventListener('resize', schedule, { passive: true });
  window.visualViewport?.addEventListener('scroll', schedule, { passive: true });
  document.addEventListener('sparkx:romeo-action-layout', render);
  document.addEventListener('sparkx:gica-navigation-complete', render);
  document.addEventListener('toggle', schedule, true);
  document.addEventListener('visibilitychange', () => { if (document.hidden) clear(); });
  document.addEventListener('submit', (event) => { if (event.target instanceof HTMLFormElement && /\/logout\/?$/.test(new URL(event.target.action, location.href).pathname)) clear(); }, true);
  window.addEventListener('pagehide', () => { clear(); disposed = true; });
  reduced.addEventListener?.('change', schedule);
  emit('sparkx:gica-companion-request');
})();

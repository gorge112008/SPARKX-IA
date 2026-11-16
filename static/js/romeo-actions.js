/* Human-commanded appearance/read-only navigation. No model, arbitrary URL or OS input. */
(() => {
  'use strict';
  const form = document.querySelector('[data-romeo-action-form]');
  const root = document.querySelector('[data-romeo-presence]');
  const field = form?.querySelector('[name="command"]');
  const output = form?.querySelector('[data-romeo-action-status]');
  const clarifications = form?.querySelector('[data-romeo-clarifications]');
  const submit = form?.querySelector('[type="submit"]');
  const stops = root?.querySelectorAll('[data-romeo-action-stop]');
  if (!form || !root || !field || !output || !submit || !stops || !clarifications || !crypto.randomUUID) return;
  if (form.dataset.actionUrl !== '/romeo/actions/' || form.dataset.interpretUrl !== '/romeo/interpret/') return;
  const tabID = crypto.randomUUID(); // Fresh for this document; never shared across tabs.
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  const navigation = Object.freeze({
    calendar_open: { path: '/calendar/', nav: 'calendar', title: 'Calendario' },
    directory_open: { path: '/directory/', nav: 'directory', title: 'Directorio' },
    people_search: { path: '/directory/', nav: 'directory', title: 'Búsqueda de personas' },
    events_open: { path: '/', nav: 'events', title: 'Eventos' }
  });
  const handoffKey = 'sparkx.romeo.navigation';
  let current = null;
  let interpreting = null;
  let lastStage = '';
  // Diagnostic metadata only. Authority remains in the server's UIAction receipt.
  let lastReceipt = { action_id: '', action: '' };
  function diagnosticDetail(stage) {
    if (current) lastReceipt = { action_id: uuid.test(current.id || '') ? current.id : '', action: current.action || '' };
    return { stage, ...lastReceipt, reply: output.textContent.slice(0, 500) };
  }
  const settled = () => document.dispatchEvent(new CustomEvent('sparkx:romeo-action-settled', { detail: diagnosticDetail(lastStage) }));
  const allowedActions = new Set(['theme_light', 'theme_dark', 'calendar_open', 'directory_open', 'events_open', 'people_search']);
  function clearClarification() { clarifications.replaceChildren(); clarifications.hidden = true; }
  function interpretation(data) {
    if (!data || !['understood', 'clarify', 'refused', 'info'].includes(data.status) ||
        typeof data.message !== 'string' || data.message.length > 500 ||
        !Array.isArray(data.options) || data.options.length > 3) throw new Error('Interpretación inválida. No se ejecutó ninguna acción.');
    if (data.status === 'understood') {
      if (!allowedActions.has(data.action) || typeof data.query !== 'string' || data.query.length > 100 ||
          /[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u.test(data.query) ||
          (data.action === 'people_search' ? !data.query.trim() : data.query !== '') || data.options.length) throw new Error('Acción interpretada inválida. No se ejecutó ninguna acción.');
    } else if (data.action != null || data.query !== '' || (data.status === 'info' && (data.action !== null || data.options.length))) throw new Error('Aclaración inválida. No se ejecutó ninguna acción.');
    for (const option of data.options) {
      if (!option || typeof option.label !== 'string' || !option.label || option.label.length > 150 ||
          typeof option.command !== 'string' || !option.command || option.command.length > 300 ||
          /[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u.test(option.command)) throw new Error('Opción inválida. No se ejecutó ninguna acción.');
    }
    return data;
  }
  function showClarification(data) {
    clearClarification();
    for (const option of data.options) {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'button button-secondary'; button.textContent = option.label;
      button.addEventListener('click', (event) => {
        if (current || interpreting) return;
        document.dispatchEvent(new CustomEvent('sparkx:dictation-cancel', { detail: { inputID: field.id, reason: 'manual-option' } }));
        if (field.dataset.voiceListening === 'true') return;
        // Removing this button must not look like an outside click to the panel.
        event.stopPropagation();
        field.value = option.command; clearClarification(); field.focus();
        state('clarify', 'Preparé la opción elegida. Revisa el texto y pulsa Ejecutar orden; todavía no se ejecutó nada.');
      });
      clarifications.append(button);
    }
    clarifications.hidden = data.options.length === 0;
  }
  function state(stage, text, error = false) {
    lastStage = stage;
    output.textContent = text; output.dataset.error = String(error);
    document.dispatchEvent(new CustomEvent('sparkx:romeo-action-state', { detail: diagnosticDetail(stage) }));
  }
  function busy(active) {
    root.dataset.uiActionActive = active ? '1' : '0';
    submit.disabled = active || field.dataset.voiceListening === 'true'; field.readOnly = active;
    form.querySelectorAll('[data-dictate]').forEach((button) => { button.disabled = active; });
    stops.forEach((button) => { button.hidden = !active; button.disabled = false; });
    document.dispatchEvent(new CustomEvent('sparkx:romeo-action-layout'));
  }
  async function post(path, values, tab = tabID) {
    const token = form.querySelector('[name="csrfmiddlewaretoken"]')?.value;
    if (!token) throw new Error('No se pudo comprobar tu sesión. Recarga la página.');
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 6000);
    try {
      const response = await fetch(path, { method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal,
        headers: { 'X-CSRFToken': token, 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json' },
        body: new URLSearchParams({ ...values, tab_id: tab }) });
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('El servidor no autorizó o no confirmó esta orden. Recarga para revisar tu sesión.');
      const text = await response.text();
      if (text.length > 4096) throw new Error('Respuesta de control inválida.');
      try { return JSON.parse(text); } catch (_) { throw new Error('Respuesta de control inválida.'); }
    } finally { clearTimeout(deadline); }
  }
  function receipt(data, order, expected) {
    if (!data || !uuid.test(data.id) || data.action !== order.action || data.state !== expected ||
        data.query !== order.query ||
        !Number.isFinite(Date.parse(data.expires_at)) || (order.id && data.id !== order.id)) throw new Error('El recibo de esta orden no es válido.');
    return data;
  }
  function controlFor(order, reveal = false) {
    const config = navigation[order.action];
    const buttons = document.querySelectorAll(config ? `.main-nav a[data-romeo-nav="${config.nav}"]` : 'button[data-theme-toggle]');
    if (buttons.length !== 1) return null;
    const button = buttons[0];
    if (config) {
      const url = new URL(button.href, location.origin);
      if (url.origin !== location.origin || url.pathname !== config.path || url.search || url.hash || button.target || button.hasAttribute('download')) return null;
    }
    let rect = button.getBoundingClientRect();
    if (reveal && (rect.top < 0 || rect.bottom > innerHeight || rect.left < 0 || rect.right > innerWidth)) {
      button.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'nearest' }); rect = button.getBoundingClientRect();
    }
    if (button.disabled || button.closest('[hidden]') || rect.width <= 0 || rect.height <= 0 || rect.top < 0 || rect.bottom > innerHeight || rect.left < 0 || rect.right > innerWidth) return null;
    const covering = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    return covering && button.contains(covering) ? button : null;
  }
  function cancelled(order) { return current !== order || order.cancelled || document.hidden; }
  function pause(order, duration) {
    return new Promise((resolve) => {
      const timer = setTimeout(() => { order.wake = null; resolve(!cancelled(order)); }, duration);
      order.wake = () => { clearTimeout(timer); order.wake = null; resolve(false); };
    });
  }
  function stop() {
    if (interpreting) {
      interpreting.cancelled = true; interpreting = null; busy(false); clearClarification();
      state('cancelled', 'Interpretación detenida. No se envió ninguna acción.'); settled(); return;
    }
    const order = current;
    if (!order || order.clicked || order.finishing) return;
    order.cancelled = true; order.wake?.();
    stops.forEach((button) => { button.disabled = true; });
    state('cancelled', 'Detenida: no se ejecutará el clic. Confirmando el registro…');
  }
  async function finish(order, outcome) {
    order.finishing = true;
    const data = await post('/romeo/actions/' + order.id + '/finish/', { outcome }, order.tab || tabID);
    receipt(data, order, outcome);
  }
  function destination(order) {
    const config = navigation[order.action];
    const params = new URLSearchParams();
    if (order.action === 'people_search') params.set('q', order.query);
    return config.path + (params.size ? '?' + params.toString() : '');
  }
  function arrived(order) {
    const config = navigation[order.action];
    if (!config || location.pathname + location.search !== destination(order)) return false;
    const marker = document.querySelector(`[data-romeo-destination="${config.nav}"]`);
    if (!marker || marker.dataset.romeoDestinationError === 'true') return false;
    return order.action !== 'people_search' || marker.dataset.romeoQuery === order.query;
  }
  async function resumeNavigation() {
    lastReceipt = { action_id: '', action: '' };
    let raw;
    try { raw = sessionStorage.getItem(handoffKey); if (raw) sessionStorage.removeItem(handoffKey); } catch (_) { return; }
    if (!raw) return;
    let order;
    try {
      if (raw.length > 1024) throw new Error('Invalid handoff');
      order = JSON.parse(raw);
      if (!order || !uuid.test(order.id) || !uuid.test(order.tab) || !Object.hasOwn(navigation, order.action) ||
          typeof order.query !== 'string' || order.query.length > 100 ||
          (order.action === 'people_search' ? !order.query : order.query !== '') || !Number.isFinite(Date.parse(order.expires_at)) ||
          Date.parse(order.expires_at) <= Date.now() || !arrived(order)) throw new Error('Invalid destination');
    } catch (_) { state('failed', 'Se interrumpió una navegación de Gica. No se repetirá ningún clic.', true); return; }
    current = order; busy(true);
    stops.forEach((control) => { control.disabled = true; });
    try {
      state('checking_destination', 'Destino cargado. Confirmando el registro de tu orden…');
      await finish(order, 'completed');
      const count = document.querySelector('[data-romeo-destination="directory"]')?.dataset.romeoResultCount;
      state('arrived', order.action === 'people_search' && /^\d+$/.test(count || '') ? `Búsqueda completada: ${count} coincidencia(s) en tu directorio. 0 tokens.` : `${navigation[order.action].title} abierto y comprobado. 0 tokens.`);
      const details = root.querySelector('#romeo-presence-details');
      if (details) { details.hidden = false; root.querySelector('[data-romeo-presence-toggle]')?.setAttribute('aria-expanded', 'true'); }
    } catch (_) { state('unrecorded', 'El destino está abierto, pero su registro final no se confirmó. No se repetirá el clic.', true); }
    finally { current = null; busy(false); settled(); }
  }
  async function execute(command) {
    const { action, query } = command;
    const order = { action, query, id: null, cancelled: false, clicked: false, started: false, finishing: false, navigating: false };
    current = order; busy(true);
    let button = null;
    try {
      state('registering', 'Registrando tu orden. Puedes detenerla antes del clic.');
      const created = receipt(await post('/romeo/actions/', { action, query, request_key: crypto.randomUUID() }), order, 'pending');
      order.id = created.id;
      order.expires_at = created.expires_at;
      if (cancelled(order)) { await finish(order, 'cancelled'); state('cancelled', 'Orden detenida. No se ejecutó ningún clic.'); return; }
      state('pending', `${command.message || 'Orden registrada.'} Puedes detenerla antes del clic.`);
      const desired = action === 'theme_light' ? 'light' : 'dark';
      const config = navigation[action];
      const already = !config && document.documentElement.dataset.theme === desired;
      if (!already) {
        if (!await pause(order, 500)) { await finish(order, 'cancelled'); state('cancelled', 'Orden detenida. No se ejecutó ningún clic.'); return; }
        button = controlFor(order, true);
        if (!button) throw new Error('El control autorizado no está visible o está cubierto. La orden no se ejecutó.');
        button.classList.add('romeo-action-target');
        state('moving', config ? `Moviendo el cursor a ${config.title}… Detener o Escape cancela antes del clic.` : 'Moviendo el cursor al botón del tema… Detener o Escape cancela antes del clic.');
        if (!await pause(order, 1800)) { await finish(order, 'cancelled'); state('cancelled', 'Orden detenida. No se ejecutó ningún clic.'); return; }
      }
      if (cancelled(order)) { await finish(order, 'cancelled'); state('cancelled', 'Orden detenida. No se ejecutó ningún clic.'); return; }
      receipt(await post('/romeo/actions/' + order.id + '/start/', {}), order, 'executing');
      order.started = true;
      if (cancelled(order)) { await finish(order, 'cancelled'); state('cancelled', 'Orden detenida. No se ejecutó ningún clic.'); return; }
      if (config) {
        button = controlFor(order);
        if (!button) throw new Error('El enlace autorizado dejó de estar disponible. No se ejecutó el clic.');
        if (!window.SparkXGicaNavigation) throw new Error('La navegación continua no está disponible. Recarga antes de iniciar otra orden.');
        const original = button.getAttribute('href');
        button.setAttribute('href', destination(order));
        state('clicking', 'Abriendo el destino autorizado. Se comprobará tras cargar…');
        order.clicked = true;
        stops.forEach((control) => { control.disabled = true; });
        window.SparkXGicaNavigation.prepare(button);
        try { button.click(); } finally { button.setAttribute('href', original); }
        const transition = window.SparkXGicaNavigation.resultFor(button);
        const result = transition ? await transition : null;
        if (!result || result.success !== true || !uuid.test(result.id || '') || result.path !== destination(order) || !arrived(order)) throw new Error('No se pudo comprobar el destino autorizado.');
        state('checking_destination', 'Destino cargado. Confirmando el registro de tu orden…');
        await finish(order, 'completed');
        const count = document.querySelector('[data-romeo-destination="directory"]')?.dataset.romeoResultCount;
        state('arrived', action === 'people_search' && /^\d+$/.test(count || '') ? `Búsqueda completada: ${count} coincidencia(s) en tu directorio. 0 tokens.` : `${config.title} abierto y comprobado. 0 tokens.`);
        return;
      }
      // No await between the final check and the single fixed-control click.
      if (document.documentElement.dataset.theme !== desired) {
        button = controlFor(order);
        if (!button) throw new Error('El botón dejó de estar disponible. No se ejecutó el clic.');
        state('clicking', 'Aplicando el tema que pediste…');
        order.clicked = true;
        stops.forEach((control) => { control.disabled = true; });
        button.click();
      }
      if (document.documentElement.dataset.theme !== desired) throw new Error('El navegador no confirmó el tema solicitado.');
      await finish(order, 'completed');
      state(order.clicked ? 'completed' : 'already', order.clicked ? `Listo: modo ${desired === 'light' ? 'claro' : 'oscuro'} comprobado. Un clic, 0 tokens.` : 'El dashboard ya tenía ese tema. Comprobado sin hacer clic, 0 tokens.');
    } catch (error) {
      if (order.id && !order.finishing) {
        try { await finish(order, order.started && !order.cancelled ? 'failed' : 'cancelled'); } catch (_) { /* Unknown receipt remains unknown; never retry a click. */ }
      }
      if (order.clicked) state('unrecorded', 'Se ejecutó el clic, pero no se confirmó toda la operación. Revisa el destino y tu sesión; no se repetirá.', true);
      else if (order.cancelled) state('cancelled', 'Orden detenida sin clic. No se pudo confirmar el registro final.', true);
      else state('failed', error instanceof Error ? error.message : 'No se pudo completar la orden. No se hará otro intento.', true);
    } finally {
      button?.classList.remove('romeo-action-target');
      if (current === order && !order.navigating) { current = null; busy(false); settled(); }
    }
  }
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (current || interpreting) return;
    if (field.dataset.voiceListening === 'true') { output.textContent = 'Termina el dictado y revisa el texto antes de ejecutar.'; return; }
    lastReceipt = { action_id: '', action: '' };
    clearClarification();
    const attempt = { cancelled: false }; interpreting = attempt; busy(true);
    state('interpreting', 'Interpretando tu frase con el catálogo local. Todavía no se envió ninguna acción.');
    try {
      const result = interpretation(await post('/romeo/interpret/', { command: field.value }));
      if (interpreting !== attempt || attempt.cancelled || document.hidden) return;
      interpreting = null; busy(false);
      if (result.status === 'info') { state('info', result.message); settled(); return; }
      if (result.status !== 'understood') {
        state(result.status === 'clarify' ? 'clarify' : 'failed', result.message, result.status === 'refused');
        showClarification(result); settled(); return;
      }
      execute(result);
    } catch (error) {
      if (interpreting === attempt) state('failed', error instanceof Error ? error.message : 'No se pudo interpretar la orden.', true);
    } finally {
      if (interpreting === attempt) { interpreting = null; busy(false); settled(); }
    }
  });
  field.addEventListener('input', clearClarification);
  document.addEventListener('sparkx:dictation-state', (event) => {
    if (event.detail?.inputID === field.id) { clearClarification(); submit.disabled = !!current || !!interpreting || field.dataset.voiceListening === 'true'; }
  });
  stops.forEach((button) => button.addEventListener('click', stop));
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && (current || interpreting)) { event.preventDefault(); stop(); } else if (event.key === 'Escape') clearClarification(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
  window.addEventListener('pagehide', stop);
  // Voice may submit only the exact visible draft through the ordinary form.
  // The interpreter, authority checks and action whitelist remain unchanged.
  window.SparkXRomeoCommands = Object.freeze({
    canStartVoice: () => !current && !interpreting && !document.hidden && !form.hidden && !field.readOnly && !field.disabled,
    executeDraft: (draft) => {
      if (typeof draft !== 'string' || !draft.trim() || draft !== field.value || draft.length > 300 ||
          current || interpreting || document.hidden || form.hidden || field.readOnly || field.disabled ||
          field.closest('[hidden]') || field.dataset.voiceListening === 'true' || submit.disabled) return false;
      form.requestSubmit(submit); return true;
    }
  });
  form.hidden = false;
  resumeNavigation();
})();

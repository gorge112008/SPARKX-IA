/* A visual marker for observed server/browser states, never a mouse driver.
 * Model output never becomes code, selectors, clicks, permissions or raw HTML.
 * The separate, human-commanded theme runner can temporarily use this marker.
 */
(() => {
  'use strict';
  const root = document.querySelector('[data-romeo-presence]');
  const overlay = document.querySelector('[data-romeo-cursor]');
  const glyph = overlay?.querySelector('[data-romeo-cursor-glyph]');
  if (!root || !overlay || !glyph) return;
  const status = root.querySelector('[data-romeo-cursor-status]');
  const copy = root.querySelector('[data-romeo-cursor-copy]');
  const toggle = root.querySelector('[data-romeo-presence-toggle]');
  const details = root.querySelector('#romeo-presence-details');
  const visibility = document.querySelector('[data-romeo-visibility]');
  const eventName = root.querySelector('[data-romeo-event-name]');
  const eventLink = root.querySelector('[data-romeo-event-link]');
  const home = root.querySelector('[data-romeo-home]');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const UUID = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
  const validID = new RegExp('^' + UUID + '$');
  const AUTHORIZED_PILOT = 'bcf52dbd-206b-4d22-a294-8c487c770c56';
  const currentEventID = () => location.pathname.match(new RegExp('^/events/(' + UUID + ')/$'))?.[1] || null;
  let eventID = currentEventID(), navigationID = null, pageGeneration = 0;
  const states = new Set(['queued', 'running', 'succeeded', 'failed', 'cancelled', 'stale']);
  const stages = new Set(['queued', 'budget_fallback', 'free_pool_selected', 'context_ready', 'request_started',
    'response_received', 'validating', 'review_ready', 'needs_changes', 'completed', 'failed', 'cancelled', 'stale', '']);
  const labels = { queued: 'En cola', running: 'En ejecución', succeeded: 'Resultado disponible',
    failed: 'Ejecución detenida', cancelled: 'Cancelado', stale: 'Contexto desactualizado' };
  const ranks = { '': 0, queued: 0, budget_fallback: 1, free_pool_selected: 1, context_ready: 2,
    request_started: 3, response_received: 4, validating: 5, review_ready: 6, needs_changes: 6,
    completed: 6, failed: 7, cancelled: 7, stale: 7 };
  // Selectors and labels are application constants. The JSON cannot select UI.
  const descriptions = {
    queued: 'Solicitud guardada; espera su turno.', budget_fallback: 'Alternativa gratuita seleccionada antes de llamar.',
    free_pool_selected: 'Modelo gratuito autorizado seleccionado para esta tarea.', context_ready: 'Contexto preparado para el modelo seleccionado.',
    request_started: 'Conexión con el proveedor iniciada.', response_received: 'Respuesta recibida del proveedor.',
    validating: 'El servidor está comprobando la respuesta.', review_ready: 'Propuesta lista para tu revisión.',
    needs_changes: 'La propuesta tiene observaciones que debes revisar.', completed: 'La respuesta está disponible en la conversación.',
    failed: 'La ejecución se detuvo. Revisa el seguimiento; el plan vigente se conserva.',
    cancelled: 'Solicitud cancelada. Una llamada ya enviada puede conservar consumo pendiente.',
    stale: 'El contexto cambió. El resultado no modifica el plan vigente.'
  };
  let shown = true;
  try { shown = localStorage.getItem('sparkx.romeo.cursor') !== 'hidden'; } catch (_) { /* Preference is optional. */ }
  let x = 0, y = 0, animation = 0, target = home, timer = 0, controller = null, pendingForm = null;
  let lastObserved = 0, lastSignature = '', localCompletedAt = 0, lastUpdate = 0, disposed = false, permitted = true;
  const jobUpdates = new Map();
  const localLoads = new Set();
  let localController = null;
  let demoCursor = null;
  const demoOwner = document.body.dataset.voiceUser;
  const demoRole = document.body.dataset.portalRole;
  const demoFields = new Set(['title', 'organization', 'speaker', 'brief', 'date', 'time', 'timezone', 'capacity', 'is_synthetic',
    'objective', 'audience', 'modality', 'duration_minutes', 'location', 'resources', 'constraints']);
  const demoBlocks = new Set(['identity', 'schedule', 'audience', 'description', 'preparation']);
  const demoNames = new Set(['title', 'organization_id', 'speaker_id', 'brief', 'scheduled_dates', 'starts_at', 'timezone', 'capacity', 'is_synthetic',
    'objective', 'audience', 'modality', 'duration_minutes', 'location', 'resources', 'constraints']);

  // The narrated tour owns this SVG marker only. Its bounded controls are not
  // general agent clicks or mouse automation. Pointing grants no activation.
  function demoLease(signal) {
    return !disposed && !document.hidden && !signal?.aborted && root.isConnected &&
      root.dataset.gicaDemoActive === 'true' && root.dataset.uiActionActive !== '1' &&
      document.body.dataset.voiceUser === demoOwner && document.body.dataset.portalRole === demoRole &&
      ['admin', 'organizer'].includes(demoRole);
  }
  function demoTarget(element) {
    if (!(element instanceof Element) || !element.isConnected || element.closest('[hidden],[inert]')) return '';
    if (root.dataset.gicaPilotEvent === AUTHORIZED_PILOT && element.matches('button[data-gica-prompt-execute]') &&
        window.SparkXGicaPilotAI?.canExecute?.(element) === true) return 'control';
    if(element.matches('button[data-gica-directory-select],button[data-gica-directory-option]')&&window.SparkXGicaDemo?.canDirectoryControl?.(element)===true)return 'control';
    if(element.matches('button[data-gica-simulate-status]')&&window.SparkXGicaDemo?.canSimulationControl?.(element)===true)return 'control';
    if (element instanceof HTMLAnchorElement) {
      const url = new URL(element.href, location.origin);
      if (url.origin !== location.origin || url.username || url.password ||
          element.target || element.hasAttribute('download')) return '';
      if (url.pathname === '/calendar/' && !url.hash && ['2026-11-19', '2026-11-26'].includes(element.dataset.calendarDay) &&
          element.matches('main[data-romeo-destination="calendar"] a[data-calendar-day]') && url.searchParams.get('day') === element.dataset.calendarDay &&
          url.searchParams.get('month') === '2026-11' && [...url.searchParams.keys()].every((key) => ['month', 'day'].includes(key))) return 'navigation';
      if(url.pathname==='/directory/'&&!url.hash&&element.matches('main[data-romeo-destination="directory"] .directory-tabs a')&&['','?tab=organizations'].includes(url.search))return 'navigation';
      if (url.search) return '';
      if (!url.hash && url.pathname === '/' && element.matches('.main-nav a[data-romeo-nav="events"]')) return 'navigation';
      if (!url.hash && url.pathname === '/calendar/' && element.matches('.main-nav a[data-romeo-nav="calendar"]')) return 'navigation';
      if (!url.hash && url.pathname === '/directory/' && element.matches('.main-nav a[data-romeo-nav="directory"]')) return 'navigation';
      if (!url.hash && url.pathname === '/assistant/profile/' && element.matches('.main-nav a[data-romeo-nav="profile"]')) return 'navigation';
      if (!url.hash && url.pathname === '/events/new/' && element.matches('main .page-heading a.button')) return 'navigation';
      if (!url.hash && url.pathname === '/directory/organizations/new/' && element.matches('main [data-gica-field="organization"] a')) return 'navigation';
      if(!url.hash&&['/directory/organizations/new/','/directory/people/new/'].includes(url.pathname)&&element.matches('main[data-romeo-destination="directory"] .directory-actions a'))return 'navigation';
      const pilot = root.dataset.gicaPilotEvent;
      if (pilot === AUTHORIZED_PILOT && element.closest('main#main-content')) {
        if (url.pathname === `/events/${pilot}/` && ['', '#plan', '#agenda', '#preparation', '#proposals', '#activity'].includes(url.hash)) {
          return url.pathname === location.pathname && url.hash ? 'control' : 'navigation';
        }
        if (!url.hash && url.pathname === `/events/${pilot}/edit/` && element.matches('.heading-actions a')) return 'navigation';
        if (!url.hash && url.pathname === `/events/${pilot}/schedule/` && element.matches('[data-gica-adjust-hours]')) return 'navigation';
      }
      return '';
    }
    if (element.matches('main[data-gica-pilot="true"] button[data-gica-pilot-plan]') && ['plan', 'replan', 'change'].includes(element.dataset.gicaPilotPlan)) return 'control';
    if (element.matches('main[data-gica-pilot="true"] #preparation [data-task-instructions] > summary')) return 'control';
    if (element.matches('main[data-gica-pilot="true"] #preparation [data-task-followup] > summary')) return 'control';
    const scheduleForm = element.closest('main[data-gica-pilot-schedule="true"] form[data-pilot-schedule]');
    if (scheduleForm && root.dataset.gicaPilotEvent === AUTHORIZED_PILOT && location.pathname === `/events/${AUTHORIZED_PILOT}/schedule/`) {
      if (element.matches('[data-gica-schedule-submit]')) return 'submit';
      if (element.matches('input') && /^(?:sessions-[12]-(?:start|duration_minutes))$/.test(element.name)) return 'field';
    }
    const candidateForm = element.closest('main[data-gica-pilot="true"] .candidate-actions form');
    if (candidateForm && element.matches('button[type="submit"]')) {
      const expected = new RegExp('^/events/' + root.dataset.gicaPilotEvent + '/candidates/[0-9a-f-]{36}/approve/$', 'i');
      if (root.dataset.gicaPilotEvent === AUTHORIZED_PILOT && expected.test(new URL(candidateForm.action, location.origin).pathname)) return 'submit';
    }
    const organizationForm = element.closest('main .directory-form');
    if (organizationForm && location.pathname === '/directory/organizations/new/') {
      if(element.matches('input[type="checkbox"][name="is_active"],input[type="checkbox"][name="is_synthetic"]'))return 'control';
      if (element.matches('input[name="name"],textarea[name="aliases"],input[name="is_active"],input[name="is_synthetic"]')) return 'field';
      if (element.matches('button[type="submit"]')) return 'submit';
    }
    if(organizationForm&&location.pathname==='/directory/people/new/'){
      if(element.matches('input[type="checkbox"][name="is_active"],input[type="checkbox"][name="is_synthetic"]'))return 'control';
      if(element.matches('input[name="full_name"],textarea[name="aliases"],input[name="email"],textarea[name="expertise"]'))return 'field';
      if(element.matches('button[type="submit"]'))return 'submit';
    }
    const form = document.querySelector('main form[data-event-block-form][data-gica-demo-live="true"], main form[data-gica-event-form="create"][data-gica-demo-preview="true"]');
    if (!form || form.dataset.gicaGuidedDraft) return '';
    if (form.contains(element)) {
      if (demoFields.has(element.dataset.gicaField) || demoBlocks.has(element.dataset.gicaFormBlock)) return 'field';
      if (demoNames.has(element.getAttribute('name')) && form.elements.namedItem(element.getAttribute('name')) === element &&
          (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement) &&
          element.type !== 'hidden') return 'field';
      if (element.matches('button[type="submit"]')) return 'submit';
      if (element.matches('[data-event-select-toggle],[data-event-select-option]') &&
          ['organization_id', 'speaker_id', 'timezone', 'modality'].includes(element.dataset.eventSelectToggle || element.dataset.eventSelectOption)) return 'control';
      if (element.matches('[data-event-preset="capacity"][data-event-preset-value="100"], [data-event-date-toggle], [data-event-time]')) return 'control';
      if (element.matches('[data-event-date-day]') && ['2026-11-19', '2026-11-26'].includes(element.dataset.eventDateDay)) return 'control';
      if (element.matches('[data-event-date-month]') && ['prev', 'next'].includes(element.dataset.eventDateMonth)) return 'control';
    }
    return '';
  }
  function demoPointTarget(element) {
    if (!(element instanceof Element) || !element.isConnected || element.closest('[hidden],[inert]') ||
        root.dataset.gicaPilotEvent !== AUTHORIZED_PILOT || element.closest('form,button,input,textarea,select')) return '';
    const main = element.closest('main#main-content');
    if (!main) return '';
    if(location.pathname==='/assistant/profile/'&&main.matches('[data-romeo-destination="profile"]')&&
        element.closest('.gica-profile-identity,.gica-profile-section')&&element.matches('h2,h3,p,ul,li,span,strong,blockquote'))return 'explanation';
    const article = element.closest('.calendar-event-detail');
    if (main.matches('[data-romeo-destination="calendar"]') && location.pathname === '/calendar/' && article) {
      const link = article.querySelector('a.calendar-open-event');
      if (!link) return '';
      const url = new URL(link.href, location.origin);
      if (url.origin !== location.origin || url.username || url.password || url.search ||
          url.pathname !== `/events/${AUTHORIZED_PILOT}/` || !['', '#plan'].includes(url.hash)) return '';
      return element === article || element.matches('h3,h4,p,ol,li,span,div') ? 'explanation' : '';
    }
    if (location.pathname !== `/events/${AUTHORIZED_PILOT}/` || main.dataset.eventId !== AUTHORIZED_PILOT ||
        main.dataset.gicaPilot !== 'true') return '';
    const region = element.closest('[data-event-speaker], .event-meta, [data-workspace-panel]');
    return region && main.contains(region) && (element === region || element.matches('h2,h3,h4,p,ol,ul,li,span,strong,div,time')) ? 'explanation' : '';
  }
  function demoRunTarget(run) { return run.mode === 'point' ? demoPointTarget(run.element) : demoTarget(run.element); }
  function demoBounds() {
    const viewport = window.visualViewport;
    const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
    return { left: left + 5, top: top + 5,
      right: left + (viewport?.width || innerWidth) - 5, bottom: top + (viewport?.height || innerHeight) - 5 };
  }
  function demoAnchor(element, mode) {
    if (mode === 'point') {
      const rect = element.getBoundingClientRect(), bounds = demoBounds();
      if (rect.height > (bounds.bottom - bounds.top) * .65 || rect.width > (bounds.right - bounds.left) * .92) {
        const headings = [...element.querySelectorAll('h2,h3,h4')].filter((node) => !node.closest('[hidden],[inert]'));
        return headings[0] || element;
      }
      return element;
    }
    const candidates = element.matches('input,textarea,select,button') ? [element] :
      [...element.querySelectorAll('input:not([type="hidden"]),textarea,select,[data-event-select-toggle],[data-event-date-toggle]')];
    // A field wrapper includes its label. Place the cursor inside its actual
    // visible control, including progressive selectors whose native select hides.
    return candidates.find((node) => visible(node) && getComputedStyle(node).visibility !== 'hidden') || element;
  }
  function demoDestination(element, mode) {
    const anchor = demoAnchor(element, mode), box = anchor.getBoundingClientRect();
    const bounds = demoBounds(), left = Math.max(box.left, bounds.left), right = Math.min(box.right, bounds.right);
    const top = Math.max(box.top, bounds.top), bottom = Math.min(box.bottom, bounds.bottom);
    const center = { x: (left + right) / 2, y: (top + bottom) / 2 };
    if (mode === 'point' || anchor.matches('input,textarea')) return center;
    // Keep the tip vertically centered, in the control's trailing padding or
    // chevron, so neither the arrow nor an agent label covers its caption.
    if (anchor.matches('select,button,a,summary')) {
      const style = getComputedStyle(anchor), inset = Math.max(7, Math.min(14, (parseFloat(style.paddingRight) || 14) / 2));
      return { x: Math.max(left + 4, right - inset), y: center.y };
    }
    return center;
  }
  function drawExplanation(run) {
    if (!run.outline || run.expired || !visible(run.element)) return;
    const box = demoAnchor(run.element, 'point').getBoundingClientRect(), bounds = demoBounds();
    const left = Math.max(bounds.left + 3, box.left - 6), right = Math.min(bounds.right - 3, box.right + 6);
    const top = Math.max(bounds.top + 3, box.top - 6), bottom = Math.min(bounds.bottom - 3, box.bottom + 6);
    demoDraw((left + right) / 2, (top + bottom) / 2);
    run.outline.setAttribute('x', String(-(right - left) / 2)); run.outline.setAttribute('y', String(-(bottom - top) / 2));
    run.outline.setAttribute('width', String(Math.max(0, right - left))); run.outline.setAttribute('height', String(Math.max(0, bottom - top)));
  }
  function demoDraw(left, top) {
    const bounds = demoBounds();
    x = Math.max(bounds.left, Math.min(bounds.right - 1, left));
    y = Math.max(bounds.top, Math.min(bounds.bottom - 1, top));
    glyph.setAttribute('transform', `translate(${x.toFixed(2)} ${y.toFixed(2)})`);
    overlay.querySelector('.romeo-cursor-label')?.setAttribute('transform', x > innerWidth - 126 ? 'translate(-104 0)' : 'translate(0 0)');
  }
  function demoDelay(run, milliseconds, draw) {
    return new Promise((resolve) => {
      const started = performance.now();
      function frame(now) {
        if (demoCursor !== run || !demoLease(run.signal) || !demoRunTarget(run) || !visible(run.element)) { resolve(false); return; }
        const fraction = milliseconds <= 0 ? 1 : Math.min(1, (now - started) / milliseconds);
        draw?.(fraction);
        if (fraction >= 1) resolve(true);
        else run.frame = requestAnimationFrame(frame);
      }
      run.frame = requestAnimationFrame(frame);
    });
  }
  function releaseDemoCursor() {
    if (demoCursor) {
      demoCursor.ripple?.remove();
      demoCursor.animation?.cancel();
      clearTimeout(demoCursor.expiry);
      demoCursor.signal?.removeEventListener('abort', demoCursor.onAbort);
      // Keep its next frame alive once so an interrupted promise resolves.
      demoCursor = null;
    }
    delete overlay.dataset.gicaDemoCursor;
    overlay.classList.remove('is-pointing', 'is-writing');
    glyph.querySelector('.romeo-explanation-pointer')?.remove();
    target = home; position(true);
  }
  async function demoMoveTo(element, options = {}, mode = 'action') {
    if (!demoLease(options.signal) || !(mode === 'point' ? demoPointTarget(element) : demoTarget(element)) || demoCursor?.busy) return false;
    clearTimeout(demoCursor?.expiry);
    demoCursor?.signal?.removeEventListener('abort', demoCursor.onAbort);
    glyph.querySelector('.romeo-explanation-pointer')?.remove();
    overlay.classList.remove('is-writing');
    overlay.classList.toggle('is-pointing', mode === 'point');
    const run = { element, signal: options.signal, busy: true, mode };
    demoCursor = run;
    run.onAbort = () => { if (demoCursor === run) releaseDemoCursor(); };
    run.signal?.addEventListener('abort', run.onAbort, { once: true });
    cancelAnimationFrame(animation);
    overlay.dataset.gicaDemoCursor = 'true';
    overlay.classList.remove('is-docked', 'is-paused');
    document.dispatchEvent(new CustomEvent('sparkx:gica-demo-target', { detail: { user: demoOwner, element: demoAnchor(element, mode) } }));
    const anchor = demoAnchor(element, mode), rect = anchor.getBoundingClientRect(), bounds = demoBounds();
    const topbar = document.querySelector('.app-topbar')?.getBoundingClientRect();
    const safeTop = Math.max(bounds.top + 12, topbar && topbar.top <= bounds.top ? topbar.bottom + 12 : 76);
    if (rect.top < safeTop || rect.bottom > bounds.bottom - 24 || rect.left < bounds.left || rect.right > bounds.right) {
      anchor.scrollIntoView({ block: 'center', inline: 'nearest', behavior: reduced.matches ? 'instant' : 'smooth' });
      const started = performance.now();
      let previous = anchor.getBoundingClientRect().top, stable = 0;
      while (performance.now() - started < 1300) {
        await new Promise((resolve) => requestAnimationFrame(resolve));
        if (demoCursor !== run || !demoLease(run.signal) || !demoRunTarget(run)) { releaseDemoCursor(); return false; }
        const top = anchor.getBoundingClientRect().top;
        stable = Math.abs(top - previous) < .5 ? stable + 1 : 0; previous = top;
        if (stable >= 4 && performance.now() - started > 160) break;
      }
    }
    if (!demoRunTarget(run) || !visible(element)) { releaseDemoCursor(); return false; }
    overlay.removeAttribute('hidden');
    const old = { x, y };
    const duration = reduced.matches ? 0 : Math.min(650, Math.max(260, Math.hypot(demoDestination(element, mode).x - x, demoDestination(element, mode).y - y) * .8));
    const completed = await demoDelay(run, duration, (fraction) => {
      const destination = demoDestination(element, mode);
      const eased = fraction < .5 ? 4 * fraction * fraction * fraction : 1 - Math.pow(-2 * fraction + 2, 3) / 2;
      demoDraw(old.x + (destination.x - old.x) * eased, old.y + (destination.y - old.y) * eased);
    });
    if (!completed) { if (demoCursor === run) releaseDemoCursor(); return false; }
    run.busy = false;
    return true;
  }
  async function demoMove(element, options = {}) { return demoMoveTo(element, options); }
  async function demoPoint(element, options = {}) {
    if (!await demoMoveTo(element, options, 'point')) return false;
    const run = demoCursor;
    if (!run || !demoLease(run.signal) || !demoPointTarget(element)) return false;
    const outline = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    outline.setAttribute('class', 'romeo-explanation-pointer'); outline.setAttribute('rx', '9');
    run.outline = outline; glyph.append(outline); drawExplanation(run);
    const hold = Number.isFinite(options.holdMs) ? Math.max(200, Math.min(8000, options.holdMs)) : 1400;
    run.expiry = setTimeout(() => { if (demoCursor === run) { run.expired = true; outline.remove(); overlay.setAttribute('hidden', ''); } }, hold);
    return true;
  }
  function demoPulse(run) {
    // Called after an actual activation. A focus-only move has no click ripple.
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('class', 'romeo-click-ripple');
    circle.setAttribute('cx', '0'); circle.setAttribute('cy', '0'); circle.setAttribute('r', '3');
    circle.setAttribute('fill', 'none'); circle.setAttribute('stroke', 'var(--link)'); circle.setAttribute('stroke-width', '2');
    run.ripple = circle; glyph.prepend(circle);
    return new Promise((resolve) => {
      const started = performance.now(), duration = reduced.matches ? 50 : 240;
      function frame(now) {
        if (demoCursor !== run || !demoLease(run.signal)) { circle.remove(); resolve(false); return; }
        const fraction = Math.min(1, (now - started) / duration);
        circle.setAttribute('r', String(3 + 14 * fraction)); circle.setAttribute('opacity', String(1 - fraction));
        if (fraction < 1) run.frame = requestAnimationFrame(frame);
        else { circle.remove(); run.ripple = null; resolve(true); }
      }
      run.frame = requestAnimationFrame(frame);
    });
  }
  async function demoClick(element, options = {}) {
    if (!await demoMove(element, options)) return false;
    const run = demoCursor, kind = demoTarget(element);
    if (!run || !kind || !demoLease(run.signal) || !visible(element)) return false;
    run.busy = true;
    if (kind === 'navigation' && options.activate !== false) {
      const navigation = window.SparkXGicaNavigation;
      if (!navigation?.prepare || !navigation?.resultFor) { releaseDemoCursor(); return false; }
      navigation.prepare(element, { signal: run.signal, source: 'narrated-demo' });
      element.click();
      const result = navigation.resultFor(element);
      if (!result) { releaseDemoCursor(); return false; }
      const [, observed] = await Promise.all([demoPulse(run), result]);
      if (demoCursor !== run || !demoLease(run.signal) || observed?.success !== true) {
        if (demoCursor === run) releaseDemoCursor(); return false;
      }
      run.busy = false;
      return true;
    }
    if (options.activate === true && ['control', 'submit'].includes(kind)) {
      if (element.matches(':disabled')) { run.busy = false; return false; }
      element.click();
      await demoPulse(run);
      run.busy = false;
      position(true);
      return demoLease(run.signal);
    }
    // Focusing a text field is real but is not an activation. In particular a
    // select wrapper never pretends to click its hidden native control.
    const control = demoAnchor(element, 'action');
    if (control?.matches('input,textarea,select,button') && !control.disabled && visible(control)) control.focus({ preventScroll: true });
    run.busy = false;
    position(true);
    return true;
  }
  window.SparkXGicaDemoCursor = Object.freeze({ move: demoMove, click: demoClick, point: demoPoint, release: releaseDemoCursor });
  document.addEventListener('sparkx:gica-demo-end', releaseDemoCursor);
  document.addEventListener('input', (event) => {
    const run = demoCursor, field = event.target;
    if (!run || run.mode !== 'action' || !demoLease(run.signal) || !field?.matches?.('input,textarea') ||
        !(field === run.element || run.element.contains(field)) || !demoTarget(field)) return;
    // Let the typed text and caret stay completely unobstructed until the
    // narrator moves to its next control.
    run.typing = true; overlay.classList.add('is-writing');
  }, true);
  new MutationObserver(() => { if (demoCursor && !demoLease(demoCursor.signal)) releaseDemoCursor(); })
    .observe(root, { attributes: true, attributeFilter: ['data-gica-demo-active'] });
  new MutationObserver(() => { if (demoCursor && !demoLease(demoCursor.signal)) releaseDemoCursor(); })
    .observe(document.body, { attributes: true, attributeFilter: ['data-voice-user', 'data-portal-role'] });

  function revealLocal(local, signature) {
    if (local.event_id !== eventID || localLoads.has(local.id)) return;
    localLoads.add(local.id);
    if (localLoads.size > 30) localLoads.delete(localLoads.values().next().value);
    const selector = `[data-romeo-local-result="${local.id}"]`;
    const reveal = () => {
      if (disposed || lastSignature !== signature || root.dataset.state !== 'local_completed') return;
      const reply = document.querySelector(selector);
      if (shown && reply) document.dispatchEvent(new CustomEvent('sparkx:romeo-result', { detail: { localId: local.id } }));
      target = visible(reply) ? reply : home; position();
    };
    if (document.querySelector(selector)) { reveal(); return; }
    // A command can arrive from the local operator while this page is open.
    // Refresh only this owner's chat from its existing, read-only event view.
    // Never execute returned scripts or insert arbitrary model HTML.
    const container = document.getElementById('chat-messages');
    if (!container || container.contains(document.activeElement)) return;
    localController?.abort();
    const request = new AbortController(); localController = request;
    const deadline = setTimeout(() => request.abort(), 7000);
    fetch(local.event_url, { credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: request.signal,
      headers: { Accept: 'text/html' } }).then(async (response) => {
      if (!response.ok || !response.headers.get('content-type')?.includes('text/html')) throw new Error('Chat unavailable');
      const text = await response.text();
      if (text.length > 1048576) throw new Error('Chat too large');
      const fragment = new DOMParser().parseFromString(text, 'text/html').getElementById('chat-messages');
      if (!fragment || !fragment.querySelector(selector)) throw new Error('Reply not visible');
      const tags = new Set(['DIV', 'ARTICLE', 'SPAN', 'P', 'BUTTON']);
      for (const node of fragment.querySelectorAll('*')) {
        if (!tags.has(node.tagName) || Array.from(node.attributes).some((attr) =>
          !['id','class','role','type','hidden'].includes(attr.name) && !/^(aria-|data-romeo-|data-read-message$)/.test(attr.name))) throw new Error('Invalid chat markup');
      }
      if (disposed || lastSignature !== signature || container.contains(document.activeElement)) return;
      container.replaceChildren(...Array.from(fragment.childNodes, (node) => document.importNode(node, true)));
      reveal();
    }).catch(() => {
      if (!disposed && lastSignature === signature) copy.textContent = 'Consulta local registrada. Abre el evento o recarga para leer su respuesta; no se llamó a un modelo de IA.';
    }).finally(() => { clearTimeout(deadline); if (localController === request) localController = null; });
  }

  function visible(element) {
    if (!element || !element.isConnected || element.closest('[hidden]')) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.top < innerHeight && rect.bottom > 0 && rect.left < innerWidth && rect.right > 0;
  }
  function position(immediate = false) {
    if (demoCursor) {
      const run = demoCursor;
      if (!demoLease(run.signal)) releaseDemoCursor();
      else if (!run.element.isConnected || !visible(run.element) || (!run.busy && !demoRunTarget(run))) overlay.setAttribute('hidden', '');
      else if (!run.busy && !run.expired) {
        overlay.removeAttribute('hidden');
        if (run.mode === 'point') drawExplanation(run);
        else {
          const destination = demoDestination(run.element, run.mode);
          demoDraw(destination.x, destination.y);
        }
      }
      return;
    }
    cancelAnimationFrame(animation);
    const anchor = !reduced.matches && visible(target) ? target : home;
    if (!visible(anchor) || !shown || document.hidden) { overlay.setAttribute('hidden', ''); return; }
    const docked = anchor === home;
    if (docked && home.querySelector('img')) { overlay.setAttribute('hidden', ''); return; }
    overlay.classList.toggle('is-docked', docked);
    overlay.removeAttribute('hidden');
    const rect = anchor.getBoundingClientRect();
    const destX = Math.max(2, Math.min(innerWidth - 24, rect.left + (docked ? 1 : 7)));
    // Keep the tip on its actual control; move the label to the left near the edge.
    overlay.querySelector('.romeo-cursor-label')?.setAttribute('transform', destX > innerWidth - 126 ? 'translate(-104 0)' : 'translate(0 0)');
    const destY = Math.max(2, Math.min(innerHeight - 44, rect.top + (docked ? 1 : Math.min(12, rect.height / 3))));
    const oldX = x, oldY = y, started = performance.now();
    function draw(now) {
      const fraction = immediate || reduced.matches ? 1 : Math.min(1, (now - started) / 420);
      const eased = 1 - Math.pow(1 - fraction, 3);
      x = oldX + (destX - oldX) * eased; y = oldY + (destY - oldY) * eased;
      // SVG transform is a presentation attribute; no inline CSS/CSP bypass.
      glyph.setAttribute('transform', `translate(${x.toFixed(2)} ${y.toFixed(2)})`);
      if (fraction < 1) animation = requestAnimationFrame(draw);
    }
    animation = requestAnimationFrame(draw);
  }
  function mark(state, label, text, anchor = home) {
    root.dataset.state = state;
    // An unchanged observation does not retrigger a live-region announcement.
    if (status.textContent !== label) status.textContent = label;
    if (copy.textContent !== text) copy.textContent = text;
    overlay.classList.toggle('is-paused', ['disconnected', 'failed', 'cancelled', 'stale'].includes(state));
    target = anchor;
    position();
  }
  function clearEvent() { eventName.hidden = eventLink.hidden = true; eventLink.removeAttribute('href'); }
  function lastChat() {
    const rows = document.querySelectorAll('#chat-messages .chat-message-assistant');
    return rows[rows.length - 1];
  }
  function anchorFor(job) {
    if (job.event_id !== eventID) return home;
    // Only point at a result/monitor explicitly bound to this exact job. An
    // earlier candidate or another model's answer is not its new result.
    const reply = document.querySelector(`[data-romeo-job="${job.id}"]`);
    if (job.status === 'succeeded' && job.kind === 'chat' && visible(reply)) return reply;
    const resultLink = document.getElementById('job-action-' + job.id);
    if (job.status === 'succeeded' && visible(resultLink)) return resultLink;
    const monitor = document.querySelector(`[data-romeo-monitor-job="${job.id}"]`);
    const row = stages.has(job.stage) && job.stage ? monitor?.querySelector(`[data-romeo-stage="${job.stage}"]`) : null;
    return visible(row) ? row : home;
  }
  function apply(payload) {
    if (root.dataset.uiActionActive === '1') return;
    if (!payload || payload.agent !== 'Gica-1' || !Array.isArray(payload.jobs) || payload.jobs.length > 2) throw new Error('Invalid status');
    const observed = Date.parse(payload.observed_at);
    if (!Number.isFinite(observed)) throw new Error('Invalid time');
    if (observed < lastObserved) return;
    if (payload.jobs.length === 0) {
      if (payload.state === 'local_completed') {
        const local = payload.local_result;
        if (!local || typeof local.id !== 'string' || !/^[1-9][0-9]{0,19}$/.test(local.id)
            || !validID.test(local.event_id) || typeof local.event_title !== 'string' || local.event_title.length > 100
            || local.event_url !== '/events/' + local.event_id + '/' || !Number.isFinite(Date.parse(local.created_at))) throw new Error('Invalid local result');
        const created = Date.parse(local.created_at);
        if (pendingForm || created < localCompletedAt) return;
        const signature = 'local:' + local.id + ':' + local.created_at;
        lastObserved = observed;
        if (signature === lastSignature && root.dataset.state !== 'disconnected') return;
        lastSignature = signature; localCompletedAt = created;
        eventName.textContent = local.event_title; eventName.hidden = false;
        eventLink.href = local.event_url + '?romeo_result=' + local.id + '#agent-panel'; eventLink.hidden = false;
        const reply = local.event_id === eventID ? document.querySelector(`[data-romeo-local-result="${local.id}"]`) : null;
        mark('local_completed', 'Consulta local completada', 'La herramienta local devolvió resultados. Abre el evento para leerlos; no se llamó a un modelo de IA.', visible(reply) ? reply : home);
        revealLocal(local, signature);
        return;
      }
      if (payload.state !== 'idle') throw new Error('Invalid idle');
      lastObserved = observed;
      if (root.dataset.state.startsWith('creation_') && document.querySelector('main form[data-gica-guided-draft]') && window.SparkXGicaCreation?.hasDraft()) return;
      if (!pendingForm && !localCompletedAt) { clearEvent(); mark('idle', 'Listo', 'Preparado para tu orden. Abrir ArquiGica no inicia una llamada de IA.'); }
      return;
    }
    for (const job of payload.jobs) {
      if (!job || !validID.test(job.id) || !validID.test(job.event_id) || !states.has(job.status) || !stages.has(job.stage)
          || !['chat', 'plan'].includes(job.kind) || typeof job.event_title !== 'string' || job.event_title.length > 100
          || job.event_url !== '/events/' + job.event_id + '/' || !Number.isFinite(Date.parse(job.updated_at))) throw new Error('Invalid job');
    }
    if (payload.state !== payload.jobs[0].status) throw new Error('Invalid state');
    const job = payload.jobs.find((item) => item.event_id === eventID) || payload.jobs[0];
    const updated = Date.parse(job.updated_at);
    const prior = jobUpdates.get(job.id);
    const level = job.status === 'queued' ? 0 : job.status === 'running' ? 1 : 2;
    if (prior && (updated < prior.updated || ranks[job.stage] < prior.rank || level < prior.level)) return;
    if (pendingForm || (localCompletedAt && !['queued','running'].includes(job.status) && updated <= localCompletedAt)) return;
    jobUpdates.set(job.id, { updated, rank: ranks[job.stage], level });
    if (jobUpdates.size > 30) jobUpdates.delete(jobUpdates.keys().next().value);
    lastObserved = observed;
    const signature = [job.id, job.status, job.stage, job.updated_at].join(':');
    if (signature === lastSignature && root.dataset.state !== 'disconnected') return;
    lastSignature = signature; localCompletedAt = 0;
    const count = payload.jobs.filter((item) => ['queued', 'running'].includes(item.status)).length;
    const label = labels[job.status] + (count > 1 ? ' · ' + count + ' trabajos' : '');
    eventName.textContent = job.event_title; eventName.hidden = false;
    eventLink.href = job.event_url + '#agent-panel'; eventLink.hidden = false;
    mark(job.status, label, descriptions[job.stage] || labels[job.status], anchorFor(job));
  }
  function schedule(delay) {
    clearTimeout(timer);
    if (!disposed && permitted && !document.hidden && root.dataset.statusUrl) timer = setTimeout(poll, delay);
  }
  async function poll() {
    if (disposed || !permitted || document.hidden || navigationID || controller || !root.dataset.statusUrl) return;
    const observedPage = pageGeneration;
    let delay = 12000;
    const url = new URL(root.dataset.statusUrl, location.origin);
    if (url.origin !== location.origin || url.pathname !== '/romeo/status/') return;
    if (eventID) url.searchParams.set('event_id', eventID);
    const request = new AbortController(); controller = request;
    const deadline = setTimeout(() => request.abort(), 7000);
    try {
      const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: request.signal });
      if ([401, 403].includes(response.status)) permitted = false;
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Status unavailable');
      const text = await response.text();
      if (text.length > 16000) throw new Error('Status too large');
      if (observedPage !== pageGeneration || navigationID) return;
      apply(JSON.parse(text)); lastUpdate = Date.now();
      delay = ['queued', 'running'].includes(root.dataset.state) ? 2000 : 12000;
    } catch (_) {
      if (!disposed && observedPage === pageGeneration && !navigationID && !document.hidden && !pendingForm && root.dataset.uiActionActive !== '1') { clearEvent(); mark('disconnected', 'Sin seguimiento', 'No se pudo comprobar el estado de Gica. No se confirma ejecución ni resultado.'); }
    } finally {
      clearTimeout(deadline);
      if (controller === request) controller = null;
      if (observedPage === pageGeneration) schedule(delay);
      else if (!navigationID) schedule(100);
    }
  }
  toggle.addEventListener('click', (event) => {
    details.hidden = !details.hidden;
    toggle.setAttribute('aria-expanded', String(!details.hidden));
    if (!details.hidden && Date.now() - lastUpdate > 3000) { clearTimeout(timer); poll(); }
    if (!details.hidden && event.isTrusted && root.dataset.gicaOpenConversation === 'true') {
      document.dispatchEvent(new CustomEvent('sparkx:gica-open'));
    }
    document.dispatchEvent(new CustomEvent('sparkx:romeo-action-layout'));
  });
  document.addEventListener('click', (event) => {
    if (event.target.closest('.voice-dialog')) return;
    // The floating companion belongs to the same conversation. In particular,
    // its Open button must not be treated as an outside click after opening it.
    if (event.composedPath().some((node) => node instanceof Element && node.matches('[data-gica-companion]'))) return;
    if (root.dataset.uiActionActive === '1' && event.target.closest('[data-theme-toggle]')) return;
    // A draft control may replace its own row synchronously. The original
    // event path still identifies a click inside Gica after that node detaches.
    if (!details.hidden && !event.composedPath().includes(root) && !root.contains(event.target)) {
      details.hidden = true; toggle.setAttribute('aria-expanded', 'false');
      document.dispatchEvent(new CustomEvent('sparkx:romeo-action-layout'));
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.defaultPrevented || document.querySelector('.voice-dialog[open]')) return;
    if (root.dataset.uiActionActive === '1' && event.key === 'Escape') return;
    if (event.key === 'Escape' && !details.hidden) {
      details.hidden = true; toggle.setAttribute('aria-expanded', 'false'); toggle.focus();
      document.dispatchEvent(new CustomEvent('sparkx:romeo-action-layout'));
    }
  });
  visibility.addEventListener('click', () => {
    shown = !shown; visibility.setAttribute('aria-pressed', String(shown));
    visibility.textContent = shown ? 'Ocultar cursor' : 'Mostrar cursor';
    try { localStorage.setItem('sparkx.romeo.cursor', shown ? 'shown' : 'hidden'); } catch (_) { /* Optional. */ }
    position(true);
  });
  visibility.setAttribute('aria-pressed', String(shown));
  visibility.textContent = shown ? 'Ocultar cursor' : 'Mostrar cursor';
  const actionLabels = {
    info: ['Respuesta local', 'Respondí a tu petición sin activar controles ni consumir tokens de modelos.'],
    interpreting: ['Interpretando frase', 'Identificando una intención con el catálogo local. Todavía no hay una acción autorizada.'],
    clarify: ['Falta aclarar', 'Revisa la pregunta y completa tu orden. Las opciones sólo preparan el texto.'],
    registering: ['Comprobando orden', 'Comprobando la orden con el servidor. Aún no se ha autorizado el clic.'],
    pending: ['Orden autorizada', 'Orden registrada. Puedes detenerla antes del clic.'],
    moving: ['Moviendo cursor', 'Gica va al control autorizado. Puedes detenerlo antes del clic.'],
    clicking: ['Ejecutando orden', 'Activando únicamente el control de tu orden.'],
    completed: ['Tema comprobado', 'El navegador confirmó el tema solicitado.'],
    already: ['Tema comprobado', 'El dashboard ya tenía el tema solicitado; no se pulsó el botón.'],
    cancelled: ['Orden detenida', 'La orden se detuvo antes del clic.'],
    failed: ['Orden sin completar', 'No se confirmó la acción. Revisa el mensaje de la orden.'],
    unrecorded: ['Resultado sin confirmar', 'El resultado o su registro final no está confirmado.'],
    checking_destination: ['Comprobando destino', 'El destino está cargado; se está confirmando su registro.'],
    arrived: ['Destino comprobado', 'La página solicitada está abierta y su registro se confirmó.']
  };
  document.addEventListener('sparkx:romeo-action-state', (event) => {
    const item = actionLabels[event.detail?.stage];
    if (!item) return;
    const stage = event.detail.stage;
    clearEvent();
    const navTypes = { calendar_open: 'calendar', directory_open: 'directory', people_search: 'directory', events_open: 'events' };
    const nav = Object.hasOwn(navTypes, event.detail.action) ? navTypes[event.detail.action] : null;
    const control = nav ? document.querySelector(`.main-nav [data-romeo-nav="${nav}"]`) : document.querySelector('[data-theme-toggle]');
    const destination = nav ? document.querySelector(`[data-romeo-destination="${nav}"] h1`) : home;
    const anchor = ['registering', 'pending'].includes(stage) ? root.querySelector('[name="command"]') :
      ['checking_destination', 'arrived'].includes(stage) ? destination :
      ['moving', 'clicking', 'completed', 'already', 'unrecorded'].includes(stage) ? control : home;
    mark('ui_' + stage, item[0], item[1], anchor);
  });
  document.addEventListener('sparkx:romeo-action-layout', () => {
    const creating = document.querySelector('main form[data-gica-guided-draft]') && window.SparkXGicaCreation?.hasDraft();
    if (creating && root.dataset.state.startsWith('creation_')) {
      const phase = root.dataset.voiceSessionState;
      if (phase === 'off') mark('creation_paused', 'Borrador en pausa',
        'El borrador se conserva. El micrófono está apagado; abre Gica y reanuda la conversación.', target);
      else if (phase === 'holding') mark('creation_holding', 'Borrador en espera',
        'Conservo tu respuesta. Revisa el mensaje de la conversación para continuar.', target);
      else if (['creation_paused', 'creation_holding'].includes(root.dataset.state)) mark('creation_filling', 'Ficha del evento',
        'Tus respuestas completan los campos. El indicador del micrófono muestra cuándo puedes hablar.', target);
    }
    position(true);
  });
  document.addEventListener('sparkx:gica-creation-state', (event) => {
    const fields = { title:'title', organization:'organization_id', speaker:'speaker_id', brief:'brief', date:'scheduled_dates', time:'starts_at', timezone:'timezone', capacity:'capacity', is_synthetic:'is_synthetic',
      objective:'objective', audience:'audience', modality:'modality', duration_minutes:'duration_minutes', location:'location', resources:'resources', constraints:'constraints' };
    const stage = event.detail?.stage;
    if (!['opening', 'opened', 'filling'].includes(stage)) return;
    const name = fields[event.detail?.field];
    const field = name ? document.querySelector(`main form[data-gica-event-form="create"] [name="${name}"]`) : null;
    const wrapper = field?.closest('[data-gica-field]');
    const anchor = (visible(field) ? field : wrapper?.querySelector('[data-event-select-toggle]') || wrapper) || document.querySelector('main[data-romeo-destination="create"] h1') || home;
    clearEvent();
    mark('creation_' + stage, stage === 'opening' ? 'Abriendo formulario' : 'Ficha del evento',
      stage === 'opening' ? 'Abriendo únicamente Nuevo evento por tu petición.' : 'Los campos muestran tus respuestas. El evento se guarda al confirmar la ficha final.', anchor);
  });
  document.addEventListener('htmx:beforeRequest', (event) => {
    const form = event.detail.elt?.closest('form');
    if (!form || !(form.id === 'proposal-form' || form.closest('.chat-composer'))) return;
    pendingForm = form; localCompletedAt = 0; lastSignature = '';
    mark('sending', 'Solicitud web', 'Preparando la solicitud de esta página. Aún no se confirma una llamada al modelo.', form.querySelector('button[type="submit"]'));
  });
  document.addEventListener('htmx:afterRequest', (event) => {
    if (!pendingForm || event.detail.elt?.closest('form') !== pendingForm) return;
    pendingForm = null;
    const response = event.detail.xhr?.responseText || '';
    const isLocal = response.includes('data-romeo-local-completed') || response.includes('Consulta local completada, sin llamadas a un modelo de IA.');
    if (event.detail.successful && isLocal) {
      localCompletedAt = Date.now(); clearEvent();
      mark('local_completed', 'Consulta local completada', 'La herramienta local devolvió resultados. No se llamó a ningún modelo de IA.', lastChat());
    } else if (!event.detail.successful) {
      mark('disconnected', 'Solicitud sin confirmar', 'La página no confirmó el resultado de esta solicitud. Revisa el mensaje del evento.');
    } else if (!response.includes('data-job-status')) {
      mark('failed', 'Revisar solicitud', 'El servidor devolvió un mensaje sin iniciar un trabajo. Revisa la información del evento.');
    } else {
      mark('queued', 'Solicitud registrada', 'La página devolvió un trabajo; el seguimiento consultará su estado observado.', document.getElementById('romeo-monitor'));
    }
    schedule(100);
  });
  ['htmx:sendError','htmx:timeout'].forEach((name) => document.addEventListener(name, () => {
    if (!pendingForm) return;
    pendingForm = null; mark('disconnected', 'Solicitud sin confirmar', 'No llegó una confirmación de la página. No se inventará un resultado.');
  }));
  document.addEventListener('htmx:oobAfterSwap', () => { if (target !== home) position(); });
  document.addEventListener('sparkx:gica-navigation-start', (event) => {
    if (!validID.test(event.detail?.id || '')) return;
    navigationID = event.detail.id; pageGeneration += 1;
    clearTimeout(timer); controller?.abort(); localController?.abort();
    pendingForm = null; lastSignature = ''; localCompletedAt = 0; localLoads.clear();
    target = home; position(true);
  });
  document.addEventListener('sparkx:gica-navigation-complete', (event) => {
    if (!navigationID || event.detail?.id !== navigationID) return;
    navigationID = null; eventID = currentEventID(); lastUpdate = 0;
    clearEvent(); target = home; position(true);
    if (event.detail?.success === true) schedule(100);
  });
  window.addEventListener('resize', () => position(true));
  window.addEventListener('scroll', () => position(true), { passive: true, capture: true });
  window.visualViewport?.addEventListener('resize', () => position(true));
  window.visualViewport?.addEventListener('scroll', () => position(true));
  reduced.addEventListener('change', () => position(true));
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { releaseDemoCursor(); clearTimeout(timer); controller?.abort(); cancelAnimationFrame(animation); overlay.setAttribute('hidden', ''); }
    else { position(true); schedule(100); }
  });
  window.addEventListener('pagehide', () => { disposed = true; releaseDemoCursor(); clearTimeout(timer); controller?.abort(); localController?.abort(); cancelAnimationFrame(animation); });
  window.addEventListener('pageshow', (event) => { if (event.persisted) { disposed = false; position(true); schedule(100); } });
  root.dataset.state = 'idle'; position(true);
  if (!root.dataset.statusUrl) copy.textContent = 'El cursor está preparado. Reinicia ArquiGica para cargar el seguimiento en vivo del servidor.';
  schedule(100);
})();

/* Preserve the human-started Gica controller across fixed local SSR views.
   This is a fixed local shell, not a general HTML/script router or agent tool. */
(() => {
  'use strict';
  const owner = document.body.dataset.voiceUser;
  const role = document.body.dataset.portalRole;
  const root = document.querySelector('[data-romeo-presence]');
  if (!root || !/^[1-9][0-9]{0,18}$/.test(owner || '') || !['admin', 'organizer'].includes(role) || !crypto.randomUUID) return;
  const routes = Object.freeze({ '/': 'events', '/calendar/': 'calendar', '/directory/': 'directory', '/events/new/': 'create', '/directory/organizations/new/': 'organization-create' });
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const AUTHORIZED_PILOT = '9c1cb0ba-4025-49dc-b9e8-d0f6cf3e84aa';
  let pilotID = null, candidatePath = '';
  function route(path) {
    if (Object.hasOwn(routes, path)) return routes[path];
    if (!pilotID || root.dataset.gicaDemoActive !== 'true') return null;
    if (path === `/events/${pilotID}/`) return 'event';
    if (path === `/events/${pilotID}/edit/`) return 'edit';
    if (path === `/events/${pilotID}/schedule/`) return 'schedule';
    if (path === candidatePath) return 'approve';
    return null;
  }
  // Other management pages leave through full navigation. The Gica profile can
  // start its own conversation; preserve its bound settings on the first swap.
  const pilotEntry = ['', 'edit/', 'schedule/'].some((suffix) => location.pathname === `/events/${AUTHORIZED_PILOT}/${suffix}`);
  if (!Object.hasOwn(routes, location.pathname) && location.pathname !== '/assistant/profile/' && !pilotEntry) return;
  const keys = Object.freeze({
    '/': new Set(['q', 'organization', 'from', 'to', 'plan', 'page']),
    '/calendar/': new Set(['q', 'organization', 'from', 'to', 'plan', 'month', 'day']),
    '/directory/': new Set(['q', 'organization', 'category', 'include_inactive', 'tab', 'page']),
    '/events/new/': new Set(), '/directory/organizations/new/': new Set()
  });
  const clicks = new WeakMap();
  const preparations = new WeakMap();
  const preparedForms = new WeakMap();
  let active = null;
  let currentURL = location.href;
  function localURL(value) {
    let url;
    try { url = new URL(value, location.href); } catch (_) { return null; }
    if (url.origin !== location.origin || url.username || url.password || !route(url.pathname) || url.href.length > 2048) return null;
    const seen = new Set();
    for (const [key, value] of url.searchParams) {
      if (!(keys[url.pathname] || new Set()).has(key) || seen.has(key) || value.length > 300 || /[\p{Cc}\p{Cf}]/u.test(value)) return null;
      seen.add(key);
    }
    return url;
  }
  function event(name, operation, success) {
    document.dispatchEvent(new CustomEvent('sparkx:gica-navigation-' + name,
      { detail: { id: operation.id, path: operation.url.pathname, user: owner,
        ...(operation.source ? { source: operation.source } : {}), ...(name === 'complete' ? { success } : {}) } }));
  }
  function notify(message) {
    let output = document.getElementById('gica-navigation-status');
    if (!output) {
      output = document.createElement('p'); output.id = 'gica-navigation-status'; output.className = 'notice notice-error';
      output.setAttribute('role', 'status'); document.querySelector('.app-topbar')?.after(output);
    }
    output.textContent = message;
  }
  function parsedPage(html, url, oldMain) {
    if (html.length > 2000000) throw new Error('La página supera el tamaño permitido.');
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const mains = doc.querySelectorAll('main#main-content');
    if (doc.body.dataset.voiceUser !== owner || doc.body.dataset.portalRole !== role ||
        doc.querySelectorAll('[data-romeo-presence]').length !== 1 || mains.length !== 1) throw new Error('Cambió la cuenta, el rol o el formato de la página. Recarga para verificar tu sesión.');
    const main = mains[0];
    const destination = route(url.pathname);
    const inferred = destination === 'event' && main.matches('[data-workspace]') || destination === 'edit' && main.querySelector('form[data-event-block-form]') || destination === 'schedule' && main.querySelector('form[data-pilot-schedule]') || destination === 'organization-create' && main.querySelector('form.directory-form [name="name"]');
    if ((!inferred && main.dataset.romeoDestination !== destination) || main.dataset.romeoDestinationError === 'true' ||
        (url.pathname === '/directory/' && main.dataset.romeoQuery !== (url.searchParams.get('q') || ''))) throw new Error('El servidor no confirmó el destino solicitado.');
    if (url.pathname === '/events/new/' && main.querySelectorAll('form[data-gica-event-form="create"]').length !== 1) throw new Error('El servidor no confirmó el formulario de creación.');
    // Never import head/scripts, inline handlers, CSS, frames or ambiguous IDs.
    if (main.querySelector('script,style,link,meta,base,iframe,object,embed,template')) throw new Error('El destino contiene elementos no admitidos para esta navegación.');
    const ids = new Set();
    for (const element of [main, ...main.querySelectorAll('*')]) {
      for (const attribute of element.attributes) {
        if (/^on/i.test(attribute.name) || ['srcdoc', 'style', 'srcset'].includes(attribute.name) ||
            (['href', 'src', 'action', 'formaction', 'xlink:href'].includes(attribute.name) && /^\s*(javascript|data|vbscript):/i.test(attribute.value))) throw new Error('El destino contiene atributos no admitidos.');
        // The event workspace uses the application's fixed HTMX forms. Never
        // import executable HTMX expressions or event handlers from a page.
        if (/^(hx-|data-hx-)/i.test(attribute.name) && !/^(?:data-)?hx-(?:get|post|target|swap|disabled-elt|trigger|swap-oob)$/i.test(attribute.name)) throw new Error('El destino contiene una expresión HTMX no admitida.');
        if (/^(?:data-)?hx-(?:get|post)$/i.test(attribute.name)) {
          const request = new URL(attribute.value, location.origin);
          const suffix = pilotID === AUTHORIZED_PILOT && request.pathname.startsWith(`/events/${pilotID}/`) ? request.pathname.slice(`/events/${pilotID}/`.length) : '';
          const identifier = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
          const allowed = /post$/i.test(attribute.name) ? ['generate/', 'chat/', 'tasks/status/'].includes(suffix) || new RegExp('^jobs/' + identifier + '/cancel/$', 'i').test(suffix) : new RegExp('^jobs/' + identifier + '/$', 'i').test(suffix);
          if (destination !== 'event' || request.origin !== location.origin || request.username || request.password || request.search || request.hash || !allowed) throw new Error('La solicitud HTMX no pertenece al piloto.');
        }
        if (/^(?:data-)?hx-trigger$/i.test(attribute.name) && (attribute.value !== 'every 2s' || !element.matches('article.job-status[hx-get]'))) throw new Error('El disparador HTMX no pertenece al seguimiento del piloto.');
        if (['href', 'src', 'action', 'formaction', 'xlink:href'].includes(attribute.name)) {
          const resource = new URL(attribute.value, location.origin);
          if (resource.origin !== location.origin || resource.username || resource.password) throw new Error('El destino contiene recursos externos no admitidos.');
        }
      }
      if (element.id) {
        const existing = document.getElementById(element.id);
        if (ids.has(element.id) || (existing && !oldMain.contains(existing))) throw new Error('El destino contiene identificadores incompatibles.');
        ids.add(element.id);
      }
    }
    const csrf = doc.querySelector('[data-romeo-action-form] [name="csrfmiddlewaretoken"]')?.value;
    if (!/^[A-Za-z0-9]{64}$/.test(csrf || '')) throw new Error('No se pudo comprobar el formulario de tu sesión.');
    return { main, title: doc.title.slice(0, 200), csrf };
  }
  async function navigate(url, historyMode = 'push', source = '', signal = null, submission = null) {
    if (active) return { success: false };
    const oldMain = document.querySelector('main#main-content');
    if (!oldMain || !root.isConnected || document.hidden || signal?.aborted || document.body.dataset.voiceUser !== owner || document.body.dataset.portalRole !== role ||
        (source === 'narrated-demo' && root.dataset.gicaDemoActive !== 'true')) return { success: false };
    const operation = { id: crypto.randomUUID(), url, controller: new AbortController(), source };
    const cancel = () => operation.controller.abort();
    signal?.addEventListener('abort', cancel, { once: true });
    active = operation; oldMain.setAttribute('aria-busy', 'true');
    document.getElementById('gica-navigation-status')?.remove();
    event('start', operation);
    const timer = setTimeout(() => operation.controller.abort(), 8000);
    let success = false;
    let committed = false;
    try {
      const response = await fetch(url.pathname + url.search, { credentials: 'same-origin', redirect: submission ? 'follow' : 'error', cache: 'no-store',
        method: submission ? 'POST' : 'GET', ...(submission ? { body: submission.body } : {}),
        headers: { Accept: 'text/html' }, signal: operation.controller.signal });
      if (!response.ok || !response.headers.get('content-type')?.includes('text/html')) throw new Error('No se pudo abrir el destino. Tu página actual se conserva.');
      if (submission) {
        const returned = new URL(response.url);
        if (!response.redirected || returned.origin !== location.origin || (returned.hash && !(submission.kind === 'schedule' && returned.hash === '#candidate'))) throw new Error('El formulario requiere revisión. No se repetirá el envío.');
        if (submission.kind === 'create') {
          const match = returned.pathname.match(/^\/events\/([0-9a-f-]{36})\/$/i);
          if (!match || !uuid.test(match[1])) throw new Error('No se confirmó el evento guardado.');
          pilotID = match[1]; root.dataset.gicaPilotEvent = pilotID;
        } else if (['edit', 'approve', 'schedule'].includes(submission.kind) && (returned.pathname !== `/events/${pilotID}/` || returned.search)) throw new Error('No se confirmó el cambio del piloto.');
        else if (submission.kind === 'organization' && (returned.pathname !== '/directory/' || returned.search !== '?tab=organizations')) throw new Error('No se confirmó la organización guardada.');
        url = localURL(returned.href);
        if (!url) throw new Error('El formulario devolvió un destino no permitido.');
        operation.url = url;
      }
      const page = parsedPage(await response.text(), url, oldMain);
      let hashID = '';
      try { hashID = decodeURIComponent(url.hash.slice(1)); } catch (_) { throw new Error('El enlace tiene un destino no válido.'); }
      if (active !== operation || operation.controller.signal.aborted || document.hidden || document.body.dataset.voiceUser !== owner || document.body.dataset.portalRole !== role ||
          (source === 'narrated-demo' && root.dataset.gicaDemoActive !== 'true')) throw new Error('La navegación se interrumpió.');
      const main = document.importNode(page.main, true);
      const heading = document.querySelector('.app-location strong');
      if (!heading || !oldMain.isConnected || !root.isConnected) throw new Error('La página cambió durante la navegación. Recarga para verificarla.');
      // htmx.remove releases timers/listeners owned by the outgoing subtree.
      // The header, cursor, microphone and reviewed-memory controller stay intact.
      const preferences = oldMain.querySelector('[data-gica-settings]');
      if (preferences) {
        const fallback = document.createElement('div'); fallback.hidden = true;
        fallback.dataset.gicaSettingsFallback = ''; root.append(fallback);
        fallback.append(preferences);
      }
      oldMain.before(main);
      committed = true;
      window.htmx ? window.htmx.remove(oldMain) : oldMain.remove();
      root.querySelectorAll('[name="csrfmiddlewaretoken"]').forEach((input) => { input.value = page.csrf; });
      document.querySelector('.flash-messages')?.remove();
      document.title = page.title;
      const destination = route(url.pathname);
      heading.textContent = { events: 'Eventos', calendar: 'Calendario', directory: 'Directorio', create: 'Nuevo evento', 'organization-create': 'Nueva institución', event: 'Mi evento', edit: 'Editar ficha', schedule:'Ajustar horarios' }[destination];
      document.querySelectorAll('.main-nav a').forEach((link) => {
        const selected = link.dataset.romeoNav === (['create', 'event', 'edit', 'schedule'].includes(destination) ? 'events' : destination === 'organization-create' ? 'directory' : destination);
        link.classList.toggle('is-current', selected);
        if (selected) link.setAttribute('aria-current', 'location'); else link.removeAttribute('aria-current');
      });
      if (historyMode === 'push') history.pushState({ gicaShell: true }, '', url.pathname + url.search + url.hash);
      currentURL = location.href;
      window.htmx?.process(main);
      main.dispatchEvent(new CustomEvent('htmx:afterSwap', { bubbles: true, detail: { target: main, elt: main } }));
      main.setAttribute('tabindex', '-1'); main.focus({ preventScroll: true });
      const hash = hashID ? document.getElementById(hashID) : null;
      if (hash && main.contains(hash)) hash.scrollIntoView({ behavior: 'instant', block: 'start' });
      else window.scrollTo({ top: 0, behavior: 'instant' });
      success = true;
      return { success: true, id: operation.id, path: url.pathname + url.search };
    } catch (error) {
      if (!committed && historyMode === 'pop') history.replaceState({ gicaShell: true }, '', currentURL);
      if (operation.source === 'creation-complete') {
        if (committed) currentURL = location.href;
        notify('Tu evento quedó creado, pero no pude confirmar la lista de eventos. Pulsa Eventos para verla o Abrir evento creado para revisar su ficha. No vuelvas a crearlo.');
      } else if (committed) {
        currentURL = location.href;
        notify('El contenido pudo cambiar, pero la navegación completa no quedó confirmada. Micrófono apagado; recarga para revisar el destino. No se repetirá la orden.');
      } else notify(error instanceof Error && error.name !== 'AbortError' ? error.message : 'Se interrumpió la navegación. Tu página actual se conserva; no se repetirá la orden.');
      return { success: false, id: operation.id };
    } finally {
      signal?.removeEventListener('abort', cancel);
      clearTimeout(timer); oldMain.removeAttribute('aria-busy');
      if (active === operation) active = null;
      event('complete', operation, success);
    }
  }
  document.addEventListener('click', (event) => {
    const anchor = event.target.closest('a[href]');
    if (!anchor || event.defaultPrevented || event.button !== 0 || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || anchor.target || anchor.hasAttribute('download') || anchor.closest('[hx-get],[hx-post]')) return;
    const url = localURL(anchor.href);
    if (!url || (url.hash && url.pathname + url.search === location.pathname + location.search)) return;
    event.preventDefault();
    clicks.delete(anchor);
    const prepared = preparations.get(anchor);
    preparations.delete(anchor);
    if (active || (event.isTrusted && root.dataset.uiActionActive === '1')) { notify('Espera a que termine la acción actual.'); return; }
    if (prepared && (prepared.signal?.aborted || root.dataset.gicaDemoActive !== 'true')) return;
    clicks.set(anchor, navigate(url, 'push', prepared ? 'narrated-demo' : '', prepared?.signal));
  });
  document.addEventListener('submit', (event) => {
    const form = event.target;
    const prepared = form instanceof HTMLFormElement ? preparedForms.get(form) : null;
    if (prepared && !event.defaultPrevented) {
      event.preventDefault(); preparedForms.delete(form); clicks.delete(form);
      if (!prepared.signal?.aborted && root.dataset.gicaDemoActive === 'true') clicks.set(form, submitPilotForm(form, prepared));
      return;
    }
    if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== 'get' || !form.closest('main#main-content') || event.defaultPrevented) return;
    const url = localURL(form.action);
    if (!url) return;
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(form)) { if (typeof value !== 'string') return; params.append(key, value); }
    url.search = params.toString();
    if (!localURL(url.href)) return;
    event.preventDefault();
    if (!active && root.dataset.uiActionActive !== '1') navigate(url);
  });
  window.addEventListener('popstate', () => {
    const url = localURL(location.href);
    if (url && !active && root.dataset.uiActionActive !== '1') navigate(url, 'pop');
    else { active?.controller.abort(); location.reload(); }
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) active?.controller.abort(); });
  window.addEventListener('pagehide', () => active?.controller.abort());
  window.SparkXGicaNavigation = Object.freeze({
    prepare: (anchor, options = {}) => {
      clicks.delete(anchor); preparations.delete(anchor);
      // Cancellation belongs only to the explicit narrated tour. The regular
      // human-commanded navigation runner keeps its existing contract.
      if (options.source === 'narrated-demo' && root.dataset.gicaDemoActive === 'true' &&
          (!options.signal || options.signal instanceof AbortSignal)) preparations.set(anchor, { signal: options.signal });
    },
    resultFor: (anchor) => { const promise = clicks.get(anchor) || null; clicks.delete(anchor); return promise; },
    bindPilot: (id) => {
      if (root.dataset.gicaDemoActive !== 'true' || id !== AUTHORIZED_PILOT || document.body.dataset.voiceUser !== owner || document.body.dataset.portalRole !== role) return false;
      pilotID = id; root.dataset.gicaPilotEvent = id; return true;
    },
    bindCandidate: (value) => {
      if (root.dataset.gicaDemoActive !== 'true' || !root.isConnected || document.hidden || document.body.dataset.voiceUser !== owner ||
          document.body.dataset.portalRole !== role || pilotID !== AUTHORIZED_PILOT || typeof value !== 'string') return false;
      const expected = new RegExp('^/events/' + pilotID + '/candidates/([0-9a-f-]{36})/approve/$', 'i');
      const match = value.match(expected);
      if (!match || !uuid.test(match[1])) return false;
      candidatePath = value; return true;
    },
    prepareForm: (form, options = {}) => {
      clicks.delete(form); preparedForms.delete(form);
      if (options.source === 'narrated-demo' && root.dataset.gicaDemoActive === 'true' &&
          (!options.signal || options.signal instanceof AbortSignal)) preparedForms.set(form, options);
    },
    // Only the explicit pilot presentation submits these CSRF-bound forms and
    // the specific proposal approval shown for this pilot. No administrator UI.
    submitPilotForm,
    // Refresh the same pilot after a deterministic, server-validated proposal.
    refreshPilot: (options = {}) => {
      const url = pilotID && localURL(`/events/${pilotID}/`);
      return url && root.dataset.gicaDemoActive === 'true' ? navigate(url, 'push', 'narrated-demo', options.signal) : Promise.resolve({ success: false });
    },
    // Refresh even if already at /: a newly saved event must be fetched from
    // the server, without retaining filters from the previous list.
    openEvents: () => {
      const url = localURL('/');
      return url ? navigate(url, 'push', 'creation-complete') : Promise.resolve({ success: false });
    },
    // Event creation is a fixed GET destination. The interview decides when a
    // human has asked to create; this helper neither submits nor creates data.
    openCreation: () => {
      if (location.pathname === '/events/new/' && !location.search &&
          document.querySelector('main#main-content[data-romeo-destination="create"] form[data-gica-event-form="create"]')) {
        return Promise.resolve({ success: true, path: '/events/new/' });
      }
      const url = localURL('/events/new/');
      return url ? navigate(url, 'push', 'creation') : Promise.resolve({ success: false });
    }
  });
  async function submitPilotForm(form, options = {}) {
      if (root.dataset.gicaDemoActive !== 'true' || options.source !== 'narrated-demo' ||
          !root.isConnected || document.hidden || document.body.dataset.voiceUser !== owner || document.body.dataset.portalRole !== role || !(form instanceof HTMLFormElement) ||
          !form.isConnected || !form.closest('main#main-content') || form.method.toLowerCase() !== 'post' ||
          !form.matches('[data-event-block-form],.directory-form,.candidate-actions form,[data-pilot-schedule]') || form.dataset.gicaGuidedDraft ||
          (options.signal && !(options.signal instanceof AbortSignal))) return { success: false };
      const url = localURL(form.action), csrf = form.elements.namedItem('csrfmiddlewaretoken');
      const kind = url?.pathname === '/events/new/' ? 'create' : url?.pathname === `/events/${pilotID}/edit/` ? 'edit' : url?.pathname === `/events/${pilotID}/schedule/` ? 'schedule' : url?.pathname === '/directory/organizations/new/' ? 'organization' : candidatePath && url?.pathname === candidatePath ? 'approve' : null;
      if (!url || !kind || !/^[A-Za-z0-9]{64}$/.test(csrf?.value || '') || form.querySelector('[name="expected_revision"]')?.value === '') return { success: false };
      const body = new FormData(form);
      if (Array.from(body.values()).some((value) => typeof value !== 'string')) return { success: false };
      if (kind === 'organization' && (body.get('name') !== 'Gicaingenieros' || body.has('is_synthetic') || !body.has('is_active') ||
          body.get('aliases') !== 'GICA Ingenieros')) return { success: false };
      if (kind === 'approve') {
        const candidate = candidatePath.split('/')[4];
        const version = document.querySelector('main[data-gica-pilot="true"]')?.dataset.eventRevision;
        if (!version || body.get('expected_revision') !== version || body.get('idempotency_key') !== candidate ||
            Array.from(body.keys()).some((key) => !['csrfmiddlewaretoken', 'expected_revision', 'expected_plan', 'idempotency_key'].includes(key))) return { success: false };
      }
      if (kind === 'create') {
        if (!uuid.test(options.run_id || '') || active || options.signal?.aborted) return { success: false };
        try {
          const response = await fetch('/assistant/pilot-control/', { method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
            signal: options.signal, headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': csrf.value },
            body: JSON.stringify({ operation: 'create', run_id: options.run_id, fields: Object.fromEntries(body) }) });
          if (!response.ok || !/^application\/json(?:;|$)/i.test(response.headers.get('Content-Type') || '')) return { success: false };
          const result = await response.json();
          if (result.event_id !== AUTHORIZED_PILOT || result.event_url !== `/events/${AUTHORIZED_PILOT}/` ||
              typeof result.created !== 'boolean' || options.signal?.aborted || document.hidden || root.dataset.gicaDemoActive !== 'true' || document.body.dataset.voiceUser !== owner || document.body.dataset.portalRole !== role) return { success: false };
          pilotID = result.event_id; root.dataset.gicaPilotEvent = pilotID;
          const target = localURL(result.event_url);
          const observed = target ? await navigate(target, 'push', 'narrated-demo', options.signal) : { success: false };
          return { ...result, ...observed };
        } catch (_) { return { success: false }; }
      }
      return navigate(url, 'push', 'narrated-demo', options.signal, { kind, body });
  }
})();

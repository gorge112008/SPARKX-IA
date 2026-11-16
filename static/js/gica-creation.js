/* A human-started, versioned event draft. Answers are data, never UI commands. */
(() => {
  'use strict';
  const root = document.querySelector('[data-romeo-presence]');
  const panel = root?.querySelector('[data-gica-creation]');
  if (!root || !panel || !crypto.randomUUID) return;
  const user = document.body.dataset.voiceUser;
  const draftView = panel.querySelector('[data-gica-creation-draft]');
  const question = panel.querySelector('[data-gica-creation-question]');
  const progress = panel.querySelector('[data-gica-creation-progress]');
  const status = panel.querySelector('[data-gica-creation-status]');
  const eventLink = panel.querySelector('[data-gica-creation-event]');
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const unsafe = /[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u;
  const labels = Object.freeze({
    title: 'Nombre', organization: 'Institución', brief: 'Descripción', date: 'Fecha', time: 'Hora',
    timezone: 'Zona horaria', capacity: 'Capacidad', is_synthetic: 'Datos ficticios',
    objective: 'Objetivo', audience: 'Público', modality: 'Modalidad', duration_minutes: 'Duración',
    location: 'Lugar o acceso', resources: 'Recursos', constraints: 'Restricciones'
  });
  const controls = new Set(['turn', 'resume', 'back', 'cancel', 'review', 'edit', 'confirm']);
  const actionForm = root.querySelector('[data-romeo-action-form]');
  const submit = actionForm?.querySelector('[type=submit]');
  const originalSubmitText = submit?.textContent || 'Ejecutar orden';
  // Template order keeps the current draft visible outside optional manual input.
  let draft = null, busy = false, preview = '', presented = '', displayedStep = '', responseStatus = 'none', projection = null;
  const monthNames = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const fieldNames = Object.freeze({ title: 'title', organization: 'organization_id', brief: 'brief',
    date: 'scheduled_dates', time: 'starts_at', timezone: 'timezone', capacity: 'capacity', is_synthetic: 'is_synthetic',
    objective:'objective', audience:'audience', modality:'modality', duration_minutes:'duration_minutes',
    location:'location', resources:'resources', constraints:'constraints' });
  const preparationNames = Object.freeze(['objective','audience','modality','duration_minutes','location','resources','constraints']);

  // Reviewed answers for known slots, never inferred from arbitrary question text.
  // These describe the organizer's choice; they do not provision external rooms.
  const choice = (id, label, value, mode = 'answer') => Object.freeze({ id, label, value, mode });
  const otherChoice = (id, label = 'Otro') => choice(id, label, '', 'custom');
  const pendingChoice = (id) => choice(id, 'Pendiente', 'pendiente');
  const choiceSets = Object.freeze({
    timezone: Object.freeze([choice('timezone_lima', 'Perú (Lima)', 'sí'), otherChoice('timezone_other', 'Otra zona')]),
    // Capacity is a required integer; unlike interview answers it cannot be pending.
    capacity: Object.freeze([choice('capacity_20', '20 personas', '20'), choice('capacity_50', '50 personas', '50'),
      choice('capacity_100', '100 personas', '100'), otherChoice('capacity_other', 'Otra cantidad')]),
    is_synthetic: Object.freeze([choice('synthetic_yes', 'Sí, demostración', 'sí'), choice('synthetic_no', 'No, datos reales', 'no')]),
    modality: Object.freeze([choice('modality_virtual', 'Virtual', 'Virtual'), choice('modality_presential', 'Presencial', 'Presencial'),
      choice('modality_hybrid', 'Híbrida', 'Híbrida'), pendingChoice('modality_pending')]),
    duration_minutes: Object.freeze([choice('duration_30', '30 minutos', '30 minutos'), choice('duration_60', '60 minutos', '60 minutos'),
      choice('duration_90', '90 minutos', '90 minutos'), pendingChoice('duration_pending')]),
    location_virtual: Object.freeze([choice('location_zoom', 'Zoom', 'Zoom, enlace pendiente'),
      choice('location_meet', 'Google Meet', 'Google Meet, enlace pendiente'), otherChoice('location_other'), pendingChoice('location_pending')]),
    location_presential: Object.freeze([otherChoice('location_other', 'Indicar lugar'), pendingChoice('location_pending')]),
    location_unspecified: Object.freeze([otherChoice('location_other', 'Indicar lugar o plataforma'), pendingChoice('location_pending')])
  });
  const noChoices = Object.freeze([]);
  function validDirectoryResolution(value, data) {
    if (value === undefined || value === null) return true;
    if (!value || typeof value !== 'object' || Array.isArray(value) ||
        Object.keys(value).sort().join(',') !== 'can_skip,candidates,kind,mode,query' ||
        !['organization', 'person'].includes(value.kind) || !['choose', 'register', 'new_name'].includes(value.mode) ||
        value.can_skip !== true || data.status !== 'collecting' || (data.draft_status && data.draft_status !== 'collecting') ||
        data.step_key !== (value.kind === 'organization' ? 'organization' : 'resources') ||
        typeof value.query !== 'string' || value.query.length > 160 || unsafe.test(value.query) || /[<>]/u.test(value.query) ||
        !Array.isArray(value.candidates) || value.candidates.length > 3) return false;
    const seen = new Set();
    for (const candidate of value.candidates) {
      if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate) ||
          Object.keys(candidate).sort().join(',') !== 'id,name' || typeof candidate.id !== 'string' ||
          !uuid.test(candidate.id) || seen.has(candidate.id) || typeof candidate.name !== 'string' ||
          !candidate.name.trim() || candidate.name.length > 160 || unsafe.test(candidate.name) || /[<>]/u.test(candidate.name)) return false;
      seen.add(candidate.id);
    }
    return value.mode === 'choose' ? value.candidates.length > 0 : value.candidates.length === 0;
  }
  function directoryChoices(resolution) {
    const institution = resolution.kind === 'organization';
    if (resolution.mode === 'new_name') return Object.freeze([otherChoice('directory_name', institution ? 'Escribir institución' : 'Escribir nombre'),
      choice('directory_no', institution ? 'Sin institución' : 'Continuar sin persona', 'no')]);
    const another = choice('directory_register_other', institution ? 'Otra institución' : 'Otra persona', 'registrar otro');
    const skip = choice('directory_no', institution ? 'Sin institución' : 'Continuar sin persona', 'no');
    if (resolution.mode === 'register') return Object.freeze([choice('directory_yes', 'Sí, registrar', 'sí'),
      choice('directory_no', 'No, continuar', 'no'), another]);
    const candidates = resolution.candidates.map((candidate, index) => choice('directory_candidate_' + (index + 1), candidate.name, String(index + 1)));
    candidates.push(another);
    if (candidates.length < 4) candidates.push(skip);
    return Object.freeze(candidates);
  }
  function currentChoices() {
    if (!draft || busy || draft.status !== 'collecting' || responseStatus !== 'collecting' || draft.error_code || document.body.dataset.voiceUser !== user) return noChoices;
    // A directory answer is a server-owned question, never another search term.
    // Ordinary field suggestions must not replace its explicit choice or consent.
    if (draft.directory_resolution) return directoryChoices(draft.directory_resolution);
    if (draft.step_key !== 'location') return Object.hasOwn(labels, draft.step_key) && Object.hasOwn(choiceSets, draft.step_key) ? choiceSets[draft.step_key] : noChoices;
    const modality = draft.fields.interview_answers?.modality;
    const value = modality?.status === 'confirmed' ? modality.value.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().trim() : '';
    if (/^(?:(?:sera|modalidad)\s+)?(?:virtual|hibrid[oa]|en linea|online)$/.test(value)) return choiceSets.location_virtual;
    if (/^(?:(?:sera|modalidad)\s+)?presencial$/.test(value)) return choiceSets.location_presential;
    return choiceSets.location_unspecified;
  }
  function presentation() {
    const resolution = draft?.directory_resolution;
    const directory = resolution ? Object.freeze({ kind: resolution.kind, mode: resolution.mode, query: resolution.query,
      candidates: Object.freeze(resolution.candidates.map((candidate) => Object.freeze({ id: candidate.id, name: candidate.name }))),
      can_skip: resolution.can_skip }) : null;
    return Object.freeze({ kind: 'creation', user: user || '', draft_id: draft?.draft_id || '', revision: draft?.revision || 0,
      step_key: draft?.step_key || '', status: responseStatus, question: draft?.reply || '', busy,
      directory_resolution: directory, choices: currentChoices() });
  }
  function validateChoice(token) {
    if (!token || typeof token !== 'object' || Array.isArray(token) || !root.isConnected || document.hidden ||
        !draft || token.draft_id !== draft.draft_id || token.revision !== draft.revision || token.step_key !== draft.step_key ||
        typeof token.choice_id !== 'string') return null;
    return currentChoices().find((item) => item.id === token.choice_id) || null;
  }
  function publishPresentation() {
    document.dispatchEvent(new CustomEvent('sparkx:gica-companion-state', { detail: presentation() }));
  }

  function dateLabel(value) {
    const match = /^(20[0-9]{2})-([0-9]{2})-([0-9]{2})$/.exec(value || '');
    return match && monthNames[Number(match[2]) - 1] ? `${Number(match[3])} de ${monthNames[Number(match[2]) - 1]} de ${match[1]}` : value;
  }
  function liveEvent(stage, key = '') {
    document.dispatchEvent(new CustomEvent('sparkx:gica-creation-state', { detail: { stage, field: key } }));
  }
  function releaseProjection() {
    const previous = projection;
    projection = null;
    if (!previous) return;
    for (const state of previous.controls) {
      state.input.disabled = state.disabled;
      if ('readOnly' in state.input) state.input.readOnly = state.readOnly;
      state.input.classList.toggle('gica-field-current', state.current);
      state.input.classList.toggle('gica-field-preview', state.preview);
    }
    if (previous.marker === null) previous.form.removeAttribute('data-gica-guided-draft');
    else previous.form.setAttribute('data-gica-guided-draft', previous.marker);
    if (previous.button) { previous.button.disabled = previous.buttonDisabled; previous.button.textContent = previous.buttonText; }
    // Keep the answers already shown, but stop owning their values. Subsequent
    // renders of a cancelled/expired draft must not overwrite manual edits.
    document.dispatchEvent(new CustomEvent('sparkx:romeo-action-layout'));
  }
  function mirrorForm() {
    const form = document.querySelector('main form[data-gica-event-form="create"]');
    const summary = document.querySelector('[data-gica-live-summary]');
    if (projection && projection.form !== form) releaseProjection();
    if (!form || !draft || document.body.dataset.voiceUser !== user || !root.isConnected) { releaseProjection(); return; }
    if (!active() && !(draft.status === 'created' && projection?.form === form)) { releaseProjection(); return; }
    if (!projection) {
      const controls = [...new Set([...Object.values(fieldNames), 'speaker_id'])].map((name) => form.elements.namedItem(name))
        .filter((input) => input instanceof HTMLInputElement || input instanceof HTMLSelectElement || input instanceof HTMLTextAreaElement);
      const button = form.querySelector('[data-gica-create-submit]');
      projection = { form, marker:form.getAttribute('data-gica-guided-draft'), button, buttonDisabled:button?.disabled, buttonText:button?.textContent,
        controls:controls.map((input) => ({ input, disabled:input.disabled, readOnly:input.readOnly,
          current:input.classList.contains('gica-field-current'), preview:input.classList.contains('gica-field-preview') })) };
    }
    const locked = active() || draft.status === 'created';
    form.dataset.gicaGuidedDraft = locked ? draft.draft_id : '';
    const fields = draft.fields;
    const selectedDates = fields.scheduled_dates || (fields.date ? [fields.date] : []);
    const values = { title: fields.title || '', organization_id: fields.organization_id || '', brief: fields.brief || '',
      scheduled_dates: selectedDates.map((value) => value.split('-').reverse().join('/')).join(', '),
      starts_at: fields.date && fields.time ? fields.date + 'T' + fields.time : '',
      timezone: fields.timezone || 'America/Lima', capacity: fields.capacity ?? '', is_synthetic: fields.is_synthetic ?? false };
    for (const name of preparationNames) values[name] = fields.interview_answers?.[name]?.value || '';
    let changed = false;
    for (const [name, value] of Object.entries(values)) {
      const input = form.elements.namedItem(name);
      if (!(input instanceof HTMLInputElement || input instanceof HTMLSelectElement || input instanceof HTMLTextAreaElement)) continue;
      if (name === 'organization_id' && input instanceof HTMLSelectElement && uuid.test(value || '') &&
          typeof fields.organization_name === 'string' && fields.organization_name.length <= 160 &&
          !Array.from(input.options).some((option) => option.value === value)) {
        // A confirmed directory registration can be newer than the SSR form.
        input.add(new Option(fields.organization_name, value));
      }
      if (name === 'modality' && input instanceof HTMLSelectElement && value &&
          !Array.from(input.options).some((option) => option.value === value)) input.add(new Option(value, value));
      const target = input.type === 'checkbox' ? 'checked' : 'value';
      const next = target === 'checked' ? value : String(value);
      if (input[target] !== next) { input[target] = next; changed = true; }
      if (input instanceof HTMLSelectElement || input.type === 'checkbox') input.disabled = locked;
      else input.readOnly = locked;
      input.classList.toggle('gica-field-current', active() && fieldNames[draft.step_key] === name);
      input.classList.remove('gica-field-preview');
    }
    const speaker = form.elements.namedItem('speaker_id');
    if (speaker instanceof HTMLSelectElement) speaker.disabled = locked;
    const currentInput = form.elements.namedItem(fieldNames[draft.step_key] || '');
    if (preview && active() && currentInput && !(currentInput instanceof HTMLSelectElement) &&
        ['title', 'brief', 'date', 'capacity', ...preparationNames].includes(draft.step_key)) {
      // Unvalidated words are visible only. They never overwrite the saved draft.
      if (!['capacity','duration_minutes'].includes(draft.step_key) || /^[0-9]+$/.test(preview)) currentInput.value = preview;
      currentInput.classList.add('gica-field-preview');
    }
    const step = draft.draft_id + ':' + draft.step_key;
    const changedStep = step !== displayedStep;
    if (active() && changedStep) {
      displayedStep = step;
      if (currentInput) {
        const rect = currentInput.getBoundingClientRect();
        if (rect.top < 90 || rect.bottom > innerHeight - 50) currentInput.scrollIntoView({ block:'center', behavior:'instant' });
      }
    }
    const button = form.querySelector('[data-gica-create-submit]');
    if (button) {
      button.disabled = busy || (active() && draft.status !== 'review') || draft.status === 'created';
      button.textContent = draft.status === 'created' ? 'Evento creado' : active() && draft.status !== 'review' ? 'Completa los datos con Gica' : 'Crear evento';
    }
    if (summary) {
      summary.hidden = false;
      summary.querySelector('[data-gica-live-progress]').textContent = progress.textContent;
      summary.querySelector('[data-gica-live-question]').textContent = draft.reply;
      summary.querySelector('[data-gica-live-status]').textContent = preview ? 'Transcribiendo tu respuesta… Se guardará cuando termine el turno.' : status.textContent + ' Los campos siguen tus respuestas; usa Corregir en Gica para modificarlos.';
      const dates = summary.querySelector('[data-gica-live-dates]'); dates.replaceChildren();
      for (const value of selectedDates) {
        const day = document.createElement('p'); day.textContent = dateLabel(value); dates.append(day);
      }
      const answers = summary.querySelector('[data-gica-live-answers]'); answers.replaceChildren();
      for (const [key, answer] of Object.entries(fields.interview_answers || {})) {
        const term = document.createElement('dt'), definition = document.createElement('dd');
        term.textContent = labels[key]; definition.textContent = answer.value || (answer.status === 'pending' ? 'Pendiente' : answer.status === 'not_applicable' ? 'No aplica' : 'En la descripción'); answers.append(term, definition);
      }
      if (preview && preparationNames.includes(draft.step_key)) {
        const term = document.createElement('dt'), definition = document.createElement('dd');
        term.textContent = labels[draft.step_key] + ' · dictando'; definition.textContent = preview; answers.append(term, definition);
      }
      if (draft.status === 'created') {
        const link = document.createElement('a'); link.className = 'button button-secondary';
        link.href = draft.event_url; link.textContent = 'Abrir evento creado'; answers.append(link);
      }
    }
    if ((changed || changedStep) && active()) liveEvent('filling', draft.step_key);
  }

  function active() { return !!draft && ['collecting', 'review', 'invalid', 'conflict'].includes(draft.status); }
  function localEventURL(value) {
    return typeof value === 'string' && /^\/events\/[0-9a-f-]{36}\/$/i.test(value) && uuid.test(value.split('/')[2]);
  }
  function valid(data) {
    if (!data || typeof data.handled !== 'boolean') return false;
    if (!data.handled) return true;
    if (!['collecting', 'review', 'created', 'cancelled', 'invalid', 'conflict', 'expired'].includes(data.status) ||
        typeof data.reply !== 'string' || !data.reply.trim() || data.reply.length > 280 || unsafe.test(data.reply) || /[<>]/u.test(data.reply) ||
        typeof data.draft_id !== 'string' || !uuid.test(data.draft_id) ||
        !Number.isSafeInteger(data.revision) || data.revision < 1 ||
        typeof data.step_key !== 'string' || data.step_key.length > 40 ||
        typeof data.label !== 'string' || data.label.length > 100 || unsafe.test(data.label) ||
        !Number.isSafeInteger(data.index) || !Number.isSafeInteger(data.total) || data.index < 0 || data.total < 1 || data.total > 30 || data.index > data.total ||
        !data.fields || typeof data.fields !== 'object' || Array.isArray(data.fields) ||
        typeof data.event_url !== 'string' || (data.event_url && !localEventURL(data.event_url))) return false;
    if (data.status === 'created' && !data.event_url) return false;
    if (!validDirectoryResolution(data.directory_resolution, data)) return false;
    const keys = new Set(['title', 'organization_id', 'organization_name', 'brief', 'date', 'scheduled_dates', 'time', 'timezone', 'capacity', 'is_synthetic', 'interview_answers', 'directory_people']);
    for (const [key, value] of Object.entries(data.fields)) {
      if (!keys.has(key)) return false;
      if (key === 'directory_people') {
        if (!Array.isArray(value) || value.length > 3 || value.some((person) =>
          !person || typeof person !== 'object' || Object.keys(person).sort().join(',') !== 'id,name,role' ||
          typeof person.id !== 'string' || !uuid.test(person.id) ||
          typeof person.name !== 'string' || !person.name.trim() || person.name.length > 160 || unsafe.test(person.name) ||
          !['speaker', 'guest'].includes(person.role))) return false;
      } else if (key === 'scheduled_dates') {
        if (!Array.isArray(value) || value.length > 366 || value.some((day) => typeof day !== 'string' || !/^20[0-9]{2}-[0-9]{2}-[0-9]{2}$/.test(day))) return false;
      } else if (key === 'interview_answers') {
        if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).length > 7) return false;
        for (const [name, answer] of Object.entries(value)) {
          if (!Object.hasOwn(labels, name) || !answer || typeof answer !== 'object' ||
              typeof answer.value !== 'string' || answer.value.length > 1000 || unsafe.test(answer.value) ||
              !['confirmed', 'assumed', 'pending', 'not_applicable', 'in_brief'].includes(answer.status)) return false;
        }
      } else if (typeof value === 'string') {
        if (value.length > 12000 || unsafe.test(value)) return false;
      } else if (value !== null && typeof value !== 'boolean' && !(typeof value === 'number' && Number.isSafeInteger(value))) return false;
    }
    return true;
  }
  function control(operation, field = '') {
    if (busy || !controls.has(operation) || (field && !Object.hasOwn(labels, field))) return;
    document.dispatchEvent(new CustomEvent('sparkx:gica-creation-control', { detail: { operation, field } }));
  }
  function addValue(key, value) {
    const row = document.createElement('div'), term = document.createElement('dt'), definition = document.createElement('dd');
    row.dataset.gicaCreationField = key; term.textContent = labels[key]; definition.textContent = value;
    const change = document.createElement('button');
    change.type = 'button'; change.className = 'text-link'; change.textContent = 'Corregir';
    change.dataset.gicaCreationEdit = key; change.setAttribute('aria-label', 'Corregir ' + labels[key]);
    change.disabled = busy || !active(); change.addEventListener('click', () => control('edit', key));
    row.append(term, definition, change); draftView.append(row);
  }
  function render() {
    panel.hidden = !draft;
    if (submit) submit.textContent = active() ? 'Responder a Gica' : originalSubmitText;
    for (const button of root.querySelectorAll('[data-gica-creation-control]')) {
      const operation = button.dataset.gicaCreationControl;
      button.disabled = busy || (['back', 'cancel', 'review', 'confirm'].includes(operation) && !active());
      if (operation === 'confirm') button.hidden = !draft || draft.status !== 'review';
      if (operation === 'back') button.hidden = !active() || draft.index < 2;
    }
    for (const button of root.querySelectorAll('[data-gica-creation-edit]')) button.disabled = busy || !active();
    if (!draft) { publishPresentation(); return; }
    progress.textContent = draft.status === 'created' ? 'Evento creado' : draft.status === 'review' ? 'Revisa tu ficha antes de crear' : `Paso ${draft.index} de ${draft.total} · ${draft.label}`;
    question.textContent = draft.reply;
    status.textContent = busy ? 'Guardando tu respuesta…' : draft.status === 'review' ? 'Confirma con el botón Crear evento o di «crear evento». Todavía no se ha guardado un evento.' : draft.status === 'created' ? 'Evento guardado. Puedes encontrarlo en Eventos o abrir su ficha desde aquí para preparar el plan.' : draft.status === 'cancelled' ? 'Creación cancelada. Puedes empezar otro evento cuando quieras.' : 'Borrador privado. Tus respuestas van completando esta ficha; puedes corregirlas antes de crear.';
    eventLink.hidden = draft.status !== 'created';
    if (!eventLink.hidden) eventLink.href = draft.event_url;
    else eventLink.removeAttribute('href');
    draftView.replaceChildren();
    const fields = draft.fields;
    for (const key of ['title', 'organization', 'brief', 'date', 'time', 'timezone', 'capacity', 'is_synthetic']) {
      let value = key === 'organization' ? (Object.hasOwn(fields, 'organization_id') ? fields.organization_name || 'Sin institución asignada' : undefined) : fields[key];
      if (key === 'is_synthetic' && typeof value === 'boolean') value = value ? 'Sí, demostración ficticia' : 'No, datos reales';
      if (value === null) value = key === 'date' || key === 'time' ? 'Por confirmar' : '';
      if ((key === 'date' || key === 'time') && value === '') value = 'Por confirmar';
      if (key === 'date' && fields.scheduled_dates?.length) value = fields.scheduled_dates.map(dateLabel).join('\n');
      if (value !== undefined && value !== '') addValue(key, String(value));
    }
    for (const [key, answer] of Object.entries(fields.interview_answers || {})) {
      const value = answer.status === 'pending' ? 'Pendiente' : answer.status === 'not_applicable' ? 'No aplica' : answer.status === 'in_brief' ? 'Ya está en la descripción' : answer.value;
      addValue(key, value);
    }
    mirrorForm();
    publishPresentation();
  }
  async function request(text, { context = '', operation = 'turn', field = '', signal, current = () => true, source = '' } = {}) {
    if ((root.dataset.gicaDemoActive === 'true') !== (source === 'narrated-demo')) throw new Error('Creation control is reserved for the current demonstration');
    if (busy) throw new Error('Creation request in progress');
    if (document.body.dataset.voiceUser !== user || !controls.has(operation)) throw new Error('Creation session changed');
    // A new explicit creation intent may replace a pending local question.
    // The server recognizes it first; other answers return to their original
    // context, while active interview fields remain literal data on the server.
    const csrf = root.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (!csrf) throw new Error('Creation session unavailable');
    const payload = { text, operation, request_id: crypto.randomUUID(), expected_revision: active() ? String(draft.revision) : '0' };
    if (active()) payload.draft_id = draft.draft_id;
    if (field) payload.field = field;
    busy = true; render();
    try {
      const response = await fetch('/assistant/event-creation/', {
        method: 'POST', credentials: 'same-origin', redirect: 'error', cache: 'no-store', signal,
        headers: { 'X-CSRFToken': csrf, Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body: new URLSearchParams(payload)
      });
      if (!current() || document.body.dataset.voiceUser !== user) return null;
      if (![200, 400, 409, 410].includes(response.status) || !(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Creation unavailable');
      const raw = await response.text();
      if (!current()) return null;
      if (raw.length > 32768) throw new Error('Creation too large');
      const data = JSON.parse(raw);
      if (!valid(data)) throw new Error('Creation invalid');
      if (data.handled) {
        preview = '';
        responseStatus = data.status;
        draft = { ...data, status: data.status === 'expired' ? 'expired' : data.draft_status || data.status };
        if (data.status === 'created' && localEventURL(data.event_url)) window.SparkXGicaGuided?.setEvent(data.event_url.split('/')[2]);
        render();
        if (active() && !document.querySelector('main form[data-gica-event-form="create"]')) {
          liveEvent('opening');
          const destination = await window.SparkXGicaNavigation?.openCreation();
          if (current() && destination?.success) { render(); liveEvent('opened'); }
          else if (current()) status.textContent = 'El borrador está guardado. No pude abrir el formulario; puedes continuar aquí o pulsar Continuar mi borrador.';
        }
        if (current() && active() && presented !== draft.draft_id && document.querySelector('main form[data-gica-event-form="create"]')) {
          presented = draft.draft_id;
          if (root.dataset.voiceSessionContinuous === 'true' || source === 'narrated-demo') {
            const details = root.querySelector('#romeo-presence-details');
            const toggle = root.querySelector('[data-romeo-presence-toggle]');
            if (details) details.hidden = true;
            toggle?.setAttribute('aria-expanded', 'false');
            document.dispatchEvent(new CustomEvent('sparkx:romeo-action-layout'));
          }
        }
      }
      return data;
    } finally { busy = false; render(); }
  }
  for (const button of root.querySelectorAll('[data-gica-creation-control]')) {
    button.addEventListener('click', () => control(button.dataset.gicaCreationControl));
  }
  // The ordinary action runner must never interpret an event-field answer.
  // Capture before its form listener, including Enter and the visible submit.
  document.addEventListener('submit', (event) => {
    if (event.target.matches?.('main form[data-gica-event-form="create"]') && event.target.dataset.gicaGuidedDraft) {
      event.preventDefault(); event.stopImmediatePropagation();
      if (active() && !busy) control('confirm');
      return;
    }
    if (event.target !== actionForm || !active()) return;
    event.preventDefault(); event.stopImmediatePropagation();
    if (!busy) control('turn');
  }, true);
  root.querySelector('[name="command"]')?.addEventListener('input', (event) => {
    preview = active() ? event.target.value.slice(0, 300) : '';
    mirrorForm();
  });
  document.addEventListener('sparkx:gica-creation-preview', (event) => {
    if (!active() || typeof event.detail?.text !== 'string') return;
    preview = event.detail.text.slice(0, 300); mirrorForm();
  });
  document.addEventListener('sparkx:gica-navigation-complete', () => { if (draft) render(); });
  new MutationObserver(() => {
    if (document.body.dataset.voiceUser !== user) {
      preview = ''; draft = null; responseStatus = 'none'; releaseProjection();
      draftView.replaceChildren(); panel.hidden = true; eventLink.hidden = true; eventLink.removeAttribute('href');
    }
  }).observe(document.body, { attributes:true, attributeFilter:['data-voice-user'] });
  render();
  window.SparkXGicaCreation = Object.freeze({ request, hasDraft: active,
    canListenEarly: () => active() && draft.status === 'collecting' && draft.step_key !== 'organization' && !draft.directory_resolution,
    presentation, validateChoice });
})();

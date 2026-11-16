/* Explicit foreground voice session; no background wake service or new tools. */
(() => {
  'use strict';
  const root = document.querySelector('[data-romeo-presence]');
  const button = root?.querySelector('[data-romeo-voice-session]');
  const topStop = root?.querySelector('[data-romeo-voice-stop]');
  const status = root?.querySelector('[data-romeo-voice-session-status]');
  const indicator = root?.querySelector('[data-romeo-voice-indicator]');
  const field = root?.querySelector('#romeo-command');
  const speakEnabled = document.querySelector('[data-romeo-speak]');
  const probe = document.querySelector('[data-romeo-voice-test]');
  const speechStatus = document.querySelector('[data-romeo-speech-status]');
  const guided = root?.querySelector('[data-gica-guided]');
  const guideStatus = root?.querySelector('[data-gica-conversation]');
  const transcript = root?.querySelector('[data-gica-transcript]');
  const reviewPattern = document.querySelector('[data-gica-review-pattern]');
  const memoryEnabled = document.querySelector('[data-gica-memory-enabled]');
  const memoryStatus = document.querySelector('[data-gica-memory-status]');
  const latency = document.querySelector('[data-gica-latency]');
  const publicKnowledge = document.querySelector('[data-gica-public-knowledge]');
  const knowledgeAnswer = root?.querySelector('[data-gica-knowledge-answer]');
  const earlyListening = document.querySelector('[data-gica-early-listening]');
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const controls = window.SparkXRomeoCommands, voice = window.SparkXVoice, speech = window.SparkXRomeoSpeech;
  if (!root || !button || !topStop || !status || !indicator || !field || !speakEnabled || !probe || !speechStatus || !controls || !voice || !speech) return;
  const unsafe = /[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u;
  const intents = Object.freeze(['theme_light', 'theme_dark', 'calendar_open', 'directory_open', 'people_search', 'events_open']);
  // Only these authored greetings may precede a prepared action. Never speak
  // arbitrary ready metadata, the original command or a searched person's name.
  const actionGreetings = Object.freeze(['Buenos días.', 'Buenas tardes.', 'Buenas noches.', 'Hola.', 'Buenas.']);
  const guidedUI = !!(guided && guideStatus && transcript && reviewPattern &&
    (!root.dataset.guideUrl || root.dataset.guideUrl === '/assistant/guide/'));
  const exchanges = [];
  let lastPattern = null;
  let guideContext = '';
  let textGuide = null;
  // Compatibility is finite and not advertised; old labels confer no new actions.
  const legacyControls = Object.freeze({
    wake: Object.freeze(['romeo hablemos']), execute: Object.freeze(['romeo ejecuta', 'rome ejecuta']),
    cancel: Object.freeze(['romeo cancela']), stop: Object.freeze(['romeo silencio', 'romeo deja de escuchar'])
  });
  const normalize = (text) => text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/[.,!?¿¡:;…]/gu, ' ').trim().replace(/\s+/gu, ' ');
  let session = null, generation = 0, config = null, language = null, writing = false;
  let speechOwner = null, outputSpeaking = false, probeGeneration = 0;
  let lab = null, labOpen = false;
  let navigation = null;
  let memoryGeneration = 0, memoryRequest = null, manualAction = null;
  const memoryQueue = [];
  const shownCreations = new Set();
  const textIdleMs = 1500;
  const directoryIdleMs = 2500;
  const turnLimit = 300, reviewLimit = 4096;
  const turnText = (value) => value.normalize('NFC').trim().replace(/\s+/gu, ' ');
  const hasTurnText = (value) => /[\p{L}\p{N}]/u.test(value);
  const retryTurn = document.createElement('button');
  retryTurn.type = 'button'; retryTurn.className = 'button button-secondary';
  retryTurn.textContent = 'Volver a dictar'; retryTurn.dataset.gicaTurnRetry = ''; retryTurn.hidden = true;
  status.after(retryTurn);
  retryTurn.addEventListener('click', () => {
    if (session?.reviewBlocked && valid(session)) applyTurnControl(session, 'correct');
  });
  const nativeCodes = new Set(['no-speech', 'aborted', 'network', 'audio-capture', 'not-allowed', 'service-not-allowed', 'language-not-supported', 'bad-grammar', 'unknown']);
  const stopCodes = new Set(['stopped', 'manual', 'voice-stop', 'start-budget', 'rapid-start-failures', ...nativeCodes]);
  const diagnosticTrace = [];
  function diagnostic(run, event, code = '') {
    const entry = Object.freeze({ event, code: nativeCodes.has(code) || stopCodes.has(code) ? code : '',
      at_ms: Math.round(performance.now()), phase: run?.phase || 'off', service: !!run?.service,
      audio: !!run?.audio, guided: !!run?.guided, holding: !!run?.holding, early: !!run?.early,
      response_pending: !!run?.responsePending, guide_pending: !!run?.guideInFlight,
      retry_scheduled: !!run?.retryTimer, starts: run?.starts || 0, retries: run?.restarts || 0 });
    diagnosticTrace.push(entry); if (diagnosticTrace.length > 40) diagnosticTrace.shift();
    document.dispatchEvent(new CustomEvent('sparkx:gica-voice-diagnostic', { detail: entry }));
  }
  window.SparkXGicaVoiceDiagnostics = Object.freeze({ snapshot: () => Object.freeze(diagnosticTrace.map((entry) => Object.freeze({ ...entry }))) });
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
  const memoryUser = document.body.dataset.voiceUser || '';
  const memoryKey = /^[1-9][0-9]{0,18}$/.test(memoryUser) ? `sparkx.gica.memory.enabled.v3.u${memoryUser}` : null;
  // Settings are visible in bot management; the fixed controller uses the same
  // single nodes (hidden fallbacks on other views). Store only account-scoped
  // booleans locally, never transcripts, permissions, keys or model settings.
  for (const [node, preferenceName] of [[speakEnabled, 'spoken'], [earlyListening, 'early'], [publicKnowledge, 'knowledge']]) {
    if (!node || !memoryKey) continue;
    const preferenceKey = `sparkx.gica.preference.${preferenceName}.v1.u${memoryUser}`;
    try { const saved = localStorage.getItem(preferenceKey); if (saved === 'on' || saved === 'off') node.checked = saved === 'on'; }
    catch (_) { /* A blocked store leaves the visible setting functional. */ }
    node.addEventListener('change', () => {
      if (document.body.dataset.voiceUser !== memoryUser) return;
      try { localStorage.setItem(preferenceKey, node.checked ? 'on' : 'off'); }
      catch (_) { /* The preference applies to this document only. */ }
    });
  }
  if (memoryEnabled && memoryKey) {
    try { const saved = localStorage.getItem(memoryKey); if (saved === 'off' || saved === 'on') memoryEnabled.checked = saved === 'on'; }
    catch (_) { /* The visible switch still works for this document. */ }
  }
  if (memoryEnabled && !memoryEnabled.checked) memoryNotice('Registro textual desactivado. Preferencia recordada para esta cuenta en este navegador.');

  function memoryNotice(message) { if (memoryStatus) memoryStatus.textContent = message; }
  function discardMemory() {
    memoryGeneration += 1; memoryQueue.length = 0;
    if (memoryRequest) {
      clearTimeout(memoryRequest.timeout); memoryRequest.controller.abort(); memoryRequest = null;
      memoryNotice('Registro detenido. Una solicitud enviada pudo llegar; comprueba Mi memoria antes de repetirla.');
    } else memoryNotice('Registro textual desactivado. No se encolarán nuevos turnos.');
  }
  async function drainMemory() {
    if (memoryRequest || !memoryQueue.length || !memoryEnabled?.checked || document.hidden) return;
    const item = memoryQueue.shift(), version = memoryGeneration;
    if (document.body.dataset.voiceUser !== item.userID) { memoryQueue.length = 0; return; }
    const token = root.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (!token) { memoryQueue.length = 0; memoryNotice('No se pudo registrar el turno. Revisa tu sesión.'); return; }
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 8000);
    memoryRequest = { controller, timeout };
    try {
      await loadLanguage();
      if (version !== memoryGeneration || !memoryEnabled.checked || document.hidden || document.body.dataset.voiceUser !== item.userID) return;
      if (item.needsNormalization) item.payload.normalized_text = item.context === 'person_name'
        ? item.payload.original_text.normalize('NFC') : language(item.payload.original_text, item.context);
      const response = await fetch('/assistant/interactions/', {
        method: 'POST', credentials: 'same-origin', redirect: 'error', cache: 'no-store', signal: controller.signal,
        headers: { 'X-CSRFToken': token, Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify(item.payload)
      });
      if (version !== memoryGeneration || !memoryEnabled.checked || document.hidden) return;
      if (response.status === 409) { memoryNotice('No se guardó el turno: revisa el límite de Mi memoria y borra registros si corresponde.'); return; }
      if (!response.ok || !(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Memory unavailable');
      const raw = await response.text();
      if (version !== memoryGeneration || !memoryEnabled.checked || document.hidden) return;
      if (raw.length > 4096 || JSON.parse(raw)?.ok !== true) throw new Error('Memory invalid');
      memoryNotice('Turno textual guardado en Mi memoria. Sin audio.');
    } catch (_) {
      if (version === memoryGeneration && memoryEnabled?.checked && !document.hidden) memoryNotice('No se confirmó el registro del turno. Tu orden sigue su curso; comprueba Mi memoria sin repetir la acción.');
    } finally {
      clearTimeout(timeout);
      if (version === memoryGeneration) { memoryRequest = null; drainMemory(); }
    }
  }
  function persistInteraction(run, payload, turn) {
    if (!run.logAccepted || !memoryEnabled?.checked || root.dataset.interactionUrl !== '/assistant/interactions/' || document.hidden ||
        !/^[1-9][0-9]{0,18}$/.test(run.userID || '') || run.userID !== document.body.dataset.voiceUser) return;
    if (memoryQueue.length >= 6) { memoryNotice('No se registró este turno: hay varias solicitudes de memoria pendientes. La acción no se repite.'); return; }
    memoryQueue.push({ userID: run.userID, payload, needsNormalization: !turn.normalizedKnown, context: turn.normalizationContext }); drainMemory();
  }
  memoryEnabled?.addEventListener('change', () => {
    if (!memoryEnabled.checked) discardMemory(); else memoryNotice('Registro textual activo para los próximos turnos finalizados. No guarda audio.');
    if (memoryKey && document.body.dataset.voiceUser === memoryUser) {
      try { localStorage.setItem(memoryKey, memoryEnabled.checked ? 'on' : 'off'); }
      catch (_) { memoryNotice('El cambio del registro vale sólo para esta página: el navegador no pudo recordar esta preferencia.'); }
    }
  });

  function render() {
    const run = session;
    const demo = root.dataset.gicaDemoActive === 'true';
    root.dataset.voiceTextIdleMs = String(turnIdleMs());
    retryTurn.hidden = !run?.reviewBlocked;
    root.dataset.voiceSessionState = demo ? 'demo' : run?.phase || 'off';
    root.dataset.voiceAudioActive = String(!!run?.audio && (!outputSpeaking || !!run?.early));
    root.dataset.voiceSpeaking = String(outputSpeaking);
    root.dataset.voiceTurn = !run ? 'off' : run.holding ? 'waiting' : outputSpeaking ? 'gica' : run.audio && run.service ? 'user' : 'paused';
    root.dataset.voiceSessionContinuous = String(!!run?.guided && !run.textOnly);
    button.setAttribute('aria-pressed', String(!!run));
    const isGuided = run?.guided || (!run && guidedUI && guided.checked);
    button.textContent = run ? (isGuided ? 'Terminar conversación' : 'Apagar voz rápida') : (isGuided ? 'Reanudar conversación' : 'Activar voz rápida');
    if (textGuide) { textGuide.hidden = !guided.checked; textGuide.disabled = !!run?.guideInFlight || !!run?.awaitingAction; }
    if (guideStatus) guideStatus.hidden = !(isGuided || exchanges.length) || guideStatus.textContent === exchanges.at(-1)?.reply;
    if (transcript) transcript.hidden = !exchanges.length;
    if (reviewPattern) reviewPattern.hidden = !lastPattern;
    topStop.hidden = !run;
    indicator.hidden = !demo && !run && !outputSpeaking && !window.SparkXGicaCreation?.hasDraft();
    indicator.textContent = demo ? 'Piloto · mic apagado' : run?.holding ? (run.audio && run.service ? 'En espera' : 'En espera · mic en pausa') : run?.early && run.audio ? 'Puedes responder · Gica termina' : outputSpeaking ? 'Gica habla' : run?.guided && run.audio && run.service ? 'Tu turno · te escucho' : run?.detected ? 'Voz detectada' : run?.audio ?
      (run.phase === 'dictating' ? 'Dictando' : 'Escuchando') : run?.phase === 'starting' ? 'Iniciando mic' :
      run?.phase === 'acting' ? 'Procesando' : run?.phase === 'reconnecting' ? 'Reconectando' :
      ['waiting', 'dictating'].includes(run?.phase) ? 'Esperando audio' : run ? 'Mic en pausa' : window.SparkXGicaCreation?.hasDraft() ? 'Mic apagado · borrador guardado' : 'Mic apagado';
    indicator.title = 'Estado del micrófono' + (root.dataset.voiceLastError ? ` · último código: ${root.dataset.voiceLastError}` : '') +
      (root.dataset.voiceStopCode ? ` · detención: ${root.dataset.voiceStopCode}` : '');
    companion({ kind: 'voice', active: demo || !!run, micActive: !!run && !run.textOnly,
      phase: demo ? 'demo' : run?.phase || 'off', speaking: outputSpeaking,
      blocked: demo || !!(run?.holding || run?.reviewBlocked || run?.guideInFlight || run?.awaitingAction || navigation || labOpen),
      listening: !!run?.audio && !!run?.service && (!outputSpeaking || !!run?.early) });
    document.dispatchEvent(new CustomEvent('sparkx:romeo-action-layout'));
  }
  function companion(detail) {
    if (!memoryKey || document.body.dataset.voiceUser !== memoryUser) return;
    document.dispatchEvent(new CustomEvent('sparkx:gica-companion-state', {
      detail: { ...detail, user: memoryUser }
    }));
  }
  function mark(phase, message) {
    if (session) session.phase = phase;
    status.textContent = message; render();
  }
  function listening(active) {
    if (active) field.dataset.voiceListening = 'true'; else delete field.dataset.voiceListening;
    document.dispatchEvent(new CustomEvent('sparkx:dictation-state', { detail: { inputID: field.id, listening: active } }));
  }
  function valid(run) {
    return root.dataset.gicaDemoActive !== 'true' && session === run && generation === run.generation && !document.hidden &&
      field.isConnected && !field.disabled && Date.now() < run.expires &&
      (!run.guided || run.userID === document.body.dataset.voiceUser);
  }
  function detach(run) {
    const service = run.service;
    run.service = null; run.ticket += 1; run.audio = false; run.detected = false;
    // Invalidate before abort: late callbacks cannot write, submit or reconnect.
    if (service) { try { service.abort(); } catch (_) { /* Already ended. */ } listening(false); }
  }
  function stop(message = 'Micrófono apagado. El texto se conserva para revisión manual.', code = 'stopped') {
    const previous = session;
    if (!previous) return;
    root.dataset.voiceStopCode = stopCodes.has(code) ? code : 'stopped';
    diagnostic(previous, 'stop', root.dataset.voiceStopCode);
    session = null; generation += 1;
    clearTimeout(previous.timer); clearTimeout(previous.retryTimer); clearTimeout(previous.actionTimer);
    clearGuide(previous);
    previous.early = null;
    detach(previous);
    if (speechOwner === previous) { speechOwner = null; outputSpeaking = false; speech.cancel(); }
    status.textContent = message; render();
  }
  function clearGuide(run) {
    clearTurn(run); clearTimeout(run.guideTimeout); run.readyOrder = null;
    run.guideTicket = (run.guideTicket || 0) + 1;
    run.guideController?.abort(); run.guideController = null; run.guideInFlight = false;
  }
  function clearTurn(run) {
    clearTimeout(run.guideTimer); clearTimeout(run.turnTimer);
    run.guideTimer = null; run.turnTimer = null; run.guideBuffer = '';
    run.speechActive = false;
    run.voiceEndAt = null; run.voiceStartAt = null; run.audioEndAt = null;
    run.interimAt = null; run.finalAt = null; run.resultAt = null;
    run.unfinalized?.clear();
    run.recognizedParts?.clear(); run.textChangedAt = null; run.textSnapshot = '';
  }
  function directoryTurn() {
    const creation = window.SparkXGicaCreation;
    if (!creation?.hasDraft()) return false;
    const current = creation.presentation?.();
    return current?.step_key === 'organization' || !!current?.directory_resolution;
  }
  function turnIdleMs() { return directoryTurn() ? directoryIdleMs : textIdleMs; }
  function idleSeconds() { return directoryTurn() ? '2,5' : '1,5'; }
  function directoryQuestionEcho(run, text) {
    const recent = run.directoryEcho;
    if (!directoryTurn() || !recent || performance.now() > recent.until) return false;
    const words = (value) => value.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().match(/[\p{L}\p{N}]+/gu) || [];
    const answer = words(text), question = words(recent.text);
    // Short choices, yes/no and actual candidate names remain valid answers.
    // Ignore only a substantial contiguous fragment of our own spoken prompt.
    if (answer.length < 4) return false;
    const value = answer.join(' ');
    const resolution = window.SparkXGicaCreation?.presentation?.()?.directory_resolution;
    const names = [resolution?.query, ...(resolution?.candidates || []).map((item) => item.name)];
    if (names.some((name) => typeof name === 'string' && words(name).join(' ') === value)) return false;
    return (` ${question.join(' ')} `).includes(` ${value} `) ||
      (question.length >= 4 && (` ${value} `).includes(` ${question.join(' ')} `));
  }
  function observeTranscript(run, ticket, index, text) {
    const part = turnText(text);
    run.recognizedParts.set(`${ticket}:${index}`, part);
    const snapshot = [...run.recognizedParts.values()].filter(Boolean).join(' ');
    if (run.recognizedParts.size > 100 || snapshot.length > turnLimit) {
      reviewLongTurn(run, snapshot, run.recognizedParts.size > 100 ? 'segments' : 'length'); return false;
    }
    const context = run.followUp === 'person_name' ? 'person_name' : '';
    const visible = context === 'person_name' ? snapshot : language ? language(snapshot, context) : snapshot;
    if (visible !== run.textSnapshot) {
      run.textSnapshot = visible; run.textChangedAt = performance.now();
    }
    // Provisional writing is visible, but only definitive understood text dispatches.
    if (!run.readyOrder && run.capture) write(visible, snapshot);
    return true;
  }
  function reviewLongTurn(run, text, reason = 'length') {
    if (!valid(run)) return;
    const retained = turnText(text).slice(0, reviewLimit);
    if (!run.guided) { stop('El dictado es demasiado largo. Revísalo antes de ejecutar.'); return; }
    clearTurn(run); run.readyOrder = null; run.draft = ''; run.readyIntent = ''; lastPattern = null;
    run.reviewBlocked = true; run.holding = true;
    if (run.responsePending) {
      run.responseTicket += 1; run.responsePending = false; run.early = null;
      if (speechOwner === run) { speechOwner = null; outputSpeaking = false; speech.cancel(); }
    }
    write(retained, retained);
    if (window.SparkXGicaCreation?.hasDraft()) {
      document.dispatchEvent(new CustomEvent('sparkx:gica-creation-preview', { detail: { text: '' } }));
    }
    openPanel();
    const manual = root.querySelector('[data-gica-manual-mode]');
    if (manual) manual.open = true;
    const clipped = turnText(text).length > reviewLimit;
    const reply = reason === 'incomplete' ?
      'El navegador no terminó de confirmar esta respuesta. Conservé el texto sin enviarlo. Pulsa Volver a dictar o di «Gica corrige» para repetirla; seguimos conversando.' : reason === 'segments' ?
      'Recibí demasiados fragmentos en esta respuesta. Conservé el texto sin enviarlo. Pulsa Volver a dictar o di «Gica corrige» para repetirla.' : clipped ?
      'La respuesta es muy extensa. Conservé una vista del texto para revisión, sin enviarlo. Pulsa Volver a dictar o di «Gica corrige» y cuéntamelo más breve.' :
      'Esta respuesta supera los 300 caracteres. Conservé el texto sin enviarlo. Pulsa Volver a dictar o di «Gica corrige» y cuéntamelo más breve; tu ficha sigue guardada.';
    diagnostic(run, reason === 'incomplete' ? 'turn-incomplete' : 'turn-overflow');
    respond(run, reply, 'holding');
  }
  function turnActivity(run, source = '') {
    if (!valid(run) || !run.guided || run.textOnly || run.guideInFlight || run.holding || run.early || run.responsePending) return;
    const now = performance.now();
    if (source === 'speech_start') { run.voiceStartAt = now; run.voiceEndAt = null; run.audioEndAt = null; }
    else if (source === 'speech_end') run.voiceEndAt = now;
    else if (source === 'audio_end' && run.audioEndAt === null) run.audioEndAt = now;
    else if (source === 'interim') { run.interimAt = now; run.resultAt = now; }
    else if (source === 'final') { run.finalAt = now; run.resultAt = now; }
    // Sound events are diagnostic only. Ambient noise cannot start or delay a turn.
    if (source !== 'interim' && source !== 'final') return;
    if (run.textChangedAt === null || !hasTurnText(run.textSnapshot)) return;
    if (!run.turnTimer) run.turnTimer = setTimeout(() => {
      if (valid(run)) reviewLongTurn(run, field.value || run.textSnapshot, 'incomplete');
    }, 30000);
    clearTimeout(run.guideTimer);
    if (!run.guideBuffer || run.unfinalized.size) return;
    // Only a changed transcript resets the idle deadline. Repeated text
    // and promotion from interim to identical final text preserve its timestamp.
    const due = run.textChangedAt + turnIdleMs();
    run.guideTimer = setTimeout(() => {
      if (!valid(run)) return;
      if (run.unfinalized.size) return;
      finishGuidedTurn(run);
    }, Math.max(0, due - now));
  }
  function captureTurn(run, original) {
    const context = run.followUp === 'person_name' ? 'person_name' : '';
    return { request_id: crypto.randomUUID(), session_id: run.sessionID, sequence: ++run.sequence,
      original_text: original, normalized_text: context === 'person_name' ? original.normalize('NFC') : language ? language(original, context) : original,
      normalizedKnown: !!language || context === 'person_name', normalizationContext: context,
      source: run.textOnly ? 'text' : 'voice', speechEndAt: run.voiceEndAt, finalAt: run.finalAt, textChangedAt: run.textChangedAt,
      anchor: run.textOnly ? 'text' : 'transcript_estimated',
      dispatchAt: null, responseAt: null, ttsStartAt: null, ttsEndAt: null, serverMs: null };
  }
  function relative(end, start) {
    return Number.isFinite(end) && Number.isFinite(start) ? Math.max(0, Math.round(end - start)) : null;
  }
  function interactionFinished(run, turn, reply, phase, statusValue, intent = '', actionID = '', outcome = 'none', detached = false) {
    if (!turn || (detached ? document.hidden || run.userID !== document.body.dataset.voiceUser : !valid(run))) return;
    const detail = { request_id: turn.request_id, session_id: turn.session_id, sequence: turn.sequence,
      original_text: turn.original_text, normalized_text: turn.normalized_text, reply, source: turn.source,
      draft: turn.draft || '', phase, status: statusValue, intent, action_id: actionID, outcome, consent_version: '3',
      timing_basis: turn.anchor === 'speech_end' ? 'speech_end' : turn.anchor === 'text' ? 'text' : 'estimated', timings: {
        text_change_to_dispatch_ms: relative(turn.dispatchAt, turn.textChangedAt),
        speech_end_to_dispatch_ms: relative(turn.dispatchAt, turn.speechEndAt),
        final_to_dispatch_ms: relative(turn.dispatchAt, turn.finalAt),
        guide_roundtrip_ms: relative(turn.responseAt, turn.dispatchAt), guide_server_ms: turn.serverMs,
        response_to_tts_ms: relative(turn.ttsStartAt, turn.responseAt),
        speech_end_to_tts_ms: relative(turn.ttsStartAt, turn.speechEndAt),
        tts_duration_ms: relative(turn.ttsEndAt, turn.ttsStartAt)
      } };
    for (const [key, value] of Object.entries(detail.timings)) if (!Number.isFinite(value) || value < 0 || value > 120000) delete detail.timings[key];
    if (latency && phase === 'request') {
      const times = detail.timings;
      latency.textContent = 'Tiempos de la transcripción del navegador: ' +
        (Number.isFinite(times.text_change_to_dispatch_ms) ? `guía a los ${(times.text_change_to_dispatch_ms / 1000).toFixed(2)} s desde el último cambio de texto. ` : '') +
        (Number.isFinite(times.guide_roundtrip_ms) ? `Respuesta local: ${times.guide_roundtrip_ms} ms. ` : '') +
        (Number.isFinite(times.tts_duration_ms) ? `Voz: ${times.tts_duration_ms} ms.` : 'Sin reproducción de voz medida.');
      latency.hidden = false;
    }
    document.dispatchEvent(new CustomEvent('sparkx:gica-interaction', { detail }));
    persistInteraction(run, detail, turn);
  }
  function actionInteraction(run, detail, terminal = false, detached = false) {
    const origin = run.actionOrigin;
    if (!origin || (!terminal && detail?.stage !== 'pending')) return;
    const id = uuid.test(detail?.action_id || '') ? detail.action_id : '';
    const intent = intents.includes(detail?.action) ? detail.action : '';
    const marker = `${detail?.stage}:${id}`;
    if (run.actionLogs.has(marker)) return;
    run.actionLogs.add(marker);
    const turn = { ...origin, request_id: crypto.randomUUID(), sequence: ++run.sequence,
      dispatchAt: null, responseAt: null, ttsStartAt: null, ttsEndAt: null, serverMs: null };
    const stage = detail?.stage;
    const statusValue = ['completed', 'already', 'arrived'].includes(stage) ? 'completed' :
      stage === 'info' ? 'info' : stage === 'cancelled' ? 'cancelled' : stage === 'clarify' ? 'clarify' : stage === 'unrecorded' ? 'unknown' : terminal ? 'failed' : 'ready';
    const outcome = ['completed', 'already', 'arrived', 'cancelled', 'unrecorded'].includes(stage) ? stage : terminal && !['clarify', 'info'].includes(stage) ? 'failed' : 'none';
    const reply = typeof detail?.reply === 'string' && detail.reply.length <= 500 && !unsafe.test(detail.reply)
      ? detail.reply : terminal ? 'La comprobación de tu orden terminó. Revisa el resultado en pantalla.' : 'La orden está registrada y pendiente de ejecución.';
    if (stage === 'info') turn.draft = '';
    interactionFinished(run, turn, reply, stage === 'info' ? 'request' : 'action', statusValue, intent, id, outcome, detached);
  }
  function rememberExchange(text, reply) {
    exchanges.push({ text, reply });
    while (exchanges.length > 6) exchanges.shift();
    transcript.replaceChildren();
    for (const exchange of exchanges) {
      const row = document.createElement('div'); row.className = 'gica-conversation-turn';
      const user = document.createElement('p'), answer = document.createElement('p');
      const userLabel = document.createElement('strong'), answerLabel = document.createElement('strong');
      userLabel.textContent = 'Tú: '; answerLabel.textContent = 'Gica: ';
      user.append(userLabel, document.createTextNode(exchange.text));
      answer.append(answerLabel, document.createTextNode(exchange.reply)); row.append(user, answer); transcript.append(row);
    }
    transcript.scrollTop = transcript.scrollHeight;
    companion({ kind: 'exchange', userText: text.slice(0, 300), assistantText: reply.slice(0, 500) });
  }
  function write(text, original = text) {
    writing = true;
    try { field.value = text; field.dispatchEvent(new Event('input', { bubbles: true })); }
    finally { writing = false; }
    if (window.SparkXGicaCreation?.hasDraft() && typeof original === 'string' && original.length <= 300 && !unsafe.test(original)) {
      document.dispatchEvent(new CustomEvent('sparkx:gica-creation-preview', { detail: { text: original.normalize('NFC') } }));
    }
  }
  function openPanel() {
    const details = root.querySelector('#romeo-presence-details');
    if (details) { details.hidden = false; root.querySelector('[data-romeo-presence-toggle]')?.setAttribute('aria-expanded', 'true'); }
    document.dispatchEvent(new CustomEvent('sparkx:romeo-action-layout'));
  }
  function schedule(run, targetPhase, delay = 150) {
    if (run.textOnly) return;
    clearTimeout(run.retryTimer); run.retryTimer = null;
    if (navigation || run.awaitingAction) { mark('paused', 'Micrófono en pausa mientras termina la navegación o la acción.'); return; }
    run.retryTimer = setTimeout(() => { run.retryTimer = null; if (valid(run) && !navigation && !run.awaitingAction) startRecognizer(run, targetPhase); }, delay);
  }
  function speechResult(result) {
    speechStatus.textContent = result.spoken ? `${voiceDescription()} Respuesta terminada.` :
      result.reason === 'voice_unavailable' && speech.getPreference().voiceID ? 'Tu voz elegida no está disponible. Abre Comparar voces para elegir otra o restablecer automática.' :
      ['unsupported', 'no_local_voice'].includes(result.reason) ? 'Sin voz española local disponible. Gica responde por texto; no usará una voz remota.' :
      'La respuesta hablada no terminó. El texto sigue disponible.';
  }
  function voiceDescription() {
    const selected = speech.selectedVoice();
    if (!selected) return 'Sin voz española local disponible.';
    return `Voz de Gica: ${selected.name} (${selected.lang}). ${selected.male ? 'Masculina local.' : speech.getPreference().voiceID ? 'Voz local elegida por ti.' : 'Local; no se identificó una voz masculina compatible.'}`;
  }
  async function respond(run, text, nextPhase = 'waiting', resume = true, turn = null, eventQuestion = false) {
    if (!valid(run)) return false;
    companion({ kind: 'exchange', assistantText: text.slice(0, 500) });
    const responseTicket = ++run.responseTicket;
    run.directoryEcho = eventQuestion && directoryTurn() && speakEnabled.checked && !run.textOnly
      ? { text, until: Infinity } : null;
    run.responsePending = true;
    clearTimeout(run.retryTimer); run.retryTimer = null; detach(run); run.early = null;
    mark('paused', 'Micrófono en pausa. Gica está respondiendo.');
    if (run.guided && guideStatus) guideStatus.textContent = text;
    if (turn && turn.responseAt === null) turn.responseAt = performance.now();
    if (speakEnabled.checked && !run.textOnly) {
      speechOwner = run; run.speechMeasure = turn;
      const onProgress = eventQuestion && run.guided && !directoryTurn() && earlyListening?.checked && !run.earlyDisabled && !run.holding &&
        window.SparkXGicaCreation?.hasDraft() && window.SparkXGicaCreation?.canListenEarly?.() === true ? (progress) => {
        if (!valid(run) || run.responseTicket !== responseTicket || !run.responsePending || run.early || run.earlyDisabled || !earlyListening.checked ||
            progress.elapsedMs < 300 || progress.remainingEstimateMs > 5000 || speechOwner !== run || !window.speechSynthesis?.speaking) return;
        run.early = { question: normalize(text), responseTicket, ending: false };
        startRecognizer(run, 'early-listening', true);
      } : null;
      const result = await speech.speak(text, { eventQuestion, onProgress });
      if (!valid(run) || run.responseTicket !== responseTicket) return false;
      if (run.directoryEcho) {
        if (result.spoken) run.directoryEcho.until = performance.now() + 4000;
        else run.directoryEcho = null;
      }
      diagnostic(run, result.spoken ? 'tts-ended' : 'tts-fallback');
      if (run.early && !result.spoken) {
        const visible = field.value, held = run.holding ? run.guideBuffer : '';
        clearTurn(run); run.early = null; detach(run); write(visible);
        if (run.holding) { run.guideBuffer = held; run.textSnapshot = visible; run.textChangedAt = performance.now(); }
        run.earlyDisabled = true;
        if (guideStatus) guideStatus.textContent = 'La lectura no terminó. Conservé el texto para revisión, sin enviarlo; repite tu respuesta cuando vuelva a escuchar.';
      }
      run.speechMeasure = null;
      if (speechOwner === run) { speechOwner = null; outputSpeaking = false; }
      if (speakEnabled.checked) {
        speechResult(result);
        if (run.earlyDisabled) speechStatus.textContent += ' Escucha anticipada no disponible en esta sesión; responde al terminar cada pregunta.';
      }
      else speechStatus.textContent = 'Respuestas habladas desactivadas. El texto sigue disponible.';
    }
    if (!valid(run) || run.responseTicket !== responseTicket) return false;
    run.responsePending = false;
    if (run.early) {
      run.early = null;
      // A recognizer may finish normally before TTS. Keep a final answer and
      // explicitly restore its idle timer even when that recognizer is gone.
      if (!run.holding && run.guideBuffer && !run.unfinalized.size) { run.textChangedAt = performance.now(); turnActivity(run, 'final'); }
      if (run.holding) {
        mark('holding', 'En espera. Conservo tu texto; di «Gica corrige» o «Gica continúa».');
        if (!run.service && resume) schedule(run, 'holding'); return true;
      }
      if (run.service) {
        mark('dictating', `Tu turno · te escucho. La pregunta terminó; esperaré ${idleSeconds()} segundos de texto estable.`);
        // Even an already-stable early answer waits 1.5 seconds after speech.
        return true;
      }
    }
    run.phase = 'paused'; render();
    if (resume) schedule(run, run.guided ? 'dictating' : nextPhase, directoryTurn() && !run.textOnly ? 600 : 150);
    return true;
  }
  function validateGuide(data) {
    if (!data || Object.keys(data).sort().join(',') !== 'draft,follow_up,intent,reply,status' ||
        !['ready', 'clarify', 'refused', 'info'].includes(data.status) ||
        typeof data.reply !== 'string' || !data.reply.trim() || data.reply.length > 280 || unsafe.test(data.reply) || /[<>]/u.test(data.reply) ||
        typeof data.draft !== 'string' || data.draft.length > 300 || unsafe.test(data.draft) ||
        typeof data.intent !== 'string' || !['', ...intents].includes(data.intent) ||
        !['', 'person_name', 'theme'].includes(data.follow_up)) return false;
    if (data.status === 'ready') return !!data.draft.trim() && intents.includes(data.intent) && data.follow_up === '';
    return data.draft === '' && data.intent === '' && (data.status === 'clarify' || data.follow_up === '');
  }
  function validKnowledge(data) {
    if (!data || typeof data.handled !== 'boolean') return false;
    if (!data.handled) return Object.keys(data).join(',') === 'handled';
    if (!['found', 'pending', 'unavailable', 'not_found', 'review_needed', 'offline', 'limited', 'invalid'].includes(data.status) ||
        typeof data.reply !== 'string' || !data.reply.trim() || data.reply.length > 280 || unsafe.test(data.reply) || /[<>]/u.test(data.reply)) return false;
    if (data.status !== 'found') return !data.answer && !data.sources;
    if (typeof data.answer !== 'string' || !data.answer || data.answer.length > 1800 || unsafe.test(data.answer) || /[<>]/u.test(data.answer) ||
        !Array.isArray(data.sources) || data.sources.length < 1 || data.sources.length > 3 ||
        !['auto', 'reviewed'].includes(data.review_status) || !['memory', 'wikipedia'].includes(data.origin) || data.tokens !== 0) return false;
    return data.sources.every((source) => {
      if (!source || typeof source.title !== 'string' || !source.title || source.title.length > 200 ||
          unsafe.test(source.title) || /[<>]/u.test(source.title) || typeof source.url !== 'string' || source.url.length > 1000) return false;
      try {
        const url = new URL(source.url);
        return url.protocol === 'https:' && /^[a-z]{2,3}(?:-[a-z0-9]{2,12})?\.wikipedia\.org$/u.test(url.hostname) &&
          !url.username && !url.password && !url.port && !url.search && !url.hash && url.pathname.startsWith('/wiki/');
      } catch (_) { return false; }
    });
  }
  function showKnowledge(data) {
    if (!knowledgeAnswer) return;
    knowledgeAnswer.replaceChildren(); knowledgeAnswer.hidden = !data || data.status !== 'found';
    if (knowledgeAnswer.hidden) return;
    const title = document.createElement('strong'), answer = document.createElement('p'), note = document.createElement('p');
    title.textContent = data.origin === 'memory' ? 'De tu memoria' : 'Referencia pública';
    answer.textContent = data.answer;
    note.className = 'field-help';
    note.textContent = (data.review_status === 'reviewed' ? 'Revisado manualmente.' : 'Incorporado automáticamente; puedes revisarlo después.') + ' 0 tokens de IA. Extracto de Wikipedia; puede estar abreviado.';
    knowledgeAnswer.append(title, answer);
    for (const source of data.sources) {
      const link = document.createElement('a');
      link.className = 'text-link'; link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      link.textContent = source.title + ' · Wikipedia'; knowledgeAnswer.append(link);
    }
    knowledgeAnswer.append(note);
  }
  async function showCreatedEvents(run, creation, ticket) {
    if (!valid(run) || run.guideTicket !== ticket || creation.status !== 'created') return;
    const receipt = creation.draft_id + ':' + creation.event_url;
    if (shownCreations.has(receipt)) return;
    shownCreations.add(receipt);
    if (shownCreations.size > 40) shownCreations.delete(shownCreations.values().next().value);
    let destination;
    try { destination = await window.SparkXGicaNavigation?.openEvents(); }
    catch (_) { destination = null; }
    if (!valid(run) || run.guideTicket !== ticket) return;
    if (destination?.success) {
      // Reveal the list while keeping the foreground voice indicator and Stop.
      const details = root.querySelector('#romeo-presence-details');
      if (details) details.hidden = true;
      root.querySelector('[data-romeo-presence-toggle]')?.setAttribute('aria-expanded', 'false');
      document.dispatchEvent(new CustomEvent('sparkx:romeo-action-layout'));
    } else {
      status.textContent = 'Tu evento quedó creado. No pude abrir la lista; pulsa Eventos o Abrir evento creado. No necesitas crearlo otra vez.';
      if (guideStatus) guideStatus.textContent = status.textContent;
    }
  }
  async function submitGuide(run, text, captured = null, creationControl = null) {
    if (!valid(run) || !run.guided || run.guideInFlight || run.holding || run.early) return;
    text = turnText(text);
    if (text.length > turnLimit) { reviewLongTurn(run, text); return; }
    const turn = captured || captureTurn(run, text);
    clearTurn(run); run.readyOrder = null;
    if (!text.trim() || text.length > 300 || unsafe.test(text)) { stop('La frase no es válida. Revisa el texto sin ejecutar.'); return; }
    const csrf = root.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (!csrf) { stop('No se pudo comprobar la sesión. Recarga antes de conversar.'); return; }
    // A human control can interrupt a spoken question. Its old completion must
    // not restart capture while the next draft mutation is being checked.
    run.responseTicket += 1; run.responsePending = false;
    if (speechOwner === run) { speechOwner = null; outputSpeaking = false; speech.cancel(); }
    detach(run); clearTimeout(run.retryTimer); run.retryTimer = null;
    let frozen = field.value;
    const ticket = ++run.guideTicket, controller = new AbortController();
    const current = () => valid(run) && run.guideTicket === ticket && field.value === frozen;
    run.guideController = controller; run.guideInFlight = true;
    run.guideTimeout = setTimeout(() => controller.abort(), 10000);
    mark('guiding', 'Micrófono en pausa. Preparando una respuesta con reglas locales, sin IA remota.');
    guideStatus.textContent = 'Consultando la guía local…';
    showKnowledge(null);
    try {
      // The event interview owns its answer slot. Never normalize or interpret
      // a title/description/person/resource as a navigation command or web query.
      if (window.SparkXGicaCreation) {
        const acceptsOffer = run.creationOffer && !window.SparkXGicaCreation.hasDraft() &&
          /^(?:si|claro|de acuerdo|vamos|listo|estoy listo)(?: (?:si|claro|de acuerdo|vamos|listo|estoy listo|por favor|gracias))*$/u.test(normalize(text));
        run.creationOffer = false;
        const creation = await window.SparkXGicaCreation.request(acceptsOffer ? 'Quiero crear un evento' : text, {
          context: run.followUp || '', operation: creationControl?.operation || 'turn',
          field: creationControl?.field || '', signal: controller.signal, current
        });
        if (!current()) return;
        if (creation?.handled || creationControl) {
          const created = creation?.status === 'created';
          const reply = created ? 'Tu evento está creado. Ahora te muestro tus eventos.' : creation?.handled ? creation.reply : 'Todavía no tienes un borrador activo. Di «quiero crear un evento» cuando quieras comenzar.';
          turn.normalized_text = text.normalize('NFC'); turn.normalizedKnown = true;
          turn.responseAt = performance.now(); turn.draft = '';
          run.followUp = ''; guideContext = ''; run.readyIntent = ''; run.draft = ''; run.readyOrder = null;
          lastPattern = null; write('');
          rememberExchange(turn.normalized_text, reply);
          run.guideInFlight = false; clearTimeout(run.guideTimeout); run.guideController = null;
          const answered = await respond(run, reply, 'dictating', !created, turn, !created);
          interactionFinished(run, turn, reply, 'request', 'info');
          if (created && answered) await showCreatedEvents(run, creation, ticket);
          return;
        }
      }
      await loadLanguage();
      if (!current()) return;
      turn.normalized_text = run.followUp === 'person_name' ? text.normalize('NFC') : language(text);
      if (field.value !== turn.normalized_text) { write(turn.normalized_text); frozen = field.value; }
      turn.normalizedKnown = true; turn.dispatchAt = performance.now();
      const response = await fetch('/assistant/guide/', {
        method: 'POST', credentials: 'same-origin', redirect: 'error', cache: 'no-store', signal: controller.signal,
        headers: { 'X-CSRFToken': csrf, Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body: new URLSearchParams({ text: turn.normalized_text, context: run.followUp || '' })
      });
      if (!current()) return;
      if (!response.ok || !(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Guide unavailable');
      const raw = await response.text();
      if (!current()) return;
      if (raw.length > 4096) throw new Error('Guide invalid');
      let data = JSON.parse(raw);
      if (!validateGuide(data)) throw new Error('Guide invalid');
      let knowledge = null;
      if (data.status === 'clarify' && !run.followUp && !data.follow_up && publicKnowledge) {
        mark('guiding', 'Micrófono en pausa. Revisando memoria y referencias públicas; sin modelos de IA.');
        guideStatus.textContent = 'Revisando memoria y referencias públicas…';
        const referenceResponse = await fetch('/assistant/knowledge/query/', {
          method: 'POST', credentials: 'same-origin', redirect: 'error', cache: 'no-store', signal: controller.signal,
          headers: { 'X-CSRFToken': csrf, Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
          body: new URLSearchParams({ text: turn.original_text, context: '', request_id: crypto.randomUUID(), allow_network: publicKnowledge.checked ? 'on' : 'off' })
        });
        if (!current()) return;
        if (![200, 400].includes(referenceResponse.status) || !(referenceResponse.headers.get('content-type') || '').includes('application/json')) throw new Error('Reference unavailable');
        const referenceRaw = await referenceResponse.text();
        if (!current()) return;
        if (referenceRaw.length > 12288) throw new Error('Reference invalid');
        knowledge = JSON.parse(referenceRaw);
        if (!validKnowledge(knowledge)) throw new Error('Reference invalid');
        if (knowledge.handled) data = { status: 'info', reply: knowledge.reply, draft: '', intent: '', follow_up: '' };
        if (!validateGuide(data)) throw new Error('Reference reply invalid');
      }
      turn.responseAt = performance.now();
      const serverMs = Number(response.headers.get('X-Gica-Guide-Ms'));
      if (response.headers.has('X-Gica-Guide-Ms') && Number.isFinite(serverMs) && serverMs >= 0 && serverMs <= 60000) turn.serverMs = serverMs;
      const wasFollowUp = !!run.followUp;
      run.followUp = data.follow_up; guideContext = data.follow_up; run.readyIntent = data.intent; run.draft = data.draft;
      if (data.status === 'ready') {
        write(data.draft); lastPattern = { phrase: wasFollowUp ? data.draft : turn.normalized_text, intent: data.intent };
        if (!run.textOnly) run.readyOrder = Object.freeze({ draft: data.draft, intent: data.intent, guideTicket: ticket, mode: 'guided-direct' });
      } else { write(''); lastPattern = null; }
      const greeting = data.status === 'ready' ? actionGreetings.find((phrase) => data.reply === phrase + ' Identifiqué la orden.') || '' : '';
      const reply = data.status === 'ready' ? (greeting ? greeting + ' ' : '') +
        (run.textOnly ? 'La orden está preparada. Revísala y pulsa Ejecutar orden.' : 'Ejecutando tu orden.') : data.reply;
      rememberExchange(turn.normalized_text, reply); run.guideInFlight = false;
      showKnowledge(knowledge);
      clearTimeout(run.guideTimeout); run.guideController = null;
      turn.draft = data.draft;
      if (run.readyOrder) {
        const order = run.readyOrder;
        run.actionOrigin = turn; run.actionLogs.clear(); guideStatus.textContent = reply;
        interactionFinished(run, turn, reply, 'request', data.status, data.intent);
        if (greeting && !await respond(run, greeting, 'dictating', false, turn)) return;
        if (!valid(run) || !readyOrderCurrent(run, order)) return;
        await executeCaptured(run, order);
      } else {
        await respond(run, reply, 'dictating', true, turn);
        interactionFinished(run, turn, reply, 'request', data.status, data.intent);
      }
    } catch (_) {
      if (valid(run) && run.guideTicket === ticket) {
        const reply = 'La guía local no respondió de forma válida. No se ejecutó ninguna orden. Revisa la sesión antes de volver a intentarlo.';
        turn.responseAt = performance.now();
        interactionFinished(run, turn, reply, 'request', 'failed', '', '', 'failed');
        stop(reply);
      }
    } finally {
      if (run.guideTicket === ticket) {
        clearTimeout(run.guideTimeout); run.guideInFlight = false; run.guideController = null;
        if (valid(run) && !run.textOnly && !run.service && !run.retryTimer && !run.responsePending && !run.awaitingAction && !navigation && !run.guideTimer) {
          diagnostic(run, 'capture-restored'); schedule(run, run.holding ? 'holding' : 'dictating');
        }
        render();
      }
    }
  }
  function queueGuide(run, text) {
    if (run.guideInFlight) return;
    const next = turnText(run.guideBuffer + (run.guideBuffer ? ' ' : '') + text);
    if (!hasTurnText(next)) return;
    if (directoryQuestionEcho(run, next)) {
      clearTurn(run); write('');
      mark('dictating', 'Sigo escuchando tu respuesta. También puedes elegir una opción en pantalla.');
      diagnostic(run, 'directory-echo-ignored');
      return;
    }
    if (unsafe.test(next)) { stop('El texto no es válido. Revísalo antes de ejecutar.'); return; }
    if (next.length > turnLimit) { reviewLongTurn(run, next); return; }
    run.guideBuffer = next;
    run.readyOrder = null; run.draft = ''; run.readyIntent = ''; lastPattern = null;
    write(run.followUp === 'person_name' ? next : language ? language(next) : next, next);
    mark(run.early ? 'early-listening' : 'dictating', run.early ? 'Puedes responder mientras Gica termina. Nada se enviará hasta terminar la lectura y esperar 1,5 segundos de texto estable.' : directoryTurn() ?
      'Tu turno · te escucho. Esperaré 2,5 segundos sin cambios para leer tu respuesta completa.' :
      'Tu turno · te escucho. Tras 1,5 segundos sin cambios en el texto ejecutaré una orden clara; si falta información, te preguntaré.');
    turnActivity(run, 'final');
  }
  function readyOrderCurrent(run, order) {
    return !!order && run.readyOrder === order && order.mode === 'guided-direct' && order.guideTicket === run.guideTicket &&
      order.draft === run.draft && field.value === order.draft && order.intent === run.readyIntent && intents.includes(order.intent);
  }
  function finishGuidedTurn(run) {
    if (!valid(run) || !run.guideBuffer || run.guideInFlight || run.holding || run.early || run.responsePending) return;
    const text = run.guideBuffer, turn = captureTurn(run, run.guideBuffer);
    clearTurn(run);
    submitGuide(run, text, turn);
  }
  async function loadLanguage() {
    if (!language) {
      const module = await import('/static/js/gica-language.js?v=20261115-fluency1');
      if (typeof module.normalizeAgentReference !== 'function') throw new Error('Language unavailable');
      language = module.normalizeAgentReference;
    }
  }
  async function loadConfig() {
    if (config) return config;
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 4000);
    try {
      const response = await fetch('/static/data/romeo-voice.es.json?v=20261115-gica1', {
        credentials: 'same-origin', redirect: 'error', cache: 'no-store', signal: controller.signal
      });
      if (!response.ok) throw new Error('Vocabulario no disponible.');
      const raw = await response.text();
      if (raw.length > 4096) throw new Error('Vocabulario inválido.');
      const data = JSON.parse(raw);
      if (!data || Object.keys(data).sort().join(',') !== 'phrases,session_seconds,version' ||
          data.version !== 'es-2026-11-15.1' || !Number.isInteger(data.session_seconds) ||
          data.session_seconds < 30 || data.session_seconds > 300 || !data.phrases ||
          Object.keys(data.phrases).sort().join(',') !== 'cancel,execute,stop,wake') throw new Error('Vocabulario inválido.');
      const all = new Set();
      for (const values of Object.values(data.phrases)) {
        if (!Array.isArray(values) || !values.length || values.length > 3) throw new Error('Vocabulario inválido.');
        for (const value of values) {
          if (typeof value !== 'string' || value.length > 60 || !/^gica [a-z ]+$/.test(value) ||
              value !== normalize(value) || all.has(value)) throw new Error('Vocabulario inválido.');
          all.add(value);
        }
      }
      config = data; return data;
    } finally { clearTimeout(timeout); }
  }
  async function executeCaptured(run, order = null) {
    if (!valid(run) || !run.draft || field.value !== run.draft || (run.guided && (run.textOnly || !readyOrderCurrent(run, order) || run.guideBuffer || run.guideInFlight))) {
      status.textContent = 'No hay una orden dictada lista. Di «Gica hablemos» y después dicta la orden.'; return;
    }
    const draft = run.draft;
    // Any explicit guided greeting has finished with capture paused. Plain
    // commands dispatch now without a spoken preamble or a confirmation turn.
    if (!run.guided && !await respond(run, 'Voy a revisar tu orden.', 'waiting', false)) return;
    if (!valid(run) || run.draft !== draft || field.value !== draft || (run.guided && !readyOrderCurrent(run, order))) { stop('Cambió el borrador. No se envió ninguna orden.'); return; }
    run.readyOrder = null; run.draft = ''; run.readyIntent = ''; run.awaitingAction = true;
    if (run.guided) openPanel();
    mark('acting', 'Micrófono en pausa mientras se interpreta y comprueba tu orden.');
    run.actionTimer = setTimeout(() => {
      if (valid(run) && run.awaitingAction) stop('No llegó la confirmación de la orden. Micrófono apagado; revisa el resultado sin repetir el clic.');
    }, 30000);
    if (!controls.executeDraft(draft)) {
      run.awaitingAction = false; clearTimeout(run.actionTimer);
      respond(run, 'No pude enviar esa orden. Revisa el texto antes de intentarlo otra vez.');
    }
  }
  function controlReply(run, turn, reply, nextPhase, statusValue, outcome = 'none') {
    return respond(run, reply, nextPhase, true, turn).then(() => interactionFinished(run, turn, reply, 'system', statusValue, '', '', outcome));
  }
  function turnControl(text) {
    const value = normalize(text);
    const name = '(?:gica|jica|yica|yika|llica|ilica|chica)(?: uno| 1|-1)?';
    const action = '(espera|esperame|espera un momento|pausa|corrige|continua|reanuda)';
    const prefix = new RegExp(`^${name} ${action}$`, 'u').exec(value);
    const suffix = /[,;]/u.test(text) ? new RegExp(`^${action} ${name}$`, 'u').exec(value) : null;
    const verb = prefix?.[1] || suffix?.[1];
    return verb ? ['corrige'].includes(verb) ? 'correct' : ['continua', 'reanuda'].includes(verb) ? 'continue' : 'hold' : '';
  }
  function stopControl(text) {
    const value = normalize(language ? language(text) : text);
    const name = '(?:gica|jica|yica|yika|llica|ilica|chica)(?: uno| 1|-1)?';
    const action = '(?:silencio|deja de escuchar)';
    return new RegExp(`^${name} ${action}$`, 'u').test(value) ||
      (/[,;]/u.test(text) && new RegExp(`^${action} ${name}$`, 'u').test(value)) || legacyControls.stop.includes(value);
  }
  function applyTurnControl(run, kind) {
    if (!run.guided) return false;
    if (run.reviewBlocked && kind !== 'correct') {
      mark('holding', 'El texto sigue pendiente de revisión. Pulsa Volver a dictar o di «Gica corrige» para resumirlo; no se enviará automáticamente.');
      return true;
    }
    if (kind === 'hold') {
      if (!run.holding) {
        const buffer = run.guideBuffer, visible = buffer || run.textSnapshot || field.value;
        clearTurn(run); run.guideBuffer = buffer; run.textSnapshot = visible; run.textChangedAt = performance.now();
        run.holding = true; run.readyOrder = null; run.readyIntent = ''; run.draft = ''; lastPattern = null;
        write(visible);
      }
      mark('holding', 'En espera. Conservo tu texto sin enviarlo. Sólo escucharé «Gica corrige», «Gica continúa» o «Gica silencio».');
      if (guideStatus) guideStatus.textContent = status.textContent;
      return true;
    }
    if (!run.holding) {
      status.textContent = 'Para corregir o continuar una respuesta en espera, di primero «Gica espera».'; render(); return true;
    }
    run.holding = false;
    if (kind === 'correct') {
      run.reviewBlocked = false;
      clearTurn(run); write('');
      const reply = 'De acuerdo. Limpié esta respuesta sin cambiar tu ficha. Vuelve a dictarla cuando termine de hablar.';
      if (run.early) {
        run.early = null; run.responseTicket += 1; run.responsePending = false;
        if (speechOwner === run) { speechOwner = null; outputSpeaking = false; speech.cancel(); }
      }
      respond(run, reply, 'dictating');
    } else {
      mark(run.early ? 'early-listening' : 'dictating', `Tu turno · te escucho. Continuamos con el texto conservado; esperaré ${idleSeconds()} segundos antes de enviarlo.`);
      run.textChangedAt = performance.now();
      if (run.guideBuffer && !run.early) turnActivity(run, 'final');
    }
    return true;
  }
  function handle(run, text) {
    const normalized = normalize(language ? language(text) : text);
    // Only a complete control phrase may canonicalize a clear spoken name.
    // GICA/Jica/Yica and exact Gica uno/Gica 1/Gica-1 share the same controls.
    const suffixControl = text.match(/^(hablemos|ejecuta|cancela|silencio|deja de escuchar)\s*[,;]\s*(?:gica|jica|yica|yika|llica|ilica)(?:-1| (?:uno|1))?[.!¡?¿]*$/iu);
    const canonical = suffixControl ? `gica ${normalize(suffixControl[1])}` : normalized.replace(/^(?:gica|jica|yica|yika|llica|ilica)(?: (?:uno|1)|-1)? (?=(?:hablemos|ejecuta|cancela|silencio|deja de escuchar)$)/u, 'gica ');
    const phrase = Object.entries(config.phrases).find(([kind, values]) =>
      values.includes(canonical) || legacyControls[kind].includes(normalized))?.[0];
    if (phrase === 'stop' || stopControl(text)) {
      const reply = 'Micrófono apagado por tu orden.';
      if (run.guided) interactionFinished(run, captureTurn(run, text), reply, 'system', 'stopped', '', '', 'stopped');
      stop(reply, 'voice-stop'); return;
    }
    const localControl = turnControl(text);
    if (localControl && applyTurnControl(run, localControl)) return;
    if (run.guided && run.holding) {
      mark('holding', 'En espera. El texto se conserva; di «Gica corrige», «Gica continúa» o «Gica silencio».'); return;
    }
    if (phrase === 'cancel') {
      if (run.guided) {
        const turn = captureTurn(run, text);
        if (window.SparkXGicaCreation?.hasDraft()) {
          submitGuide(run, text, turn, { operation: 'cancel', field: '' }); return;
        }
        clearGuide(run); run.draft = ''; run.readyIntent = ''; run.followUp = ''; guideContext = ''; lastPattern = null;
        write(''); controlReply(run, turn, 'Borrador cancelado. Dime otra petición cuando vuelva a escuchar.', 'dictating', 'cancelled', 'cancelled'); return;
      }
      if (run.draft && field.value === run.draft) write(run.previousValue);
      run.draft = ''; run.capture = false; respond(run, 'Dictado cancelado. Sigo disponible.'); return;
    }
    if (phrase === 'wake') {
      if (run.guided) {
        const turn = captureTurn(run, text);
        clearGuide(run); run.readyIntent = ''; run.draft = ''; lastPattern = null;
        controlReply(run, turn, 'Te escucho. Dime qué quieres consultar o preparar.', 'dictating', 'info'); return;
      }
      openPanel(); run.capture = true; run.draft = ''; run.previousValue = field.value;
      respond(run, 'Adelante. Dime tu orden.', 'dictating'); return;
    }
    if (phrase === 'execute') {
      if (run.guided) {
        const turn = captureTurn(run, text);
        clearTurn(run);
        controlReply(run, turn, 'Dime una orden clara, como abre eventos. Tras 1,5 segundos de texto estable la ejecutaré.', 'dictating', 'clarify'); return;
      }
      if (run.phase === 'dictating') executeCaptured(run);
      else status.textContent = 'Di «Gica hablemos» y dicta una orden antes de ejecutarla.';
      return;
    }
    if (/\b(?:gica|jica|yica|yika|llica|ilica|romeo|rome)(?: (?:uno|1)|-1)?\s+(?:hablemos|ejecuta|cancela|silencio|deja de escuchar)\b/u.test(normalized)) {
      if (run.guided) {
        const turn = captureTurn(run, text);
        clearGuide(run); run.draft = ''; run.readyIntent = ''; lastPattern = null;
        controlReply(run, turn, 'Di los controles por separado, sin citas ni negaciones. Esa frase no preparó ni ejecutó una orden.', 'dictating', 'refused'); return;
      }
      status.textContent = 'Di cada comando por separado. No se ejecutó ni añadió esa frase al borrador.'; return;
    }
    if (run.guided) { queueGuide(run, text); return; }
    if (run.phase !== 'dictating') { status.textContent = 'Sigo disponible. Di «Gica hablemos» para dictar.'; return; }
    const draft = run.draft + (run.draft ? ' ' : '') + text.trim();
    if (!draft.trim() || draft.length > 300 || unsafe.test(draft)) {
      stop('Dictado demasiado largo o con caracteres no admitidos. No se envió; revisa el texto.'); return;
    }
    run.draft = draft; write(draft);
    mark('dictating', 'Borrador visible. Di «Gica ejecuta» en otra frase para enviarlo, o «Gica cancela».');
  }
  function rejectEarlyListening(run) {
    run.earlyDisabled = true; run.early = null;
    const visible = field.value, held = run.holding ? run.guideBuffer : '';
    clearTurn(run); detach(run); write(visible);
    if (run.holding) { run.guideBuffer = held; run.textSnapshot = visible; run.textChangedAt = performance.now(); }
    speechStatus.textContent = 'Este navegador no permitió la escucha anticipada. Esperaré a que Gica termine; después podrás responder.';
    mark('speaking', 'La escucha anticipada no está disponible. Micrófono en pausa hasta que termine la pregunta.');
  }
  function questionEcho(text, question) {
    const value = normalize(text);
    if (!value || /^(?:si|no|\d+(?: \d+)*)$/u.test(value)) return false;
    if (` ${question} `.includes(` ${value} `)) return true;
    return question.split(' ').length >= 3 && value.includes(question);
  }
  function startRecognizer(run, targetPhase, early = false) {
    if (!valid(run)) return;
    if (run.textOnly) return;
    if (navigation || run.awaitingAction || (run.responsePending && !early)) { mark('paused', 'Micrófono en pausa mientras termina la navegación o la respuesta.'); return; }
    const now = performance.now();
    run.startTimes = run.startTimes.filter((time) => now - time < 300000);
    if (run.service) return;
    const startLimit = run.guided && window.SparkXGicaCreation?.hasDraft() ? 40 : 20;
    if (run.guided && run.startTimes.length >= startLimit) {
      const delay = Math.max(600, run.startTimes[0] + 300000 - now + 50);
      mark(run.holding ? 'holding' : 'paused', 'El navegador necesita una pausa. La conversación sigue abierta y el micrófono se reanudará automáticamente; puedes continuar por texto o apagarlo.');
      diagnostic(run, 'start-budget-wait', 'start-budget');
      schedule(run, targetPhase, delay); return;
    }
    if (!run.guided && run.starts >= 20) {
      stop('Se alcanzó el límite de 20 inicios de micrófono de esta sesión. Puedes activar otra si la necesitas.', 'start-budget'); return;
    }
    if (!controls.canStartVoice() || (window.speechSynthesis?.speaking && !early)) {
      if (early) { rejectEarlyListening(run); return; }
      stop('La escucha no puede continuar. Termina la lectura o acción y activa otra sesión si la necesitas.'); return;
    }
    // The persistent foreground indicator and Stop remain visible when collapsed.
    if (!run.capture || (!run.guided && root.querySelector('#romeo-presence-details')?.hidden)) targetPhase = 'waiting';
    else if (run.guided) targetPhase = run.holding ? 'holding' : early ? 'early-listening' : 'dictating';
    let service;
    try { service = new Recognition(); } catch (_) { if (early) rejectEarlyListening(run); else stop('No se pudo preparar el micrófono. Puedes escribir.'); return; }
    run.service = service; run.starts += 1; run.startTimes.push(now);
    let startedAt = null, audioStartedAt = null;
    const ticket = ++run.ticket, seen = new Set();
    const owns = () => valid(run) && run.service === service && run.ticket === ticket;
    const capturePhase = () => run.holding ? 'holding' : run.early ? 'early-listening' : targetPhase === 'early-listening' ? 'dictating' : targetPhase;
    service.lang = 'es-PE'; service.continuous = true; service.interimResults = run.guided; service.maxAlternatives = 1;
    listening(true); mark('starting', 'Iniciando micrófono; el navegador puede solicitar permiso.');
    service.onstart = () => {
      if (!owns()) return;
      startedAt = performance.now();
      diagnostic(run, 'native-start');
      mark(capturePhase(), 'Servicio iniciado. Esperando señal de audio del navegador…');
    };
    service.onaudiostart = () => {
      if (!owns()) return;
      run.audio = true;
      audioStartedAt = performance.now();
      diagnostic(run, 'native-audio');
      mark(capturePhase(), run.holding ? 'En espera. Sólo escucharé «Gica corrige», «Gica continúa» o «Gica silencio».' : run.early ? 'Escucha anticipada activa. Puedes responder; esperaré a que termine Gica y a 1,5 segundos de texto estable.' : targetPhase === 'dictating' ? `Tu turno · te escucho. Esperaré ${idleSeconds()} segundos sin cambios en el texto.` : 'Micrófono capturando audio. Di «Gica hablemos» o «Gica silencio».');
    };
    service.onspeechstart = () => { if (owns()) { run.audio = true; run.detected = true; run.speechActive = true; turnActivity(run, 'speech_start'); mark(capturePhase(), run.holding ? 'En espera. Esperando un control de continuación o corrección.' : 'El navegador detectó voz. Esperando la transcripción…'); } };
    service.onspeechend = () => { if (owns()) { run.detected = false; run.speechActive = false; turnActivity(run, 'speech_end'); render(); } };
    service.onaudioend = () => { if (owns()) { run.audio = false; run.detected = false; run.speechActive = false; turnActivity(run, 'audio_end'); render(); } };
    service.onresult = (event) => {
      if (!owns() || !['waiting', 'dictating', 'holding', 'early-listening'].includes(run.phase)) return;
      if (run.phase === 'dictating' && (!run.capture || (!run.guided && root.querySelector('#romeo-presence-details')?.hidden))) {
        run.draft = ''; run.capture = false; detach(run); schedule(run, 'waiting'); return;
      }
      if (window.speechSynthesis?.speaking && !run.early) { stop('La lectura tomó el audio. Micrófono apagado para evitar eco.'); return; }
      const finals = [];
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        if (event.results[i].isFinal && seen.has(i)) continue;
        const text = event.results[i][0]?.transcript;
        if (typeof text === 'string' && !hasTurnText(turnText(text))) {
          // Empty/noise-only results neither start nor postpone the turn. A
          // retracted nonempty provisional remains unresolved, never final.
          if (event.results[i].isFinal && !run.unfinalized.has(`${ticket}:${i}`)) seen.add(i);
          continue;
        }
        if (typeof text !== 'string' || text.length > reviewLimit || unsafe.test(text)) { stop('Transcripción inválida. No se envió ninguna orden.'); return; }
        const isControl = run.guided && (!!turnControl(text) || stopControl(text));
        if ((run.holding && !isControl) || (!isControl &&
            ((run.early && questionEcho(text, run.early.question)) || directoryQuestionEcho(run, text)))) {
          run.unfinalized.delete(`${ticket}:${i}`); run.recognizedParts.delete(`${ticket}:${i}`);
          if (event.results[i].isFinal) seen.add(i);
          continue;
        }
        if (isControl && event.results[i].isFinal) {
          // Native Web Speech may deliver a completed answer and a separate
          // control in the same result event. Keep the answer as data before
          // applying its standalone wait/stop control, never join both texts.
          if (finals.length) {
            queueGuide(run, finals.join(' ')); finals.length = 0;
            if (!owns()) { if (stopControl(text)) handle(run, text); return; }
          }
          run.unfinalized.delete(`${ticket}:${i}`); seen.add(i); handle(run, text);
          if (!owns()) return;
          continue;
        }
        if (run.guided && !isControl && !observeTranscript(run, ticket, i, text)) return;
        if (!event.results[i].isFinal) {
          if (run.guided) { run.unfinalized.add(`${ticket}:${i}`); turnActivity(run, 'interim'); }
          continue;
        }
        if (run.guided) run.unfinalized.delete(`${ticket}:${i}`);
        seen.add(i);
        finals.push(text);
      }
      if (run.guided && finals.some((text) => text.trim())) run.restarts = 0;
      if (run.guided && finals.length > 1) {
        const turn = finals.join(' ');
        if (turnText(turn).length > turnLimit) { reviewLongTurn(run, turn); return; }
        run.audio = true; render(); handle(run, turn); return;
      }
      if (finals.length > 1) { status.textContent = 'Recibí varias frases juntas. Repítelas en turnos separados; no se envió ninguna orden.'; return; }
      if (finals.length === 1) { run.audio = true; render(); handle(run, finals[0]); }
    };
    const finishNative = (code = '') => {
      if (!owns()) return;
      diagnostic(run, code ? 'native-error' : 'native-end', code);
      if (code) root.dataset.voiceLastError = code;
      const fatal = {
        'not-allowed': 'El navegador denegó el permiso del micrófono (not-allowed). Revisa el permiso y pulsa Reanudar cuando quieras.',
        'service-not-allowed': 'El navegador bloqueó el servicio de voz (service-not-allowed). Revisa sus permisos; no se reintentará automáticamente.',
        'audio-capture': 'No se pudo capturar el micrófono (audio-capture). Revisa el dispositivo y vuelve a activarlo cuando esté disponible.',
        'language-not-supported': 'El reconocimiento no admite este idioma (language-not-supported). Puedes continuar por texto.',
        'bad-grammar': 'El servicio rechazó la configuración de voz (bad-grammar). Puedes continuar por texto.',
        unknown: 'El navegador interrumpió la voz sin un código reconocido (unknown). Puedes reanudarla o continuar por texto.'
      };
      if (fatal[code]) { stop(fatal[code], code); return; }
      const elapsed = startedAt === null ? 0 : performance.now() - startedAt;
      const healthy = (!code && audioStartedAt !== null) || (code === 'no-speech' && (audioStartedAt !== null || elapsed >= 1000));
      const incomplete = run.guided && run.unfinalized.size > 0;
      detach(run); // Error and subsequent native end now share one recovery.
      if (incomplete) {
        const visible = field.value, held = run.holding ? run.guideBuffer : '';
        clearTurn(run); run.readyOrder = null; run.draft = ''; run.readyIntent = ''; lastPattern = null;
        write(visible);
        if (run.holding) { run.guideBuffer = held; run.textSnapshot = visible; run.textChangedAt = performance.now(); }
        if (guideStatus) guideStatus.textContent = 'El dictado quedó incompleto. Conservé el texto para revisión sin enviarlo; repítelo cuando vuelva a escuchar.';
      }
      if (early && run.responsePending) {
        // Normal early completion is not a failed answer. Retain final text,
        // Wait for TTS, then re-arm capture and the 1.5-second idle gate.
        if (code) run.earlyDisabled = true;
        mark(run.holding ? 'holding' : 'speaking', code ?
          `La captura anticipada terminó (${code}). Esperaré al final de la pregunta antes de reanudar el micrófono.` :
          'La captura anticipada terminó. Conservo la respuesta final y esperaré a que Gica termine.');
        return;
      }
      if (healthy) run.restarts = 0;
      else {
        run.restarts += 1;
        if (run.restarts > 2) {
          stop(`El micrófono tuvo tres fallos rápidos consecutivos${code ? ` (${code})` : ''}. Detuve los reintentos; revisa el navegador y pulsa Reanudar.`, 'rapid-start-failures'); return;
        }
      }
      const message = run.holding ? 'En espera. Conservo tu texto; reanudando la escucha de controles.' : healthy ?
        code === 'no-speech' ? 'No se detectó voz (no-speech). Reanudando el micrófono; tu ficha sigue guardada.' :
          'El navegador terminó una captura normal. Reanudando el micrófono; tu ficha sigue guardada.' :
        `La captura se interrumpió${code ? ` (${code})` : ' antes de recibir audio'}. Reconexión ${run.restarts} de 2.`;
      mark(run.holding ? 'holding' : 'reconnecting', message);
      if (run.guided && run.guideBuffer && !run.holding) turnActivity(run, 'final');
      diagnostic(run, 'retry', code);
      schedule(run, run.holding ? 'holding' : targetPhase, healthy ? code === 'no-speech' ? 1000 : 600 : 500 * run.restarts);
    };
    service.onerror = (event) => finishNative(nativeCodes.has(event?.error) ? event.error : 'unknown');
    service.onend = () => finishNative();
    try { service.start(); } catch (_) { if (early) rejectEarlyListening(run); else stop('No se pudo iniciar el micrófono. Puedes escribir.'); }
  }
  async function start() {
    if (root.dataset.gicaDemoActive === 'true') { status.textContent = 'Gica está guiando el piloto. Pulsa Detener piloto para conversar.'; return; }
    if (labOpen) { status.textContent = 'Cierra el laboratorio de voces antes de activar el micrófono.'; return; }
    if (session) { stop(); return; }
    voice.stopDictation();
    if (!Recognition || navigation || !controls.canStartVoice() || window.speechSynthesis?.speaking || speechOwner) {
      status.textContent = 'Termina la acción o la lectura antes de activar la voz. También puedes escribir.'; return;
    }
    if (guided?.checked && !guidedUI) { status.textContent = 'La guía local no está disponible en esta página.'; return; }
    if (guidedUI && guided.checked) guideContext = '';
    const run = newRun(!!(guidedUI && guided.checked));
    session = run; mark('consent', 'Preparando la sesión de voz. Todavía no se escucha.');
    try {
      await loadConfig();
      if (run.guided) await loadLanguage();
      if (!valid(run)) return;
      if (!await voice.requestConsent(run.guided ? 'guided-session' : 'command-session', button)) { if (session === run) stop('Voz no activada. Puedes escribir o usar Hablar.'); return; }
      if (!valid(run)) return;
      run.logAccepted = run.guided;
      if (!run.guided) {
        run.expires = Date.now() + config.session_seconds * 1000;
        run.timer = setTimeout(() => { if (session === run) stop('Terminó el tiempo de la sesión. Pulsa Reanudar conversación para iniciar otra.'); }, config.session_seconds * 1000);
      }
      if (run.guided) {
        openPanel(); run.capture = true;
        const name = root.dataset.gicaUserName || '';
        const prefix = name.length >= 1 && name.length <= 60 && !unsafe.test(name) && !/[<>]/u.test(name) ? `Hola, ${name}.` : 'Hola.';
        run.creationOffer = !window.SparkXGicaCreation?.hasDraft();
        const greetingCopy = {
          friendly: [' ¿Estás listo para crear un evento o deseas hacer otra cosa?', ' Tu borrador sigue disponible. Puedes continuar respondiendo o usar Continuar mi borrador.'],
          professional: [' Soy Gica. ¿Deseas crear un evento o realizar otra gestión?', ' Tu borrador está disponible. Puedes continuar respondiendo o usar Continuar mi borrador.'],
          direct: [' ¿Creamos un evento o hacemos otra tarea?', ' Tu borrador está listo para continuar. Responde o usa Continuar mi borrador.']
        };
        const personality = Object.hasOwn(greetingCopy, root.dataset.gicaPersonality) ? root.dataset.gicaPersonality : 'friendly';
        const greeting = prefix + greetingCopy[personality][run.creationOffer ? 0 : 1];
        await respond(run, greeting, 'dictating');
      } else await respond(run, 'Hola. Soy Gica. Di Gica hablemos cuando se active el micrófono.');
    } catch (_) { if (session === run) stop('No se pudo iniciar la conversación. El micrófono está apagado; puedes escribir.'); }
  }
  function newRun(isGuided, textOnly = false) {
    return { generation: ++generation, phase: 'consent', service: null, ticket: 0, starts: 0, restarts: 0, startTimes: [], responseTicket: 0, responsePending: false,
      timer: null, retryTimer: null, actionTimer: null, awaitingAction: false, capture: false, draft: '', previousValue: '',
      expires: Infinity, audio: false, detected: false, guided: isGuided, textOnly, userID: document.body.dataset.voiceUser,
      guideTimer: null, guideTimeout: null, guideTicket: 0, guideController: null, guideInFlight: false,
      guideBuffer: '', followUp: guideContext, readyIntent: '', readyOrder: null,
      turnTimer: null, speechActive: false,
      voiceEndAt: null, voiceStartAt: null, audioEndAt: null, interimAt: null, finalAt: null, resultAt: null,
      recognizedParts: new Map(), textChangedAt: null, textSnapshot: '',
      sessionID: crypto.randomUUID(), sequence: 0, speechMeasure: null, logAccepted: false, creationOffer: false,
      holding: false, reviewBlocked: false, early: null, earlyDisabled: false, directoryEcho: null,
      actionOrigin: null, actionLogs: new Set(), unfinalized: new Set() };
  }
  if (guidedUI) {
    textGuide = document.createElement('button'); textGuide.type = 'button';
    textGuide.className = 'button button-secondary gica-guide-text';
    textGuide.dataset.gicaTextGuide = ''; textGuide.textContent = 'Conversar por texto';
    guided.closest('label')?.after(textGuide);
    textGuide.addEventListener('click', () => {
      if (root.dataset.gicaDemoActive === 'true' || !guided.checked || document.hidden || labOpen || !controls.canStartVoice() || window.speechSynthesis?.speaking) return;
      const text = field.value;
      if (!text.trim()) { guideStatus.textContent = 'Escribe una petición en Tu orden y pulsa Conversar por texto.'; guideStatus.hidden = false; field.focus(); return; }
      stop('Continuando por texto. Micrófono apagado.'); cancelProbe(); voice.stopDictation();
      const run = newRun(true, true); run.expires = Date.now() + 300000; run.capture = true; session = run;
      run.logAccepted = true;
      run.timer = setTimeout(() => { if (session === run) stop('La conversación terminó. Puedes volver a conversar por texto.'); }, 300000);
      submitGuide(run, text);
    });
    guided.addEventListener('change', () => { stop('Cambiaste el modo. Actívalo de nuevo cuando quieras.'); guideContext = ''; render(); });
    reviewPattern.addEventListener('click', () => {
      if (!lastPattern) return;
      const candidate = { ...lastPattern };
      stop('Conversación detenida para revisar la frase.'); cancelProbe(); voice.stopDictation();
      document.dispatchEvent(new CustomEvent('sparkx:gica-pattern-review', { detail: candidate }));
    });
  }
  document.addEventListener('sparkx:gica-creation-control', (event) => {
    const operation = event.detail?.operation, fieldName = event.detail?.field || '';
    if (!['turn', 'resume', 'back', 'cancel', 'review', 'edit', 'confirm'].includes(operation) ||
        (fieldName && !['title', 'organization', 'brief', 'date', 'time', 'timezone', 'capacity', 'is_synthetic', 'objective', 'audience', 'modality', 'duration_minutes', 'location', 'resources', 'constraints'].includes(fieldName)) ||
        root.dataset.gicaDemoActive === 'true' || document.hidden || labOpen || session?.guideInFlight || session?.awaitingAction || !controls.canStartVoice()) return;
    const text = operation === 'turn' ? (window.SparkXGicaCreation?.hasDraft() ? field.value : 'Quiero crear un evento') :
      { resume: 'Continuar mi borrador', back: 'Atrás', cancel: 'Cancelar creación', review: 'Revisar borrador', edit: 'Corregir ' + fieldName, confirm: 'Crear evento' }[operation];
    if (!text.trim()) { guideStatus.textContent = 'Escribe o di tu respuesta para continuar con este paso.'; return; }
    let run = session;
    if (!run || !valid(run)) {
      stop('Continuando la creación por texto.'); cancelProbe(); voice.stopDictation();
      run = newRun(true, true); run.expires = Date.now() + 300000; run.capture = true; run.logAccepted = true; session = run;
      run.timer = setTimeout(() => { if (session === run) stop('Conversación detenida. Tu borrador queda guardado; puedes continuarlo después.'); }, 300000);
    }
    openPanel(); write(text);
    const turn = captureTurn(run, text); turn.source = 'text';
    submitGuide(run, text, turn, { operation, field: fieldName });
  });
  // Suggestions answer only the current server-owned interview slot. The
  // client snapshot never grants a new tool or bypasses final confirmation.
  document.addEventListener('sparkx:gica-companion-answer', (event) => {
    const detail = event.detail;
    if (!guidedUI || !guided.checked || !detail || document.hidden || labOpen || navigation ||
        session?.guideInFlight || session?.awaitingAction || session?.holding || session?.reviewBlocked ||
        !controls.canStartVoice() || (speechOwner && speechOwner !== session) ||
        (window.speechSynthesis?.speaking && (!session || speechOwner !== session))) return;
    const choice = window.SparkXGicaCreation?.validateChoice(detail);
    if (!choice) return;
    const text = choice.mode === 'custom' && detail.source === 'other' && typeof detail.value === 'string'
      ? turnText(detail.value) : choice.mode === 'answer' && detail.source === 'choice' ? choice.value : '';
    if (!hasTurnText(text) || text.length > turnLimit || unsafe.test(text)) return;
    event.preventDefault();
    let run = session;
    if (!run || !valid(run) || !run.guided) {
      stop('Continuando la creación por texto.'); cancelProbe(); voice.stopDictation();
      run = newRun(true, true); run.expires = Date.now() + 300000;
      run.capture = true; run.logAccepted = true; session = run;
      run.timer = setTimeout(() => {
        if (session === run) stop('Conversación detenida. Tu borrador queda guardado; puedes continuarlo después.');
      }, 300000);
    }
    // A deliberate click supersedes a partial dictation or the current spoken
    // question. Invalidate its callbacks before submitting exactly one answer.
    run.early = null; clearTurn(run); detach(run); write(text);
    const turn = captureTurn(run, text); turn.source = 'text';
    submitGuide(run, text, turn, { operation: 'turn', field: '' });
  });
  document.addEventListener('sparkx:gica-companion-open', () => { if (!document.hidden) openPanel(); });
  // An explicit narrated-demo click temporarily owns speech and creation. It
  // cannot borrow a running request or restart the microphone when it ends.
  document.addEventListener('sparkx:gica-demo-prepare', (event) => {
    if (!event.cancelable || event.defaultPrevented || !root.isConnected || document.hidden ||
        root.dataset.gicaDemoActive === 'true' || navigation || session?.guideInFlight || session?.awaitingAction ||
        window.SparkXGicaCreation?.presentation()?.busy || !controls.canStartVoice()) return;
    stop('Piloto guiado. El micrófono permanece apagado.');
    cancelProbe(); lab?.close('Laboratorio cerrado durante el piloto.'); voice.stopDictation();
    root.dataset.gicaDemoActive = 'true'; event.preventDefault();
    status.textContent = 'Piloto guiado. Puedes detenerlo en cualquier momento.';
    render();
  });
  document.addEventListener('sparkx:gica-demo-end', () => {
    if (root.dataset.gicaDemoActive !== 'true') return;
    delete root.dataset.gicaDemoActive;
    status.textContent = 'Recorrido terminado. El micrófono sigue apagado.';
    render();
  });
  document.addEventListener('sparkx:gica-companion-stop', () => {
    if (window.SparkXGicaDemo?.isActive()) window.SparkXGicaDemo.stop();
    else stop('Micrófono apagado por tu clic. Tu ficha sigue guardada.', 'manual');
  });
  document.addEventListener('sparkx:gica-companion-request', render);
  function availability() {
    speechStatus.textContent = speech.available() ? `${voiceDescription()} Pulsa Probar voz para escucharla.` :
      speech.getPreference().voiceID ? `Tu voz elegida (${speech.getPreference().name}) no está disponible. Abre Comparar voces para elegir otra o restablecer automática.` :
      'Buscando voz española local. Si no hay una instalada, Gica responderá por texto.';
  }
  document.addEventListener('sparkx:romeo-speech-availability', availability);
  document.addEventListener('sparkx:romeo-speech-state', (event) => {
    if (!speechOwner) return;
    const measure = speechOwner.speechMeasure;
    if (measure && event.detail?.state === 'speaking' && measure.ttsStartAt === null) measure.ttsStartAt = performance.now();
    if (measure && event.detail?.state === 'ended' && measure.ttsStartAt !== null) measure.ttsEndAt = performance.now();
    outputSpeaking = event.detail?.state === 'speaking';
    if (outputSpeaking && session === speechOwner) mark('speaking', 'Gica habla. Micrófono en pausa para evitar eco.'); else render();
  });
  earlyListening?.addEventListener('change', () => {
    if (earlyListening.checked || !session?.early) return;
    const run = session, visible = field.value, held = run.holding ? run.guideBuffer : '';
    run.early = null; clearTurn(run); detach(run); write(visible);
    if (run.holding) { run.guideBuffer = held; run.textSnapshot = visible; run.textChangedAt = performance.now(); }
    speechStatus.textContent = 'Escucha anticipada desactivada. El texto captado no se envió; responde cuando termine la pregunta.';
    mark('speaking', 'Micrófono en pausa hasta que termine la pregunta.');
  });
  probe.addEventListener('click', async () => {
    if (root.dataset.gicaDemoActive === 'true') return;
    if (labOpen) return;
    if (session) {
      if (session.guided && (session.guideBuffer || session.guideInFlight || session.turnTimer)) { speechStatus.textContent = 'Espera la respuesta de la guía antes de probar la voz.'; return; }
      if (!['waiting', 'dictating', 'reconnecting'].includes(session.phase)) { speechStatus.textContent = 'Espera a que termine la respuesta o la acción.'; return; }
      if (!speakEnabled.checked) { speechStatus.textContent = 'Activa Respuestas habladas para probar la voz.'; return; }
      respond(session, 'Hola. Soy Gica. Esta es mi voz de prueba.', session.phase === 'dictating' ? 'dictating' : 'waiting'); return;
    }
    if (speechOwner) { probeGeneration += 1; speechOwner = null; outputSpeaking = false; speech.cancel(); probe.textContent = 'Probar voz'; render(); return; }
    if (window.speechSynthesis?.speaking) { speechStatus.textContent = 'Termina la lectura actual antes de probar la voz.'; return; }
    voice.stopDictation();
    const owner = {}, id = ++probeGeneration;
    speechOwner = owner; probe.textContent = 'Detener prueba';
    const result = await speech.speak('Hola. Soy Gica. Estoy listo para ayudarte.');
    if (id !== probeGeneration) return;
    if (speechOwner === owner) { speechOwner = null; outputSpeaking = false; }
    probe.textContent = 'Probar voz'; speechResult(result); render();
  });
  speakEnabled.addEventListener('change', () => {
    if (!speakEnabled.checked) { speech.cancel(); outputSpeaking = false; speechStatus.textContent = 'Respuestas habladas desactivadas. El texto sigue disponible.'; render(); }
    else availability();
  });
  function cancelProbe() {
    if (!speechOwner || speechOwner === session) return;
    probeGeneration += 1; speechOwner = null; outputSpeaking = false;
    speech.cancel(); probe.textContent = 'Probar voz'; render();
  }
  function prepareLab() {
    if (root.dataset.gicaDemoActive === 'true' || !controls.canStartVoice() || (window.speechSynthesis?.speaking && !speechOwner)) {
      speechStatus.textContent = 'Termina la acción o lectura actual antes de comparar voces.'; return false;
    }
    stop('Micrófono apagado para comparar voces.'); cancelProbe(); voice.stopDictation();
    labOpen = true; return true;
  }
  async function previewLab(options) {
    if (!labOpen || session || document.hidden || !controls.canStartVoice()) return { spoken: false, reason: 'unavailable' };
    cancelProbe(); voice.stopDictation();
    const owner = {}, id = ++probeGeneration;
    speechOwner = owner;
    let result;
    try { result = await speech.preview(options); }
    catch (_) { result = { spoken: false, reason: 'error' }; }
    if (id !== probeGeneration) return { spoken: false, reason: 'cancelled' };
    if (speechOwner === owner) { speechOwner = null; outputSpeaking = false; }
    render(); return result;
  }
  field.addEventListener('input', () => { if (session && !writing) stop('Editaste la orden. Revisa el texto y pulsa Ejecutar orden.'); });
  button.addEventListener('click', (event) => { if (event.isTrusted) start(); }); topStop.addEventListener('click', () => stop('Micrófono apagado por tu clic. Tu ficha sigue guardada.', 'manual'));
  document.addEventListener('sparkx:gica-open', () => {
    if (root.dataset.gicaOpenConversation !== 'true' || !guidedUI || !guided.checked || session || document.hidden ||
        root.querySelector('#romeo-presence-details')?.hidden || navigator.userActivation?.isActive !== true) return;
    start();
  });
  document.addEventListener('click', (event) => {
    if (!event.isTrusted || !event.target.closest('[data-gica-settings-open]')) return;
    openPanel(); document.dispatchEvent(new CustomEvent('sparkx:gica-open'));
  });
  document.addEventListener('sparkx:dictation-starting', () => { window.SparkXGicaDemo?.stop(); lab?.close('Laboratorio cerrado al iniciar otro dictado.'); stop('Otro dictado tomó el micrófono. Voz rápida apagada.'); cancelProbe(); });
  document.addEventListener('sparkx:dictation-cancel', (event) => {
    if (event.detail?.inputID !== field.id || !session) return;
    if (event.detail.reason === 'panelclose') {
      if (session.guided) return;
      session.draft = ''; session.capture = false;
      if (session.service) {
        // Recreate the recognizer so its callbacks cannot restore dictating mode.
        clearTimeout(session.retryTimer); detach(session); mark('paused', 'Panel cerrado. El borrador requiere una nueva orden de dictado.'); schedule(session, 'waiting');
      }
      return;
    }
    stop();
  });
  document.addEventListener('submit', (event) => {
    if (!event.isTrusted || event.target !== field.closest('[data-romeo-action-form]') || session?.awaitingAction ||
        document.hidden || !memoryEnabled?.checked || !field.value.trim() || field.value.length > 300 || unsafe.test(field.value)) return;
    const owner = { userID: document.body.dataset.voiceUser, logAccepted: true, textOnly: true,
      sessionID: crypto.randomUUID(), sequence: 0, actionLogs: new Set(), voiceEndAt: null, finalAt: null, audioEndAt: null };
    owner.actionOrigin = captureTurn(owner, field.value); owner.actionOrigin.draft = field.value;
    manualAction = owner;
  }, true);
  document.addEventListener('sparkx:romeo-action-state', (event) => {
    if (session?.awaitingAction) actionInteraction(session, event.detail);
    else {
      if (event.detail?.stage === 'interpreting') guideContext = '';
      if (manualAction) actionInteraction(manualAction, event.detail, false, true);
      if (session) stop('Una acción manual tomó el control. Conversación apagada.');
    }
  });
  document.addEventListener('sparkx:romeo-action-settled', (event) => {
    const run = session;
    if (!run?.awaitingAction && manualAction) { actionInteraction(manualAction, event.detail, true, true); manualAction = null; }
    if (!run?.awaitingAction || !valid(run)) return;
    actionInteraction(run, event.detail, true);
    run.awaitingAction = false; clearTimeout(run.actionTimer);
    const stage = event.detail?.stage;
    if (stage === 'unrecorded') { stop('No se confirmó toda la orden. Micrófono apagado; revisa el resultado antes de continuar.'); return; }
    const message = ['completed', 'already', 'arrived'].includes(stage) ? 'Listo. Tu orden quedó comprobada. Sigo disponible.' :
      stage === 'clarify' ? 'Necesito que aclares tu orden. Revisa las opciones en pantalla.' :
      stage === 'cancelled' ? 'Orden detenida. Sigo disponible.' : 'No pude completar esa orden. Revisa el mensaje en pantalla.';
    if (run.guided) { run.capture = true; run.followUp = ''; guideContext = ''; }
    respond(run, message, run.guided ? 'dictating' : 'waiting');
  });
  document.addEventListener('sparkx:gica-navigation-start', (event) => {
    const id = event.detail?.id;
    if (typeof id !== 'string' || !uuid.test(id)) return;
    navigation = { id, userID: document.body.dataset.voiceUser };
    cancelProbe();
    const run = session;
    if (!run) return;
    if (event.detail?.source === 'creation-complete' && event.detail?.path === '/' && run.guided && !run.guideInFlight && !run.responsePending) {
      clearTimeout(run.retryTimer); detach(run);
      mark('paused', 'Evento creado. Mostrando tus eventos; micrófono en pausa mientras cambia la página.'); return;
    }
    if (event.detail?.source === 'creation' && event.detail?.path === '/events/new/' && run.guided && run.guideInFlight) {
      // This fixed GET belongs to the current creation response, not a new
      // command. Keep its controller/ticket so its server question can finish.
      clearTimeout(run.retryTimer); detach(run);
      mark('paused', 'Abriendo el formulario del evento. Micrófono en pausa mientras se muestra tu ficha.'); return;
    }
    if (!run.guided || run.textOnly || run.phase === 'consent') { stop('La navegación apagó esta sesión. Puedes reanudarla con tu clic.'); return; }
    clearTimeout(run.retryTimer); clearGuide(run); detach(run);
    run.responseTicket += 1; run.responsePending = false; run.speechMeasure = null;
    if (speechOwner === run) { speechOwner = null; outputSpeaking = false; speech.cancel(); }
    run.capture = true; run.draft = ''; run.readyIntent = ''; run.followUp = ''; guideContext = '';
    mark('paused', 'Conversación activa. Micrófono en pausa mientras cambia la página.');
  });
  document.addEventListener('sparkx:gica-navigation-complete', (event) => {
    if (!navigation || event.detail?.id !== navigation.id) return;
    const previous = navigation; navigation = null;
    if (event.detail?.success !== true || previous.userID !== document.body.dataset.voiceUser) {
      stop('No se comprobó la navegación o cambió la cuenta. Micrófono apagado; revisa la página.'); return;
    }
    const run = session;
    if (!run || !valid(run) || !run.guided || run.textOnly) return;
    if (run.awaitingAction || run.guideInFlight || run.responsePending || speechOwner === run) {
      status.textContent = 'Conversación activa. Micrófono en pausa hasta comprobar la acción y terminar la respuesta.'; render(); return;
    }
    schedule(run, 'dictating');
  });
  document.addEventListener('click', (event) => { if (event.target.closest('[data-read-message]')) { lab?.close('Laboratorio cerrado al iniciar otra lectura.'); stop('La lectura apagó la escucha para evitar eco.'); cancelProbe(); } }, true);
  function leave() {
    discardMemory(); manualAction = null;
    lab?.close();
    stop(); probeGeneration += 1; speechOwner = null; outputSpeaking = false; speech.cancel(); probe.textContent = 'Probar voz'; render();
    companion({ kind: 'clear' });
  }
  document.addEventListener('visibilitychange', () => { if (document.hidden) leave(); });
  window.addEventListener('pagehide', leave);
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && session && !session.guided) { event.preventDefault(); stop(); } });
  status.textContent = Recognition ? 'Micrófono apagado. Abre Gica con tu clic o pulsa Reanudar conversación. Al contraer el panel seguirá activa; usa Detener para terminar.' : 'Este navegador no ofrece reconocimiento de voz. Puedes conversar por texto y probar la voz de Gica.';
  button.hidden = !Recognition; availability(); render();
  import('/static/js/romeo-voice-lab.js?v=20261115-gica1').then(({ installVoiceLab }) => {
    lab = installVoiceLab({ root, anchor: probe, speech, prepare: prepareLab, preview: previewLab, stop: cancelProbe,
      closed: (message) => { labOpen = false; speechStatus.textContent = message; },
      notify: (message) => { speechStatus.textContent = message; } });
  }).catch(() => { speechStatus.textContent = 'El comparador temporal no pudo cargarse. Puedes seguir usando Probar voz.'; });
})();

/* Short application feedback and requested local social replies. Greeting may
 * include the bounded SSR username or a validated name explicitly given for a
 * local salutation, or a short attributed reference excerpt already checked by
 * the knowledge flow. No chat reads, contact lookup, sending or remote voice fallback.
 * spoken=true means the browser reported onend; it does not prove audible sound.
 * The caller coordinates microphone exclusion and whether feedback is enabled.
 */
(() => {
  'use strict';
  const synthesis = window.speechSynthesis;
  const Utterance = window.SpeechSynthesisUtterance;
  const localSpanish = /^es(?:[-_]|$)/i;
  const controls = /[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u;
  const forbidden = /[<>\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u;
  const DEFAULT_RATE = 1.04, PREVIEW_TEXT = 'Hola, soy Gica. Vamos a organizar tu próximo evento.';
  let active = null, sequence = 0, preference = null;

  function supported() {
    return !!synthesis && typeof Utterance === 'function' &&
      typeof synthesis.getVoices === 'function' && typeof synthesis.speak === 'function' &&
      typeof synthesis.cancel === 'function';
  }
  function voices() {
    if (!supported()) return [];
    try { return Array.from(synthesis.getVoices() || []).slice(0, 300); } catch (_) { return []; }
  }
  function voiceID(voice) {
    if (!voice || typeof voice.name !== 'string' || !voice.name.trim() || voice.name.length > 200 ||
        typeof voice.lang !== 'string' || !voice.lang || voice.lang.length > 40) return null;
    const uri = typeof voice.voiceURI === 'string' ? voice.voiceURI : '';
    if (uri.length > 512 || [uri, voice.name, voice.lang].some((value) => controls.test(value))) return null;
    const id = JSON.stringify([uri, voice.name, voice.lang]);
    return id.length <= 1000 ? id : null;
  }
  function decodedID(id) {
    if (typeof id !== 'string' || id.length > 1000) return null;
    try {
      const values = JSON.parse(id);
      if (!Array.isArray(values) || values.length !== 3 || values.some((value) => typeof value !== 'string') ||
          voiceID({ voiceURI: values[0], name: values[1], lang: values[2] }) !== id) return null;
      return { name: values[1], lang: values[2] };
    } catch (_) { return null; }
  }
  function validRate(rate) { return typeof rate === 'number' && Number.isFinite(rate) && rate >= 0.85 && rate <= 1.2; }
  function preferenceKey() {
    const user = document.body?.dataset.voiceUser || '';
    return /^[1-9][0-9]{0,18}$/.test(user) ? 'sparkx.romeo.voice.preference.v1.u' + user : null;
  }
  function readPreference() {
    const key = preferenceKey();
    if (preference && preference.key === key) return preference;
    preference = { key, voiceID: null, rate: DEFAULT_RATE, saved: false, persisted: false };
    if (!key) return preference;
    try {
      const raw = localStorage.getItem(key);
      if (!raw || raw.length > 1500) return preference;
      const data = JSON.parse(raw), identity = decodedID(data?.voiceID);
      if (data && Object.keys(data).sort().join(',') === 'rate,version,voiceID' && data.version === 1 &&
          identity && localSpanish.test(identity.lang) && validRate(data.rate)) {
        preference = { key, voiceID: data.voiceID, rate: data.rate, saved: true, persisted: true };
      }
    } catch (_) { /* Invalid/unavailable storage never authorizes a voice. */ }
    return preference;
  }
  function maleRank(voice) {
    // Web Speech has no gender property. These Microsoft names/locales are
    // documented masculine voices; unknown names never receive that label.
    const name = voice.name.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
    const known = /^microsoft\s+(jorge|alvaro|raul|pablo)(?:\s|$)/u.exec(name);
    const locales = { jorge: 'es-mx', alvaro: 'es-es', raul: 'es-mx', pablo: 'es-es' };
    if (!known || voice.lang.toLowerCase().replace('_', '-') !== locales[known[1]] || /\bonline\b/u.test(name)) return Infinity;
    return ['jorge', 'alvaro', 'raul', 'pablo'].indexOf(known[1]);
  }
  function isLocal(voice) { return voice?.localService === true && voiceID(voice) !== null; }
  function femaleRank(voice) {
    const name = voice.name.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
    const known = /^microsoft\s+(sabina|laura|helena)(?:\s|$)/u.exec(name);
    const locales = { sabina: 'es-mx', laura: 'es-es', helena: 'es-es' };
    if (!known || voice.lang.toLowerCase().replace('_', '-') !== locales[known[1]] || /\bonline\b/u.test(name)) return Infinity;
    return ['sabina', 'laura', 'helena'].indexOf(known[1]);
  }
  function pickVoice(list) {
    const candidates = list.filter((voice) => isLocal(voice) && localSpanish.test(voice.lang));
    return candidates.reduce((best, voice) => !best || femaleRank(voice) < femaleRank(best) ? voice : best, null);
  }
  function pickFemaleVoice(list) {
    return list.filter((voice)=>isLocal(voice)&&localSpanish.test(voice.lang)&&Number.isFinite(femaleRank(voice)))
      .sort((a,b)=>femaleRank(a)-femaleRank(b))[0] || null;
  }
  function exactVoice(list, id, spanishOnly = true) {
    return list.find((voice) => isLocal(voice) && (!spanishOnly || localSpanish.test(voice.lang)) && voiceID(voice) === id) || null;
  }
  function selectedNative() {
    const saved = readPreference(), list = voices();
    return saved.voiceID ? exactVoice(list, saved.voiceID) : pickVoice(list);
  }
  function metadata(voice) {
    return Object.freeze({ id: voiceID(voice), name: voice.name, lang: voice.lang,
      local: voice.localService === true, male: Number.isFinite(maleRank(voice)), female: Number.isFinite(femaleRank(voice)) });
  }
  function listVoices() {
    const entries = new Map();
    for (const voice of voices()) {
      const id = voiceID(voice);
      if (id && (!entries.has(id) || voice.localService === true)) entries.set(id, metadata(voice));
    }
    return Object.freeze(Array.from(entries.values()));
  }
  function available() { return supported() && !!selectedNative(); }
  function selectedVoice() {
    const selected = supported() ? selectedNative() : null;
    return selected ? metadata(selected) : null;
  }
  function getPreference() {
    const saved = readPreference(), selected = selectedVoice(), identity = decodedID(saved.voiceID);
    return Object.freeze({ voiceID: saved.voiceID, name: selected?.name || identity?.name || '',
      lang: selected?.lang || identity?.lang || '', rate: saved.rate, saved: saved.saved,
      persisted: saved.persisted, available: !!selected });
  }
  function reportAvailability() {
    document.dispatchEvent(new CustomEvent('sparkx:romeo-speech-availability', { detail: { available: available() } }));
  }
  function setPreference(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value) || !validRate(value.rate)) return { ok: false, reason: 'invalid_rate', persisted: false };
    if (!decodedID(value.voiceID) || !exactVoice(voices(), value.voiceID)) return { ok: false, reason: 'voice_unavailable', persisted: false };
    const key = preferenceKey();
    cancelActive('preference_changed');
    preference = { key, voiceID: value.voiceID, rate: value.rate, saved: true, persisted: false };
    let persisted = false;
    if (key) {
      try { localStorage.setItem(key, JSON.stringify({ version: 1, voiceID: value.voiceID, rate: value.rate })); persisted = true; }
      catch (_) { /* The explicit choice remains in this document's memory. */ }
    }
    preference.persisted = persisted;
    reportAvailability();
    return { ok: true, reason: persisted ? 'saved' : 'memory_only', persisted };
  }
  function resetPreference() {
    const key = preferenceKey();
    cancelActive('preference_changed');
    preference = { key, voiceID: null, rate: DEFAULT_RATE, saved: false, persisted: false };
    let persisted = false;
    if (key) { try { localStorage.removeItem(key); persisted = true; } catch (_) { /* Memory reset remains effective for this document. */ } }
    reportAvailability();
    return { ok: true, persisted };
  }
  function current(request) { return active === request && sequence === request.id && !request.settled; }
  function report(state) {
    document.dispatchEvent(new CustomEvent('sparkx:romeo-speech-state', { detail: { state } }));
  }
  function settle(request, spoken, reason, notify = true) {
    if (request.settled) return;
    request.settled = true;
    clearTimeout(request.waitTimer); clearTimeout(request.speechTimer); clearInterval(request.progressTimer);
    if (request.voiceListener && typeof synthesis?.removeEventListener === 'function') synthesis.removeEventListener('voiceschanged', request.voiceListener);
    if (request.utterance) request.utterance.onstart = request.utterance.onend = request.utterance.onerror = request.utterance.onboundary = null;
    const owned = active === request;
    if (owned) active = null;
    request.resolve({ spoken, reason });
    if (notify && owned) report(['no_local_voice', 'voice_unavailable'].includes(reason) ? 'unavailable' : 'ended');
  }
  function cancelActive(reason = 'cancelled') {
    const request = active;
    if (!request) return;
    const ownsUtterance = request.submitted;
    sequence += 1;
    settle(request, false, reason, false); // Invalidate before native callbacks can run.
    if (ownsUtterance) { try { synthesis.cancel(); } catch (_) { /* Already settled. */ } }
    if (!active) report('ended');
    // While merely waiting for voices, never cancel another component's speech.
  }
  function cancel() { cancelActive(); }
  function startSpeech(request, voice) {
    if (!current(request)) return;
    if (document.hidden || request.scope !== preferenceKey()) { cancelActive(document.hidden ? 'hidden' : 'identity_changed'); return; }
    clearTimeout(request.waitTimer);
    if (request.voiceListener && typeof synthesis.removeEventListener === 'function') {
      synthesis.removeEventListener('voiceschanged', request.voiceListener); request.voiceListener = null;
    }
    try {
      const utterance = new Utterance(request.text);
      utterance.voice = voice; // Explicit local voice; never browser default.
      utterance.lang = voice.lang; utterance.rate = request.rate; utterance.pitch = 1; utterance.volume = 1;
      request.utterance = utterance;
      const estimateMs = Math.min(18000, Math.max(1000, request.text.split(/\s+/u).length * 400 / request.rate));
      let startedAt = null, lastBoundary = null;
      const progress = () => {
        if (!current(request) || startedAt === null || typeof request.onProgress !== 'function') return;
        const elapsedMs = Math.max(0, performance.now() - startedAt);
        const remainingEstimateMs = lastBoundary && lastBoundary.index > 0
          ? Math.min(20000, Math.max(0, (request.text.length - lastBoundary.index) * elapsedMs / lastBoundary.index))
          : Math.max(0, estimateMs - elapsedMs);
        try { request.onProgress(Object.freeze({ elapsedMs, remainingEstimateMs, source: lastBoundary ? 'boundary' : 'estimate' })); }
        catch (_) { /* Progress is advisory; observers never own speech completion. */ }
      };
      if (typeof request.onProgress === 'function') utterance.onboundary = (event) => {
        if (!current(request) || !Number.isInteger(event.charIndex) || event.charIndex < 0 || event.charIndex > request.text.length) return;
        if (!lastBoundary || event.charIndex >= lastBoundary.index) lastBoundary = { index: event.charIndex };
        progress();
      };
      utterance.onstart = () => {
        if (!current(request)) return;
        if (request.scope !== preferenceKey()) { cancelActive('identity_changed'); return; }
        report('speaking');
        startedAt = performance.now();
        if (typeof request.onProgress === 'function') { progress(); request.progressTimer = setInterval(progress, 250); }
      };
      utterance.onend = () => { if (current(request)) settle(request, request.scope === preferenceKey(), request.scope === preferenceKey() ? 'ended' : 'identity_changed'); };
      utterance.onerror = () => { if (current(request)) settle(request, false, 'error'); };
      request.speechTimer = setTimeout(() => { if (current(request)) cancelActive('timeout'); }, request.speechTimeout || 8000);
      request.submitted = true;
      synthesis.speak(utterance);
    } catch (_) {
      request.submitted = false; // A rejected speak/constructor does not own someone else's queue.
      if (current(request)) cancelActive('start_error');
    }
  }
  function requestSpeech(text, selection) {
    if (typeof text !== 'string' || !text.trim() || text.length > 300 || forbidden.test(text)) {
      if (!active) report('ended');
      return Promise.resolve({ spoken: false, reason: 'invalid_text' });
    }
    if (!supported()) { if (!active) report('unavailable'); return Promise.resolve({ spoken: false, reason: 'unsupported' }); }
    if (document.hidden) { cancelActive('hidden'); return Promise.resolve({ spoken: false, reason: 'hidden' }); }
    cancelActive('superseded');
    return new Promise((resolve) => {
      const request = { id: ++sequence, text: text.trim(), resolve, settled: false, scope: preferenceKey(),
        ...selection, utterance: null, submitted: false, voiceListener: null, waitTimer: null, speechTimer: null };
      active = request;
      const choose = (list) => {
        const savedVoice = request.voiceID ? exactVoice(list, request.voiceID, !request.preview) : null;
        if(request.voiceStyle === 'female')return savedVoice&&Number.isFinite(femaleRank(savedVoice))?savedVoice:pickFemaleVoice(list);
        return request.voiceID?savedVoice:pickVoice(list);
      };
      const failure = request.voiceStyle === 'female' ? 'female_voice_unavailable' : request.voiceID ? 'voice_unavailable' : 'no_local_voice';
      const list = voices(), selected = choose(list);
      if (selected) { startSpeech(request, selected); return; }
      if (list.length || request.preview) { settle(request, false, failure); return; }
      request.voiceListener = () => {
        if (!current(request)) return;
        if (request.scope !== preferenceKey()) { cancelActive('identity_changed'); return; }
        const voice = choose(voices());
        if (voice) startSpeech(request, voice);
      };
      if (typeof synthesis.addEventListener === 'function') synthesis.addEventListener('voiceschanged', request.voiceListener);
      request.waitTimer = setTimeout(() => {
        if (!current(request)) return;
        if (request.scope !== preferenceKey()) { cancelActive('identity_changed'); return; }
        const voice = choose(voices());
        if (voice) startSpeech(request, voice); else settle(request, false, failure);
      }, 1000);
    });
  }
  function speak(text, options = {}) {
    const saved = readPreference();
    return requestSpeech(text, { voiceID: saved.voiceID, rate: saved.rate, preview: false, voiceStyle:options.voiceStyle==='female'?'female':null,
      speechTimeout: options.eventQuestion === true ? 20000 : 8000,
      onProgress: options.eventQuestion === true && typeof options.onProgress === 'function' ? options.onProgress : null });
  }
  function preview(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value) || !validRate(value.rate)) return Promise.resolve({ spoken: false, reason: 'invalid_rate' });
    if (!decodedID(value.voiceID) || !exactVoice(voices(), value.voiceID, false)) return Promise.resolve({ spoken: false, reason: 'voice_unavailable' });
    return requestSpeech(PREVIEW_TEXT, { voiceID: value.voiceID, rate: value.rate, preview: true });
  }

  if (typeof synthesis?.addEventListener === 'function') synthesis.addEventListener('voiceschanged', reportAvailability);
  document.addEventListener('visibilitychange', () => { if (document.hidden) cancelActive('hidden'); });
  window.addEventListener('pagehide', cancel);
  window.SparkXRomeoSpeech = Object.freeze({ available, selectedVoice, speak, cancel,
    listVoices, getPreference, setPreference, resetPreference, preview });
})();

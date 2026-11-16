/* Temporary comparison UI. Native voices plus one fixed local WAV; no uploads. */
export function installVoiceLab({ root, anchor, speech, prepare, preview, stop, closed, notify }) {
  if (!root || !anchor || !speech || root.querySelector('[data-romeo-voice-lab-open]')) return null;
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function button(text, name, className = 'button button-secondary') {
    const node = element('button', text, className);
    node.type = 'button'; node.setAttribute(name, ''); return node;
  }
  const opener = button('Comparar voces (temporal)', 'data-romeo-voice-lab-open');
  opener.setAttribute('aria-haspopup', 'dialog'); anchor.after(opener);
  const dialog = element('dialog', '', 'romeo-voice-lab');
  dialog.setAttribute('data-romeo-voice-lab', '');
  dialog.setAttribute('aria-labelledby', 'romeo-lab-title');
  dialog.setAttribute('aria-describedby', 'romeo-lab-intro');
  const heading = element('div', '', 'romeo-lab-heading');
  const title = element('h2', 'Laboratorio de voces'); title.id = 'romeo-lab-title';
  const badge = element('span', 'Temporal', 'romeo-presence-badge');
  const closeButton = button('Cerrar', 'data-romeo-lab-close'); heading.append(title, badge, closeButton);
  const intro = element('p', 'Compara con la misma frase y elige cómo hablará Gica. Abrir este panel apaga el micrófono; ninguna prueba lo vuelve a activar.');
  intro.id = 'romeo-lab-intro';
  const filterLabel = element('label', '', 'romeo-lab-check');
  const filter = element('input'); filter.type = 'checkbox'; filter.checked = true;
  filter.setAttribute('data-romeo-lab-spanish', ''); filterLabel.append(filter, document.createTextNode(' Sólo voces en español'));
  const refresh = button('Actualizar voces', 'data-romeo-lab-refresh');
  const filterRow = element('div', '', 'romeo-lab-filter'); filterRow.append(filterLabel, refresh);
  const count = element('p', '', 'field-help'); count.setAttribute('data-romeo-lab-count', '');
  const voiceLabel = element('label', 'Voz para comparar'); voiceLabel.htmlFor = 'romeo-lab-voice';
  const select = element('select'); select.id = 'romeo-lab-voice'; select.setAttribute('data-romeo-lab-voice', '');
  const detail = element('p', '', 'field-help'); detail.setAttribute('data-romeo-lab-detail', '');
  select.setAttribute('aria-describedby', 'romeo-lab-voice-detail'); detail.id = 'romeo-lab-voice-detail';
  const rateLabel = element('label', 'Ritmo de lectura'); rateLabel.htmlFor = 'romeo-lab-rate';
  const rateRow = element('div', '', 'romeo-lab-rate');
  const rate = element('input'); rate.type = 'range'; rate.id = 'romeo-lab-rate';
  rate.min = '0.85'; rate.max = '1.20'; rate.step = '0.01'; rate.value = '1.04';
  rate.setAttribute('data-romeo-lab-rate', '');
  const rateValue = element('output'); rateValue.htmlFor = rate.id; rateValue.setAttribute('data-romeo-lab-rate-value', '');
  rateRow.append(rate, rateValue);
  const sample = element('blockquote', '«Hola, soy Gica. Vamos a organizar tu próximo evento.»', 'romeo-lab-sample');
  const actions = element('div', '', 'romeo-lab-actions');
  const play = button('Escuchar muestra', 'data-romeo-lab-play', 'button');
  const halt = button('Detener', 'data-romeo-lab-stop'); halt.disabled = true;
  actions.append(play, halt);
  const status = element('p', 'Elige una voz y pulsa Escuchar muestra.', 'romeo-lab-status');
  status.setAttribute('data-romeo-lab-status', ''); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const choice = element('p', '', 'field-help'); choice.setAttribute('data-romeo-lab-choice', '');
  const footer = element('div', '', 'romeo-lab-actions');
  const save = button('Usar en Gica', 'data-romeo-lab-save', 'button');
  const reset = button('Restablecer automática', 'data-romeo-lab-reset'); footer.append(save, reset);
  const note = element('p', 'Las voces locales no necesitan una API de pago. Las externas se muestran, pero su reproducción está deshabilitada. Tu elección se guarda para tu cuenta en este navegador; probar no cambia la voz de Gica.', 'field-help');
  const piper = element('section', '', 'romeo-lab-piper');
  piper.setAttribute('aria-labelledby', 'romeo-lab-piper-title');
  const piperTitle = element('h3', 'Piper · Davefx (muestra descargada)'); piperTitle.id = 'romeo-lab-piper-title';
  const piperNote = element('p', 'Compara la misma frase con un archivo de audio local. No es una voz nativa del navegador y todavía no se usa en las respuestas de Gica.', 'field-help');
  const piperActions = element('div', '', 'romeo-lab-actions');
  const piperPlay = button('Escuchar Davefx', 'data-romeo-piper-play');
  const piperStop = button('Detener muestra', 'data-romeo-piper-stop'); piperStop.disabled = true;
  piperActions.append(piperPlay, piperStop);
  const piperStatus = element('p', 'Muestra lista para comparar. Escucharla no cambia tu elección.', 'field-help');
  piperStatus.setAttribute('data-romeo-piper-status', ''); piperStatus.setAttribute('role', 'status');
  piperStatus.setAttribute('aria-live', 'polite');
  piper.append(piperTitle, piperNote, piperActions, piperStatus);
  dialog.append(heading, intro, filterRow, count, voiceLabel, select, detail, rateLabel, rateRow, sample, actions, status, choice, footer, note, piper);
  root.append(dialog);
  let catalogue = [], sequence = 0, opened = false;
  let piperRun = null, piperSequence = 0;
  const isSpanish = (voice) => /^es(?:[-_]|$)/i.test(voice.lang);
  function selection() { return catalogue.find((voice) => voice.id === select.value) || null; }
  function showRate() { rateValue.value = `${Math.round(Number(rate.value) * 100)} %`; }
  function currentChoice() {
    const preference = speech.getPreference(), selected = speech.selectedVoice();
    choice.textContent = preference.voiceID ?
      `Elección actual: ${preference.name || 'voz guardada'}. ${preference.available ? '' : 'No está disponible; elige otra o restablece automática. '}${preference.persisted ? 'Recordada en este navegador.' : 'Sólo en esta página; no pudo guardarse en el navegador.'}` :
      `Selección automática: ${selected?.name || 'sin voz española local disponible'}.`;
  }
  function describe() {
    const selected = selection();
    play.disabled = !selected?.local; save.disabled = !selected?.local || !isSpanish(selected);
    detail.textContent = !selected ? 'No hay voces para este filtro. Pulsa Actualizar voces o desmarca Sólo voces en español.' :
      !selected.local ? `${selected.name} · ${selected.lang}. Servicio externo; prueba y uso en Gica deshabilitados.` :
      `${selected.name} · ${selected.lang}. Local${selected.female ? ', femenina identificada' : selected.male ? ', masculina identificada' : ''}. ${isSpanish(selected) ? 'Puedes usarla en Gica.' : 'Puedes probarla; Gica admite voces en español.'}`;
    showRate(); currentChoice();
  }
  function haltPreview(message) {
    sequence += 1; stop(); halt.disabled = true; stopPiper();
    if (message) status.textContent = message;
  }
  function releaseAudio(audio) {
    audio.onplaying = audio.onended = audio.onerror = null;
    try { audio.pause(); } catch (_) { /* No playback remains authorized. */ }
    audio.removeAttribute('src');
    try { audio.load(); } catch (_) { /* Already detached. */ }
    audio.remove();
  }
  function stopPiper(message) {
    const run = piperRun;
    piperRun = null; piperSequence += 1;
    if (run) { clearTimeout(run.timer); releaseAudio(run.audio); }
    piperPlay.disabled = false; piperStop.disabled = true;
    if (message) piperStatus.textContent = message;
    else if (run) piperStatus.textContent = 'Muestra detenida. No se cambió la voz de Gica.';
  }
  function refreshVoices(preserve = true) {
    const previous = preserve ? select.value : '', preference = speech.getPreference();
    catalogue = speech.listVoices();
    const visible = catalogue.filter((voice) => !filter.checked || isSpanish(voice));
    select.replaceChildren();
    for (const voice of visible) {
      const option = element('option', `${voice.name} · ${voice.lang} · ${voice.local ? 'Local' : 'Externa'}${voice.female ? ' · Femenina' : voice.male ? ' · Masculina' : ''}`);
      option.value = voice.id; select.append(option);
    }
    if (!visible.length) { const option = element('option', 'Sin voces disponibles'); option.value = ''; select.append(option); }
    const automatic = speech.selectedVoice();
    const initial = visible.find((voice) => voice.id === (previous || preference.voiceID)) ||
      visible.find((voice) => voice.local && voice.name === automatic?.name && voice.lang === automatic?.lang) || visible.find((voice) => voice.local) || visible[0];
    select.value = initial?.id || ''; select.disabled = !visible.length;
    const localCount = visible.filter((voice) => voice.local).length, externalCount = visible.length - localCount;
    count.textContent = `${visible.length} ${visible.length === 1 ? 'voz' : 'voces'} · ${localCount} ${localCount === 1 ? 'local' : 'locales'} · ${externalCount} ${externalCount === 1 ? 'externa' : 'externas'}.`;
    describe();
  }
  function close(message = 'Laboratorio cerrado. Micrófono apagado.') {
    if (!opened) return;
    opened = false; haltPreview(); if (dialog.open) dialog.close(); closed(message);
  }
  opener.addEventListener('click', () => {
    if (dialog.open) return;
    if (typeof dialog.showModal !== 'function') { notify('Este navegador no puede abrir el laboratorio. Puedes seguir usando Probar voz.'); return; }
    if (!prepare()) return;
    rate.value = String(speech.getPreference().rate); refreshVoices(false);
    status.textContent = 'Elige una voz y pulsa Escuchar muestra. Ninguna prueba cambia tu elección.';
    opened = true;
    try { dialog.showModal(); select.focus(); }
    catch (_) { close('No se pudo abrir el laboratorio. Puedes seguir usando Probar voz.'); }
  });
  closeButton.addEventListener('click', () => close());
  dialog.addEventListener('cancel', (event) => { event.preventDefault(); close(); });
  dialog.addEventListener('close', () => { if (!dialog.open) close(); });
  filter.addEventListener('change', () => { haltPreview('Filtro actualizado. Elige una voz para escucharla.'); refreshVoices(); });
  refresh.addEventListener('click', () => { haltPreview('Lista de voces actualizada.'); refreshVoices(); });
  select.addEventListener('change', () => { haltPreview('Voz preparada para comparar; todavía no se ha guardado.'); describe(); });
  rate.addEventListener('input', () => { haltPreview('Ritmo preparado para comparar; todavía no se ha guardado.'); showRate(); });
  halt.addEventListener('click', () => haltPreview('Prueba detenida. Puedes escuchar otra voz.'));
  piperPlay.addEventListener('click', () => {
    if (!dialog.open || document.hidden) return;
    haltPreview();
    const audio = element('audio');
    audio.preload = 'none'; audio.autoplay = false; audio.hidden = true;
    audio.src = '/static/audio/romeo/davefx-sample.wav?v=20261115-gica1';
    const run = { audio, ticket: ++piperSequence, timer: null };
    piperRun = run; piper.append(audio);
    const owns = () => piperRun === run && run.ticket === piperSequence && dialog.open && !document.hidden;
    piperPlay.disabled = true; piperStop.disabled = false;
    piperStatus.textContent = 'Preparando la muestra descargada de Davefx…';
    audio.onplaying = () => {
      if (!owns()) { releaseAudio(audio); return; }
      piperStatus.textContent = 'Reproduciendo Davefx. Es sólo una muestra; no modifica la voz elegida.';
    };
    audio.onended = () => { if (owns()) stopPiper('Muestra terminada. Piper todavía no se utiliza en las respuestas de Gica.'); };
    audio.onerror = () => { if (owns()) stopPiper('No se pudo reproducir la muestra local. Puedes probar las voces nativas de arriba.'); };
    run.timer = setTimeout(() => { if (piperRun === run) stopPiper('La muestra no terminó a tiempo. Puedes volver a probarla manualmente.'); }, 15000);
    try {
      const playing = audio.play();
      if (playing && typeof playing.then === 'function') playing.then(() => { if (!owns()) releaseAudio(audio); }).catch(() => {
        if (owns()) stopPiper('El navegador no inició la muestra. Revisa el volumen o vuelve a probar manualmente.');
      });
    } catch (_) { if (owns()) stopPiper('El navegador no pudo iniciar la muestra local.'); }
  });
  piperStop.addEventListener('click', () => stopPiper('Muestra detenida. No se cambió la voz de Gica.'));
  play.addEventListener('click', async () => {
    const selected = selection();
    if (!dialog.open || !selected?.local) return;
    haltPreview(); const ticket = ++sequence; halt.disabled = false;
    status.textContent = `Preparando muestra: ${selected.name}.`;
    const result = await preview({ voiceID: selected.id, rate: Number(rate.value) });
    if (!dialog.open || sequence !== ticket) return;
    halt.disabled = true;
    status.textContent = result.spoken ? `Muestra terminada: ${selected.name}. Si te gusta, pulsa Usar en Gica.` :
      'No se completó la muestra. Comprueba el volumen y la disponibilidad de la voz, o elige otra.';
  });
  save.addEventListener('click', () => {
    const selected = selection();
    if (!dialog.open || !selected?.local || !isSpanish(selected)) return;
    haltPreview(); const result = speech.setPreference({ voiceID: selected.id, rate: Number(rate.value) });
    status.textContent = result.ok ? `${selected.name} será la voz de Gica. ${result.persisted ? 'Elección guardada en este navegador para tu cuenta.' : 'Sólo para esta página; el navegador no permitió guardarla.'}` : 'No se guardó. La voz debe estar disponible, ser local y estar en español.';
    describe();
  });
  reset.addEventListener('click', () => {
    if (!dialog.open) return;
    haltPreview(); const result = speech.resetPreference(); rate.value = '1.04'; refreshVoices(false);
    status.textContent = result.persisted ? 'Selección automática restablecida, con preferencia masculina local.' : 'Selección automática para esta página; el navegador no permitió guardar el cambio.';
  });
  document.addEventListener('sparkx:romeo-speech-availability', () => {
    if (!dialog.open) return;
    haltPreview(); refreshVoices();
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) close(); });
  window.addEventListener('pagehide', () => close());
  document.addEventListener('sparkx:dictation-starting', () => close());
  document.addEventListener('click', (event) => { if (event.target.closest('[data-read-message]')) close(); }, true);
  return Object.freeze({ close });
}

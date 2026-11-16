/* Reviewed, user-scoped phrase saving. No transcript/audio storage or automatic saving. */
(() => {
  'use strict';
  const root = document.querySelector('[data-romeo-presence]');
  if (!root || (root.dataset.patternSaveUrl && root.dataset.patternSaveUrl !== '/assistant/patterns/save/') ||
      (root.dataset.patternsUrl && root.dataset.patternsUrl !== '/assistant/patterns/')) return;
  const choices = Object.freeze([
    ['theme_light', 'Tema claro'], ['theme_dark', 'Tema oscuro'], ['calendar_open', 'Abrir calendario'],
    ['directory_open', 'Abrir directorio'], ['people_search', 'Buscar una persona'], ['events_open', 'Abrir eventos']
  ]);
  const unsafe = /[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u;
  let dialog = null, sequence = 0, pending = null;
  const notice = document.createElement('p'); notice.className = 'gica-pattern-notice';
  notice.dataset.gicaPatternNotice = ''; notice.setAttribute('role', 'status'); notice.hidden = true;
  root.querySelector('#romeo-presence-details')?.append(notice);

  function notify(text) { notice.textContent = text; notice.hidden = false; }
  function invalidate() {
    sequence += 1;
    if (pending) {
      clearTimeout(pending.timeout); pending.controller.abort(); pending = null;
      notify('La solicitud de guardado ya se envió. Si no viste la confirmación, comprueba Mis patrones antes de volver a guardarla.');
    }
  }
  function close() {
    invalidate();
    if (dialog?.open) dialog.close();
  }
  function bounded(value, max) { return typeof value === 'string' && value.length <= max && !unsafe.test(value); }
  function open(candidate) {
    if (document.hidden || !bounded(candidate?.phrase, 300) || !candidate.phrase.trim() ||
        !choices.some(([id]) => id === candidate.intent)) return;
    close();
    if (dialog) dialog.remove();
    window.SparkXVoice?.stopDictation(); window.SparkXRomeoSpeech?.cancel();
    dialog = document.createElement('dialog'); dialog.className = 'gica-pattern-dialog';
    dialog.dataset.gicaPatternDialog = ''; dialog.setAttribute('aria-labelledby', 'gica-pattern-heading');
    const title = document.createElement('h2'); title.id = 'gica-pattern-heading'; title.textContent = 'Revisar frase como patrón';
    const explanation = document.createElement('p');
    explanation.textContent = 'Se guardará sólo esta frase revisada y su intención para tu usuario. No se guarda audio ni la conversación. Guardarla no ejecuta ninguna acción.';
    const form = document.createElement('form'); form.noValidate = true;
    const phraseLabel = document.createElement('label'); phraseLabel.htmlFor = 'gica-pattern-phrase'; phraseLabel.textContent = 'Frase que quieres recordar';
    const phrase = document.createElement('textarea'); phrase.id = 'gica-pattern-phrase'; phrase.name = 'phrase'; phrase.maxLength = 300; phrase.rows = 3; phrase.value = candidate.phrase;
    const intentLabel = document.createElement('label'); intentLabel.htmlFor = 'gica-pattern-intent'; intentLabel.textContent = 'Intención permitida';
    const select = document.createElement('select'); select.id = 'gica-pattern-intent'; select.name = 'intent';
    for (const [id, label] of choices) { const option = document.createElement('option'); option.value = id; option.textContent = label; select.append(option); }
    select.value = candidate.intent;
    const review = document.createElement('label'); review.className = 'gica-pattern-review';
    const checked = document.createElement('input'); checked.type = 'checkbox'; checked.name = 'reviewed'; checked.required = true;
    review.append(checked, document.createTextNode(' Revisé la frase y confirmo que representa esta intención.'));
    const result = document.createElement('p'); result.dataset.gicaPatternResult = ''; result.setAttribute('role', 'status');
    const actions = document.createElement('div'); actions.className = 'dialog-actions';
    const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'button button-secondary'; cancel.textContent = 'Cancelar';
    const save = document.createElement('button'); save.type = 'submit'; save.className = 'button button-primary'; save.textContent = 'Guardar patrón';
    const link = document.createElement('a'); link.href = '/assistant/patterns/'; link.textContent = 'Mis patrones';
    actions.append(cancel, save); form.append(phraseLabel, phrase, intentLabel, select, review, result, actions, link);
    dialog.append(title, explanation, form); document.body.append(dialog);
    const thisDialog = dialog;
    cancel.addEventListener('click', close);
    thisDialog.addEventListener('cancel', (event) => { event.preventDefault(); close(); });
    thisDialog.addEventListener('close', () => { if (!thisDialog.open && dialog === thisDialog) invalidate(); });
    form.addEventListener('input', () => { if (pending && dialog === thisDialog) close(); });
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (pending || !thisDialog.open || document.hidden || dialog !== thisDialog) return;
      const text = phrase.value.normalize('NFC').trim(), intent = select.value;
      if (!bounded(phrase.value, 300) || !text || !bounded(text, 300) || !choices.some(([id]) => id === intent) || !checked.checked) {
        result.textContent = 'Escribe una frase de hasta 300 caracteres, elige una intención y confirma la revisión.'; return;
      }
      const token = root.querySelector('[name=csrfmiddlewaretoken]')?.value;
      if (!token) { result.textContent = 'No se pudo comprobar la sesión. Recarga antes de guardar.'; return; }
      const user = document.body.dataset.voiceUser, id = ++sequence, controller = new AbortController();
      if (!/^[1-9][0-9]{0,18}$/.test(user || '')) { result.textContent = 'Inicia sesión para guardar un patrón.'; return; }
      const owned = () => id === sequence && dialog === thisDialog && thisDialog.open && !document.hidden && document.body.dataset.voiceUser === user;
      const timeout = setTimeout(() => controller.abort(), 10000); pending = { controller, timeout };
      save.disabled = true; phrase.disabled = true; select.disabled = true; checked.disabled = true;
      result.textContent = 'Guardando la frase revisada…';
      try {
        const response = await fetch('/assistant/patterns/save/', {
          method: 'POST', credentials: 'same-origin', redirect: 'error', cache: 'no-store', signal: controller.signal,
          headers: { 'X-CSRFToken': token, Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
          body: new URLSearchParams({ phrase: text, intent, reviewed: 'on' })
        });
        if (!owned()) return;
        if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Invalid response');
        const raw = await response.text(); if (!owned()) return;
        if (raw.length > 8192) throw new Error('Invalid response');
        const data = JSON.parse(raw);
        if (response.ok && data?.ok === true && bounded(data.message, 500) && data.message.trim()) {
          result.textContent = data.message; notify(data.message); save.hidden = true;
          cancel.textContent = 'Cerrar';
        } else if (data?.ok === false && data.errors && typeof data.errors === 'object' && !Array.isArray(data.errors)) {
          const messages = Object.values(data.errors).flat().filter(value => bounded(value, 500)).slice(0, 5);
          if (!messages.length) throw new Error('Invalid response');
          result.textContent = messages.join(' ');
        } else throw new Error('Invalid response');
      } catch (_) {
        if (owned()) result.textContent = 'No se confirmó el guardado. La solicitud pudo llegar al servidor; comprueba Mis patrones antes de repetirla.';
      } finally {
        clearTimeout(timeout);
        if (id === sequence) { pending = null; save.disabled = false; phrase.disabled = false; select.disabled = false; checked.disabled = false; }
      }
    });
    if (typeof thisDialog.showModal === 'function') { thisDialog.showModal(); phrase.focus(); }
    else { thisDialog.remove(); dialog = null; notify('Este navegador no ofrece el diálogo de revisión. Abre Mis patrones.'); }
  }
  document.addEventListener('sparkx:gica-pattern-review', event => open(event.detail));
  document.addEventListener('visibilitychange', () => { if (document.hidden) close(); });
  window.addEventListener('pagehide', close);
  document.addEventListener('sparkx:dictation-starting', close);
  document.addEventListener('click', (event) => { if (event.target.closest('[data-read-message]')) close(); }, true);
})();

/* Progressive enhancement: text and ordinary POST forms work without this file. */
(() => {
  'use strict';
  const accountMenu = document.querySelector('[data-account-menu]');
  if (accountMenu) {
    const trigger = accountMenu.querySelector('[data-account-trigger]');
    document.addEventListener('click', (event) => {
      if (accountMenu.open && (!accountMenu.contains(event.target) || event.target.closest('a[href]'))) accountMenu.open = false;
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && accountMenu.open) {
        event.preventDefault(); accountMenu.open = false; trigger?.focus();
      }
    });
    document.addEventListener('focusin', (event) => {
      if (accountMenu.open && !accountMenu.contains(event.target)) accountMenu.open = false;
    });
    document.addEventListener('sparkx:gica-navigation-start', () => { accountMenu.open = false; });
  }
  const status = document.getElementById('voice-status');
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let listeningButton = null;
  let dictationInput = null;
  let dictationRun = 0;
  let dictationConsent = false;
  let readingConsent = false;
  let consentOpen = false;
  const noticeVersions = Object.freeze({ dictation: '1', 'command-session': '2', 'guided-session': '5' });
  const jobStates = new Map(Array.from(document.querySelectorAll('.job-status'), (job) => [job.id, job.dataset.jobStatus]));
  const setVoiceStatus = (text, button = listeningButton) => {
    const target = document.getElementById(button?.dataset.voiceStatus || 'voice-status');
    if (target) target.textContent = text;
  };
  function markListening(input, listening) {
    if (listening) input.dataset.voiceListening = 'true';
    else delete input.dataset.voiceListening;
    document.dispatchEvent(new CustomEvent('sparkx:dictation-state', { detail: { inputID: input.id, listening } }));
  }

  function noticeKey(kind) {
    const user = document.body?.dataset.voiceUser || '';
    if (!Object.hasOwn(noticeVersions, kind) || !/^[1-9][0-9]{0,18}$/.test(user)) return null;
    return `sparkx.voice.notice.${kind}.v${noticeVersions[kind]}.u${user}`;
  }

  function askConsent(kind, button = null) {
    if (!['dictation', 'command-session', 'guided-session', 'reading'].includes(kind) || consentOpen || document.hidden) return Promise.resolve(false);
    const key = noticeKey(kind);
    if (key) {
      try { if (localStorage.getItem(key) === 'accepted') return Promise.resolve(true); } catch (_) { /* The notice remains available without storage. */ }
    }
    consentOpen = true;
    return new Promise((resolve) => {
      const dialog = document.createElement('dialog');
      dialog.className = 'voice-dialog';
      dialog.setAttribute('aria-labelledby', 'voice-dialog-title');
      dialog.setAttribute('aria-describedby', 'voice-dialog-description');
      const heading = document.createElement('h2');
      heading.id = 'voice-dialog-title';
      heading.textContent = kind === 'guided-session' ? 'Conversación guiada local con Gica' : kind === 'command-session' ? 'Antes de conversar con Gica' : kind === 'dictation' ? 'Antes de activar el micrófono' : 'Antes de leer en voz alta';
      const description = document.createElement('p');
      description.id = 'voice-dialog-description';
      description.textContent = kind === 'guided-session'
        ? 'Al aceptar, Gica te saluda con tu usuario y escucha por turnos. Sólo cuando reconoce palabras comienza la espera de 1,5 segundos desde el último cambio del texto. Si el texto definitivo forma una orden clara y no quedan resultados parciales pendientes, la ejecuta sin IA remota ni «¿Procedo?». Sin palabras reconocidas no empieza la cuenta, no envía consultas y el silencio no termina la conversación. Los resultados idénticos no reinician la espera. El reconocimiento del navegador puede añadir demora y enviar audio a su servicio; requiere permiso. Si faltan datos o hay ambigüedad, Gica pregunta. Puedes seguir conversando al abrir Eventos, Calendario y Directorio, incluso con el panel contraído; el micrófono se pausa durante la navegación, la acción y la respuesta de voz. Usa Detener o Apagar mic para terminar. Ocultar, recargar, salir de estas secciones, cambiar de cuenta o un error fatal apagan la sesión. El límite móvil es de 20 inicios en 5 minutos, o 40 al crear un evento: al alcanzarlo el micrófono queda en pausa visible y se reanuda al liberarse capacidad, sin cerrar la conversación. Se mantienen hasta dos reconexiones cortas consecutivas para evitar bucles; no se promete escucha ilimitada. Escape puede cancelar una acción antes del clic. Planes y tareas mantienen su aprobación humana. Si Registro textual está activado se guardan turnos finales, normalización, respuestas y tiempos relativos privados para revisión del mentor; nunca audio ni resultados parciales. Puedes apagar el registro y borrar registros desde Mi memoria. Los patrones requieren revisión y guardado separado. Recordar el aviso permite iniciar al abrir Gica con tu clic, nunca al cargar o abrir por código.'
        : kind === 'command-session'
        ? 'La sesión permanece disponible hasta 5 minutos mientras esta página está visible, incluso con el panel cerrado. Di «Gica hablemos» para dictar y, en otra frase, «Gica ejecuta» para enviar. Tras una orden en esta página vuelve a esperar. Gica puede responder con una voz española local: el micrófono se pausa mientras habla. Si el navegador termina normalmente la escucha, habrá como máximo dos reconexiones; no se reintenta tras un error. Navegar, ocultar o recargar apaga la sesión. El reconocimiento puede enviar audio al servicio del navegador y requiere su permiso. Puedes apagar la voz y el micrófono cuando quieras. Recordar este aviso no inicia el micrófono automáticamente.'
        : kind === 'dictation'
        ? 'El dictado lo ofrece tu navegador. Según su configuración, el audio puede enviarse a un servicio externo para transcribirlo. Se solicitará permiso para el micrófono. Puedes detener la escucha cuando quieras. Revisa el texto: no se enviará ni ejecutará hasta que pulses ' + (button?.dataset.voiceSubmitLabel || 'Enviar') + '.'
        : 'La lectura utiliza las voces de tu navegador. Algunas pueden depender de servicios externos. Puedes detenerla cuando quieras. No se reproduce ninguna respuesta automáticamente.';
      if (kind === 'guided-session') {
        description.textContent = description.textContent.replace('20 inicios en 5 minutos', '20 inicios en 5 minutos (40 mientras completas un borrador de evento)').replace('hasta dos reconexiones cortas consecutivas', 'hasta dos reintentos tras fallos rápidos de arranque o conexión').replace('o un error apagan la sesión', 'o un fallo de permiso o dispositivo apagan la sesión').replace('el micrófono se pausa durante la navegación, la acción y la respuesta de voz', 'el micrófono se pausa durante la navegación y la acción; las preguntas de creación permiten la escucha anticipada opcional al final estimado de la voz');
        description.textContent += ' Si eliges crear un evento, se abre su formulario y las respuestas rellenan los campos y un borrador privado de 24 horas, independiente del registro de interacciones. La escucha anticipada, si está marcada, puede comenzar en los últimos cinco segundos estimados de una pregunta y captar eco. Sólo si hay texto reconocido, al terminar Gica de hablar espera 1,5 segundos de texto estable antes de enviar una respuesta definitiva, sin parciales pendientes. La confirmación final espera a que termine de hablar. Gica espera conserva tu texto sin enviarlo; después Gica corrige pide otra respuesta y Gica continúa reanuda. Puedes corregir o cancelar la ficha; sólo se crea el evento al confirmar el resumen. Las asociaciones que enseñes explícitamente pueden incorporarse automáticamente y revisarse después.';
      }
      let remember = null;
      if (kind !== 'reading') {
        const label = document.createElement('label');
        label.className = 'voice-consent-remember';
        remember = document.createElement('input');
        remember.type = 'checkbox'; remember.checked = true; remember.disabled = !key;
        if (!key) label.title = 'Inicia sesión para recordar este aviso.';
        label.append(remember, document.createTextNode(' Recordar este aviso en este navegador'));
        dialog.append(heading, description, label);
      } else dialog.append(heading, description);
      const actions = document.createElement('div');
      actions.className = 'dialog-actions';
      const cancel = document.createElement('button');
      cancel.type = 'button'; cancel.className = 'button button-secondary';
      cancel.textContent = kind === 'dictation' ? 'Seguir escribiendo' : 'Cancelar';
      const accept = document.createElement('button');
      accept.type = 'button'; accept.className = 'button button-primary';
      accept.textContent = ['command-session', 'guided-session'].includes(kind) ? 'Aceptar e iniciar sesión' : kind === 'dictation' ? 'Aceptar y dictar' : 'Aceptar y leer';
      actions.append(cancel, accept); dialog.append(actions);
      document.body.append(dialog);
      let settled = false;
      function finish(accepted) {
        if (settled) return;
        settled = true; consentOpen = false;
        const allowed = accepted && !document.hidden && (!key || noticeKey(kind) === key);
        document.removeEventListener('visibilitychange', cancelHidden);
        window.removeEventListener('pagehide', cancelLeaving);
        if (allowed && remember?.checked && key) {
          try { localStorage.setItem(key, 'accepted'); } catch (_) { /* Remembering the notice is optional. */ }
        }
        if (dialog.open) dialog.close();
        dialog.remove(); resolve(allowed);
      }
      const cancelHidden = () => { if (document.hidden) finish(false); };
      const cancelLeaving = () => finish(false);
      document.addEventListener('visibilitychange', cancelHidden);
      window.addEventListener('pagehide', cancelLeaving);
      cancel.addEventListener('click', () => finish(false));
      accept.addEventListener('click', () => finish(true));
      dialog.addEventListener('cancel', (event) => { event.preventDefault(); finish(false); });
      dialog.addEventListener('close', () => finish(false));
      if (typeof dialog.showModal === 'function') { dialog.showModal(); cancel.focus(); }
      else { finish(false); setVoiceStatus('La voz no está disponible en este navegador. Puedes seguir escribiendo.', button); }
    });
  }

  function stopDictation(discard = false) {
    if (!recognition) return;
    if (discard) {
      dictationRun += 1;
      const service = recognition, button = listeningButton, input = dictationInput;
      recognition = null; listeningButton = null; dictationInput = null;
      if (input) markListening(input, false);
      if (button) { button.setAttribute('aria-pressed', 'false'); const label = button.querySelector('span'); if (label) label.textContent = button.dataset.dictateLabel || 'Dictar'; }
      setVoiceStatus('Dictado detenido. El texto conservado requiere revisión y envío manual.', button);
      try { service.abort(); } catch (_) { /* Already stopped; late results are ignored. */ }
    } else { try { recognition.stop(); } catch (_) { /* Already stopped. */ } }
  }

  async function startDictation(button) {
    if (recognition) { stopDictation(); return; }
    if (button.disabled || document.hidden) return;
    if (!dictationConsent) {
      dictationConsent = await askConsent('dictation', button);
      if (!dictationConsent) return;
    }
    const input = document.getElementById(button.dataset.dictate);
    if (!input || input.readOnly || input.disabled || input.closest('[hidden]') || !Recognition || recognition || document.hidden) return;
    const run = ++dictationRun;
    let service;
    try { service = new Recognition(); } catch (_) { setVoiceStatus('No se pudo iniciar el dictado. Puedes seguir escribiendo.', button); return; }
    service.lang = 'es-PE'; service.continuous = false; service.interimResults = false; service.maxAlternatives = 1;
    recognition = service; listeningButton = button; dictationInput = input;
    let failed = false;
    const seen = new Set();
    service.onstart = () => {
      if (recognition !== service || run !== dictationRun) return;
      button.setAttribute('aria-pressed', 'true');
      const label = button.querySelector('span'); if (label) label.textContent = 'Detener';
      setVoiceStatus('Escuchando. Pulsa Detener para terminar. Hablar no envía ni ejecuta la orden.', button);
    };
    service.onresult = (event) => {
      if (recognition !== service || run !== dictationRun || input.readOnly || input.disabled || !input.isConnected || input.closest('[hidden]') || document.hidden) return;
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        if (!event.results[i].isFinal || seen.has(i)) continue;
        seen.add(i);
        const transcript = event.results[i][0].transcript.trim();
        const prefix = input.value.trimEnd();
        const value = prefix + (prefix && transcript ? ' ' : '') + transcript;
        const limit = input.maxLength > 0 ? input.maxLength : 12000;
        input.value = value.slice(0, limit);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        if (value.length > limit) setVoiceStatus('Se alcanzó el límite del campo. Revisa el texto antes de enviarlo.', button);
      }
    };
    service.onerror = (event) => {
      if (recognition !== service || run !== dictationRun) return;
      failed = true;
      const explanations = {
        'not-allowed': 'No se concedió acceso al micrófono. Puedes seguir escribiendo.',
        'service-not-allowed': 'El servicio de dictado no está permitido. Puedes seguir escribiendo.',
        'audio-capture': 'No se encontró un micrófono disponible. Puedes seguir escribiendo.',
        'no-speech': 'No se detectó voz. Puedes intentarlo otra vez o escribir.',
        'network': 'El servicio de dictado no pudo conectarse. El texto que ya escribiste se conserva.',
        'aborted': 'El dictado se detuvo. Revisa el texto antes de enviarlo.'
      };
      setVoiceStatus(explanations[event.error] || 'No se pudo completar el dictado. Puedes seguir escribiendo.', button);
    };
    service.onend = () => {
      if (recognition !== service) return;
      recognition = null; listeningButton = null; dictationInput = null;
      markListening(input, false);
      button.setAttribute('aria-pressed', 'false');
      const label = button.querySelector('span'); if (label) label.textContent = button.dataset.dictateLabel || 'Dictar';
      if (!failed) setVoiceStatus('Dictado terminado. Revisa el texto y pulsa ' + (button.dataset.voiceSubmitLabel || 'Enviar') + ' cuando esté listo.', button);
    };
    try {
      document.dispatchEvent(new CustomEvent('sparkx:dictation-starting', { detail: { inputID: input.id } }));
      if (recognition !== service || run !== dictationRun || document.hidden || input.readOnly || input.disabled || !input.isConnected || input.closest('[hidden]')) {
        if (recognition === service) stopDictation(true);
        return;
      }
      // The previous voice owner clears its marker while handling the event.
      markListening(input, true);
      service.start();
    }
    catch (_) {
      recognition = null; listeningButton = null; dictationInput = null;
      markListening(input, false);
      setVoiceStatus('No se pudo iniciar el dictado. Puedes seguir escribiendo.', button);
    }
  }

  window.SparkXVoice = Object.freeze({ requestConsent: askConsent, stopDictation: () => stopDictation(true) });

  function enableVoice(scope = document) {
    scope.querySelectorAll('[data-dictate]').forEach((button) => {
      if (Recognition) {
        button.hidden = false;
        button.setAttribute('aria-pressed', String(button === listeningButton));
        if (!button.dataset.voiceBound) {
          button.dataset.voiceBound = 'true';
          button.addEventListener('click', () => { startDictation(button); });
        }
      } else if (button.dataset.voiceStatus) setVoiceStatus('Tu navegador no ofrece dictado en esta sesión. Puedes escribir la orden.', button);
    });
    if ('speechSynthesis' in window && 'SpeechSynthesisUtterance' in window) {
      scope.querySelectorAll('[data-read-message]').forEach((button) => { button.hidden = false; });
    }
  }

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-read-message]');
    if (!button || !('speechSynthesis' in window)) return;
    if (!readingConsent) { readingConsent = await askConsent('reading'); if (!readingConsent) return; }
    const content = button.closest('.chat-message')?.querySelector('.message-content');
    if (!content) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(content.textContent);
    utterance.lang = 'es-PE';
    const localSpanish = window.speechSynthesis.getVoices().find((voice) => voice.localService && voice.lang.startsWith('es'));
    if (localSpanish) utterance.voice = localSpanish;
    const stop = document.querySelector('[data-stop-reading]');
    if (stop) stop.hidden = false;
    const finished = () => { if (stop) stop.hidden = true; };
    utterance.onend = finished; utterance.onerror = finished;
    window.speechSynthesis.speak(utterance);
  });
  document.querySelector('[data-stop-reading]')?.addEventListener('click', (event) => {
    window.speechSynthesis?.cancel(); event.currentTarget.hidden = true;
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { stopDictation(true); window.speechSynthesis?.cancel(); }
  });
  window.addEventListener('pagehide', () => { stopDictation(true); window.speechSynthesis?.cancel(); });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && recognition) { event.preventDefault(); stopDictation(true); }
  });
  document.addEventListener('sparkx:dictation-cancel', (event) => {
    if (event.detail?.inputID === dictationInput?.id) stopDictation(true);
  });

  document.addEventListener('htmx:configRequest', (event) => {
    const form = event.detail.elt.closest('form');
    const token = form?.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (token) event.detail.headers['X-CSRFToken'] = token;
  });
  document.addEventListener('htmx:afterSwap', (event) => {
    enableVoice(event.detail.target);
    describeFields(event.detail.target);
    const jobs = document.querySelectorAll('#job-region .job-status');
    const seenJobs = new Set();
    jobs.forEach((job) => { if (seenJobs.has(job.id)) job.remove(); else seenJobs.add(job.id); });
    if (jobs.length) document.getElementById('no-jobs')?.remove();
    const updates = [];
    document.querySelectorAll('#job-region .job-status').forEach((job) => {
      if (jobStates.get(job.id) !== job.dataset.jobStatus) {
        const label = job.querySelector('strong')?.textContent || '';
        const kind = job.querySelector('.job-kind')?.textContent || '';
        updates.push(kind + ': ' + label);
        jobStates.set(job.id, job.dataset.jobStatus);
      }
    });
    const announcement = document.getElementById('job-announcement');
    if (announcement && updates.length) announcement.textContent = updates.join('. ');
  });
  document.addEventListener('htmx:oobAfterSwap', (event) => {
    enableVoice(event.detail.target || document);
    const conversation = document.getElementById('chat-messages');
    if (conversation && event.detail.target?.id === 'chat-messages') conversation.scrollTop = conversation.scrollHeight;
  });
  document.addEventListener('htmx:beforeRequest', (event) => {
    const feedback = document.getElementById('connection-feedback');
    if (feedback && event.detail.elt.closest('form')) feedback.hidden = true;
  });
  const connectionError = () => {
    const feedback = document.getElementById('connection-feedback');
    if (!feedback) return;
    feedback.textContent = 'No se pudo completar la solicitud. Tu texto se conserva; revisa la conexión o vuelve a cargar la página.';
    feedback.hidden = false;
  };
  document.addEventListener('htmx:responseError', connectionError);
  document.addEventListener('htmx:sendError', connectionError);
  document.addEventListener('htmx:timeout', connectionError);

  function describeFields(scope = document) {
    scope.querySelectorAll('.field').forEach((field) => {
      const errors = field.querySelector('.errorlist');
      const input = field.querySelector('input,textarea,select');
      const help = field.querySelector('.field-help');
      if (!input) return;
      const descriptions = [];
      if (help) { help.id = input.id + '-help'; descriptions.push(help.id); }
      if (errors) {
        errors.id = input.id + '-errors';
        input.setAttribute('aria-invalid', 'true');
        descriptions.push(errors.id);
      }
      if (descriptions.length) input.setAttribute('aria-describedby', descriptions.join(' '));
    });
  }
  describeFields();
  enableVoice();
  if (status && !Recognition) setVoiceStatus('Tu navegador no ofrece dictado en esta sesión. Puedes escribir tu mensaje.');
})();

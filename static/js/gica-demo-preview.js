/* Bounded form presentation for the human-started pilot. This module fills
 * native controls only; the server and ordinary forms own all persistence. */
(() => {
  'use strict';
  const root = document.querySelector('[data-romeo-presence]');
  const owner = document.body.dataset.voiceUser;
  if (!root || !/^[1-9][0-9]{0,18}$/.test(owner || '')) return;
  const names = Object.freeze({ title:'title', organization:'organization_id', speaker:'speaker_id', brief:'brief', date:'scheduled_dates',
    time:'starts_at', timezone:'timezone', capacity:'capacity', is_synthetic:'is_synthetic', objective:'objective', audience:'audience',
    modality:'modality', duration_minutes:'duration_minutes', location:'location', resources:'resources', constraints:'constraints' });
  const unsafe = /[\p{Cf}\p{Cs}\p{Zl}\p{Zp}\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/u;
  let active = null;
  function lease() {
    return root.isConnected && !document.hidden && document.body.dataset.voiceUser === owner &&
      root.dataset.gicaDemoActive === 'true' && window.SparkXGicaCreation?.hasDraft() === false;
  }
  function end() {
    const run = active;
    if (!run) return;
    active = null; run.typingCleanup?.();
    for (const [node, classes] of run.classes) {
      if (classes === null) node.removeAttribute('class'); else node.setAttribute('class', classes);
    }
    if (run.marker === null) run.form.removeAttribute('data-gica-demo-live'); else run.form.setAttribute('data-gica-demo-live', run.marker);
  }
  function begin(fields, { editing = false } = {}) {
    if (active || !lease() || !fields || typeof fields !== 'object' || Array.isArray(fields)) return false;
    const form = document.querySelector('main form[data-event-block-form]');
    if (!form || form.dataset.gicaGuidedDraft || (editing ? !form.querySelector('[name="expected_revision"]') : !form.matches('[data-gica-event-form="create"]'))) return false;
    for (const name of Object.values(names)) {
      const input = form.elements.namedItem(name);
      if (!(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement || input instanceof HTMLSelectElement) || input.disabled) return false;
    }
    if (typeof fields.title !== 'string' || !fields.title.trim() || fields.title.length > 160 || unsafe.test(fields.title)) return false;
    active = { form, fields: structuredClone(fields), marker: form.getAttribute('data-gica-demo-live'), typed: false,
      classes: [...form.querySelectorAll('[data-gica-form-block],[data-gica-field]')].map((node) => [node, node.getAttribute('class')]) };
    form.dataset.gicaDemoLive = 'true';
    return true;
  }
  function mark(key) {
    const run = active;
    if (!run || !lease() || !run.form.isConnected || !Object.hasOwn(names, key)) return false;
    run.form.querySelectorAll('[data-gica-field]').forEach((node) => node.classList.toggle('gica-field-current', node.dataset.gicaField === key));
    const field = run.form.querySelector(`[data-gica-field="${key}"]`), block = field?.closest('[data-gica-form-block]');
    run.form.querySelectorAll('[data-gica-form-block]').forEach((node) => node.classList.toggle('gica-demo-block-current', node === block));
    document.dispatchEvent(new CustomEvent('sparkx:gica-creation-state', { detail: { stage:'filling', field:key } }));
    return true;
  }
  function fill(key, supplied) {
    const run = active;
    if (!mark(key)) return false;
    const input = run.form.elements.namedItem(names[key]);
    let value = supplied;
    if (value === undefined) {
      const fields = run.fields;
      value = key === 'organization' ? fields.organization_id : key === 'speaker' ? fields.speaker_id : key === 'date' ? fields.date.split('-').reverse().join('/') :
        key === 'time' ? fields.date + 'T' + fields.time : fields[key];
    }
    if (input.type === 'checkbox') {
      if (typeof value !== 'boolean') return false;
      input.checked = value;
    } else {
      if (!['string', 'number'].includes(typeof value) || unsafe.test(String(value)) || String(value).length > 20000) return false;
      if (input.maxLength > 0 && String(value).length > input.maxLength) return false;
      if (input instanceof HTMLSelectElement && !Array.from(input.options).some((option) => option.value === String(value))) return false;
      input.value = String(value);
      if (input.value !== String(value)) return false;
    }
    input.dispatchEvent(new Event('input', { bubbles:true })); input.dispatchEvent(new Event('change', { bubbles:true }));
    return true;
  }
  function typeTitle({ signal } = {}) {
    const run = active;
    if (!run || run.typed || !lease() || signal?.aborted || !mark('title')) return Promise.resolve(false);
    run.typed = true;
    const input = run.form.elements.namedItem('title'), letters = Array.from(run.fields.title);
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    input.value = '';
    return new Promise((resolve) => {
      let timer, index = 0, settled = false;
      const finish = (success = false) => {
        if (settled) return;
        settled = true; clearTimeout(timer); signal?.removeEventListener('abort', finish);
        run.typingCleanup = null; resolve(success === true);
      };
      run.typingCleanup = finish;
      const next = () => {
        if (active !== run || !lease() || !run.form.isConnected || signal?.aborted) { finish(); return; }
        index = reduced ? letters.length : index + 1;
        input.value = letters.slice(0, index).join(''); input.scrollLeft = input.scrollWidth;
        input.dispatchEvent(new Event('input', { bubbles:true }));
        if (index === letters.length) { input.dispatchEvent(new Event('change', { bubbles:true })); finish(true); }
        else timer = setTimeout(next, 42);
      };
      signal?.addEventListener('abort', finish, { once:true }); next();
    });
  }
  document.addEventListener('visibilitychange', () => { if (document.hidden) end(); });
  window.addEventListener('pagehide', end);
  new MutationObserver(() => { if (active && !lease()) end(); }).observe(document.body, { attributes:true, attributeFilter:['data-voice-user'] });
  new MutationObserver(() => { if (active && !lease()) end(); }).observe(root, { attributes:true, attributeFilter:['data-gica-demo-active'] });
  window.SparkXGicaDemoPreview = Object.freeze({ begin, fill, mark, typeTitle, end });
})();
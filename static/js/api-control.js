/* Private controls: explicit key editor and policy selection; no secret storage. */
(() => {
  'use strict';
  const field = document.querySelector('[data-agent-access-form] [name="fallback_preset"]');
  if (field) {
    const acceptance = document.querySelector('[data-agent-access-form] [name="accept_fallback_policy"]');
    const fingerprint = document.querySelector('[data-agent-access-form] [name="expected_fallback_policy_fingerprint"]');
    const update = () => document.querySelectorAll('[data-fallback-policy]').forEach(
      (entry) => {
        entry.hidden = entry.dataset.fallbackPolicy !== field.value;
        if (!entry.hidden && fingerprint) fingerprint.value = entry.dataset.policyFingerprint || '';
      });
    field.addEventListener('change', () => {
      if (acceptance) acceptance.checked = false;
      if (fingerprint) fingerprint.value = '';
      update();
    });
    update();
  }

  const pool = document.querySelector('[data-pool-entry-form]');
  const poolPreset = pool?.querySelector('[name="preset"]');
  const poolAcceptance = pool?.querySelector('[name="accept_policy"]');
  const poolFingerprint = pool?.querySelector('[name="expected_policy_fingerprint"]');
  if (poolPreset) {
    const showPolicy = () => pool.querySelectorAll('[data-pool-policy]').forEach((entry) => {
      entry.hidden = entry.dataset.poolPolicy !== poolPreset.value;
      entry.open = !entry.hidden;
      if (!entry.hidden && poolFingerprint) poolFingerprint.value = entry.dataset.policyFingerprint || '';
    });
    poolPreset.addEventListener('change', () => {
      if (poolAcceptance) poolAcceptance.checked = false;
      showPolicy();
    });
    showPolicy();
  }

  const form = document.querySelector('.api-credential-form');
  const provider = form?.querySelector('[name="provider"]');
  const secret = form?.querySelector('[name="api_key"]');
  const dialog = document.createElement('dialog');
  // Enhance the current server-rendered form, including cached local templates.
  // Older browsers keep the original form instead of losing access to it.
  if (!form || !provider || !secret || form.dataset.editorBound || typeof dialog.showModal !== 'function') return;
  form.dataset.editorBound = 'true';
  dialog.className = 'voice-dialog api-credential-dialog';
  dialog.setAttribute('aria-labelledby', 'api-key-editor-title');
  const title = document.createElement('h2');
  title.id = 'api-key-editor-title';
  const cancel = document.createElement('button');
  cancel.type = 'button';
  cancel.className = 'button button-secondary';
  cancel.textContent = 'Cancelar';
  cancel.addEventListener('click', () => dialog.close());
  const actions = document.createElement('div');
  actions.className = 'dialog-actions';
  actions.append(cancel, form.querySelector('button[type="submit"]'));
  form.append(actions);
  provider.closest('.field').hidden = true;
  dialog.append(title, form);
  document.body.append(dialog);
  let trigger = null;
  const clear = () => { secret.value = ''; };
  dialog.addEventListener('close', () => {
    clear();
    form.reset();
    trigger?.focus();
  });
  dialog.addEventListener('cancel', clear);
  window.addEventListener('pagehide', clear);
  window.addEventListener('pageshow', (event) => {
    if (!event.persisted) return;
    clear();
    if (dialog.open) dialog.close();
  });
  const options = Array.from(provider.options);
  document.querySelectorAll('.api-connection').forEach((row) => {
    const name = row.querySelector('strong')?.textContent.trim();
    const choice = options.find((option) => option.textContent.trim() === name);
    if (!choice) return;
    const configured = row.querySelector('p')?.textContent.trim().startsWith('Disponible');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'button button-small button-secondary';
    button.textContent = configured ? 'Cambiar clave' : 'Añadir clave';
    button.addEventListener('click', () => {
      clear();
      provider.value = choice.value;
      title.textContent = (configured ? 'Cambiar clave de ' : 'Añadir clave de ') + name;
      trigger = button;
      dialog.showModal();
      secret.focus();
    });
    const controls = document.createElement('div');
    controls.className = 'api-connection-actions';
    controls.append(button);
    const disconnect = row.querySelector('form');
    if (disconnect) controls.append(disconnect);
    row.append(controls);
  });
})();

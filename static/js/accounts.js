/* Local account controls. Passwords are never stored, logged or sent by this file. */
(() => {
  'use strict';
  const fields = () => document.querySelectorAll('[data-private-form] input[type="password"], [data-private-form] input[data-password-visible]');
  function conceal(input) {
    input.type = 'password';
    delete input.dataset.passwordVisible;
    document.querySelectorAll('[data-password-toggle]').forEach((button) => {
      if (button.dataset.passwordToggle !== input.id) return;
      button.setAttribute('aria-pressed', 'false');
      button.setAttribute('aria-label', 'Mostrar contraseña');
    });
  }
  document.querySelectorAll('[data-password-toggle]').forEach((button) => { button.hidden = false; });
  function announce(button, message) {
    const feedback = button.closest('form')?.querySelector('[data-password-feedback]');
    if (feedback) feedback.textContent = message;
  }
  const available = typeof window.crypto?.getRandomValues === 'function';
  document.querySelectorAll('[data-password-generate]').forEach((button) => {
    button.hidden = false;
    button.disabled = !available;
    if (!available) announce(button, 'El generador no está disponible en este navegador. Escribe una contraseña de al menos 16 caracteres.');
  });
  document.querySelectorAll('[data-password-copy]').forEach((button) => { button.hidden = false; });

  function generatePassword() {
    const groups = ['abcdefghjkmnpqrstuvwxyz', 'ABCDEFGHJKMNPQRSTUVWXYZ', '23456789', '!@#$%*+-=?'];
    const alphabet = groups.join('');
    const limit = 256 - (256 % alphabet.length);
    // Reject out-of-range bytes and incomplete character groups; no modulo bias.
    for (let attempt = 0; attempt < 128; attempt += 1) {
      let candidate = '';
      while (candidate.length < 20) {
        const bytes = window.crypto.getRandomValues(new Uint8Array(32));
        for (const byte of bytes) {
          if (byte < limit) candidate += alphabet[byte % alphabet.length];
          if (candidate.length === 20) break;
        }
      }
      if (groups.every((group) => Array.from(candidate).some((char) => group.includes(char)))) return candidate;
    }
    throw new Error('Password generation unavailable');
  }

  document.addEventListener('click', async (event) => {
    const toggle = event.target.closest('[data-password-toggle]');
    if (toggle) {
      const input = document.getElementById(toggle.dataset.passwordToggle);
      if (!input) return;
      const visible = input.type === 'password';
      if (!visible) conceal(input);
      else {
        input.type = 'text';
        input.dataset.passwordVisible = 'true';
        toggle.setAttribute('aria-pressed', 'true');
        toggle.setAttribute('aria-label', 'Ocultar contraseña');
      }
      return;
    }
    const generate = event.target.closest('[data-password-generate]');
    if (generate && available) {
      const input = document.getElementById(generate.dataset.passwordGenerate);
      if (!input) return;
      try {
        input.value = generatePassword();
        conceal(input);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        announce(generate, 'Contraseña de 20 caracteres generada. Puedes mostrarla o copiarla para entregarla por un canal privado.');
      } catch (_) { announce(generate, 'No se pudo generar la contraseña. Inténtalo de nuevo o escribe una manualmente.'); }
      return;
    }
    const copy = event.target.closest('[data-password-copy]');
    if (!copy) return;
    const input = document.getElementById(copy.dataset.passwordCopy);
    if (!input?.value) { announce(copy, 'Primero genera o escribe una contraseña.'); return; }
    if (!navigator.clipboard?.writeText) {
      announce(copy, 'Tu navegador no permite copiar automáticamente. Muestra la contraseña y cópiala manualmente.');
      return;
    }
    try {
      await navigator.clipboard.writeText(input.value);
      announce(copy, 'Contraseña copiada. El portapapeles puede conservarla; límpialo después de compartirla.');
    } catch (_) { announce(copy, 'No se pudo copiar. Muestra la contraseña y cópiala manualmente.'); }
  });

  const panel = document.querySelector('[data-account-create]');
  if (panel && typeof HTMLDialogElement !== 'undefined' && typeof HTMLDialogElement.prototype.showModal === 'function') {
    const dialog = document.createElement('dialog');
    dialog.id = panel.id;
    panel.removeAttribute('id');
    dialog.className = 'account-dialog';
    dialog.setAttribute('aria-labelledby', 'account-create-title');
    panel.before(dialog);
    dialog.append(panel);
    let opener = null;
    panel.querySelectorAll('[data-account-create-close]').forEach((button) => { button.hidden = false; });
    function open() {
      if (dialog.open) return;
      dialog.showModal();
      const focus = panel.querySelector('[aria-invalid="true"]') || panel.querySelector('input:not([type="hidden"]), select');
      focus?.focus({ preventScroll: true });
    }
    document.querySelectorAll('[data-account-create-open]').forEach((button) => {
      button.setAttribute('aria-haspopup', 'dialog');
      button.setAttribute('aria-controls', dialog.id);
      button.addEventListener('click', (event) => { event.preventDefault(); opener = button; open(); });
    });
    panel.querySelectorAll('[data-account-create-close]').forEach((button) => { button.addEventListener('click', () => dialog.close()); });
    dialog.addEventListener('close', () => {
      panel.querySelectorAll('input[type="password"], input[data-password-visible]').forEach((input) => { input.value = ''; conceal(input); });
      const feedback = panel.querySelector('[data-password-feedback]');
      if (feedback) feedback.textContent = '';
      if (opener?.isConnected) opener.focus({ preventScroll: true });
    });
    if (panel.dataset.createOpen === 'true') open();
  }
  window.addEventListener('pagehide', () => { fields().forEach((input) => { input.value = ''; conceal(input); }); });
  window.addEventListener('pageshow', (event) => { if (event.persisted) fields().forEach((input) => { input.value = ''; conceal(input); }); });
})();

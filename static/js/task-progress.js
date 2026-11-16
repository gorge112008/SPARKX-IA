/* Explicit task commands keep drafts on errors and move focus after a saved change. */
(() => {
  'use strict';
  const pending = new Map();
  const formFor = (event) => event.detail?.elt?.closest('form[data-task-update]');
  const enableCancel = (scope) => scope.querySelectorAll('[data-task-cancel]').forEach((button) => { button.hidden = false; });
  const focus = (target) => target?.focus({ preventScroll: true });

  function continueWith(row) {
    const id = row.querySelector('[data-task-next-id]')?.dataset.taskNextId;
    const next = id && document.getElementById(id);
    const editor = next?.querySelector('[data-task-followup]');
    if (!editor || next.querySelector('[data-task-state="completed"]')) return false;
    // Opening a pending editor must never reset the user's existing draft.
    editor.open = true;
    const summary = editor.querySelector('summary');
    focus(summary);
    summary?.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'nearest', inline: 'nearest',
    });
    return true;
  }

  document.addEventListener('click', (event) => {
    const cancel = event.target.closest('[data-task-cancel]');
    if (cancel) {
      const editor = cancel.closest('[data-task-followup]');
      editor.open = false;
      focus(editor.querySelector('summary'));
      return;
    }
    const link = event.target.closest('[data-task-next-id]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (continueWith(link.closest('[data-task-row]'))) event.preventDefault();
  });

  document.addEventListener('htmx:beforeRequest', (event) => {
    const form = formFor(event);
    if (!form) return;
    const row = form.closest('[data-task-row]');
    if (!row) return;
    row.querySelector('[data-task-network-error]')?.remove();
    const scroll = row.closest('.plan-scroll');
    pending.set(row.id, {
      scroll, top: scroll?.scrollTop,
      instructions: row.querySelector('[data-task-instructions]')?.open,
    });
  });

  document.addEventListener('htmx:afterSwap', (event) => {
    const id = event.detail.target?.id;
    const state = pending.get(id);
    if (!state) return;
    const row = document.getElementById(id);
    const result = row?.querySelector('[data-task-result]');
    if (!row || !result) return;
    // Only the requested row can consume its pending state; the OOB totals cannot advance twice.
    pending.delete(id);
    enableCancel(row);
    const instructions = row.querySelector('[data-task-instructions]');
    const editor = row.querySelector('[data-task-followup]');
    if (state.scroll?.isConnected) state.scroll.scrollTop = state.top;
    if (result.dataset.taskResult !== 'saved') {
      if (instructions) instructions.open = Boolean(state.instructions);
      if (editor) editor.open = true;
      focus(row.querySelector('[aria-invalid="true"]') || result);
      return;
    }
    if (editor) editor.open = false;
    const completed = Boolean(row.querySelector('[data-task-state="completed"]'));
    if (instructions) instructions.open = completed ? false : Boolean(state.instructions);
    if (completed && continueWith(row)) return;
    const allCompleted = completed && document.querySelector('[data-task-completion]');
    focus(allCompleted || result);
  });

  function failedRequest(event) {
    const form = formFor(event);
    const row = form?.closest('[data-task-row]');
    if (!row || !pending.has(row.id)) return;
    pending.delete(row.id);
    const editor = row.querySelector('[data-task-followup]');
    if (editor) editor.open = true;
    const alert = document.createElement('p');
    alert.className = 'task-update-feedback is-error';
    alert.dataset.taskNetworkError = '';
    alert.setAttribute('role', 'alert');
    alert.tabIndex = -1;
    alert.textContent = 'No se pudo confirmar el cambio. Tu borrador se conserva; revisa la conexión e inténtalo de nuevo.';
    editor?.before(alert);
    focus(alert);
  }
  ['htmx:sendError', 'htmx:timeout', 'htmx:responseError', 'htmx:sendAbort'].forEach((name) => document.addEventListener(name, failedRequest));
  document.addEventListener('htmx:afterRequest', (event) => {
    if (!event.detail.successful) failedRequest(event);
  });
  document.addEventListener('sparkx:gica-navigation-complete', () => enableCancel(document));
  enableCancel(document);
})();

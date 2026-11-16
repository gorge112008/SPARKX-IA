/* Local view switching only. All execution observations come from the server. */
(() => {
  'use strict';
  function initialize() {
  const panel = document.querySelector('.romeo-panel');
  if (!panel || panel.dataset.romeoViewsReady === 'true') return;
  panel.dataset.romeoViewsReady = 'true';
  const events = new AbortController();
  document.addEventListener('sparkx:gica-navigation-complete', () => { if (!panel.isConnected) events.abort(); }, { signal:events.signal });
  const tabs = Array.from(panel.querySelectorAll('[data-romeo-tab]'));
  let submitted = false;
  let observed = '';
  const show = (name) => {
    tabs.forEach((tab) => { const selected = tab.dataset.romeoTab === name;
      tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1; });
    panel.querySelectorAll('[data-romeo-view]').forEach((view) => { view.hidden = view.dataset.romeoView !== name; });
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => show(tab.dataset.romeoTab));
    tab.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 :
        (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      show(tabs[next].dataset.romeoTab); tabs[next].focus();
    });
  });
  document.addEventListener('htmx:beforeRequest', (event) => {
    const form = event.detail.elt.closest('form');
    if (form?.id === 'proposal-form' || form?.closest('.chat-composer')) submitted = true;
  }, { signal:events.signal });
  document.addEventListener('htmx:afterSwap', (event) => {
    if (event.detail.target.id !== 'job-region' || !submitted) return;
    submitted = false;
    show(event.detail.target.querySelector('.job-status') ? 'follow' : 'chat');
    panel.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }, { signal:events.signal });
  document.addEventListener('htmx:oobAfterSwap', () => {
    const view = panel.querySelector('#romeo-follow-view');
    const rows = view?.querySelectorAll('[data-romeo-stage]');
    const row = rows?.[rows.length - 1];
    if (!row) return;
    const signature = row.dataset.romeoStage + row.querySelector('time')?.dateTime;
    if (observed === signature) return;
    observed = signature;
    if (!view.hidden) view.scrollTo({ top: view.scrollTop + row.getBoundingClientRect().top - view.getBoundingClientRect().top - 72, behavior: 'auto' });
  }, { signal:events.signal });
  panel.addEventListener('click', (event) => {
    if (event.target.closest('.romeo-result')?.textContent.trim() === 'Ver conversación') {
      event.preventDefault(); show('chat');
    }
  });
  document.addEventListener('sparkx:romeo-result', (event) => {
    const id = event.detail?.localId;
    if (typeof id !== 'string' || !/^[1-9][0-9]{0,19}$/.test(id)
        || document.activeElement?.matches('input,textarea,select,[contenteditable="true"]')) return;
    const reply = panel.querySelector(`[data-romeo-local-result="${id}"]`);
    if (!reply) return;
    show('chat');
    const view = panel.querySelector('#romeo-chat-view');
    if (view) view.scrollTop += reply.getBoundingClientRect().top - view.getBoundingClientRect().top - 20;
  }, { signal:events.signal });
  show(new URLSearchParams(location.search).has('romeo_result') ? 'chat' : 'follow');
  }
  document.addEventListener('sparkx:gica-navigation-complete', initialize);
  document.addEventListener('htmx:afterSwap', initialize);
  initialize();
})();

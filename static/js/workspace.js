/* Accessible event views. All sections remain ordinary anchors without JS. */
(() => {
  'use strict';
  let boundWorkspace = null, lifecycle = null;
  function initialize() {
    const workspace = document.querySelector('[data-workspace]');
    if (boundWorkspace === workspace) return;
    lifecycle?.abort(); lifecycle = new AbortController(); boundWorkspace = workspace;
    const listen = (target, name, handler) => target.addEventListener(name, handler, { signal:lifecycle.signal });
    const navigation = workspace?.querySelector('[data-workspace-nav]');
    if (!workspace || !navigation) return;
    const panels = new Map(Array.from(workspace.querySelectorAll('[data-workspace-panel]'),
      (panel) => [panel.dataset.workspacePanel, panel]));
    const links = Array.from(navigation.querySelectorAll('[data-panel-link]'));
    const columns = workspace.querySelector('.workspace-columns');
    const primary = workspace.querySelector('.workspace-primary');
    const expand = workspace.querySelector('[data-agent-expand]');
    let active = null;
    let expanded = false;
    let revealWork = false;

    function panelForHash(hash) {
      if (hash.startsWith('#task-') && document.getElementById(hash.slice(1))?.closest('[data-workspace-panel="preparation"]')) return 'preparation';
      const known = {
        '#plan': 'plan', '#agenda': 'plan', '#preparation': 'preparation', '#demo-context': 'plan', '#proposals': 'proposals',
        '#proposal-form': 'proposals', '#event-context': 'proposals',
        '#candidate': 'proposals', '#activity': 'activity'
      };
      if (known[hash]) return known[hash];
      return panels.has(workspace.dataset.defaultPanel) ? workspace.dataset.defaultPanel : 'plan';
    }
    function setExpanded(value) {
      expanded = value;
      columns?.classList.toggle('is-agent-expanded', value);
      if (primary) primary.hidden = value;
      if (expand) {
        expand.setAttribute('aria-pressed', String(value));
        const label = value ? 'Volver al panel del evento' : 'Ampliar agente del evento';
        expand.setAttribute('aria-label', label);
        expand.title = label;
      }
    }
    function activate(id, hash = '', updateURL = false) {
      if (!panels.has(id)) return;
      if (expanded) setExpanded(false);
      const previousPanel = panels.get(active);
      const changed = active !== id;
      active = id;
      panels.forEach((panel, key) => { panel.hidden = key !== id; });
      links.forEach((link) => {
        const selected = link.dataset.panelLink === id;
        link.classList.toggle('is-current', selected);
        link.setAttribute('aria-selected', String(selected));
        link.tabIndex = selected ? 0 : -1;
        if (selected) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
      workspace.dataset.activePanel = id;
      if (updateURL) {
        const url = new URL(window.location.href);
        url.hash = hash || id;
        window.history.pushState(null, '', url);
      }
      if (changed) document.dispatchEvent(new CustomEvent('sparkx:panel-change', {
        detail: { panel: panels.get(id), previousPanel }
      }));
    }
    function visit(hash, moveFocus = false) {
      activate(panelForHash(hash), hash, true);
      if (!moveFocus) return;
      const target = document.getElementById(hash.slice(1));
      if (!target) return;
      if (target.tagName === 'DETAILS') target.open = true;
      const focus = target.tagName === 'DETAILS' ? target.querySelector('summary') : target;
      if (!focus.hasAttribute('tabindex') && !focus.matches('a,button,input,textarea,select')) focus.tabIndex = -1;
      focus.focus({ preventScroll: true });
      target.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    }

    navigation.setAttribute('role', 'tablist');
    links.forEach((link) => {
      const id = link.dataset.panelLink;
      link.id ||= 'nav-' + id;
      link.setAttribute('role', 'tab');
      link.setAttribute('aria-controls', panels.get(id).id);
      panels.get(id).setAttribute('role', 'tabpanel');
      panels.get(id).setAttribute('aria-labelledby', link.id);
    });
    workspace.dataset.workspaceEnhanced = 'true';
    activate(panelForHash(window.location.hash));

    workspace.addEventListener('click', (event) => {
      const link = event.target.closest('a[href^="#"]');
      if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const hash = link.getAttribute('href');
      if (!['#plan','#agenda','#preparation','#demo-context','#proposals','#proposal-form','#event-context','#candidate','#activity'].includes(hash)) return;
      event.preventDefault();
      visit(hash, !link.matches('[data-panel-link]'));
    });
    navigation.addEventListener('keydown', (event) => {
      const current = event.target.closest('[data-panel-link]');
      if (!current) return;
      let index = links.indexOf(current);
      if (event.key === 'ArrowRight') index = (index + 1) % links.length;
      else if (event.key === 'ArrowLeft') index = (index - 1 + links.length) % links.length;
      else if (event.key === 'Home') index = 0;
      else if (event.key === 'End') index = links.length - 1;
      else if (event.key === ' ') { event.preventDefault(); current.click(); return; }
      else return;
      event.preventDefault();
      const next = links[index];
      activate(next.dataset.panelLink, next.getAttribute('href'), true);
      next.focus({ preventScroll: true });
    });
    const restore = () => activate(panelForHash(window.location.hash));
    listen(window, 'hashchange', restore);
    listen(window, 'popstate', restore);
    if (expand) {
      expand.hidden = false;
      expand.addEventListener('click', () => setExpanded(!expanded));
      listen(document, 'keydown', (event) => {
        if (event.key === 'Escape' && expanded) { setExpanded(false); expand.focus({ preventScroll: true }); }
      });
    }
    listen(document, 'htmx:beforeRequest', (event) => {
      const form = event.detail.elt.closest('form');
      if (form?.id === 'proposal-form' || form?.closest('.chat-composer')) revealWork = true;
    });
    listen(document, 'htmx:afterSwap', (event) => {
      if (revealWork && event.detail.target.id === 'job-region') {
        revealWork = false;
        activate('activity', '#activity', true);
      }
    });
    ['htmx:responseError','htmx:sendError','htmx:timeout'].forEach((name) => {
      listen(document, name, () => { revealWork = false; });
    });
  }
  document.addEventListener('sparkx:gica-navigation-complete', initialize);
  document.addEventListener('htmx:afterSwap', initialize);
  window.addEventListener('pagehide', () => lifecycle?.abort());
  window.addEventListener('pageshow', (event) => { if (event.persisted) { boundWorkspace = null; initialize(); } });
  initialize();
})();

/* Motion 14.10.1, self-hosted. Hyrup-inspired masks, safe text and CSS gestures.
   Entries are finite; live updates and editable fields are never entrance targets. */
(() => {
  'use strict';
  const preference = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  const engine = window.Motion;
  const seen = new WeakSet();
  const prepared = new WeakMap();
  const observers = new Map();
  const running = new Map();
  const selector = '[data-reveal]';
  const quiet = '[aria-live], [role="alert"], #chat-messages, .job-status, .chat-composer, .voice-dialog';
  const available = typeof engine?.animateMini === 'function' || typeof Element.prototype.animate === 'function';

  function elements(scope, query = selector) {
    const result = [];
    if (scope.matches?.(query)) result.push(scope);
    scope.querySelectorAll?.(query).forEach((element) => result.push(element));
    return result;
  }
  function eligible(element) {
    if (element.closest('[hidden], ' + quiet) || element.matches('form')) return false;
    const block = element.parentElement?.closest('[data-reveal="block"]');
    return !block && (element.dataset.reveal === 'block' || /^H[123]$/.test(element.tagName));
  }
  function prepareButtons(scope) {
    elements(scope, '.button, .icon-button').forEach((button) => {
      if (button.closest('[hidden], ' + quiet) || button.matches('[data-dictate], [data-read]')) return;
      button.classList.add('motion-button');
      if (button.matches('.icon-button') || button.querySelector('.motion-label-mask') ||
          button.hasAttribute('aria-labelledby')) return;
      // Enhance only plain text labels and decorative SVGs; retain the control itself.
      const nodes = Array.from(button.childNodes);
      const text = nodes.filter((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
      if (text.length !== 1 || nodes.some((node) => node.nodeType === Node.ELEMENT_NODE &&
          !node.matches('svg[aria-hidden="true"]'))) return;
      const label = text[0].textContent.trim();
      const mask = document.createElement('span');
      const content = document.createElement('span');
      mask.className = 'motion-label-mask';
      mask.setAttribute('aria-hidden', 'true');
      content.className = 'motion-label-text';
      content.dataset.motionCopy = label;
      // The CSS copy is decorative. The control exposes its original name once.
      if (!button.hasAttribute('aria-label')) button.setAttribute('aria-label', label);
      text[0].replaceWith(mask);
      content.append(text[0]); mask.append(content);
    });
  }
  function targets(element) {
    if (element.dataset.reveal === 'block' || element.childElementCount) return [element];
    const originalNodes = Array.from(element.childNodes);
    const text = element.textContent;
    // Hyrup's H1 uses a whole-block mask; split small section headings by words.
    const parts = element.dataset.reveal === 'section' ? text.match(/\S+|\s+/g) || [] : [text];
    const fragment = document.createDocumentFragment();
    const items = [];
    parts.forEach((part) => {
      if (!part.trim()) { fragment.append(document.createTextNode(part)); return; }
      const mask = document.createElement('span');
      const content = document.createElement('span');
      mask.className = 'reveal-mask'; content.className = 'reveal-text';
      content.textContent = part; mask.append(content); fragment.append(mask); items.push(content);
    });
    const nodes = Array.from(fragment.childNodes);
    element.replaceChildren(fragment);
    prepared.set(element, { originalNodes, nodes, text });
    return items;
  }
  function unmask(element) {
    const state = prepared.get(element);
    if (!state) return;
    prepared.delete(element);
    // Do not overwrite content that another part of the app changed meanwhile.
    if (element.textContent === state.text && element.childNodes.length === state.nodes.length &&
        state.nodes.every((node, index) => element.childNodes[index] === node)) {
      element.replaceChildren(...state.originalNodes);
    }
  }
  function restore(record) {
    record.original.forEach(({ target, transform, opacity }) => {
      if (transform) target.style.transform = transform; else target.style.removeProperty('transform');
      if (opacity) target.style.opacity = opacity; else target.style.removeProperty('opacity');
      // Avoid later HTML/style snapshot restoration of an empty inline attribute.
      if (target.hasAttribute('style') && !target.getAttribute('style').trim()) target.removeAttribute('style');
    });
  }
  function settle(element, record, interrupted = false) {
    if (running.get(element) !== record) return;
    running.delete(element);
    clearTimeout(record.watchdog);
    record.controls.forEach((control) => { try { control.cancel(); } catch (_) { /* Already settled. */ } });
    restore(record);
    unmask(element);
    if (interrupted) seen.delete(element);
  }
  function reveal(element, delay = 0) {
    if (!available || seen.has(element) || preference?.matches || document.hidden || !eligible(element)) return;
    observers.get(element)?.(); observers.delete(element);
    const title = element.dataset.reveal === 'title';
    const block = element.dataset.reveal === 'block';
    const items = targets(element);
    if (!items.length) { unmask(element); return; }
    const duration = title ? 0.88 : block ? 0.55 : 0.66;
    const step = !title && !block ? Math.min(0.065, 0.28 / Math.max(items.length - 1, 1)) : 0;
    const baseDelay = (title ? 0.12 : 0.05) + delay;
    const record = {
      controls: [], watchdog: null,
      original: items.map((target) => ({ target, transform: target.style.transform, opacity: target.style.opacity }))
    };
    running.set(element, record); seen.add(element);
    let remaining = items.length;
    const finished = () => { if (--remaining === 0) settle(element, record); };
    try {
      items.forEach((target, index) => {
        const options = { duration, delay: baseDelay + index * step, ease: [0.4, 0, 0.4, 1] };
        const frames = {
          transform: [block ? 'translate3d(0, 16px, 0)' : title ? 'translate3d(0, 105%, 0) scaleY(1.06)' : 'translate3d(0, 112%, 0)', 'translate3d(0, 0, 0) scaleY(1)'],
          opacity: [block ? 0.35 : 1, 1]
        };
        let control;
        if (typeof engine?.animateMini === 'function') {
          control = engine.animateMini(target, frames, options);
          control.then(finished, finished);
        } else {
          const animation = target.animate([
            { transform: frames.transform[0], opacity: frames.opacity[0] },
            { transform: frames.transform[1], opacity: 1 }
          ], { duration: duration * 1000, delay: options.delay * 1000, easing: 'cubic-bezier(0.4, 0, 0.4, 1)', fill: 'backwards' });
          control = animation; animation.finished.then(finished, finished);
        }
        record.controls.push(control);
      });
      // A suspended timeline or failed provider must leave all content readable.
      record.watchdog = setTimeout(() => settle(element, record), 2200 + delay * 1000);
    } catch (_) { settle(element, record); }
  }
  function prune() {
    observers.forEach((disconnect, element) => {
      if (!element.isConnected) { disconnect(); observers.delete(element); }
    });
    Array.from(running).forEach(([element, record]) => {
      if (!element.isConnected) settle(element, record);
    });
  }
  function initialize(scope = document) {
    prune(); prepareButtons(scope);
    if (!available || preference?.matches || document.hidden) return;
    let index = 0;
    elements(scope).forEach((element) => {
      if (!eligible(element) || seen.has(element) || observers.has(element)) return;
      const delay = Math.min(index++, 3) * 0.04;
      if (typeof engine?.inView === 'function') {
        const disconnect = engine.inView(element, () => { reveal(element, delay); }, { amount: 0.1, margin: '0px 0px -16px 0px' });
        observers.set(element, disconnect);
      } else if (typeof IntersectionObserver === 'function') {
        const observer = new IntersectionObserver((entries) => {
          entries.forEach((entry) => { if (entry.isIntersecting) reveal(entry.target, delay); });
        }, { threshold: 0.1, rootMargin: '0px 0px -16px 0px' });
        observer.observe(element); observers.set(element, () => observer.disconnect());
      } else reveal(element, delay);
    });
  }
  function stop(interrupted = true) {
    observers.forEach((disconnect) => disconnect()); observers.clear();
    Array.from(running).forEach(([element, record]) => settle(element, record, interrupted));
  }
  function reset(scope) {
    elements(scope).forEach((element) => {
      const record = running.get(element);
      if (record) settle(element, record);
      observers.get(element)?.(); observers.delete(element); seen.delete(element);
    });
  }
  function syncReplay() {
    document.querySelectorAll('[data-motion-replay]').forEach((button) => {
      button.hidden = !available;
      button.disabled = !!preference?.matches;
      button.title = preference?.matches ? 'Movimiento reducido activado en tu dispositivo' : 'Repetir animación de entrada';
    });
  }
  document.addEventListener('click', (event) => {
    if (!event.target.closest('[data-motion-replay]') || preference?.matches) return;
    reset(document); initialize();
  });
  document.addEventListener('sparkx:panel-change', (event) => {
    if (event.detail.previousPanel) reset(event.detail.previousPanel);
    reset(event.detail.panel); initialize(event.detail.panel);
  });
  document.addEventListener('htmx:beforeCleanupElement', (event) => {
    if (event.detail.elt) reset(event.detail.elt);
  });
  document.addEventListener('htmx:afterSwap', (event) => {
    // outerHTML keeps detail.target pointing to the detached, pre-swap node.
    const scope = event.detail.elt?.isConnected ? event.detail.elt : event.target;
    if (scope?.isConnected) initialize(scope);
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); else initialize(); });
  const change = () => { syncReplay(); if (preference.matches) stop(); else initialize(); };
  if (preference?.addEventListener) preference.addEventListener('change', change);
  else preference?.addListener?.(change);
  window.addEventListener('beforeprint', () => stop(false));
  window.addEventListener('afterprint', () => initialize());
  window.addEventListener('pagehide', () => stop());
  window.addEventListener('pageshow', (event) => { if (event.persisted) reset(document); initialize(); });
  // Theme/voice setup may reveal controls at DOMContentLoaded after deferred scripts.
  document.addEventListener('DOMContentLoaded', () => initialize(), { once: true });
  syncReplay(); initialize();
})();

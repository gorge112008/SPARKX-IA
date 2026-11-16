/* Calendar links remain ordinary server navigation when JavaScript is absent. */
(() => {
  'use strict';
  function initialize(scope = document) {
    const grid = scope.querySelector('[data-calendar-grid]');
    if (!grid || grid.dataset.calendarBound) return;
    grid.dataset.calendarBound = 'true';
    const days = Array.from(grid.querySelectorAll('[data-calendar-day]'));
    grid.addEventListener('keydown', (event) => {
      const current = event.target.closest('[data-calendar-day]');
      if (!current || event.altKey || event.ctrlKey || event.metaKey) return;
      const index = days.indexOf(current);
      let target = index;
      if (event.key === 'ArrowRight') target += 1;
      else if (event.key === 'ArrowLeft') target -= 1;
      else if (event.key === 'ArrowDown') target += 7;
      else if (event.key === 'ArrowUp') target -= 7;
      else if (event.key === 'Home') target -= index % 7;
      else if (event.key === 'End') target += 6 - index % 7;
      else return;
      event.preventDefault();
      days[Math.max(0, Math.min(days.length - 1, target))]?.focus();
    });
  }
  document.addEventListener('htmx:afterSwap', (event) => initialize(event.detail.target || document));
  initialize();
})();

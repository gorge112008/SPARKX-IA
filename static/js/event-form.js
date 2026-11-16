/* Progressive controls for the real, server-validated event form. No network IO. */
(() => {
  'use strict';
  const presets = Object.freeze({ capacity: Object.freeze(['20', '50', '100']), timezone: Object.freeze(['America/Lima']) });
  const selectNames = Object.freeze(['organization_id', 'speaker_id', 'timezone', 'modality']);
  const calendars = new WeakMap();
  const pad = (value) => String(value).padStart(2, '0');
  const emit = (control) => {
    control.dispatchEvent(new Event('input', { bubbles: true }));
    control.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const locked = (form, control) => !!form.dataset.gicaGuidedDraft || form.dataset.gicaDemoPreview === 'true' || control.disabled || control.readOnly === true;
  function closeSelect(wrapper, restoreFocus = false) {
    const button = wrapper.querySelector('[data-event-select-toggle]');
    wrapper.querySelector('[data-event-select-options]').hidden = true;
    button.setAttribute('aria-expanded', 'false');
    if (restoreFocus) button.focus({ preventScroll: true });
  }
  function enhanceSelect(form, name) {
    const control = form.elements.namedItem(name);
    if (!(control instanceof HTMLSelectElement) || control.dataset.eventSelectEnhanced) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'event-select'; wrapper.dataset.eventSelect = name;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'event-select-toggle'; button.dataset.eventSelectToggle = name;
    button.id = `${control.id}-toggle`; button.setAttribute('aria-haspopup', 'listbox'); button.setAttribute('aria-expanded', 'false');
    const label = form.querySelector(`label[for="${control.id}"]`);
    if (label) { label.id ||= `${control.id}-label`; button.setAttribute('aria-labelledby', `${label.id} ${button.id}`); }
    const list = document.createElement('div');
    list.className = 'event-select-options'; list.dataset.eventSelectOptions = name;
    list.id = `${control.id}-options`; list.setAttribute('role', 'listbox'); list.setAttribute('aria-label', label?.textContent || name); list.hidden = true;
    button.setAttribute('aria-controls', list.id);
    for (const option of control.options) {
      const item = document.createElement('button'); item.type = 'button'; item.setAttribute('role', 'option');
      item.dataset.eventSelectOption = name; item.dataset.eventSelectValue = option.value;
      item.textContent = option.textContent; item.disabled = option.disabled; item.setAttribute('aria-selected', String(option.selected));
      list.append(item);
    }
    control.before(wrapper); wrapper.append(control, button, list); control.hidden = true;
    control.dataset.eventSelectEnhanced = 'true';
  }
  function currentDate(form) {
    const parsed = /^(20\d{2})-(\d{2})-(\d{2})T/.exec(String(form.elements.namedItem('starts_at')?.value || ''));
    return parsed ? new Date(Number(parsed[1]), Number(parsed[2]) - 1, Number(parsed[3]), 12) : new Date();
  }
  function renderCalendar(form) {
    const state = calendars.get(form), panel = form.querySelector('[data-event-date-panel]');
    if (!state || !panel) return;
    panel.querySelector('[data-event-date-heading]').textContent = new Intl.DateTimeFormat('es-PE', { month: 'long', year: 'numeric' }).format(state.month);
    const grid = panel.querySelector('[data-event-date-grid]'); grid.replaceChildren();
    const year = state.month.getFullYear(), month = state.month.getMonth();
    const offset = (new Date(year, month, 1).getDay() + 6) % 7;
    for (let index = 0; index < offset; index++) { const blank = document.createElement('span'); blank.setAttribute('aria-hidden', 'true'); grid.append(blank); }
    const selected = String(form.elements.namedItem('starts_at')?.value || '').slice(0, 10);
    const disabled = locked(form, form.elements.namedItem('starts_at')), referenceYear = new Date().getFullYear();
    for (let day = 1; day <= new Date(year, month + 1, 0).getDate(); day++) {
      const value = `${year}-${pad(month + 1)}-${pad(day)}`, button = document.createElement('button');
      button.type = 'button'; button.dataset.eventDateDay = value; button.textContent = String(day);
      button.setAttribute('aria-label', new Intl.DateTimeFormat('es-PE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(year, month, day, 12)));
      button.setAttribute('aria-pressed', String(value === selected)); button.disabled = disabled || year < referenceYear || year > 2099;
      grid.append(button);
    }
    panel.querySelector('[data-event-date-month="prev"]').disabled = disabled || (year <= referenceYear && month === 0);
    panel.querySelector('[data-event-date-month="next"]').disabled = disabled || (year >= 2099 && month === 11);
  }
  function update(form) {
    if (!(form instanceof HTMLFormElement) || !form.matches('[data-event-block-form]')) return;
    for (const name of selectNames) {
      enhanceSelect(form, name);
      const control = form.elements.namedItem(name), wrapper = form.querySelector(`[data-event-select="${name}"]`);
      if (!wrapper || !control) continue;
      const toggle = wrapper.querySelector('[data-event-select-toggle]');
      toggle.textContent = control.selectedOptions[0]?.textContent || 'Selecciona una opción'; toggle.disabled = locked(form, control);
      for (const item of wrapper.querySelectorAll('[data-event-select-option]')) item.setAttribute('aria-selected', String(item.dataset.eventSelectValue === control.value));
      if (toggle.disabled) closeSelect(wrapper);
    }
    for (const button of form.querySelectorAll('[data-event-preset]')) {
      const name = button.dataset.eventPreset, value = button.dataset.eventPresetValue;
      const control = form.elements.namedItem(name);
      if (!Object.hasOwn(presets, name) || !presets[name].includes(value) || !(control instanceof HTMLInputElement || control instanceof HTMLSelectElement)) continue;
      button.disabled = locked(form, control);
      button.setAttribute('aria-pressed', String(control.value === value));
    }
    const start = form.elements.namedItem('starts_at'), dateControls = form.querySelector('[data-event-date-controls]');
    if (dateControls && start instanceof HTMLInputElement) {
      dateControls.hidden = false;
      if (!calendars.has(form)) { const date = currentDate(form); calendars.set(form, { month: new Date(date.getFullYear(), date.getMonth(), 1, 12) }); }
      const toggle = form.querySelector('[data-event-date-toggle]'), time = form.querySelector('[data-event-time]');
      toggle.disabled = time.disabled = locked(form, start);
      if (document.activeElement !== time) time.value = start.value.slice(11, 16);
      if (toggle.disabled) { form.querySelector('[data-event-date-panel]').hidden = true; toggle.setAttribute('aria-expanded', 'false'); }
    }
  }
  function updateAll() { document.querySelectorAll('form[data-event-block-form]').forEach(update); }
  document.addEventListener('click', (event) => {
    document.querySelectorAll('.event-select').forEach((wrapper) => { if (!wrapper.contains(event.target)) closeSelect(wrapper); });
    const button = event.target.closest?.('button');
    const form = button?.closest('form[data-event-block-form]');
    if (!form || !form.isConnected) return;
    update(form);
    if (button.disabled) return;
    if (button.hasAttribute('data-event-select-toggle')) {
      const wrapper = button.closest('.event-select'), list = wrapper.querySelector('[data-event-select-options]');
      list.hidden = !list.hidden; button.setAttribute('aria-expanded', String(!list.hidden));
      if (!list.hidden) { const selected = list.querySelector('[aria-selected="true"]'); if (selected) list.scrollTop = selected.offsetTop - list.offsetTop; }
    } else if (button.hasAttribute('data-event-select-option')) {
      const name = button.dataset.eventSelectOption, control = form.elements.namedItem(name);
      if (!selectNames.includes(name) || !(control instanceof HTMLSelectElement) || locked(form, control)) return;
      const option = Array.from(control.options).find((item) => item.value === button.dataset.eventSelectValue && !item.disabled);
      if (!option) return;
      control.value = option.value; emit(control); closeSelect(button.closest('.event-select'), true); update(form);
    } else if (button.hasAttribute('data-event-preset')) {
      const name = button.dataset.eventPreset, value = button.dataset.eventPresetValue, control = form.elements.namedItem(name);
      if (!Object.hasOwn(presets, name) || !presets[name].includes(value) || !(control instanceof HTMLInputElement || control instanceof HTMLSelectElement) || locked(form, control)) return;
      control.value = value; emit(control); control.focus({ preventScroll: true }); update(form);
    } else if (button.hasAttribute('data-event-date-toggle')) {
      const panel = form.querySelector('[data-event-date-panel]'); panel.hidden = !panel.hidden;
      button.setAttribute('aria-expanded', String(!panel.hidden)); if (!panel.hidden) renderCalendar(form);
    } else if (button.hasAttribute('data-event-date-month')) {
      const state = calendars.get(form); state.month.setMonth(state.month.getMonth() + (button.dataset.eventDateMonth === 'prev' ? -1 : 1)); renderCalendar(form);
    } else if (button.hasAttribute('data-event-date-day')) {
      const start = form.elements.namedItem('starts_at'), dates = form.elements.namedItem('scheduled_dates');
      if (locked(form, start)) return;
      const day = button.dataset.eventDateDay, time = form.querySelector('[data-event-time]');
      if (!/^20\d{2}-\d{2}-\d{2}$/.test(day) || !day.startsWith(String(calendars.get(form).month.getFullYear()))) return;
      start.value = `${day}T${time.value || '09:00'}`;
      const [year, month, date] = day.split('-'); dates.value = `${date}/${month}/${year}`;
      emit(start); emit(dates);
      form.querySelector('[data-event-date-panel]').hidden = true; form.querySelector('[data-event-date-toggle]').setAttribute('aria-expanded', 'false');
      time.focus({ preventScroll: true }); update(form);
    }
  });
  document.addEventListener('input', (event) => {
    const form = event.target.closest?.('form[data-event-block-form]');
    if (form && event.target.matches('[data-event-time]')) {
      const control = form.elements.namedItem('starts_at');
      if (event.target.validity.valid && event.target.value && control.value && !locked(form, control)) { control.value = `${control.value.slice(0, 10)}T${event.target.value}`; emit(control); }
    }
    update(event.target.form);
  });
  document.addEventListener('change', (event) => update(event.target.form));
  document.addEventListener('keydown', (event) => {
    const wrapper = event.target.closest?.('.event-select');
    if (!wrapper) return;
    const list = wrapper.querySelector('[data-event-select-options]'), toggle = wrapper.querySelector('[data-event-select-toggle]');
    if (event.key === 'Escape' && !list.hidden) { event.preventDefault(); closeSelect(wrapper, true); }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (toggle.disabled) return;
      event.preventDefault(); list.hidden = false; toggle.setAttribute('aria-expanded', 'true');
      const items = Array.from(list.querySelectorAll('button:not(:disabled)'));
      const index = items.indexOf(document.activeElement), next = index < 0 ? items.findIndex((item) => item.getAttribute('aria-selected') === 'true') : index + (event.key === 'ArrowDown' ? 1 : -1);
      items[Math.max(0, Math.min(items.length - 1, next))]?.focus({ preventScroll: false });
    }
  });
  document.addEventListener('sparkx:gica-creation-state', updateAll);
  document.addEventListener('sparkx:gica-navigation-complete', updateAll);
  document.addEventListener('sparkx:romeo-action-layout', updateAll);
  document.addEventListener('sparkx:gica-demo-end', updateAll);
  updateAll();
})();

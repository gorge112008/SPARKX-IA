/* Apply a local appearance preference before CSS paints. No account data is stored. */
(() => {
  'use strict';
  const key = 'sparkx.theme';
  const root = document.documentElement;
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  const brandIcon = document.querySelector('link[rel="icon"]');
  const iconSource = brandIcon?.href;
  let brandImage = null;
  function updateBrandIcon() {
    if (!brandIcon || !iconSource) return;
    let source;
    try { source = new URL(iconSource, window.location.href); } catch (_) { return; }
    if (source.origin !== window.location.origin || !source.pathname.endsWith('/brand/arquigica-monogram.png')) return;
    if (!brandImage) {
      brandImage = new Image();
      brandImage.onload = updateBrandIcon;
      brandImage.src = source.href;
      return;
    }
    if (!brandImage.complete || !brandImage.naturalWidth) return;
    try {
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 64;
      const paint = canvas.getContext('2d');
      if (!paint) return;
      const dark = root.dataset.theme === 'dark';
      paint.drawImage(brandImage, -4, 8, 72, 46);
      paint.globalCompositeOperation = 'source-in';
      paint.fillStyle = dark ? '#ffffff' : '#00437d';
      paint.fillRect(0, 0, 64, 64);
      paint.globalCompositeOperation = 'destination-over';
      paint.fillStyle = dark ? '#00437d' : '#ffffff';
      paint.fillRect(0, 0, 64, 64);
      brandIcon.href = canvas.toDataURL('image/png');
    } catch (_) { /* Keep the local blue mark if this browser cannot render a themed icon. */ }
  }
  const valid = (value) => value === 'light' || value === 'dark';
  let preference = null;
  try {
    const stored = window.localStorage.getItem(key);
    if (valid(stored)) preference = stored;
  } catch (_) { /* Storage may be unavailable; the page remains usable. */ }

  function apply(theme) {
    root.dataset.theme = theme;
    const dark = theme === 'dark';
    updateBrandIcon();
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#101113' : '#f5f7fb');
    const toggle = document.querySelector('[data-theme-toggle]');
    if (!toggle) return;
    const label = dark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
    toggle.setAttribute('aria-label', label);
    toggle.setAttribute('title', label);
    toggle.setAttribute('aria-pressed', String(dark));
    toggle.hidden = false;
  }
  const preferred = () => preference || (system.matches ? 'dark' : 'light');
  apply(preferred());
  document.addEventListener('DOMContentLoaded', () => apply(preferred()), { once: true });
  document.addEventListener('click', (event) => {
    if (!event.target.closest('[data-theme-toggle]')) return;
    preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
    try { window.localStorage.setItem(key, preference); } catch (_) { /* Keep the preference in this page. */ }
    apply(preference);
  });
  system.addEventListener('change', () => { if (!preference) apply(preferred()); });
  window.addEventListener('storage', (event) => {
    if (event.key !== key && event.key !== null) return;
    preference = valid(event.newValue) ? event.newValue : null;
    apply(preferred());
  });
})();

/* Explicit local agenda template. Remote model generation stays a separate action. */
(() => {
  'use strict';
  const pilot = '9c1cb0ba-4025-49dc-b9e8-d0f6cf3e84aa';
  document.addEventListener('click', async (event) => {
    const button = event.target.closest?.('[data-gica-pilot-plan]');
    if (!button || window.SparkXGicaDemo?.isActive() || button.disabled || button.dataset.eventId !== pilot) return;
    const root = button.closest('main[data-gica-pilot="true"]');
    const status = root?.querySelector('[data-gica-pilot-feedback]');
    const csrf = root?.querySelector('[name="csrfmiddlewaretoken"]')?.value;
    if (!root || !status || !/^[a-zA-Z0-9]{64}$/.test(csrf || '')) return;
    event.preventDefault(); button.disabled = true; status.textContent = 'Preparando la propuesta de agenda…';
    const owner = document.body.dataset.voiceUser;
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 10000);
    async function request(payload) {
      const response = await fetch('/assistant/pilot-control/', { method:'POST', credentials:'same-origin', redirect:'error', cache:'no-store', signal:controller.signal,
        headers:{ 'Content-Type':'application/json', 'X-CSRFToken':csrf, Accept:'application/json' }, body:JSON.stringify(payload) });
      if (!response.headers.get('Content-Type')?.startsWith('application/json')) throw new Error('No pude comprobar la respuesta de SparkX.');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'La propuesta requiere revisión.');
      return data;
    }
    try {
      const run = await request({ operation:'bootstrap' });
      if (run.event_id !== pilot || !/^[0-9a-f-]{36}$/i.test(run.run_id || '')) throw new Error('Vuelve a abrir el piloto para continuar.');
      const result = await request({ operation:button.dataset.gicaPilotPlan, run_id:run.run_id, event_id:pilot, expected_revision:Number(button.dataset.expectedRevision) });
      if (!root.isConnected || document.hidden || document.body.dataset.voiceUser !== owner) return;
      if (result.event_id !== pilot || result.candidate_url !== `/events/${pilot}/#candidate`) throw new Error('No pude confirmar la propuesta.');
      location.assign(result.candidate_url);
    } catch (error) {
      if (root.isConnected && document.body.dataset.voiceUser === owner) status.textContent = error.name === 'AbortError' ? 'La comprobación tardó demasiado. Revisa las propuestas antes de intentarlo de nuevo.' : error.message;
    } finally { clearTimeout(timer); if (button.isConnected) button.disabled = false; }
  });
})();

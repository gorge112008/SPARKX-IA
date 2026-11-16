/* Human-clicked pilot planning. The same bounded compact client serves the
 * narrator and this manual entry; the server never auto-approves its output. */
(() => {
  'use strict';
  const pilot='bcf52dbd-206b-4d22-a294-8c487c770c56';
  let active=null;
  document.addEventListener('click',async(event)=>{
    const button=event.target.closest?.('[data-gica-pilot-plan]');
    if(!button||window.SparkXGicaDemo?.isActive()||button.disabled||button.dataset.eventId!==pilot||active)return;
    const root=button.closest('main[data-gica-pilot="true"]'),status=root?.querySelector('[data-gica-pilot-feedback]');
    const csrf=root?.querySelector('[name="csrfmiddlewaretoken"]')?.value;
    const owner=document.body.dataset.voiceUser,role=document.body.dataset.portalRole;
    if(!root||!status||!/^[A-Za-z0-9]{64}$/.test(csrf||'')||!['admin','organizer'].includes(role))return;
    event.preventDefault();window.SparkXGicaWaiting?.prepareFromGesture();button.disabled=true;
    const controller=new AbortController();active=controller;
    let credentialPaused=false;
    const current=()=>root.isConnected&&(!document.hidden||credentialPaused)&&document.body.dataset.voiceUser===owner&&document.body.dataset.portalRole===role;
    const stop=()=>controller.abort();
    document.addEventListener('sparkx:gica-navigation-start',stop,{once:true});window.addEventListener('pagehide',stop,{once:true});
    const visibility=()=>{if(document.hidden&&!credentialPaused)stop();};document.addEventListener('visibilitychange',visibility);
    async function request(payload){
      const timer=setTimeout(stop,15000);
      try{
        const response=await fetch('/assistant/pilot-control/',{method:'POST',credentials:'same-origin',redirect:'error',cache:'no-store',signal:controller.signal,
          headers:{'Content-Type':'application/json','X-CSRFToken':csrf,Accept:'application/json'},body:JSON.stringify(payload)});
        if(!current()||controller.signal.aborted)throw new DOMException('Stopped','AbortError');
        if(!response.headers.get('Content-Type')?.startsWith('application/json'))throw new Error('No pude comprobar la respuesta de ArquiGica.');
        const data=await response.json();if(!response.ok)throw new Error(typeof data.error==='string'?data.error:'La propuesta requiere revisión.');return data;
      }finally{clearTimeout(timer);}
    }
    try{
      status.textContent='Preparando la solicitud…';
      const run=await request({operation:'bootstrap'});
      if(run.event_id!==pilot||!/^[0-9a-f-]{36}$/i.test(run.run_id||''))throw new Error('Vuelve a abrir el evento para continuar.');
      const expected=Number(button.dataset.expectedRevision);
      const retryID=button.dataset.gicaCompactRetryId||null;
      if(retryID&&!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(retryID))throw new Error('La referencia para continuar ya no está disponible.');
      const result=button.dataset.gicaPilotPlan==='replan'&&!retryID
        ?await request({operation:'replan',run_id:run.run_id,event_id:pilot,expected_revision:expected})
        :await window.SparkXGicaPilotAI.generate({runID:run.run_id,eventID:pilot,expectedRevision:expected,signal:controller.signal,csrf,check:current,
          narrate:async(text)=>{if(current())status.textContent=text;},onStatus:(text)=>{if(current())status.textContent=text;},onCredentialPause:(paused)=>{credentialPaused=paused;},provider:button.dataset.gicaAiProvider||'free',saveCopy:true,retryJobID:retryID,changeRequest:button.dataset.gicaPilotPlan==='change'?'more_case_time':null});
      if(!current()||controller.signal.aborted)return;
      if(result.event_id!==pilot||result.candidate_url!==`/events/${pilot}/#candidate`)throw new Error('No pude confirmar la propuesta.');
      location.assign(result.candidate_url);
    }catch(error){if(current())status.textContent=error.name==='AbortError'?'Solicitud detenida. Revisa las propuestas antes de volver a intentarlo.':error.message;}
    finally{
      document.removeEventListener('sparkx:gica-navigation-start',stop);window.removeEventListener('pagehide',stop);document.removeEventListener('visibilitychange',visibility);
      if(active===controller)active=null;if(button.isConnected)button.disabled=false;
    }
  });
})();

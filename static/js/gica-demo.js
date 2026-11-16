/* Human-started, owner-scoped pilot. Visible controls and local narration;
 * the server owns persistence and approvals. No microphone or remote model. */
(() => {
  'use strict';
  const root = document.querySelector('[data-romeo-presence]'), owner = document.body.dataset.voiceUser, role = document.body.dataset.portalRole;
  if (!root || !/^[1-9][0-9]{0,18}$/.test(owner || '')) return;
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const title = 'Gestión estratégica del mantenimiento: de la planificación al rendimiento';
  const initialDate = '2026-11-19', nextDate = '2026-11-26';
  const authorizedPilot = '9c1cb0ba-4025-49dc-b9e8-d0f6cf3e84aa';
  const answerKeys = Object.freeze(['objective','audience','modality','duration_minutes','location','resources','constraints']);
  const unsafe = /[\p{Cf}\p{Cs}\p{Zl}\p{Zp}\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/u;
  const opening = 'Hola, soy Gica. Vamos a organizar nuestro seminario de Gicaingenieros, con información real registrada para este piloto. Verás cada selección, el calendario y cómo adaptar el evento ante un cambio. El micrófono permanece apagado.';
  const steps = Object.freeze([
    { key:'title', label:'Nombre', speech:'Escribo el nombre de nuestro seminario: Gestión estratégica del mantenimiento, de la planificación al rendimiento.' },
    { key:'organization', label:'Institución', speech:'Despliego las instituciones y selecciono Gicaingenieros como organización de este evento.' },
    { key:'speaker', label:'Expositor', speech:'Selecciono al doctor Robert Castillo Alva desde el directorio. Lo vinculamos a este evento de Gicaingenieros, conservando su institución de origen.' },
    { key:'date', label:'Fecha', speech:'Abro el calendario y elijo el jueves diecinueve de noviembre de dos mil veintiséis.' },
    { key:'time', label:'Hora de inicio', speech:'Fijo el inicio a las siete y media de la noche. El seminario tendrá una duración de noventa minutos.' },
    { key:'timezone', label:'Zona horaria', speech:'Abro las zonas horarias y selecciono América, Lima. El programa se comunicará en hora de Perú.' },
    { key:'capacity', label:'Aforo', speech:'Pulso cien participantes. La opción queda seleccionada y el campo muestra el aforo que estamos planificando.' },
    { key:'brief', label:'Descripción', speech:'Completo la descripción de nuestro seminario de mantenimiento y confiabilidad: exposición, caso aplicado y preguntas para conectar la planificación con el rendimiento.' },
    { key:'objective', label:'Objetivo', speech:'En preparación, escribo el resultado que queremos lograr: aplicar criterios de mantenimiento y gestión de activos para mejorar el rendimiento operativo.' },
    { key:'audience', label:'Perfil del público', speech:'Defino el perfil del público: profesionales y responsables de mantenimiento, además de estudiantes de áreas afines.' },
    { key:'modality', label:'Modalidad', speech:'Despliego las modalidades y selecciono virtual.' },
    { key:'duration_minutes', label:'Duración', speech:'Registro noventa minutos para distribuir la apertura, los temas, el caso aplicado, las preguntas y el cierre.' },
    { key:'location', label:'Acceso', speech:'Indicamos Zoom como plataforma prevista. El enlace y la licencia se coordinarán antes de difundir el evento.' },
    { key:'resources', label:'Recursos', speech:'Registro el expositor y los recursos que debemos coordinar: presentación, material de apoyo, moderación y soporte.' },
    { key:'constraints', label:'Condiciones', speech:'Finalmente, dejo las condiciones del piloto: hora de Perú, cien personas previstas y confirmación de disponibilidad y acceso antes de publicar.' }
  ]);
  let active = null, sequence = 0, savedURL = '';
  const all = (selector) => document.querySelectorAll(selector);
  const emit = (kind, detail = {}) => document.dispatchEvent(new CustomEvent('sparkx:gica-companion-state', { detail: { kind, user:owner, ...detail } }));
  function current(run) {
    return active === run && run.id === sequence && !run.controller.signal.aborted && root.isConnected &&
      !document.hidden && document.body.dataset.voiceUser === owner && document.body.dataset.portalRole === role && root.dataset.gicaDemoActive === 'true';
  }
  function guard(run) { if (!current(run)) throw new DOMException('Pilot stopped', 'AbortError'); }
  function status(text, state) {
    if (document.body.dataset.voiceUser !== owner) return;
    all('[data-gica-demo-status]').forEach((node) => { node.textContent = text; });
    if (state) root.dataset.gicaDemoState = state;
  }
  function controls() {
    all('[data-gica-demo-start]').forEach((node) => { node.disabled = !!active || document.body.dataset.voiceUser !== owner || document.body.dataset.portalRole !== role; });
    all('[data-gica-demo-stop]').forEach((node) => { node.hidden = !active; });
    all('[data-gica-demo-event]').forEach((node) => { node.hidden = !savedURL; if (savedURL) node.href = savedURL; else node.removeAttribute('href'); });
  }
  function script() {
    all('[data-gica-demo-script]').forEach((node) => {
      if (node.dataset.gicaDemoReady) return;
      node.dataset.gicaDemoReady = 'true';
      const introduction = document.createElement('p'); introduction.textContent = opening;
      const list = document.createElement('ol');
      for (const step of steps) { const item = document.createElement('li'); item.dataset.gicaDemoStep = step.key; item.textContent = `${step.label}: ${step.speech}`; list.append(item); }
      for (const text of ['Guardar la ficha y preparar y aprobar la agenda del piloto.', 'Consultar el evento en el calendario.', 'Sustituir a Robert por Jorge Gayoso Ugas y reprogramar al jueves 26 de noviembre.', 'Revisar agenda, preparación, propuestas, actividad y edición de horas.']) { const item = document.createElement('li'); item.textContent = text; list.append(item); }
      node.replaceChildren(introduction, list);
    });
  }
  function progress(label, key = '') {
    all('[data-gica-demo-progress]').forEach((node) => { node.textContent = label; });
    all('[data-gica-demo-step]').forEach((node) => { if (node.dataset.gicaDemoStep === key) node.setAttribute('aria-current','step'); else node.removeAttribute('aria-current'); });
    document.dispatchEvent(new CustomEvent('sparkx:gica-pilot-stage', { detail:{ user:owner, stage:key || label, eventURL:savedURL } }));
  }
  function wait(run, milliseconds) {
    return new Promise((resolve,reject) => {
      guard(run);
      const abort = () => { clearTimeout(timer); reject(new DOMException('Pilot stopped','AbortError')); };
      const timer = setTimeout(() => { run.controller.signal.removeEventListener('abort',abort); resolve(); }, milliseconds);
      run.controller.signal.addEventListener('abort',abort,{once:true});
    });
  }
  function voice(speaking) { emit('voice',{active:!!active,micActive:false,listening:false,speaking,blocked:!!active,phase:active?'demo':'off'}); }
  async function narrate(run,text) {
    guard(run); status(text,'running'); emit('exchange',{assistantText:text,userText:''}); voice(true); run.speaking = true;
    try {
      const result = await window.SparkXRomeoSpeech.speak(text,{eventQuestion:true}); guard(run);
      if (result?.spoken !== true || result.reason !== 'ended') { const error = new Error('speech'); error.reason=result?.reason; throw error; }
    } finally { run.speaking=false; if (current(run)) voice(false); }
    await wait(run,280);
  }
  function csrf() {
    const token = root.querySelector('[name="csrfmiddlewaretoken"]')?.value;
    if (!/^[A-Za-z0-9]{64}$/.test(token || '')) throw new Error('state');
    return token;
  }
  async function control(run,operation,extra={}) {
    guard(run); run.inFlight=true;
    try {
      const response=await fetch('/assistant/pilot-control/',{method:'POST',credentials:'same-origin',cache:'no-store',redirect:'error',signal:run.controller.signal,
        headers:{Accept:'application/json','Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({operation,...extra})});
      guard(run);
      if (!/^application\/json(?:;|$)/i.test(response.headers.get('Content-Type') || '')) throw new Error('state');
      const data=await response.json(); guard(run);
      if (!response.ok) { const error=new Error('server'); error.notice=typeof data.error==='string'&&data.error.length<=500&&!unsafe.test(data.error)?data.error:''; throw error; }
      return data;
    } finally { run.inFlight=false; }
  }
  function specification(data) {
    const f=data?.fields, org=data?.organization, speakers=data?.speakers;
    const safe=(value,max)=>typeof value==='string'&&value.trim().length>0&&value.length<=max&&!unsafe.test(value);
    if (!uuid.test(data?.run_id||'') || !['create','resume'].includes(data?.narration_mode) || !(data.event_id===null||data.event_id===authorizedPilot) ||
        !f||typeof f!=='object'||Array.isArray(f)||f.title!==title||f.date!==initialDate||f.time!=='19:30'||f.timezone!=='America/Lima'||f.capacity!==100||f.is_synthetic!==false||
        !safe(f.brief,12000)||data.next_date!==nextDate||!org||org.name!=='Gicaingenieros'||!(org.id===null||uuid.test(org.id||''))||
        !Array.isArray(org.aliases)||org.aliases.length>12||org.aliases.some((value)=>!safe(value,160))||
        !speakers||!uuid.test(speakers.robert||'')||!uuid.test(speakers.jorge||'')||speakers.robert===speakers.jorge||f.speaker_id!==speakers.robert||
        answerKeys.some((key)=>!safe(f[key],1000))||String(f.duration_minutes)!=='90'||f.modality!=='Virtual') throw new Error('state');
    if (data.event_id && data.event_url!==`/events/${data.event_id}/`) throw new Error('state');
    return data;
  }
  async function click(run,target,activate=false) {
    guard(run); const priorNavigation=run.internalNavigation, priorAction=run.internalAction;
    run.internalNavigation=activate||priorNavigation; run.internalAction=activate||priorAction;
    try { if (!await window.SparkXGicaDemoCursor.click(target,{signal:run.controller.signal,activate})) throw new Error('state'); guard(run); }
    finally { run.internalNavigation=priorNavigation; run.internalAction=priorAction; }
  }
  async function events(run) {
    await click(run,document.querySelector('.main-nav [data-romeo-nav="events"]'),true);
    if (!document.querySelector('main[data-romeo-destination="events"]')) throw new Error('state');
    await wait(run,550);
  }
  async function newEvent(run) {
    await click(run,document.querySelector('main[data-romeo-destination="events"] .page-heading a[href="/events/new/"]'),true);
    if (!document.querySelector('main form[data-gica-event-form="create"]')) throw new Error('state');
  }
  async function submit(run,form) {
    guard(run); const button=form?.querySelector('button[type="submit"]');
    if (!button || button.disabled) throw new Error('state');
    run.internalNavigation=true; run.internalAction=true; run.internalForm=form;
    window.SparkXGicaNavigation.prepareForm(form,{source:'narrated-demo',signal:run.controller.signal,run_id:run.spec.run_id});
    try {
      if (!await window.SparkXGicaDemoCursor.click(button,{signal:run.controller.signal,activate:true})) throw new Error('state');
      const promise=window.SparkXGicaNavigation.resultFor(form); if (!promise) throw new Error('state');
      const result=await promise; guard(run); if (result?.success!==true) throw new Error('save'); return result;
    } finally { run.internalNavigation=false; run.internalAction=false; run.internalForm=null; }
  }
  async function select(run,name,value) {
    const form=document.querySelector('main form[data-event-block-form]'), toggle=form?.querySelector(`[data-event-select-toggle="${name}"]`);
    if (!toggle) throw new Error('state');
    await click(run,toggle,true); await wait(run,500);
    const option=Array.from(form.querySelectorAll(`[data-event-select-option="${name}"]`)).find((node)=>node.dataset.eventSelectValue===String(value));
    await click(run,option,true); await wait(run,300);
    if (form.elements.namedItem(name)?.value!==String(value) || toggle.getAttribute('aria-expanded')!=='false') throw new Error('state');
  }
  async function date(run,value) {
    const form=document.querySelector('main form[data-event-block-form]');
    await click(run,form?.querySelector('[data-event-date-toggle]'),true); await wait(run,500);
    let day=form.querySelector(`[data-event-date-day="${value}"]`);
    for (let count=0;!day&&count<12;count++) {
      const visibleDay=form.querySelector('[data-event-date-day]')?.dataset.eventDateDay;
      if (!visibleDay) throw new Error('state');
      await click(run,form.querySelector(`[data-event-date-month="${visibleDay<value?'next':'prev'}"]`),true);
      day=form.querySelector(`[data-event-date-day="${value}"]`);
    }
    await click(run,day,true); await wait(run,350);
    if (form.elements.namedItem('starts_at')?.value.slice(0,10)!==value) throw new Error('state');
  }
  async function time(run,value) {
    const form=document.querySelector('main form[data-event-block-form]'), input=form?.querySelector('[data-event-time]');
    await click(run,input); input.value=value; input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new Event('change',{bubbles:true}));
    if (form.elements.namedItem('starts_at')?.value.slice(11,16)!==value) throw new Error('state');
  }
  function endForm(run) { if (run.previewStarted) { run.previewStarted=false; window.SparkXGicaDemoPreview?.end(); } }
  function beginForm(run,fields,editing=false) { if (!window.SparkXGicaDemoPreview.begin(fields,{editing})) throw new Error('state'); run.previewStarted=true; }
  async function registerOrganization(run) {
    if (run.spec.organization.id) return;
    progress('Identidad de la institución','organization_register');
    await narrate(run,'Primero registraremos nuestra institución. Abro su ficha y guardo Gicaingenieros con el nombre alternativo GICA Ingenieros. Así podremos reutilizarla en el directorio.');
    await click(run,document.querySelector('main [data-gica-field="organization"] a[href="/directory/organizations/new/"]'),true);
    const form=document.querySelector('main form.directory-form'), name=form?.elements.namedItem('name'), aliases=form?.elements.namedItem('aliases');
    await click(run,name); name.value=run.spec.organization.name; name.dispatchEvent(new Event('input',{bubbles:true}));
    await click(run,aliases); aliases.value=run.spec.organization.aliases.join('\n'); aliases.dispatchEvent(new Event('input',{bubbles:true}));
    form.elements.namedItem('is_active').checked=true; form.elements.namedItem('is_synthetic').checked=false;
    await submit(run,form);
    const spec=specification(await control(run,'bootstrap'));
    if (spec.run_id!==run.spec.run_id || !spec.organization.id) throw new Error('state'); run.spec=spec;
    await narrate(run,'Gicaingenieros ya está registrada. Regreso a Mis eventos y abro la ficha del seminario para seleccionarla.');
    await events(run); await newEvent(run);
  }
  async function fillForm(run) {
    const fields={...run.spec.fields,organization_id:run.spec.organization.id}; beginForm(run,fields);
    for (const [index,step] of steps.entries()) {
      progress(`Ficha · ${index+1} de ${steps.length} · ${step.label}`,step.key);
      const form=document.querySelector('main form[data-gica-demo-live="true"]'), field=form?.querySelector(`[data-gica-field="${step.key}"]`);
      if (!field || !window.SparkXGicaDemoPreview.mark(step.key)) throw new Error('state');
      await click(run,field);
      const action=async()=>{
        if (step.key==='title') { if (!await window.SparkXGicaDemoPreview.typeTitle({signal:run.controller.signal})) throw new Error('state'); }
        else if (step.key==='organization') await select(run,'organization_id',fields.organization_id);
        else if (step.key==='speaker') await select(run,'speaker_id',run.spec.speakers.robert);
        else if (step.key==='date') await date(run,fields.date);
        else if (step.key==='time') await time(run,fields.time);
        else if (step.key==='timezone') await select(run,'timezone',fields.timezone);
        else if (step.key==='capacity') {
          await click(run,form.querySelector('[data-event-preset="capacity"][data-event-preset-value="100"]'),true);
          if (form.elements.namedItem('capacity').value!=='100') throw new Error('state');
        } else if (step.key==='modality') await select(run,'modality',fields.modality);
        else if (!window.SparkXGicaDemoPreview.fill(step.key)) throw new Error('state');
      };
      const outcomes=await Promise.allSettled([action(),narrate(run,step.speech)]);
      for (const result of outcomes) if (result.status==='rejected') throw result.reason;
    }
    if (!window.SparkXGicaDemoPreview.fill('is_synthetic',false)) throw new Error('state');
    await narrate(run,'La ficha está completa. Guardo nuestro piloto con la institución, el expositor, la programación y los siete puntos de preparación.');
    const result=await submit(run,document.querySelector('main form[data-gica-demo-live="true"]')); endForm(run);
    if (result.event_id!==authorizedPilot || result.event_url!==`/events/${authorizedPilot}/`) throw new Error('state');
    run.eventID=result.event_id; savedURL=result.event_url; controls();
    if (!window.SparkXGicaNavigation.bindPilot(run.eventID)) throw new Error('state');
    if (!result.created) {
      await narrate(run,'Este piloto ya estaba guardado. Lo reutilizo para este recorrido, sin crear una copia, y restablezco su programación inicial del diecinueve con Robert.');
      await edit(run,false);
    }
    progress('Evento guardado','created');
  }
  function revision() {
    const raw=document.querySelector('main[data-workspace]')?.dataset.eventRevision || document.querySelector('main #proposal-form [name="expected_revision"]')?.value;
    const value=Number(raw); if (!Number.isSafeInteger(value)||value<1) throw new Error('state'); return value;
  }
  async function panel(run,name) { await click(run,document.querySelector(`main[data-workspace] [data-panel-link="${name}"]`),true); await wait(run,380); }
  async function plan(run,operation) {
    await panel(run,'proposals'); progress('Agenda del piloto',operation);
    await narrate(run,operation==='plan'?'Preparo una agenda local de noventa minutos: bienvenida, contenido, caso aplicado, preguntas y cierre. El servidor comprobará los horarios antes de aplicarla.':'Ahora preparo la agenda actualizada con Jorge y la nueva fecha. Revisamos los cambios y conservamos el historial del plan.');
    const button=document.querySelector('main[data-gica-pilot="true"] [data-gica-pilot-plan]');
    if (!button) throw new Error('state'); run.planOperation=operation; run.planPromise=null;
    await click(run,button,true);
    if (!run.planPromise) throw new Error('state');
    const candidate=await run.planPromise; guard(run);
    if (candidate.event_id!==run.eventID || candidate.event_url!==savedURL || !uuid.test(candidate.candidate_id||'') ||
        candidate.approve_url!==`${savedURL}candidates/${candidate.candidate_id}/approve/` || !window.SparkXGicaNavigation.bindCandidate(candidate.approve_url)) throw new Error('state');
    run.internalNavigation=true;
    try { const result=await window.SparkXGicaNavigation.refreshPilot({signal:run.controller.signal}); guard(run); if (!result.success) throw new Error('state'); }
    finally { run.internalNavigation=false; }
    await approve(run,candidate.approve_url);
    progress('Agenda aprobada',operation+'_approved');
  }
  async function approve(run,path) {
    await panel(run,'proposals');
    await narrate(run,'La propuesta está lista para revisar. Para este piloto autorizado, pulso Aprobar propuesta y aplico únicamente esta versión comprobada.');
    const form=Array.from(document.querySelectorAll('main .candidate-actions form')).find((node)=>new URL(node.action,location.origin).pathname===path);
    await submit(run,form);
  }
  async function calendar(run,day) {
    await click(run,document.querySelector('.main-nav [data-romeo-nav="calendar"]'),true); await wait(run,450);
    await click(run,document.querySelector(`main[data-romeo-destination="calendar"] [data-calendar-day="${day}"]`),true);
    await narrate(run,day===initialDate?'Nuestro evento aparece el jueves diecinueve. Al seleccionar el día, vemos el horario y las sesiones aprobadas. Abramos su detalle.':'El calendario confirma el jueves veintiséis. Selecciono el día y abro el evento para comprobar su agenda y su preparación.');
    const anchor=Array.from(document.querySelectorAll('main .calendar-open-event')).find((node)=>new URL(node.href).pathname===savedURL);
    await click(run,anchor,true); progress('Evento abierto desde el calendario',day===initialDate?'calendar_initial':'calendar_updated');
  }
  async function edit(run,changed=true) {
    const fields={...run.spec.fields,organization_id:run.spec.organization.id,speaker_id:changed?run.spec.speakers.jorge:run.spec.speakers.robert,date:changed?nextDate:initialDate};
    await click(run,document.querySelector(`main .heading-actions a[href="${savedURL}edit/"]`),true); beginForm(run,fields,true);
    await click(run,document.querySelector('main [data-gica-field="speaker"]')); await select(run,'speaker_id',fields.speaker_id);
    if (changed) await narrate(run,'En este caso, Robert tiene un inconveniente. Selecciono a Jorge Gayoso Ugas como reemplazo en el evento. Su asignación queda planificada y su disponibilidad debe coordinarse.');
    await date(run,fields.date); await time(run,fields.time);
    if (changed) await narrate(run,'Elegimos el jueves de la semana siguiente: veintiséis de noviembre, a las siete y media de la noche.');
    const resources=changed?'Expositor: Jorge Gayoso Ugas. Reemplazo del Dr. Robert Castillo Alva para este evento; disponibilidad por coordinar. Presentación, material PDF, moderación y soporte por coordinar.':run.spec.fields.resources;
    await click(run,document.querySelector('main [data-gica-field="resources"]'));
    if (!window.SparkXGicaDemoPreview.fill('resources',resources)) throw new Error('state');
    await narrate(run,'Guardo los cambios de la ficha. Revisaremos una nueva propuesta para que la agenda coincida con la fecha y el expositor actualizados.');
    await submit(run,document.querySelector('main form[data-gica-demo-live="true"]')); endForm(run);
    progress('Ficha actualizada',changed?'rescheduled':'initial_restored');
  }
  async function adjustHours(run) {
    await panel(run,'plan');
    await click(run,document.querySelector('main [data-gica-adjust-hours]'),true);
    await narrate(run,'Para modificar las horas, abrimos Ajustar horarios. Cada sesión conserva su título y permite cambiar inicio y duración. Ampliaremos el tema estratégico cinco minutos y ajustaremos el caso aplicado.');
    const form=document.querySelector('main form[data-pilot-schedule]');
    const updates=[['sessions-1-duration_minutes','25'],['sessions-2-start',nextDate+'T20:00'],['sessions-2-duration_minutes','30']];
    for (const [name,value] of updates) {
      const input=form?.elements.namedItem(name); await click(run,input);
      input.value=value; input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new Event('change',{bubbles:true}));
      if (input.value!==value) throw new Error('state'); await wait(run,420);
    }
    progress('Ajustar las horas de la agenda','schedule_editor');
    await narrate(run,'El tema estratégico tendrá veinticinco minutos y el caso empezará a las ocho, con treinta minutos. Mantenemos el cierre a las nueve. Preparo la propuesta para validar el horario.');
    await submit(run,form);
    const candidateForm=Array.from(document.querySelectorAll('main .candidate-actions form')).find((node)=>/\/approve\/$/.test(new URL(node.action).pathname));
    const path=candidateForm?new URL(candidateForm.action).pathname:'';
    if (!path || !window.SparkXGicaNavigation.bindCandidate(path)) throw new Error('state');
    await approve(run,path); progress('Horario ajustado y aprobado','schedule_approved');
    await calendar(run,nextDate);
  }
  async function finalReview(run) {
    await panel(run,'plan');
    await narrate(run,'La agenda muestra cinco sesiones con sus horas, duración y expositor. Las actividades suman noventa minutos y el servidor valida que no se solapen.');
    progress('Revisar la agenda','final_agenda');
    await adjustHours(run);
    await panel(run,'preparation');
    const instruction=document.querySelector('main #preparation [data-task-instructions] summary');
    if (instruction) await click(run,instruction,true);
    await narrate(run,'En preparación, abrimos las instrucciones de cada tarea. El equipo confirma datos y expositor, configura acceso, prepara materiales y realiza el ensayo. Se actualizan los estados con evidencia; los trabajos pendientes siguen pendientes.');
    progress('Revisar tareas y dependencias','final_preparation');
    await panel(run,'proposals');
    await narrate(run,'En propuestas revisamos nuevas versiones antes de aprobarlas. Un cambio de horario o ponente debe comprobarse contra las restricciones. El plan vigente se conserva hasta aplicar una nueva versión.');
    progress('Revisar propuestas','final_proposals');
    await panel(run,'activity');
    await narrate(run,'Actividad muestra los trabajos del agente cuando se solicitan. Este recorrido usa reglas y una plantilla local: no ha realizado llamadas a modelos ni consumido su presupuesto.');
    progress('Revisar actividad','final_activity');
    await panel(run,'plan');
    await narrate(run,'El piloto termina planificado y configurado para el jueves veintiséis de noviembre, con Jorge Gayoso Ugas y su agenda aprobada. Queda ejecutar las tareas de preparación y confirmar disponibilidad y acceso antes de difundir.');
    progress('Piloto planificado y configurado','complete');
  }
  async function execute(run) {
    // Start speech in the explicit click's activation, before any network await.
    await narrate(run,opening);
    const draft=await window.SparkXGicaCreation.request('',{operation:'resume',source:'narrated-demo',signal:run.controller.signal,current:()=>current(run)}); guard(run);
    if (draft?.handled&&['collecting','review','invalid','conflict'].includes(draft.draft_status||draft.status)) throw new Error('existing');
    if (!draft || draft.handled&&!['created','cancelled','expired'].includes(draft.status)) throw new Error('state');
    run.spec=specification(await control(run,'bootstrap'));
    if (run.spec.event_id) { savedURL=run.spec.event_url; window.SparkXGicaNavigation.bindPilot(run.spec.event_id); controls(); }
    await events(run);
    await narrate(run,'Estamos en Mis eventos. Pulso Nuevo evento para empezar por la identidad y completar la ficha bloque por bloque.');
    await newEvent(run); await registerOrganization(run); await fillForm(run); await plan(run,'plan');
    await narrate(run,'Consultemos nuestro evento en el calendario, antes de revisar un cambio de expositor y de fecha.');
    await calendar(run,initialDate);
    await narrate(run,'Ahora planteamos un inconveniente del expositor. Abro Editar ficha para sustituirlo y mover el seminario al jueves siguiente.');
    await edit(run,true); await plan(run,'replan'); await calendar(run,nextDate); await finalReview(run);
    status('Piloto planificado para el 26 de noviembre con Jorge Gayoso Ugas. Revisa las tareas pendientes y confirma acceso y disponibilidad.','complete');
    release(run); emit('exchange',{assistantText:'Piloto planificado y configurado. Puedes revisar su agenda, preparación e historial y continuar las coordinaciones pendientes.',userText:''});
  }
  function release(run) {
    if (active!==run) return;
    endForm(run); window.SparkXGicaDemoCursor?.release(); active=null; sequence+=1; controls();
    document.dispatchEvent(new CustomEvent('sparkx:gica-demo-end',{detail:{user:owner,completed:root.dataset.gicaDemoState==='complete'}})); voice(false);
  }
  function stop(message='Recorrido detenido. Los cambios que ya se guardaron se conservan. Revisa Mis eventos o el calendario antes de continuar.') {
    const run=active; if (!run) return;
    sequence+=1; run.controller.abort(); if (run.speaking) window.SparkXRomeoSpeech?.cancel();
    status(message,'stopped'); release(run); emit('exchange',{assistantText:message,userText:''});
  }
  async function start() {
    if (active||document.hidden||!root.isConnected||document.body.dataset.voiceUser!==owner||document.body.dataset.portalRole!==role) return;
    if (!window.SparkXGicaCreation?.request||!window.SparkXRomeoSpeech?.speak||!window.SparkXGicaDemoCursor?.click||!window.SparkXGicaNavigation?.submitPilotForm||!window.SparkXGicaDemoPreview?.fill) { status('Recarga SparkX para cargar el recorrido completo del piloto.','error'); return; }
    const run={id:++sequence,controller:new AbortController(),speaking:false,inFlight:false,internalNavigation:false,internalAction:false,internalForm:null,previewStarted:false};
    active=run; controls(); status('Preparando recorrido del piloto con micrófono apagado…','preparing');
    const permission=new CustomEvent('sparkx:gica-demo-prepare',{cancelable:true}); document.dispatchEvent(permission);
    if (!permission.defaultPrevented||root.dataset.gicaDemoActive!=='true') { active=null; controls(); status('Termina la acción actual o cierra el comparador de voces antes de iniciar el piloto.','error'); return; }
    const panel=root.querySelector('#romeo-presence-details'); if (panel) panel.hidden=true;
    root.querySelector('[data-romeo-presence-toggle]')?.setAttribute('aria-expanded','false'); document.dispatchEvent(new CustomEvent('sparkx:romeo-action-layout'));
    try { await execute(run); }
    catch(error) {
      if (active!==run) return;
      if (!current(run)) { stop(); return; }
      const voiceMessage=error?.reason==='no_local_voice'?'No encontré una voz española local. Selecciona una en Comparar voces.':error?.reason==='voice_unavailable'?'La voz elegida ya no está disponible. Selecciona otra voz local en Comparar voces.':'El navegador interrumpió la narración. Comprueba Probar voz y vuelve a iniciar el recorrido.';
      const message=error?.message==='existing'?'Tienes un borrador pendiente. Continúalo o cancélalo antes de iniciar este piloto. Tu borrador se conserva.':
        error?.message==='speech'?voiceMessage+' Los cambios ya guardados se conservan.':error?.notice?error.notice+' El recorrido queda detenido para revisar.':
        'El recorrido se detuvo porque no pude confirmar un paso. Revisa Mis eventos o el calendario: los cambios guardados se conservan y no se repetirá el envío automáticamente.';
      status(message,'error'); run.controller.abort(); release(run); emit('exchange',{assistantText:message,userText:''});
    }
  }
  document.addEventListener('click',(event)=>{
    const target=event.target instanceof Element?event.target:null; if (!target) return;
    if (target.closest('[data-gica-demo-stop]')) { event.preventDefault(); event.stopImmediatePropagation(); stop(); return; }
    if (target.closest('[data-gica-demo-start]')) { event.preventDefault(); event.stopImmediatePropagation(); start(); return; }
    if (!active) return;
    const planButton=target.closest('main[data-gica-pilot="true"] [data-gica-pilot-plan]');
    if (planButton && active.internalAction && !event.isTrusted && ['plan','replan'].includes(active.planOperation)) {
      event.preventDefault(); event.stopImmediatePropagation();
      active.planPromise=control(active,active.planOperation,{run_id:active.spec.run_id,event_id:active.eventID,expected_revision:revision()}); return;
    }
    const anchor=target.closest('a[href]');
    if (anchor&&anchor.getAttribute('href')&&!anchor.getAttribute('href').startsWith('#')) { if (!active.internalNavigation||event.isTrusted) stop(); return; }
    if (active.internalAction&&!event.isTrusted) return;
    if (target.closest('main button,main input,main select,main textarea,main summary,[data-gica-creation-control],[data-gica-creation-edit],[data-romeo-voice-session],[data-dictate],[data-gica-choice],[data-gica-companion-choice],[data-gica-companion-other],[data-gica-companion] form,[data-romeo-action-form] button')) { event.preventDefault(); event.stopImmediatePropagation(); }
  },true);
  document.addEventListener('submit',(event)=>{
    if (!active) return;
    if (active.internalAction&&active.internalForm===event.target) return;
    event.preventDefault(); event.stopImmediatePropagation();
  },true);
  document.addEventListener('sparkx:gica-navigation-start',()=>{if(active&&!active.internalNavigation)stop();});
  document.addEventListener('sparkx:gica-navigation-complete',()=>{script();controls();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();}); window.addEventListener('pagehide',()=>stop());
  new MutationObserver(()=>{if(active&&(!root.isConnected||document.body.dataset.voiceUser!==owner||document.body.dataset.portalRole!==role))stop();}).observe(document.body,{attributes:true,attributeFilter:['data-voice-user','data-portal-role'],childList:true});
  script();controls(); window.SparkXGicaDemo=Object.freeze({isActive:()=>!!active,stop:()=>stop()});
})();

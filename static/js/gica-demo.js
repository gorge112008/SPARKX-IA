/* Human-started, owner-scoped pilot. Visible controls and local narration;
 * the server owns persistence and approvals. Narration is local; compact planning uses a bounded free model job. */
(() => {
  'use strict';
  const root = document.querySelector('[data-romeo-presence]'), owner = document.body.dataset.voiceUser, role = document.body.dataset.portalRole;
  if (!root || !/^[1-9][0-9]{0,18}$/.test(owner || '')) return;
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const title = 'Gestión estratégica del mantenimiento: de la planificación al rendimiento';
  const initialDate = '2026-11-19';
  const authorizedPilot = 'bcf52dbd-206b-4d22-a294-8c487c770c56';
  const answerKeys = Object.freeze(['objective','audience','modality','duration_minutes','location','resources','constraints']);
  const unsafe = /[\p{Cf}\p{Cs}\p{Zl}\p{Zp}\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/u;
  const opening = 'Bienvenido a ArquiGica, tu plataforma de eventos. Soy Gica, tu bot arquitecto. Organizaremos un seminario desde el directorio hasta su agenda y veremos cómo cambiar de expositor.';
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
    { key:'constraints', label:'Condiciones', speech:'Dejo las condiciones: hora de Perú, cien personas y acceso por coordinar.' }
  ]);
  let active = null, sequence = 0, savedURL = '';
  const all = (selector) => document.querySelectorAll(selector);
  const emit = (kind, detail = {}) => document.dispatchEvent(new CustomEvent('sparkx:gica-companion-state', { detail: { kind, user:owner, ...detail } }));
  function current(run) {
    return active === run && run.id === sequence && !run.controller.signal.aborted && root.isConnected &&
      (!document.hidden || run.credentialPaused) && document.body.dataset.voiceUser === owner && document.body.dataset.portalRole === role && root.dataset.gicaDemoActive === 'true';
  }
  function guard(run) { if (!current(run)) throw new DOMException('Pilot stopped', 'AbortError'); }
  function status(text, state) {
    if (document.body.dataset.voiceUser !== owner) return;
    all('[data-gica-demo-status]').forEach((node) => { node.textContent = text; });
    if (state) root.dataset.gicaDemoState = active?.credentialPaused ? 'paused' : state;
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
      const directory=document.createElement('p');directory.textContent='Antes de la ficha: Directorio → Gicaingenieros → Jorge Gayoso. Guardar una identidad no confirma su participación.';
      for (const text of ['Guardar la ficha y solicitar agenda, preparación y comunicaciones a la IA.', 'Responder las aclaraciones necesarias y aprobar la propuesta.', 'Consultar el calendario: jueves 19, con Robert.', 'Mostrar el inconveniente, elegir a Jorge y actualizar la agenda sin cambiar la fecha.', 'Revisar tareas específicas del seminario y simular estados y porcentaje sin guardar avances ficticios.', 'Leer la invitación, la descripción y las indicaciones preparadas por la IA.', 'Pedir más tiempo para el caso práctico, revisar y aprobar el cambio de la IA.', 'Terminar en Conoce a Gica para explicar voz, personalidad y memoria.']) { const item = document.createElement('li'); item.textContent = text; list.append(item); }
      node.replaceChildren(introduction,directory,list);
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
      const result = await window.SparkXRomeoSpeech.speak(text,{eventQuestion:true,voiceStyle:'female'}); guard(run);
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
    const f=data?.fields,org=data?.organization,speakers=data?.speakers,registration=data?.speaker_registration;
    const safe=(value,max)=>typeof value==='string'&&value.trim().length>0&&value.length<=max&&!unsafe.test(value);
    if (!uuid.test(data?.run_id||'') || !['create','resume'].includes(data?.narration_mode) || !(data.event_id===null||data.event_id===authorizedPilot) ||
        !f||typeof f!=='object'||Array.isArray(f)||f.title!==title||f.date!==initialDate||f.time!=='19:30'||f.timezone!=='America/Lima'||f.capacity!==100||f.is_synthetic!==false||
        !safe(f.brief,12000)||!org||org.name!=='Gicaingenieros'||!(org.id===null||uuid.test(org.id||''))||
        !Array.isArray(org.aliases)||org.aliases.length>12||org.aliases.some((value)=>!safe(value,160))||
        !speakers||!uuid.test(speakers.robert||'')||!(speakers.jorge===null||uuid.test(speakers.jorge||''))||speakers.robert===speakers.jorge||f.speaker_id!==speakers.robert||
        !registration||registration.full_name!=='Jorge Gayoso'||registration.category!=='speaker'||registration.email!==''||registration.expertise!=='Planificación y gestión del mantenimiento.'||registration.is_synthetic!==false||!Array.isArray(registration.aliases)||registration.aliases.length!==0||
        answerKeys.some((key)=>!safe(f[key],1000))||String(f.duration_minutes)!=='90'||f.modality!=='Virtual') throw new Error('state');
    if (data.event_id && data.event_url!==`/events/${data.event_id}/`) throw new Error('state');
    return data;
  }
  async function click(run,target,activate=false) {
    guard(run); const priorNavigation=run.internalNavigation, priorAction=run.internalAction;
    run.internalNavigation=activate||priorNavigation; run.internalAction=activate||priorAction;
    try { const clicked=await window.SparkXGicaDemoCursor.click(target,{signal:run.controller.signal,activate}); if (!clicked && !(run.credentialPaused && run.planPromise && current(run))) throw new Error('state'); guard(run); }
    finally { run.internalNavigation=priorNavigation; run.internalAction=priorAction; }
  }
  async function events(run) {
    if(!document.querySelector('main[data-romeo-destination="events"]'))await click(run,document.querySelector('.main-nav [data-romeo-nav="events"]'),true);
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
    if(toggle.getAttribute('aria-expanded')!=='true'){await click(run,toggle,true);await wait(run,500);}
    const option=Array.from(form.querySelectorAll(`[data-event-select-option="${name}"]`)).find((node)=>node.dataset.eventSelectValue===String(value));
    await click(run,option,true); await wait(run,300);
    if (form.elements.namedItem(name)?.value!==String(value) || toggle.getAttribute('aria-expanded')!=='false') throw new Error('state');
  }
  async function date(run,value) {
    const form=document.querySelector('main form[data-event-block-form]');
    const toggle=form?.querySelector('[data-event-date-toggle]');if(!toggle)throw new Error('state');
    if(toggle.getAttribute('aria-expanded')!=='true'){await click(run,toggle,true);await wait(run,500);}
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
  async function typeControl(run,input,value,{paste=false}={}) {
    guard(run); if (!(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) || input.disabled || typeof value!=='string' || unsafe.test(value) || value.length>12000) throw new Error('state');
    await click(run,input); input.focus({preventScroll:true});
    const priorType=input instanceof HTMLInputElement?input.type:null, masked=['time','datetime-local'].includes(priorType);
    if(masked)input.type='text';
    try {
      input.value='';
      if(paste)input.value=value;
      else for(const letter of Array.from(value)){guard(run);input.value+=letter;input.scrollLeft=input.scrollWidth;if(!masked)input.dispatchEvent(new Event('input',{bubbles:true}));await wait(run,36);}
      guard(run); if(masked)input.type=priorType;
      input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
      if(input.value!==value)throw new Error('state');
    } finally {if(masked&&input.type!==priorType)input.type=priorType;}
  }
  async function point(run,target,holdMs=1100) {
    guard(run);if(!await window.SparkXGicaDemoCursor.point(target,{signal:run.controller.signal,holdMs}))throw new Error('state');guard(run);
  }
  async function time(run,value) {
    const form=document.querySelector('main form[data-event-block-form]'),input=form?.querySelector('[data-event-time]');
    await typeControl(run,input,value);
    if(form.elements.namedItem('starts_at')?.value.slice(11,16)!==value)throw new Error('state');
  }
  function endForm(run) { if (run.previewStarted) { run.previewStarted=false; window.SparkXGicaDemoPreview?.end(); } }
  function beginForm(run,fields,editing=false) { if (!window.SparkXGicaDemoPreview.begin(fields,{editing})) throw new Error('state'); run.previewStarted=true; }
  async function registerOrganization(run) {
    if(!document.querySelector('main[data-romeo-destination="directory"]'))await click(run,document.querySelector('.main-nav [data-romeo-nav="directory"]'),true);
    await directoryTab(run,'organizations');
    if(run.spec.organization.id){await narrate(run,'Gicaingenieros ya está en el directorio. Conservamos su registro.');return;}
    progress('Identidad de la institución','organization_register');
    await narrate(run,'En Directorio abrimos Nueva organización. Registro Gicaingenieros para reutilizar su identidad en nuestros eventos.');
    await click(run,document.querySelector('main[data-romeo-destination="directory"] .directory-actions a[href="/directory/organizations/new/"]'),true);
    const form=document.querySelector('main form.directory-form'), name=form?.elements.namedItem('name'), aliases=form?.elements.namedItem('aliases');
    await typeControl(run,name,run.spec.organization.name);
    await typeControl(run,aliases,run.spec.organization.aliases.join('\n'));
    await directoryCheck(run,form,'is_active',true);await directoryCheck(run,form,'is_synthetic',false);
    await submit(run,form);
    const spec=specification(await control(run,'bootstrap'));
    if (spec.run_id!==run.spec.run_id || !spec.organization.id) throw new Error('state'); run.spec=spec;
    await narrate(run,'La organización está guardada. Ahora registraremos al expositor para tenerlo disponible antes de crear el evento.');
  }
  async function directoryTab(run,tab) {
    const main=document.querySelector('main[data-romeo-destination="directory"]');if(!main)throw new Error('state');
    const link=Array.from(main.querySelectorAll('.directory-tabs a')).find((node)=>{const url=new URL(node.href,location.origin);return url.pathname==='/directory/'&&(tab==='organizations'?url.search==='?tab=organizations':!url.search)&&!url.hash;});
    if(!link)throw new Error('state');if(link.getAttribute('aria-current')!=='page')await click(run,link,true);
  }
  async function directoryCheck(run,form,name,value) {
    const input=form?.elements.namedItem(name);if(!(input instanceof HTMLInputElement)||input.type!=='checkbox')throw new Error('state');
    if(input.checked!==value)await click(run,input,true);if(input.checked!==value)throw new Error('state');
  }
  function directorySelect(run,form,name) {
    guard(run);const control=form?.elements.namedItem(name);
    if(!(control instanceof HTMLSelectElement)||!['category','organization'].includes(name))throw new Error('state');
    const wrapper=document.createElement('div');wrapper.className='event-select';
    const toggle=document.createElement('button');toggle.type='button';toggle.className='event-select-toggle';toggle.dataset.gicaDirectorySelect=name;toggle.dataset.eventSelectToggle=name;toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-haspopup','listbox');toggle.setAttribute('aria-label',name==='category'?'Categoría del expositor':'Organización del expositor');
    const list=document.createElement('div');list.className='event-select-options';list.dataset.eventSelectOptions=name;list.hidden=true;list.setAttribute('role','listbox');list.setAttribute('aria-label',toggle.getAttribute('aria-label'));
    const close=()=>{list.hidden=true;toggle.setAttribute('aria-expanded','false');};
    toggle.addEventListener('click',()=>{if(!current(run))return;const open=list.hidden;for(const node of form.querySelectorAll('[data-gica-directory-select]')){node.setAttribute('aria-expanded','false');node.nextElementSibling.hidden=true;}list.hidden=!open;toggle.setAttribute('aria-expanded',String(open));});
    toggle.textContent=control.selectedOptions[0]?.textContent||'Selecciona una opción';
    run.directoryControls??=new Set();run.directoryControls.add(toggle);
    for(const option of control.options){
      const button=document.createElement('button');button.type='button';button.dataset.gicaDirectoryOption=name;button.dataset.gicaDirectoryValue=option.value;button.setAttribute('role','option');button.setAttribute('aria-selected',String(option.selected));button.textContent=option.textContent;button.disabled=option.disabled;
      button.addEventListener('click',()=>{if(!current(run)||button.disabled)return;control.value=option.value;control.dispatchEvent(new Event('input',{bubbles:true}));control.dispatchEvent(new Event('change',{bubbles:true}));toggle.textContent=option.textContent;for(const node of list.children)node.setAttribute('aria-selected',String(node===button));close();toggle.focus({preventScroll:true});});
      run.directoryControls.add(button);list.append(button);
    }
    control.hidden=true;control.after(wrapper);wrapper.append(toggle,list);return {control,toggle,list};
  }
  async function directoryChoice(run,widget,value) {
    if(widget.toggle.getAttribute('aria-expanded')!=='true')await click(run,widget.toggle,true);
    await wait(run,350);const option=Array.from(widget.list.children).find((node)=>node.dataset.gicaDirectoryValue===value);
    if(!option)throw new Error('state');await click(run,option,true);if(widget.control.value!==value)throw new Error('state');
  }
  async function registerSpeaker(run) {
    await directoryTab(run,'people');
    if(run.spec.speakers.jorge){await narrate(run,'Jorge Gayoso ya está disponible en el directorio. Su participación se coordina para cada evento.');return;}
    const registration=run.spec.speaker_registration;
    if(!run.spec.organization.id||!window.SparkXGicaNavigation.bindDirectory({run_id:run.spec.run_id,organization_id:run.spec.organization.id,speaker_registration:registration}))throw new Error('state');
    progress('Registrar expositor','speaker_register');
    await narrate(run,'Pulso Nueva persona y registro a Jorge Gayoso como expositor de Gicaingenieros. Lo tendremos disponible para el caso de reemplazo; registrar sus datos no confirma su disponibilidad.');
    await click(run,document.querySelector('main[data-romeo-destination="directory"] .directory-actions a[href="/directory/people/new/"]'),true);
    const form=document.querySelector('main form.directory-form');if(!form)throw new Error('state');
    await typeControl(run,form.elements.namedItem('full_name'),registration.full_name);
    const category=directorySelect(run,form,'category'),organization=directorySelect(run,form,'organization');
    await directoryChoice(run,category,registration.category);
    await typeControl(run,form.elements.namedItem('expertise'),registration.expertise);
    await directoryChoice(run,organization,run.spec.organization.id);
    await directoryCheck(run,form,'is_active',true);await directoryCheck(run,form,'is_synthetic',registration.is_synthetic);
    if(form.elements.namedItem('aliases')?.value!==''||form.elements.namedItem('email')?.value!=='')throw new Error('state');
    await narrate(run,'Guardo a Jorge Gayoso sin inventar correo ni datos de contacto.');await submit(run,form);run.directoryControls?.clear();
    const spec=specification(await control(run,'bootstrap'));
    if(spec.run_id!==run.spec.run_id||spec.organization.id!==run.spec.organization.id||!uuid.test(spec.speakers.jorge||''))throw new Error('state');run.spec=spec;
    await narrate(run,'El expositor está guardado. Ahora volvemos a Mis eventos para crear el seminario con Robert Castillo como expositor inicial.');
  }
  async function fillForm(run) {
    const fields={...run.spec.fields,organization_id:run.spec.organization.id}; beginForm(run,fields);
    for (const [index,step] of steps.entries()) {
      progress(`Ficha · ${index+1} de ${steps.length} · ${step.label}`,step.key);
      const form=document.querySelector('main form[data-gica-demo-live="true"]'), field=form?.querySelector(`[data-gica-field="${step.key}"]`);
      if (!field || !window.SparkXGicaDemoPreview.mark(step.key)) throw new Error('state');
      const input=field.querySelector('input:not([type=hidden]),textarea,button');
      // Dropdowns and the date picker perform their single activation below.
      // Moving to their field first must not look like a second click.
      if(['organization','speaker','date','timezone','modality','capacity'].includes(step.key)){
        if(!await window.SparkXGicaDemoCursor.move(input||field,{signal:run.controller.signal}))throw new Error('state');
      }else await click(run,input||field);
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
        else if (step.key==='brief' || String(fields[step.key]).length>240) { if(!window.SparkXGicaDemoPreview.fill(step.key))throw new Error('state'); }
        else if(!await window.SparkXGicaDemoPreview.type(step.key,{signal:run.controller.signal}))throw new Error('state');
      };
      const outcomes=await Promise.allSettled([action(),narrate(run,step.speech)]);
      for (const result of outcomes) if (result.status==='rejected') throw result.reason;
    }
    if (!window.SparkXGicaDemoPreview.fill('is_synthetic',false)) throw new Error('state');
    await narrate(run,'La ficha está completa. Guardo el evento para preparar su agenda.');
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
  async function panel(run,name) {
    guard(run);const link=document.querySelector(`main[data-workspace] [data-panel-link="${name}"]`),region=document.querySelector(`main[data-workspace] [data-workspace-panel="${name}"]`);
    if(!link||!region)throw new Error('state');
    if((link.getAttribute('aria-selected')==='true'||link.getAttribute('aria-current')==='location')&&!region.hidden)return false;
    await click(run,link,true);await wait(run,380);return true;
  }
  async function plan(run,operation) {
    await panel(run,'proposals'); progress(operation==='plan'?'Preparar agenda con IA':operation==='change'?'Pedir cambio a la IA':'Actualizar expositor',operation);
    await narrate(run,operation==='change'?'Ahora pedimos un cambio de contenido a la IA: dar al menos cinco minutos más al caso práctico, mantener los noventa minutos del seminario y conservar al menos diez minutos de preguntas. Verás la solicitud, la espera y la nueva propuesta. Tú confirmarás si la aplicamos.':operation==='plan'?(run.continueExisting?'Retomo tus respuestas confirmadas y solicito a OpenAI que complete la propuesta. La ficha se conserva.':`Envío una ficha breve a ${run.provider==='openai'?'OpenAI':'la IA'} para preparar la agenda, las tareas y los borradores de comunicación. Mientras trabaja, puedes detener, continuar o cambiar la música.`):'Actualizo la asignación a Jorge. Conservamos los temas y los horarios que ya aprobamos; este cambio no necesita otra consulta a la IA.');
    const button=document.querySelector(operation==='change'?'main[data-gica-pilot="true"] [data-gica-pilot-plan="change"]':'main[data-gica-pilot="true"] [data-gica-pilot-plan]:not([data-gica-pilot-plan="change"])');
    if(!button)throw new Error('state'); run.planOperation=operation;run.planPromise=null;
    await click(run,button,true);if(!run.planPromise)throw new Error('state');
    const candidate=await run.planPromise;guard(run);
    if(run.reviewOnly){
      if(operation!=='plan'||candidate.run_id!==run.spec.run_id||candidate.event_id!==run.eventID||!uuid.test(candidate.job_id||'')||candidate.status!=='archived'||candidate.saved!==true)throw new Error('state');
      await narrate(run,'La agenda quedó guardada en Temporal para compararla después. No se ha publicado ni aprobado.');
      progress('Agenda guardada para comparación','agenda_archived');return;
    }
    if(run.autoApply&&operation==='plan'&&candidate.copy_saved!==true)throw new Error('state');
    if(candidate.event_id!==run.eventID||candidate.event_url!==savedURL||!uuid.test(candidate.candidate_id||'')||candidate.approve_url!==`${savedURL}candidates/${candidate.candidate_id}/approve/`||!window.SparkXGicaNavigation.bindCandidate(candidate.approve_url))throw new Error('state');
    run.internalNavigation=true;
    try {const result=await window.SparkXGicaNavigation.refreshPilot({signal:run.controller.signal});guard(run);if(!result.success)throw new Error('state');}
    finally{run.internalNavigation=false;}
    await panel(run,'proposals'); await point(run,document.querySelector('main #candidate .agenda-list')||document.querySelector('main #candidate h2'));
    await narrate(run,operation==='change'?'La IA propone esta distribución del tiempo. El caso práctico gana minutos, se conserva el turno de preguntas y el total sigue siendo noventa. Revisa las diferencias antes de pulsar Aprobar y continuar.':run.autoApply?(operation==='plan'?'La propuesta está lista y guardé una copia. Aplico la agenda para continuar el recorrido.':'La propuesta conserva la fecha y las sesiones. Aplico el reemplazo por Jorge.'):(operation==='plan'?'La propuesta está lista. Revisa sus sesiones, duración y tareas y pulsa Aprobar y continuar.':'La propuesta conserva la fecha y las sesiones. Ahora Jorge aparece como expositor. Revisa el reemplazo y pulsa Aprobar y continuar.'));
    // Only the explicitly authorized, fixed-pilot auto-apply presentations may
    // continue to its visible approval form without an intermediate pause.
    if(operation==='change'||!run.autoApply)await reviewApproval(run,operation==='change'?'Cambio de la IA · más tiempo para el caso práctico':operation==='plan'?'Agenda, preparación y comunicaciones':'Reemplazo por Jorge · misma fecha y horario');
    await approve(run,candidate.approve_url);progress('Agenda aprobada',operation+'_approved');
  }
  function reviewApproval(run,label) {
    return new Promise((resolve,reject)=>{
      guard(run);window.SparkXGicaDemoCursor?.release();run.reviewing=true;const box=document.createElement('aside');box.className='gica-ai-question';box.dataset.gicaPilotReview='';box.setAttribute('aria-label','Revisar propuesta');
      const title=document.createElement('strong');title.textContent=label;
      const text=document.createElement('p');text.textContent='La propuesta está visible para tu revisión. Tu aprobación permite aplicar esta versión y continuar.';
      const button=document.createElement('button');button.type='button';button.className='button button-primary';button.dataset.gicaPilotApproveContinue='';button.textContent='Aprobar y continuar';
      const finish=(approved)=>{run.reviewing=false;run.controller.signal.removeEventListener('abort',abort);box.remove();approved?resolve():reject(new DOMException('Pilot stopped','AbortError'));};
      const abort=()=>finish(false);button.addEventListener('click',(event)=>{if(event.isTrusted&&current(run))finish(true);});
      run.controller.signal.addEventListener('abort',abort,{once:true});box.append(title,text,button);document.body.append(box);button.focus({preventScroll:true});
    });
  }
  async function approve(run,path) {
    await panel(run,'proposals');
    await narrate(run,'Pulso Aprobar propuesta para aplicar esta versión.');
    const form=Array.from(document.querySelectorAll('main .candidate-actions form')).find((node)=>new URL(node.action,location.origin).pathname===path);
    await submit(run,form);
  }
  async function calendar(run,{replaced=false}={}) {
    if(!document.querySelector('main[data-romeo-destination="calendar"]')){await click(run,document.querySelector('.main-nav [data-romeo-nav="calendar"]'),true);await wait(run,450);}
    const day=document.querySelector(`main[data-romeo-destination="calendar"] [data-calendar-day="${initialDate}"]`);
    if(!day)throw new Error('state');if(day.getAttribute('aria-current')!=='date')await click(run,day,true);
    const anchor=Array.from(document.querySelectorAll('main .calendar-open-event')).find((node)=>new URL(node.href).pathname===savedURL);
    const detail=anchor?.closest('.calendar-event-detail');if(!detail)throw new Error('state');
    await point(run,detail,1400);
    await narrate(run,replaced?'El calendario mantiene el jueves diecinueve a las siete y media. Abrimos el evento para confirmar que Jorge reemplazó a Robert.':'El calendario muestra el jueves diecinueve a las siete y media. Abrimos el evento para revisar la agenda con Robert.');
    await click(run,anchor,true);progress('Evento abierto desde el calendario',replaced?'calendar_updated':'calendar_initial');
    await point(run,document.querySelector('main [data-event-speaker]'));
  }
  async function edit(run,changed=true) {
    const fields={...run.spec.fields,organization_id:run.spec.organization.id,speaker_id:changed?run.spec.speakers.jorge:run.spec.speakers.robert,date:initialDate};
    await narrate(run,changed?'Desde Mis eventos abrimos la ficha para cambiar únicamente el expositor.':'Abro la ficha guardada desde Mis eventos.');
    await events(run);
    const row=document.querySelector(`main[data-romeo-destination="events"] a.event-row[href="${savedURL}"]`);
    if(!row)throw new Error('state');await click(run,row,true);
    if(document.querySelector('main[data-workspace]')?.dataset.eventId!==run.eventID)throw new Error('state');
    await click(run,document.querySelector(`main .heading-actions a[href="${savedURL}edit/"]`),true);beginForm(run,fields,true);
    if(changed){await narrate(run,'Robert no puede participar ese día. En Editar ficha abrimos Expositor y elegimos a Jorge Gayoso, a quien registramos antes. La fecha se mantiene.');}
    await select(run,'speaker_id',fields.speaker_id);
    if(!changed){await date(run,fields.date);await time(run,fields.time);}
    const resources=changed?'Expositor: Jorge Gayoso. Presentación, material PDF, moderación y soporte por coordinar.':run.spec.fields.resources;
    const resourcesField=document.querySelector('main [data-gica-field="resources"] textarea,main [data-gica-field="resources"] input');
    await typeControl(run,resourcesField,resources);
    await narrate(run,'Guardo la ficha. Después actualizaré la agenda para que sus sesiones queden asignadas al expositor seleccionado.');
    await submit(run,document.querySelector('main form[data-gica-demo-live="true"]'));endForm(run);
    progress('Ficha actualizada',changed?'speaker_replaced':'initial_restored');
  }
  async function preparationReview(run) {
    await panel(run,'preparation');
    const region=document.querySelector('main #preparation'),rows=[...region.querySelectorAll('.preparation-row')];
    if(!rows.length)throw new Error('state');
    await point(run,region.querySelector('h2'));
    await narrate(run,`La preparación contiene ${rows.length} tareas. Deben concretar el contenido técnico de mantenimiento, el caso aplicado, los materiales, el acceso a Zoom, el ensayo y la moderación. Veamos lo que propone esta agenda.`);
    for(const row of rows.slice(0,3)){
      const instructions=row.querySelector('[data-task-instructions]');
      if(instructions&&!instructions.open)await click(run,instructions.querySelector('summary'),true);
      await point(run,row.querySelector('h4'));
      const dependencies=[...row.querySelectorAll('.preparation-dependencies li')].map((item)=>item.textContent.trim());
      await narrate(run,`${row.querySelector('h4').textContent.trim()}.${dependencies.length?' Antes debemos completar: '+dependencies.join('; ')+'.':''}`);
    }
    if(rows.length>3){await point(run,rows.at(-1).querySelector('h4'));await narrate(run,'La lista se desplaza dentro de Preparación. Cada tarea conserva sus instrucciones, dependencias y seguimiento.');}
    progress('Preparación específica del seminario','final_preparation');
  }
  async function simulateTask(run) {
    await panel(run,'preparation');
    const region=document.querySelector('main #preparation'),rows=[...region.querySelectorAll('.preparation-row')],row=rows[0];
    if(!row)throw new Error('state');
    const editor=row.querySelector('[data-task-followup]'),wasOpen=editor?.open;
    if(editor&&!editor.open)await click(run,editor.querySelector('summary'),true);
    await narrate(run,'Para registrar el avance, abre Actualizar estado, selecciona el estado y guarda una nota. Veamos un ejemplo de ensayo técnico, sin guardar avances ficticios en el evento.');
    if(editor&&!wasOpen)await click(run,editor.querySelector('summary'),true);
    const scene=document.createElement('section');scene.className='gica-demo-simulation';scene.dataset.gicaDemoSimulation='';scene.setAttribute('aria-label','Ejemplo de seguimiento sin guardar');
    const label=document.createElement('p');label.className='gica-simulation-label';label.textContent='Ejemplo de seguimiento · no modifica el evento';
    const heading=document.createElement('h3');heading.textContent=rows.find((item)=>/ensay|audio|pantalla|técnic/i.test(item.querySelector('h4')?.textContent||''))?.querySelector('h4').textContent||row.querySelector('h4').textContent;
    const badge=document.createElement('span');badge.dataset.gicaSimulatedState='';badge.setAttribute('role','status');
    const note=document.createElement('p');note.textContent='Supongamos que el equipo prepara la prueba de audio, pantalla y acceso a Zoom.';
    const actions=document.createElement('div');actions.className='gica-simulation-actions';
    const percentage=document.createElement('strong');percentage.dataset.gicaSimulatedProgress='';
    const bar=document.createElement('progress');bar.max=rows.length;bar.setAttribute('aria-label','Porcentaje del ejemplo de seguimiento');
    const labels={not_started:'No iniciado',in_progress:'En proceso',completed:'Completado'};
    run.simulationControls=new Set();run.simulation=scene;
    const show=(state)=>{badge.className=`task-state task-state-${state}`;badge.textContent=labels[state];badge.dataset.gicaSimulatedState=state;bar.value=state==='completed'?1:0;percentage.textContent=`${Math.floor(100*bar.value/rows.length)} % de avance en el ejemplo · ${bar.value} de ${rows.length} tareas`;for(const button of actions.children)button.setAttribute('aria-pressed',String(button.dataset.gicaSimulateStatus===state));};
    for(const [state,text] of Object.entries(labels)){
      const button=document.createElement('button');button.type='button';button.className='button button-secondary button-small';button.dataset.gicaSimulateStatus=state;button.textContent=text;run.simulationControls.add(button);
      button.addEventListener('click',()=>{if(current(run))show(state);});actions.append(button);
    }
    scene.append(label,heading,badge,note,actions,percentage,bar);region.querySelector('h2').after(scene);show('not_started');
    try{
      await point(run,heading);
      await click(run,actions.querySelector('[data-gica-simulate-status="in_progress"]'),true);
      await narrate(run,'El equipo inicia el ensayo: En proceso. El porcentaje aún no sube, porque la tarea no está terminada.');
      await click(run,actions.querySelector('[data-gica-simulate-status="completed"]'),true);
      await narrate(run,`Al comprobar audio, pantalla y acceso, registramos Completado con una nota. Una de ${rows.length} tareas representa el ${Math.floor(100/rows.length)} por ciento. En el evento real, cada cambio queda en su historial y puede reabrirse con un motivo.`);
      await wait(run,800);
      await click(run,actions.querySelector('[data-gica-simulate-status="not_started"]'),true);
      await narrate(run,'Termina el ejemplo. Las tareas reales conservan su avance; el equipo lo actualizará cuando las ejecute.');
    }finally{scene.remove();run.simulation=null;run.simulationControls?.clear();}
    progress('Estados y porcentaje de avance','task_states');
  }
  async function communicationReview(run) {
    await panel(run,'proposals');
    const communications=document.querySelector('main [data-gica-ai-communications]');
    if(!communications||communications.hidden)return;
    await point(run,communications.querySelector('h3'));
    await narrate(run,'Estos son textos preparados por la IA para comunicar el seminario. La invitación sirve para convocar; la descripción resume el contenido y las indicaciones orientan el acceso. Son editables antes de usarlos: revisa fecha, expositor y enlace. No se envían automáticamente.');
    for(const article of [...communications.querySelectorAll('article')].slice(0,3)){
      await point(run,article.querySelector('strong')||article);
      const text=article.querySelector('[data-communication-text]')?.textContent||article.querySelector('p')?.textContent;
      if(text?.trim()&&text.length<=1800)await narrate(run,`${article.querySelector('strong')?.textContent||'Mensaje'}: ${text.trim()}`);
    }
    progress('Contenido de las comunicaciones','final_proposals');
  }
  async function introduceGica(run) {
    await narrate(run,'Para terminar, abro Conoce a Gica. Aquí puedes configurar mi personalidad, mi voz y la conversación.');
    await click(run,document.querySelector('.main-nav [data-romeo-nav="profile"]'),true);
    if(!document.querySelector('main[data-romeo-destination="profile"]'))throw new Error('state');
    await point(run,document.querySelector('main #gica-profile-name'));
    await narrate(run,'Soy Gica, tu bot arquitecto. Te ayudo a completar la ficha y a navegar; solicito a la IA el contenido y te acompaño a revisar las propuestas.');
    await point(run,document.querySelector('main #gica-personalize-title'));
    await narrate(run,'Puedes elegir mi tono y apariencia. En Voz y conversación ajustas cómo hablo y cómo te escucho. El micrófono se activa cuando tú abres la conversación.');
    await point(run,document.querySelector('main #gica-memory-title'));
    await narrate(run,'Memoria reúne las interacciones y los patrones revisados. Las fechas, los horarios, los permisos y el presupuesto se validan en el software. También puedes pedirme los pasos del recorrido por voz o texto; preguntaré lo que falte y tú revisarás los cambios. Gracias por acompañarme en ArquiGica.');
    progress('Conoce a Gica','complete');
  }
  async function finalReview(run) {
    await panel(run,'plan');await point(run,document.querySelector('main #agenda .agenda-list'));
    await narrate(run,'La agenda ya está asignada a Jorge, el jueves diecinueve. Los temas y las horas se mantienen. Desde Ajustar horarios puedes preparar otro cambio para revisión.');
    progress('Revisar la agenda','final_agenda');
    await preparationReview(run);await simulateTask(run);await communicationReview(run);
    await plan(run,'change');
    await panel(run,'plan');await point(run,document.querySelector('main #agenda .agenda-list'));
    await narrate(run,'La agenda incorpora más tiempo para el caso práctico. El horario total y las preguntas se conservaron; la versión anterior sigue en el historial.');
    await panel(run,'activity');await point(run,document.querySelector('main #activity'));
    await narrate(run,'Actividad conserva el seguimiento de la solicitud y las versiones aprobadas.');progress('Revisar actividad','final_activity');
    await introduceGica(run);
  }
  async function execute(run) {
    // Start speech in the explicit click's activation, before any network await.
    await narrate(run,run.continueExisting?'Bienvenido a ArquiGica. Soy Gica, tu bot arquitecto. Continuaremos la agenda del evento guardado.':opening);
    if(!run.continueExisting){
      const draft=await window.SparkXGicaCreation.request('',{operation:'resume',source:'narrated-demo',signal:run.controller.signal,current:()=>current(run)}); guard(run);
      if (draft?.handled&&['collecting','review','invalid','conflict'].includes(draft.draft_status||draft.status)) throw new Error('existing');
      if (!draft || draft.handled&&!['created','cancelled','expired'].includes(draft.status)) throw new Error('state');
    }
    run.spec=specification(await control(run,'bootstrap'));
    if(run.continueExisting&&!run.spec.event_id){const error=new Error('missing');error.notice='No encontré el evento guardado para continuar. Abre Mis eventos y revisa su ficha.';throw error;}
    if (run.spec.event_id) { run.eventID=run.spec.event_id;savedURL=run.spec.event_url; window.SparkXGicaNavigation.bindPilot(run.spec.event_id); controls(); }
    await events(run);
    if(run.continueExisting){
      const eventRow=document.querySelector(`main[data-romeo-destination="events"] a.event-row[href="${savedURL}"]`);
      if(!eventRow)throw new Error('state');
      await narrate(run,'Abro el evento guardado para continuar su propuesta.');await click(run,eventRow,true);
      if(document.querySelector('main[data-workspace]')?.dataset.eventId!==run.eventID)throw new Error('state');
      run.eventID=run.spec.event_id;await plan(run,'plan');
    }else{
      await narrate(run,'Desde Mis eventos iremos primero al Directorio. Guardamos las identidades antes de utilizarlas en un evento.');
      await registerOrganization(run);await registerSpeaker(run);await events(run);
      await narrate(run,'Estamos en Mis eventos. Pulso Nuevo evento y completo la ficha bloque por bloque.');
      await newEvent(run);await fillForm(run);await plan(run,'plan');
    }
    if(run.reviewOnly){
      status('Agenda guardada en Temporal para comparación. No se publicó ni aprobó.','complete');
      release(run);emit('exchange',{assistantText:'La solicitud terminó. La agenda está guardada para su comparación.',userText:''});return;
    }
    await narrate(run,'Consultemos el evento en el calendario.');
    await calendar(run);
    await narrate(run,'Supongamos que Robert avisa que no puede participar el diecinueve. Mantendremos la fecha y elegiremos un reemplazo.');
    await edit(run,true); await plan(run,'replan'); await calendar(run,{replaced:true}); await finalReview(run);
    status('Evento organizado para el 19 de noviembre con Jorge Gayoso.','complete');
    release(run); emit('exchange',{assistantText:'Evento organizado. Puedes revisar su agenda, preparación y comunicaciones.',userText:''});
  }
  function release(run) {
    if (active!==run) return;
    endForm(run);run.directoryControls?.clear();run.simulation?.remove();run.simulationControls?.clear();window.SparkXGicaWaiting?.stop(); window.SparkXGicaDemoCursor?.release(); active=null; sequence+=1; controls();
    document.dispatchEvent(new CustomEvent('sparkx:gica-demo-end',{detail:{user:owner,completed:root.dataset.gicaDemoState==='complete'}})); voice(false);
  }
  function stop(message='Recorrido detenido. Los cambios que ya se guardaron se conservan. Revisa Mis eventos o el calendario antes de continuar.') {
    const run=active; if (!run) return;
    sequence+=1; run.controller.abort(); if (run.speaking) window.SparkXRomeoSpeech?.cancel();
    status(message,'stopped'); release(run); emit('exchange',{assistantText:message,userText:''});
  }
  async function start(mode='full',retryJobID=null) {
    if(!['full','agenda-review','agenda-live','agenda-openai','agenda-openai-continue'].includes(mode))return;
    if(mode==='agenda-openai-continue'&&!uuid.test(retryJobID||'')){status('Abre el evento y utiliza su opción de continuar disponible.','error');return;}
    if (active||document.hidden||!root.isConnected||document.body.dataset.voiceUser!==owner||document.body.dataset.portalRole!==role) return;
    window.SparkXGicaWaiting?.prepareFromGesture();
    if (!window.SparkXGicaPilotAI?.generate || !window.SparkXGicaWaiting?.complete||!window.SparkXGicaCreation?.request||!window.SparkXRomeoSpeech?.speak||!window.SparkXGicaDemoCursor?.click||!window.SparkXGicaNavigation?.bindDirectory||!window.SparkXGicaNavigation?.submitPilotForm||!window.SparkXGicaDemoPreview?.fill) { status('Recarga ArquiGica para cargar el recorrido completo del piloto.','error'); return; }
    const run={id:++sequence,controller:new AbortController(),speaking:false,inFlight:false,internalNavigation:false,internalAction:false,internalForm:null,previewStarted:false,reviewOnly:mode==='agenda-review',autoApply:['agenda-live','agenda-openai','agenda-openai-continue'].includes(mode),provider:mode.startsWith('agenda-openai')?'openai':'free',continueExisting:mode==='agenda-openai-continue',retryJobID:mode==='agenda-openai-continue'?retryJobID:null};
    active=run; controls(); status('Preparando recorrido del piloto con micrófono apagado…','preparing');
    const permission=new CustomEvent('sparkx:gica-demo-prepare',{cancelable:true}); document.dispatchEvent(permission);
    if (!permission.defaultPrevented||root.dataset.gicaDemoActive!=='true') { active=null; controls(); status('Termina la acción actual o cierra el comparador de voces antes de iniciar el piloto.','error'); return; }
    const panel=root.querySelector('#romeo-presence-details'); if (panel) panel.hidden=true;
    root.querySelector('[data-romeo-presence-toggle]')?.setAttribute('aria-expanded','false'); document.dispatchEvent(new CustomEvent('sparkx:romeo-action-layout'));
    try { await execute(run); }
    catch(error) {
      if (active!==run) return;
      if (!current(run)) { stop(); return; }
      const voiceMessage=error?.reason==='female_voice_unavailable'?'No encontré una voz femenina española local. Comprueba Sabina, Laura o Helena en Comparar voces.':error?.reason==='no_local_voice'?'No encontré una voz española local. Selecciona una en Comparar voces.':error?.reason==='voice_unavailable'?'La voz elegida ya no está disponible. Selecciona otra voz local en Comparar voces.':'El navegador interrumpió la narración. Comprueba Probar voz y vuelve a iniciar el recorrido.';
      const message=error?.message==='existing'?'Tienes un borrador pendiente. Continúalo o cancélalo antes de iniciar este piloto. Tu borrador se conserva.':
        error?.message==='speech'?voiceMessage+' Los cambios ya guardados se conservan.':error?.notice?error.notice+' El recorrido queda detenido para revisar.':
        'El recorrido se detuvo porque no pude confirmar un paso. Revisa Mis eventos o el calendario: los cambios guardados se conservan y no se repetirá el envío automáticamente.';
      status(message,'error'); run.controller.abort(); release(run); emit('exchange',{assistantText:message,userText:''});
    }
  }
  document.addEventListener('click',(event)=>{
    const target=event.target instanceof Element?event.target:null; if (!target) return;
    if (target.closest('[data-gica-demo-stop]')) { event.preventDefault(); event.stopImmediatePropagation(); stop(); return; }
    const startButton=target.closest('[data-gica-demo-start]');
    if(startButton){event.preventDefault();event.stopImmediatePropagation();start(startButton.dataset.gicaDemoMode||'full',startButton.dataset.gicaCompactRetryId||null);return;}
    if (!active) return;
    const configure=target.closest('[data-gica-ai-configure]');
    if(event.isTrusted&&active.credentialPaused&&configure&&window.SparkXGicaPilotAI?.canConfigure?.(configure))return;
    // Review expands already-rendered instructions and resources only. Forms,
    // business buttons and navigation keep the same presentation lease guards.
    const summary=target.closest('summary');
    if(active.reviewing&&event.isTrusted&&current(active)&&summary?.matches('main #candidate details > summary')&&summary.closest('main[data-gica-pilot="true"]')?.dataset.eventId===active.eventID)return;
    const planButton=target.closest('main[data-gica-pilot="true"] [data-gica-pilot-plan]');
    if (planButton && active.internalAction && !event.isTrusted && ['plan','replan','change'].includes(active.planOperation)) {
      event.preventDefault(); event.stopImmediatePropagation();
      const run=active;
      const retryID=planButton.dataset.gicaCompactRetryId||null;
      if((retryID&&!uuid.test(retryID))||(run.continueExisting&&active.planOperation==='plan'&&retryID!==run.retryJobID)){active.planPromise=Promise.reject(new Error('state'));return;}
      active.planPromise=['plan','change'].includes(active.planOperation)?window.SparkXGicaPilotAI.generate({runID:run.spec.run_id,eventID:run.eventID,expectedRevision:revision(),signal:run.controller.signal,csrf:csrf(),check:()=>current(run),narrate:(text)=>narrate(run,text),onStatus:(text)=>status(text,'waiting'),onCredentialPause:(paused)=>{if(active===run){run.credentialPaused=paused;status(paused?'Guía en pausa. Guarda la clave API y pulsa Reanudar guía.':'Reanudando guía desde este paso…',paused?'paused':'waiting');}},archive:run.reviewOnly,saveCopy:run.autoApply,provider:run.provider,retryJobID:retryID,changeRequest:active.planOperation==='change'?'more_case_time':null,executePrompt:(button)=>click(run,button,true)}):control(run,'replan',{run_id:run.spec.run_id,event_id:run.eventID,expected_revision:revision()}); return;
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
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&!active?.credentialPaused)stop();}); window.addEventListener('pagehide',()=>stop());
  new MutationObserver(()=>{if(active&&(!root.isConnected||document.body.dataset.voiceUser!==owner||document.body.dataset.portalRole!==role))stop();}).observe(document.body,{attributes:true,attributeFilter:['data-voice-user','data-portal-role'],childList:true});
  script();controls(); window.SparkXGicaDemo=Object.freeze({isActive:()=>!!active,stop:()=>stop(),canSimulationControl:(element)=>!!(active&&current(active)&&active.simulationControls?.has(element)&&element?.isConnected&&element.closest('main #preparation [data-gica-demo-simulation]')&&!element.disabled),canDirectoryControl:(element)=>!!(active&&current(active)&&active.directoryControls?.has(element)&&element?.isConnected&&element.closest('main .directory-form')&&location.pathname==='/directory/people/new/'&&!element.disabled)});
})();

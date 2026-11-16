/* Human-only local guidance. Server actions open bounded GET views; values
 * may prefill normal forms. Saving, generating and approving require the
 * form's ordinary human control. No model, credentials or admin tools here. */
(() => {
  'use strict';
  const root=document.querySelector('[data-romeo-presence]'),owner=document.body.dataset.voiceUser,role=document.body.dataset.portalRole;
  if(!root||!/^[1-9][0-9]{0,18}$/.test(owner||'')||!['admin','organizer'].includes(role)||!crypto.randomUUID)return;
  const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,unsafe=/[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}<>]/u;
  const actions=new Set(['open_event','open_agenda','open_preparation','open_calendar','open_generate','open_approval','open_edit_speaker','open_schedule','open_organization_create','open_speaker_create']);
  const interview=new Set(['objective','audience','modality','duration_minutes','location','resources','constraints']);
  const fieldNames=new Set(['organization_id','speaker_id','scheduled_dates','starts_at',...interview]);
  let state=null,selectedEvent='',busy=false,directory=null,choicesBox=null,banner=null,operation=null;
  const marked=new Set(),lastValues=new WeakMap();
  const clean=(value,max)=>typeof value==='string'&&value.trim().length>0&&value.length<=max&&!unsafe.test(value);
  const normalize=(value)=>value.normalize('NFD').replace(/\p{M}/gu,'').toLowerCase().match(/[\p{L}\p{N}]+/gu)?.join(' ')||'';
  function eligible(){return root.isConnected&&!document.hidden&&root.dataset.gicaDemoActive!=='true'&&document.body.dataset.voiceUser===owner&&document.body.dataset.portalRole===role;}
  function currentEvent(){const dom=document.querySelector('main[data-event-id]')?.dataset.eventId,match=/^\/events\/([0-9a-f-]{36})\//i.exec(location.pathname);return uuid.test(dom||'')?dom:uuid.test(match?.[1]||'')?match[1]:selectedEvent;}
  function isCreation(text){const words=new Set(normalize(text).split(' '));return [...words].some(w=>/^(?:cre|registr|agreg|organiz)/.test(w))&&[...words].some(w=>/^(?:eventos?|seminarios?|reuniones?|talleres?|conferencias?)$/.test(w));}
  function recognizes(text){const words=new Set(normalize(text).split(' '));return ['evento','eventos','ficha','agenda','agendas','propuesta','propuestas','plan','planes','calendario','calendarios','preparacion','tarea','tareas','hora','horas','fecha','fechas','horario','horarios','expositor','expositores','expositora','ponente','ponentes','asesor','institucion','instituciones','organizacion','organizaciones','empresa','empresas','continuar','continua','continuemos','siguiente','sigamos','seguimos','estado','pendiente','pendientes','falta','aprobar','aprobacion','listo','guardado','guarde','cancelar','cancela'].some(w=>words.has(w))||words.has('que')&&words.has('sigue')||words.has('donde')&&words.has('quedamos');}
  function clearView(){choicesBox?.remove();choicesBox=null;banner?.remove();banner=null;for(const node of marked)node.classList.remove('gica-field-current');marked.clear();}
  function reset(){operation?.abort();state=null;directory=null;selectedEvent='';clearView();}
  function local(reply,awaiting=''){return{handled:true,status:awaiting?'clarify':'info',reply,step:'directory',event_id:currentEvent()||'',event_revision:0,draft_id:'',revision:0,awaiting};}
  function choices(data){
    choicesBox?.remove();choicesBox=null;if(!data.choices?.length||!eligible())return;
    const box=document.createElement('aside');box.className='gica-ai-question';box.dataset.gicaGuidedChoices='';box.setAttribute('aria-label','Opciones de la guía de Gica');
    const title=document.createElement('strong');title.textContent=data.reply;
    const list=document.createElement('div');list.className='gica-ai-question-options';
    for(const [index,item]of data.choices.entries()){
      const button=document.createElement('button');button.type='button';button.className='button button-secondary';button.textContent=`${index+1}. ${item.label}`;
      button.addEventListener('click',()=>{if(!eligible()||busy||choicesBox!==box)return;document.dispatchEvent(new CustomEvent('sparkx:gica-guided-answer',{detail:{user:owner,draft_id:data.draft_id,revision:data.revision,value:item.value}}));});list.append(button);
    }
    const note=document.createElement('p');note.textContent='Elige una opción o responde con su nombre o número. No se guardará ningún cambio automáticamente.';
    box.append(title,list,note);document.body.append(box);choicesBox=box;
  }
  function show(data){
    banner?.remove();banner=null;const main=document.querySelector('main#main-content');
    if(!main||!eligible())return;
    const section=document.createElement('section');section.className='notice';section.dataset.gicaGuidedStatus='';section.setAttribute('role','status');
    const label=document.createElement('strong');label.textContent='Guía de Gica';
    const message=document.createElement('p');message.textContent=data.reply;
    section.append(label,message);main.prepend(section);banner=section;choices(data);
  }
  function valid(data){
    if(!data||typeof data!=='object'||Array.isArray(data)||typeof data.handled!=='boolean')return false;
    if(!data.handled)return true;
    if(!['ready','clarify','info','conflict'].includes(data.status)||!clean(data.reply,300)||!/^[a-z_]{1,40}$/.test(data.step||'')||
      typeof data.event_id!=='string'||data.event_id&&!uuid.test(data.event_id)||typeof data.draft_id!=='string'||data.draft_id&&!uuid.test(data.draft_id)||
      !Number.isSafeInteger(data.event_revision)||data.event_revision<0||!Number.isSafeInteger(data.revision)||data.revision<0||
      typeof data.awaiting!=='string'||data.awaiting&&!/^[a-z_]{1,40}$/.test(data.awaiting)||
      data.action!==undefined&&(!actions.has(data.action)||typeof data.url!=='string')||data.candidate_id!==undefined&&!uuid.test(data.candidate_id))return false;
    if(data.choices!==undefined&&(!Array.isArray(data.choices)||data.choices.length>3||data.choices.some(item=>!item||!uuid.test(item.value||'')||!clean(item.label,160))||new Set(data.choices.map(item=>item.value)).size!==data.choices.length))return false;
    if(data.field_values!==undefined&&(!data.action||!data.field_values||typeof data.field_values!=='object'||Array.isArray(data.field_values)||Object.keys(data.field_values).length>8))return false;
    return true;
  }
  function allowedURL(data){
    if(!data.action)return true;let url;try{url=new URL(data.url,location.origin);}catch(_){return false;}
    if(url.origin!==location.origin||url.username||url.password||!data.url.startsWith('/')||data.url.startsWith('//')||data.url.length>2048)return false;
    const base=`/events/${data.event_id}/`;
    if(['open_organization_create','open_speaker_create'].includes(data.action))return url.pathname===(data.action==='open_organization_create'?'/directory/organizations/new/':'/directory/people/new/')&&!url.search&&!url.hash;
    if(!uuid.test(data.event_id))return false;
    if(data.action==='open_calendar')return url.pathname==='/calendar/'&&!url.hash&&[...url.searchParams].every(([key,value])=>key==='month'?/^20\d{2}-\d{2}$/.test(value):key==='day'?/^20\d{2}-\d{2}-\d{2}$/.test(value):false);
    if(url.search)return false;
    if(data.action==='open_event')return [base,base+'edit/'].includes(url.pathname)&&['','#plan'].includes(url.hash);
    if(data.action==='open_edit_speaker')return url.pathname===base+'edit/'&&!url.hash;
    if(data.action==='open_schedule')return url.pathname===base+'schedule/'&&!url.hash;
    if(data.action==='open_preparation')return url.pathname===base+'preparation/'&&!url.hash||url.pathname===base&&url.hash==='#preparation';
    const hashes={open_agenda:['#agenda','#plan'],open_generate:['#proposal-form','#proposals'],open_approval:['#candidate']};
    return Object.hasOwn(hashes,data.action)&&url.pathname===base&&hashes[data.action].includes(url.hash);
  }
  function normalForm(){return document.querySelector('main#main-content form[data-event-block-form],main#main-content form.directory-form');}
  function dirty(form){return [...(form?.elements||[])].some(node=>node instanceof HTMLInputElement&&['checkbox','radio'].includes(node.type)?node.checked!==node.defaultChecked:
    node instanceof HTMLSelectElement?node.value!==([...node.options].find(option=>option.defaultSelected)?.value||node.options[0]?.value||''):
    (node instanceof HTMLInputElement||node instanceof HTMLTextAreaElement)&&node.type!=='hidden'&&node.value!==node.defaultValue);}
  function fill(data){
    const values=data.field_values||{},names=Object.keys(values);if(!names.length)return;
    const form=normalForm();if(!form||form.method.toLowerCase()!=='post'||new URL(form.action).origin!==location.origin)throw new Error('El formulario necesita revisión manual. No guardé ningún cambio.');
    const directoryFields=data.action==='open_organization_create'?new Set(['name']):data.action==='open_speaker_create'?new Set(['full_name','category','organization']):fieldNames;
    const pending=[];
    for(const name of names){
      const value=values[name],node=form.elements.namedItem(name);
      if(!directoryFields.has(name)||typeof value!=='string'||value.length>1200||unsafe.test(value)||!(node instanceof HTMLInputElement||node instanceof HTMLSelectElement||node instanceof HTMLTextAreaElement)||node.type==='hidden'||node.disabled||node.readOnly)throw new Error('Ese campo requiere revisión manual. No guardé ningún cambio.');
      if(node instanceof HTMLSelectElement&&![...node.options].some(option=>option.value===value))throw new Error('La opción ya no está disponible. Actualiza el formulario antes de elegirla.');
      const prior=node instanceof HTMLSelectElement?[...node.options].find(option=>option.defaultSelected)?.value||node.options[0]?.value||'':node.defaultValue;
      if(node.value!==prior&&node.value!==value&&lastValues.get(node)!==node.value)throw new Error('Tienes cambios manuales sin guardar. Revísalos; no los reemplacé.');
      pending.push([node,value]);
    }
    for(const [node,value]of pending){node.value=value;lastValues.set(node,value);node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));node.classList.add('gica-field-current');marked.add(node);}
    pending[0]?.[0].scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  }
  function beginDirectory(data){
    if(!['open_organization_create','open_speaker_create'].includes(data.action))return;
    const form=normalForm();if(!form?.matches('.directory-form'))return;
    const person=data.action==='open_speaker_create';
    directory={form,path:location.pathname,person,step:person?'full_name':'name',choices:[],event:data.event_id||''};
    const input=form.elements.namedItem(directory.step);
    if(input?.value.trim())directory.step=person?'organization':'aliases';
    data.reply=directory.step==='name'?'¿Cómo se llama la institución? Escribiré su nombre para que lo revises.':directory.step==='full_name'?'¿Cuál es el nombre completo del expositor? Lo escribiré en el formulario.':person?'¿Con qué institución lo registramos? Puedes decir ninguna.':'¿Qué siglas o nombre alternativo tiene? Puedes decir ninguna.';
    data.awaiting=directory.step;
  }
  function localValue(name,value){
    const form=directory.form,node=form.elements.namedItem(name);
    if(!eligible()||!form.isConnected||directory.path!==location.pathname||!(node instanceof HTMLInputElement||node instanceof HTMLTextAreaElement||node instanceof HTMLSelectElement)||node.disabled||node.readOnly||node.type==='hidden')return false;
    if(node instanceof HTMLSelectElement&&![...node.options].some(option=>option.value===value))return false;
    const old=node.value;node.value=value;
    if(node.value!==value||!node.checkValidity()){node.value=old;return false;}
    lastValues.set(node,value);node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));node.classList.add('gica-field-current');marked.add(node);return true;
  }
  function directoryAnswer(text){
    if(!directory)return null;
    if(!directory.form.isConnected||directory.path!==location.pathname){directory=null;return null;}
    const answer=normalize(text),skip=/^(?:no|ninguna?|sin (?:correo|institucion|siglas)|pendiente|omitir|saltar)$/.test(answer);
    if(/^(?:cancelar|cancela|cancelar registro)$/.test(answer)){directory=null;return local('De acuerdo. Dejé los campos para revisión; no registré ningún dato.');}
    const step=directory.step;
    if(/^(?:estado|continuar|continua|que sigue|que falta|donde nos quedamos|gracias|muchas gracias|guardar|guarda)$/.test(answer)){
      const prompt={name:'Necesito el nombre de la institución.',full_name:'Necesito el nombre completo del expositor.',aliases:'Dime una sigla o responde ninguna.',organization:'Dime la institución o responde ninguna.',email:'Dime el correo o responde pendiente.',expertise:'Dime su especialidad o responde pendiente.'}[step];
      return local((answer.includes('gracias')?'Con gusto. ':'Seguimos en el registro. ')+prompt+' El guardado necesita tu clic en el formulario.',step);
    }
    if(step==='name'||step==='full_name'){
      if(!clean(text,160)||skip)return local('Necesito un nombre válido. Dime sólo el nombre que irá en el formulario.',step);
      if(!localValue(step,text.trim()))return local('Revisa el nombre en el formulario; todavía no se ha guardado.',step);
      if(directory.person){localValue('category','speaker');directory.step='organization';return local('¿Con qué institución lo registramos? Puedes decir ninguna.','organization');}
      directory.step='aliases';return local('¿Qué siglas o nombre alternativo tiene? Puedes decir ninguna.','aliases');
    }
    if(step==='aliases'){
      if(!skip&&(!clean(text,160)||!localValue('aliases',text.trim())))return local('Dime una sigla breve o responde ninguna.','aliases');
      directory=null;return local('El nombre está en el formulario. Revisa sus datos y pulsa Crear organización para registrarla. Aún no se ha guardado.');
    }
    if(step==='organization'){
      const select=directory.form.elements.namedItem('organization');
      if(!(select instanceof HTMLSelectElement))return local('Selecciona la institución en el formulario. No guardé ningún dato.','organization');
      const candidates=[...select.options].filter(option=>option.value&&uuid.test(option.value));
      let matches=skip?[]:candidates.filter(option=>option.value===text||normalize(option.textContent)===answer);
      if(!skip&&!matches.length&&/^[1-3]$/.test(answer)&&directory.choices[Number(answer)-1])matches=candidates.filter(option=>option.value===directory.choices[Number(answer)-1].value);
      if(!skip&&!matches.length){const words=answer.split(' ');matches=candidates.filter(option=>words.every(word=>normalize(option.textContent).split(' ').includes(word)));}
      if(!skip&&matches.length!==1){directory.choices=matches.slice(0,3).map(option=>({value:option.value,label:option.textContent.trim()}));return{...local(matches.length?'Elige la institución por su nombre o número.':'No la encuentro en este formulario. Puedes decir ninguna o elegir otra institución.','organization'),choices:directory.choices};}
      if(!localValue('organization',skip?'':matches[0].value))return local('Selecciona la institución en el formulario. No guardé ningún dato.','organization');
      directory.choices=[];directory.step='email';return local('¿Qué correo tiene? Puedes decir pendiente para dejarlo vacío.','email');
    }
    if(step==='email'){
      const value=skip?'':text.trim().toLowerCase().replace(/\s+arroba\s+/g,'@').replace(/\s+punto\s+/g,'.').replace(/\s+/g,'');
      if(!localValue('email',value))return local('Ese correo necesita revisión. Dilo de nuevo o responde pendiente.','email');
      directory.step='expertise';return local('¿Cuál es su especialidad? Puedes decir pendiente.','expertise');
    }
    if(step==='expertise'){
      if(!skip&&(!clean(text,300)||!localValue('expertise',text.trim())))return local('Dime una especialidad breve o responde pendiente.','expertise');
      directory=null;return local('Sus datos están en el formulario. Revisa y pulsa Crear persona para registrarlo. Aún no se ha guardado.');
    }
    return local('Revisa el formulario y usa su botón para guardar. No he registrado ningún dato.');
  }
  async function request(text,{signal,current=()=>true}={}){
    if(!eligible()||busy||signal?.aborted||!clean(text,300)||isCreation(text))return null;
    if(directory){const result=directoryAnswer(text);if(result){show(result);return result;}}
    if(!state?.awaiting&&!recognizes(text))return null;
    const csrf=root.querySelector('[name=csrfmiddlewaretoken]')?.value;if(!/^[A-Za-z0-9]{64}$/.test(csrf||''))throw new Error('No pude comprobar tu sesión. Recarga antes de continuar.');
    const eventID=currentEvent(),payload={operation:'guide',text,request_id:crypto.randomUUID(),expected_revision:state?.draft_id?state.revision:0};
    if(uuid.test(eventID))payload.event_id=eventID;
    if(state?.draft_id&&state.event_id===eventID)payload.draft_id=state.draft_id;else payload.expected_revision=0;
    const controller=new AbortController(),abort=()=>controller.abort(),timer=setTimeout(abort,10000);operation=controller;signal?.addEventListener('abort',abort,{once:true});
    const owned=()=>eligible()&&!controller.signal.aborted&&!signal?.aborted&&current();
    busy=true;
    try{
      const response=await fetch('/assistant/event-creation/',{method:'POST',credentials:'same-origin',redirect:'error',cache:'no-store',signal:controller.signal,headers:{Accept:'application/json','Content-Type':'application/x-www-form-urlencoded;charset=UTF-8','X-CSRFToken':csrf},body:new URLSearchParams(payload)});
      if(!owned())return null;
      if(![200,409].includes(response.status)||!/^application\/json(?:;|$)/i.test(response.headers.get('Content-Type')||''))throw new Error('No pude comprobar el paso de la guía. No guardé ningún cambio.');
      const raw=await response.text();if(raw.length>12000)throw new Error('La respuesta de la guía necesita revisión.');
      const data=JSON.parse(raw);if(!valid(data)||!allowedURL(data))throw new Error('No pude comprobar el destino de la guía. No guardé ningún cambio.');
      if(data.handled&&((eventID&&data.event_id&&eventID!==data.event_id)||(payload.draft_id&&payload.draft_id!==data.draft_id)))throw new Error('La respuesta pertenece a otro paso. No se aplicó ningún cambio.');
      if(!data.handled||!owned())return data;
      state={...data};if(data.event_id)selectedEvent=data.event_id;
      choicesBox?.remove();choicesBox=null;
      if(data.action){
        const target=new URL(data.url,location.origin),form=normalForm();
        if(form&&dirty(form)&&(target.pathname!==location.pathname||target.search!==location.search)){data.reply='Tienes cambios sin guardar en este formulario. Revísalos antes de salir; no cambié de página.';data.status='info';show(data);return data;}
        const observed=await window.SparkXGicaNavigation?.openGuided({url:data.url,eventID:data.event_id||null,action:data.action,signal:controller.signal});
        if(!owned())return null;
        if(!observed?.success){data.reply='No pude comprobar la apertura del formulario. Tu página se conserva; no se guardó ningún cambio.';data.status='info';show(data);return data;}
        fill(data);beginDirectory(data);
      }
      show(data);return data;
    }finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);if(operation===controller)operation=null;busy=false;}
  }
  function validateChoice(token){
    if(!eligible()||busy||!token||token.user!==owner)return null;
    const data=directory?{draft_id:'',revision:0,choices:directory.choices}:state;
    if(!data||token.draft_id!==data.draft_id||token.revision!==data.revision)return null;
    return data.choices?.find(item=>item.value===token.value)||null;
  }
  new MutationObserver(()=>{if(document.body.dataset.voiceUser!==owner||document.body.dataset.portalRole!==role)reset();}).observe(document.body,{attributes:true,attributeFilter:['data-voice-user','data-portal-role']});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){operation?.abort();choicesBox?.remove();choicesBox=null;}});
  window.addEventListener('pagehide',reset);
  window.SparkXGicaGuided=Object.freeze({request,hasPending:()=>eligible()&&!!(directory||state?.awaiting),validateChoice,
    setEvent:(id)=>{if(eligible()&&uuid.test(id||'')){state=null;directory=null;selectedEvent=id;clearView();}},
    presentation:()=>Object.freeze({active:eligible()&&!!(directory||state||uuid.test(currentEvent())),busy,event_id:currentEvent()||'',awaiting:directory?.step||state?.awaiting||'',step:directory?'directory':state?.step||'',revision:state?.revision||0})});
})();

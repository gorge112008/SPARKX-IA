/* Bounded compact-planning client. Content is untrusted until the server has
 * validated it; only owner-bound pilot jobs and closed clarification choices
 * are accepted here. This module cannot approve a proposal. */
(() => {
  'use strict';
  const owner=document.body.dataset.voiceUser, role=document.body.dataset.portalRole;
  const pilot='bcf52dbd-206b-4d22-a294-8c487c770c56', uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const unsafe=/[\p{Cf}\p{Cs}\p{Zl}\p{Zp}\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/u;
  const plain=(value,max)=>typeof value==='string'&&value.trim().length>0&&value.length<=max&&!unsafe.test(value);
  let active=null;
  function valid(run) { return active===run&&!run.signal?.aborted&&(!document.hidden||run.credentialPaused)&&document.body.dataset.voiceUser===owner&&document.body.dataset.portalRole===role&&run.check()!==false; }
  function guard(run) { if(!valid(run))throw new DOMException('Planning stopped','AbortError'); }
  function delay(run,ms) { return new Promise((resolve,reject)=>{guard(run);const abort=()=>{clearTimeout(timer);reject(new DOMException('Planning stopped','AbortError'));};const timer=setTimeout(()=>{run.signal?.removeEventListener('abort',abort);resolve();},ms);run.signal?.addEventListener('abort',abort,{once:true});}); }
  function scope(run,data,jobRequired=true) {
    if(!data||data.run_id!==run.runID||data.event_id!==pilot||(jobRequired&&!uuid.test(data.job_id||'')))throw new Error('No pude verificar la respuesta de planificación.');
    return data;
  }
  function credentialPauseState(run,paused) {
    run.credentialPaused=paused;
    run.onCredentialPause(paused);
  }
  function clearCredentialPause(run) {
    if(run.credentialPaused)credentialPauseState(run,false);
    run.credentialBox?.remove();run.credentialBox=null;run.credentialConfigure=null;
  }
  function waitForCredential(run) {
    guard(run);
    window.SparkXGicaWaiting?.stop();
    if(run.promptBox)run.promptBox.hidden=true;
    credentialPauseState(run,true);
    const message='No encuentro la clave OpenAI. La guía queda en pausa en este paso. Guarda la clave y vuelve aquí para pulsar Reanudar guía.';
    run.onStatus(message);
    let box=run.credentialBox;
    if(!box){
      box=document.createElement('aside');box.className='gica-ai-question gica-ai-pause';box.dataset.gicaAiCredentialPause='';box.setAttribute('role','region');box.setAttribute('aria-label','Guía en pausa');
      const heading=document.createElement('h3');heading.textContent='Guía en pausa';
      const notice=document.createElement('p');notice.dataset.gicaAiPauseStatus='';notice.setAttribute('role','status');
      const instructions=document.createElement('p');instructions.textContent='La configuración se abre en otra pestaña. Al volver continuaremos desde aquí, con tus datos y respuestas guardados.';
      const actions=document.createElement('div');actions.className='gica-ai-pause-actions';
      if(role==='admin'){
        const configure=document.createElement('a');configure.className='button button-secondary';configure.dataset.gicaAiConfigure='';configure.href='/ai/control/';configure.target='_blank';configure.rel='noopener noreferrer';configure.textContent='Guardar clave API';actions.append(configure);run.credentialConfigure=configure;
      }else instructions.textContent='Pide al superadministrador que guarde la conexión OpenAI. Tus datos y respuestas se conservan mientras esperas aquí.';
      const resume=document.createElement('button');resume.type='button';resume.className='button button-primary';resume.dataset.gicaAiResume='';resume.textContent='Reanudar guía';
      actions.append(resume);box.append(heading,notice,instructions,actions);document.body.append(box);run.credentialBox=box;
    }
    const resume=box.querySelector('[data-gica-ai-resume]'),notice=box.querySelector('[data-gica-ai-pause-status]');
    notice.textContent=message;resume.disabled=false;resume.textContent='Reanudar guía';resume.focus({preventScroll:true});
    return new Promise((resolve,reject)=>{
      let finished=false;
      const finish=(error)=>{if(finished)return;finished=true;resume.removeEventListener('click',continueGuide);run.signal.removeEventListener('abort',abort);if(error)reject(error);else resolve();};
      const abort=()=>finish(new DOMException('Planning stopped','AbortError'));
      const continueGuide=(event)=>{
        if(!event.isTrusted||document.hidden||!valid(run)||resume.disabled)return;
        window.SparkXGicaWaiting?.prepareFromGesture?.();
        resume.disabled=true;resume.textContent='Comprobando conexión…';notice.textContent='Comprobando la conexión para continuar desde este paso.';
        credentialPauseState(run,false);finish();
      };
      resume.addEventListener('click',continueGuide);run.signal.addEventListener('abort',abort,{once:true});
    });
  }
  async function request(run,payload,path='/assistant/pilot-ai/') {
    // Retry only a local pre-enqueue rejection, on the user's Resume click.
    // Timeouts, failed workers and unknown receipts never resend inference.
    while(true){
      try{const data=await requestOnce(run,payload,path);clearCredentialPause(run);return data;}
      catch(error){
        if(error.code!=='ai_not_configured'||error.httpStatus!==400||run.provider!=='openai'||!['preview','start','answers','retry'].includes(payload?.operation))throw error;
        await waitForCredential(run);guard(run);
      }
    }
  }
  async function requestOnce(run,payload,path='/assistant/pilot-ai/') {
    guard(run);
    // A create POST is allowed to return its receipt after Stop so its exact
    // job can be cancelled. No response can resume the stopped presentation.
    const creates=payload&&['start','answers','retry'].includes(payload.operation),controller=new AbortController();
    if(creates)run.createdRequest=true;
    const abort=()=>controller.abort(),timer=setTimeout(abort,15000);
    if(!creates)run.signal?.addEventListener('abort',abort,{once:true});
    try{
      if(creates)promptState(run,'Enviando solicitud a ArquiGica…');
      const response=await fetch(path,{method:payload?'POST':'GET',credentials:'same-origin',redirect:'error',cache:'no-store',signal:controller.signal,
        headers:{Accept:'application/json',...(payload?{'Content-Type':'application/json','X-CSRFToken':run.csrf}: {})},...(payload?{body:JSON.stringify(payload)}:{})});
      if(!/^application\/json(?:;|$)/i.test(response.headers.get('Content-Type')||''))throw new Error('No pude comprobar la respuesta de ArquiGica.');
      const data=await response.json();
      if(!response.ok){guard(run);const error=new Error(plain(data?.error,500)?data.error:'La IA no pudo preparar la propuesta. Revisa su disponibilidad y vuelve a intentarlo.');error.notice=error.message;error.code=data?.code;error.httpStatus=response.status;throw error;}
      scope(run,data,payload?.operation!=='preview');
      if(creates||payload===null){
        const expected=run.provider==='openai'?'openai':'opencode';
        if(data.provider!==expected)throw new Error('Cambió el proveedor de esta solicitud. No aplicaré la respuesta.');
        run.model=plain(data.model,80)&&/^[a-z0-9._/-]+$/i.test(data.model)?data.model:'';
      }
      if(creates)run.jobID=data.job_id;guard(run);
      if(creates){
        promptState(run,'Solicitud recibida por ArquiGica');
        run.promptReady=false;run.promptExecute=null;run.promptBox?.remove();run.promptBox=null;
        if(['queued','running'].includes(data.status))await window.SparkXGicaWaiting?.start({signal:run.signal,provider:data.provider,model:run.model,phase:data.status==='queued'?'queued':'generating'});guard(run);
      }
      return data;
    }finally{clearTimeout(timer);run.signal?.removeEventListener('abort',abort);}
  }
  function checkQuestions(data) {
    const questions=data.questions;
    if(!Array.isArray(questions)||questions.length<1||questions.length>4)throw new Error('La IA devolvió preguntas que requieren revisión.');
    const ids=new Set();
    for(const item of questions){
      if(!/^q[1-4]$/.test(item?.id||'')||ids.has(item.id)||!plain(item.text,320)||!Array.isArray(item.options)||item.options.length<1||item.options.length>4)throw new Error('La IA devolvió preguntas que requieren revisión.');
      ids.add(item.id); const values=new Set();
      for(const option of item.options){if(!plain(option?.value,100)||!plain(option.label,180)||values.has(option.value))throw new Error('La IA devolvió opciones que requieren revisión.');values.add(option.value);}
    }
    return questions;
  }
  const normalized=(value)=>String(value).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  function selectedOption(item,text) {
    const value=normalized(text),letters=['a','b','c','d'];
    if(!value)return null;
    // Interpretation stays local and returns a closed option value only. An
    // ambiguous sentence, free text or silence cannot invent a preference.
    const exact=item.options.filter((option,index)=>[letters[index],`opcion ${letters[index]}`,normalized(option.label),normalized(option.value)].includes(value));
    if(exact.length===1)return exact[0];
    const marked=Array.from(value.matchAll(/(?:^|\s)(?:opcion|alternativa|prefiero|elijo|quiero|la)\s+(?:la\s+)?([abcd])(?=\s|$)/g),match=>letters.indexOf(match[1]));
    const distinct=[...new Set(marked)];
    return distinct.length===1&&distinct[0]<item.options.length&&!/\b(?:y|o)\s+(?:la\s+)?[abcd]\b/.test(value)?item.options[distinct[0]]:null;
  }
  function choose(run,item,index,total,previous) {
    return new Promise((resolve,reject)=>{
      guard(run);
      const box=document.createElement('aside');box.className='gica-ai-question';box.dataset.gicaAiQuestion=item.id;box.setAttribute('aria-label','Responder a Gica');
      const counter=document.createElement('span');counter.className='gica-ai-question-progress';counter.textContent=`Pregunta ${index+1} de ${total}`;
      const label=document.createElement('h3');label.textContent=item.text;
      const instruction=document.createElement('p');instruction.textContent='Elige una idea o escribe su letra. Esperaré tu respuesta.';
      const options=document.createElement('div');options.className='gica-ai-question-options';options.setAttribute('role','group');options.setAttribute('aria-label',item.text);
      const answer=document.createElement('div');answer.className='gica-ai-question-answer';
      const input=document.createElement('input');input.type='text';input.maxLength=240;input.autocomplete='off';input.dataset.gicaQuestionAnswer='';input.setAttribute('aria-label','Tu opción');input.placeholder='Por ejemplo: opción B';
      const confirm=document.createElement('button');confirm.type='button';confirm.className='button button-primary';confirm.dataset.gicaQuestionConfirm='';confirm.textContent='Elegir';
      const feedback=document.createElement('p');feedback.dataset.gicaQuestionFeedback='';feedback.setAttribute('role','status');
      const actions=document.createElement('div');actions.className='gica-ai-question-actions';
      const back=document.createElement('button');back.type='button';back.className='button button-secondary';back.dataset.gicaQuestionBack='';back.textContent='Corregir anterior';back.hidden=index===0;
      const cancelButton=document.createElement('button');cancelButton.type='button';cancelButton.className='text-link';cancelButton.dataset.gicaQuestionCancel='';cancelButton.textContent='Cancelar solicitud';
      let finished=false;
      const finish=(value)=>{if(finished)return;finished=true;run.signal?.removeEventListener('abort',abort);box.remove();if(value===null)reject(new DOMException('Planning stopped','AbortError'));else resolve(value);};
      const abort=()=>finish(null);
      const chooseOption=(option)=>{if(!valid(run)){finish(null);return;}document.dispatchEvent(new CustomEvent('sparkx:gica-companion-state',{detail:{kind:'exchange',user:owner,assistantText:item.text,userText:option.label}}));finish({action:'answer',value:option.value});};
      const cancelChoice=()=>{run.cancelledByChoice=true;run.controller.abort();};
      const goBack=()=>{if(index>0&&valid(run))finish({action:'back'});else feedback.textContent='Esta es la primera pregunta. Elige una opción o cancela la solicitud.';};
      const read=()=>{
        if(!valid(run)){finish(null);return;}
        const text=normalized(input.value);
        if(/^(?:cancelar|cancela|detener|deten)(?: la)?(?: solicitud| agenda)?$/.test(text)){cancelChoice();return;}
        if(/^(?:corregir|corrige|anterior|volver|regresar)(?: la)?(?: anterior| respuesta)?$/.test(text)){goBack();return;}
        const option=selectedOption(item,input.value);
        if(option){chooseOption(option);return;}
        feedback.textContent='No pude distinguir una sola opción. Pulsa una idea o escribe A, B, C o D, según las opciones visibles.';input.focus({preventScroll:true});
      };
      for(const [optionIndex,option]of item.options.entries()){const button=document.createElement('button');button.type='button';button.className='button button-secondary gica-ai-question-option';button.textContent=`${String.fromCharCode(65+optionIndex)}. ${option.label}`;button.dataset.gicaAiAnswer=option.value;
        if(previous===option.value)button.setAttribute('aria-label',`${button.textContent}. Tu elección anterior`);
        button.addEventListener('click',()=>chooseOption(option));options.append(button);}
      const prior=item.options.find((option)=>option.value===previous);if(prior)feedback.textContent=`Tu elección anterior: ${prior.label}. Puedes cambiarla.`;
      confirm.addEventListener('click',read);input.addEventListener('keydown',(event)=>{if(event.key==='Enter'){event.preventDefault();read();}});back.addEventListener('click',goBack);cancelButton.addEventListener('click',cancelChoice);
      answer.append(input,confirm);actions.append(back,cancelButton);box.append(counter,label,instruction,options,answer,feedback,actions);document.body.append(box);run.signal?.addEventListener('abort',abort,{once:true});input.focus({preventScroll:true});
    });
  }
  async function collectAnswers(run,questions) {
    const answers={};let index=0;
    while(index<questions.length){
      guard(run);const item=questions[index];await run.narrate(`${item.text} ${item.options.map((option,position)=>`${String.fromCharCode(65+position)}: ${option.label}`).join('. ')}.`);guard(run);
      const result=await choose(run,item,index,questions.length,answers[item.id]);guard(run);
      if(result.action==='back'){index-=1;continue;}
      answers[item.id]=result.value;index+=1;
    }
    return answers;
  }
  function candidate(run,data) {
    const base=`/events/${pilot}/`;
    if(!uuid.test(data.candidate_id||'')||data.candidate_url!==base+'#candidate'||data.approve_url!==`${base}candidates/${data.candidate_id}/approve/`)throw new Error('No pude confirmar la propuesta generada.');
    if(!Array.isArray(data.communications)||data.communications.length>3||data.communications.some((item)=>!plain(item?.type,40)||!plain(item.text,1800)))throw new Error('Los borradores de comunicación requieren revisión.');
    return {...data,event_url:base};
  }
  function promptState(run,text) {
    if(run.promptBox?.isConnected)run.promptBox.querySelector('[data-gica-ai-prompt-state]').textContent=text;
    run.onStatus(text);
  }
  async function preview(run,extra={}) {
    guard(run);
    const data=await request(run,{operation:'preview',run_id:run.runID,event_id:pilot,expected_revision:run.expectedRevision,...(!extra.parent_job_id&&!extra.failed_job_id?{provider:run.provider,...(run.changeRequest?{change_request:run.changeRequest}:{})}:{}),...extra});
    if(data.status!=='preview'||data.version!==1||!plain(data.prompt_text,24000)||data.max_input_tokens!==12000||data.max_output_tokens!==1800||!data.context||typeof data.context!=='object'||Array.isArray(data.context))throw new Error('No pude verificar el prompt preparado por ArquiGica.');
    if(!run.promptBox){
      document.querySelectorAll('[data-gica-ai-prompt-panel]').forEach((node)=>node.remove());
      const box=document.createElement('aside');box.className='gica-ai-prompt';box.dataset.gicaAiPromptPanel='';box.setAttribute('aria-label','Solicitud de Gica a la IA');
      const heading=document.createElement('strong');heading.textContent=run.provider==='openai'?'Gica → OpenAI':'Solicitud de Gica';
      const state=document.createElement('p');state.dataset.gicaAiPromptState='';state.setAttribute('role','status');
      const label=document.createElement('label');label.htmlFor='gica-ai-prompt-text';label.textContent='Prompt completo';
      const textarea=document.createElement('textarea');textarea.id='gica-ai-prompt-text';textarea.dataset.gicaAiPromptText='';textarea.readOnly=true;textarea.rows=10;textarea.spellcheck=false;
      const caps=document.createElement('small');caps.textContent='Respuesta limitada a 1.800 tokens · contrato JSON breve.';
      const execute=document.createElement('button');execute.type='button';execute.className='button button-primary';execute.dataset.gicaPromptExecute='';execute.textContent='Ejecutar solicitud';execute.disabled=true;
      const hide=document.createElement('button');hide.type='button';hide.className='text-link';hide.textContent='Ocultar prompt';hide.dataset.gicaAiPromptHide='';hide.hidden=true;
      hide.addEventListener('click',()=>{if(active!==run)box.remove();});
      box.append(heading,state,label,textarea,caps,execute,hide);document.body.append(box);run.promptBox=box;run.promptExecute=execute;
    }
    // Only this display is animated. Its final value is byte-for-byte the
    // server preview; neither the prompt nor the outgoing request is rebuilt.
    const textarea=run.promptBox.querySelector('[data-gica-ai-prompt-text]');textarea.value='';
    promptState(run,'Escribiendo el prompt · todavía sin enviar');textarea.focus({preventScroll:true});
    const characters=Array.from(data.prompt_text),chunk=Math.max(12,Math.ceil(characters.length/100));
    for(let offset=0;offset<characters.length;offset+=chunk){guard(run);textarea.value+=characters.slice(offset,offset+chunk).join('');textarea.scrollTop=textarea.scrollHeight;textarea.dispatchEvent(new Event('input',{bubbles:true}));await delay(run,18);}
    if(textarea.value!==data.prompt_text)throw new Error('No pude verificar el prompt completo.');
    promptState(run,'Prompt preparado');
    await run.narrate(run.executePrompt?(run.provider==='openai'?'El prompt está listo. Pulso Ejecutar para enviarlo a OpenAI.':'El prompt está listo. Pulso Ejecutar para enviarlo a la IA.'):'El prompt está listo. Revísalo y pulsa Ejecutar solicitud para enviarlo.');guard(run);
    run.promptReady=true;run.promptExecute.disabled=false;
    await new Promise((resolve,reject)=>{
      let finished=false,clicked=false;
      const finish=(error)=>{if(finished)return;finished=true;run.signal.removeEventListener('abort',abort);run.promptExecute?.removeEventListener('click',send);run.promptReady=false;if(error)reject(error);else resolve();};
      const abort=()=>finish(new DOMException('Planning stopped','AbortError'));
      const send=(event)=>{if(!valid(run)||(!event.isTrusted&&!run.executingPrompt))return;run.promptExecute.disabled=true;clicked=true;if(!run.executePrompt)finish();};
      run.signal.addEventListener('abort',abort,{once:true});run.promptExecute.addEventListener('click',send);
      if(run.executePrompt)Promise.resolve().then(async()=>{guard(run);run.executingPrompt=true;try{await run.executePrompt(run.promptExecute);}finally{run.executingPrompt=false;}guard(run);if(!clicked)throw new Error('No pude confirmar el clic de ejecución.');finish();}).catch(finish);
      else run.promptExecute.focus({preventScroll:true});
    });
  }
  function archived(run,data) {
    if(data.status!=='archived'||data.saved!==true||data.job_id!==run.jobID)throw new Error('No pude confirmar que la agenda quedó guardada.');
    return {run_id:run.runID,event_id:pilot,job_id:run.jobID,status:'archived',saved:true};
  }
  async function received(run,data,message) {
    guard(run);
    await window.SparkXGicaWaiting?.complete?.({signal:run.signal,provider:data.provider,model:run.model,message});
    guard(run);
  }
  async function cancel(run) {
    if(!run.jobID&&!run.createdRequest)return;
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
    try {await fetch('/assistant/pilot-ai/',{method:'POST',credentials:'same-origin',redirect:'error',cache:'no-store',signal:controller.signal,
      headers:{Accept:'application/json','Content-Type':'application/json','X-CSRFToken':run.csrf},body:JSON.stringify({operation:'cancel',run_id:run.runID,event_id:pilot,...(run.jobID?{job_id:run.jobID}:{request_key:run.requestKey})})});}catch(_){/* Status can still be checked manually; never resend generation. */}finally{clearTimeout(timer);}
  }
  async function generate({runID,eventID,expectedRevision,signal,csrf,narrate=async()=>{},check=()=>true,onStatus=()=>{},onCredentialPause=()=>{},archive=false,saveCopy=false,provider='free',retryJobID=null,changeRequest=null,executePrompt=null}={}) {
    if(active||(changeRequest!==null&&(changeRequest!=='more_case_time'||retryJobID!==null||archive===true))||!['free','openai'].includes(provider)||(retryJobID!==null&&(!uuid.test(retryJobID||'')||provider!=='openai'||archive===true))||eventID!==pilot||!uuid.test(runID||'')||!Number.isSafeInteger(expectedRevision)||expectedRevision<1||!/^[A-Za-z0-9]{64}$/.test(csrf||''))throw new Error('La planificación no está disponible en este momento.');
    const controller=new AbortController(),parentSignal=signal,abort=()=>controller.abort();
    parentSignal?.addEventListener('abort',abort,{once:true});if(parentSignal?.aborted)controller.abort();
    const run={runID,eventID,expectedRevision,signal:controller.signal,controller,csrf,narrate,check,onStatus,onCredentialPause:typeof onCredentialPause==='function'?onCredentialPause:()=>{},credentialPaused:false,credentialBox:null,credentialConfigure:null,provider,retryJobID,changeRequest,model:'',jobID:null,requestKey:crypto.randomUUID(),createdRequest:false,archive:archive===true,saveCopy:saveCopy===true,promptBox:null,promptExecute:null,promptReady:false,executingPrompt:false,executePrompt:typeof executePrompt==='function'?executePrompt:null};active=run;
    signal=run.signal;
    let complete=false;
    try{
      guard(run);await preview(run,run.retryJobID?{failed_job_id:run.retryJobID}:{});guard(run);
      let data=await request(run,{operation:run.retryJobID?'retry':'start',run_id:runID,event_id:pilot,expected_revision:expectedRevision,request_key:run.requestKey,...(run.retryJobID?{failed_job_id:run.retryJobID}:{provider:run.provider,...(run.changeRequest?{change_request:run.changeRequest}:{}),...(run.archive?{review_only:true}:{})})});
      run.jobID=data.job_id;await delay(run,350);let clarified=!!run.retryJobID,deadline=Date.now()+180000;
      while(true){
        guard(run);if(Date.now()>deadline)throw new Error('La IA está tardando demasiado. La solicitud queda detenida; puedes revisar su estado antes de reintentar.');
        if(data.status==='private_ready'&&run.archive){
          window.SparkXGicaWaiting?.update?.({phase:'saving',provider:data.provider,model:run.model,message:'Guardando la agenda para comparación.'});promptState(run,'Guardando agenda para comparación…');
          const receipt=archived(run,await request(run,{operation:'archive',run_id:runID,event_id:pilot,job_id:run.jobID}));
          await received(run,data,'Agenda recibida y guardada para comparación.');complete=true;promptState(run,'Agenda guardada en Temporal para comparación.');return receipt;
        }
        if(data.status==='proposal'&&!run.archive){
          window.SparkXGicaWaiting?.update?.({phase:'validating',provider:data.provider,model:run.model,message:'Respuesta recibida; comprobando la propuesta.'});
          const proposed=candidate(run,data);
          if(run.saveCopy){
            window.SparkXGicaWaiting?.update?.({phase:'saving',provider:data.provider,model:run.model,message:'Guardando una copia antes de aplicar la agenda.'});promptState(run,'Guardando una copia de la agenda…');
            archived(run,await request(run,{operation:'archive',run_id:runID,event_id:pilot,job_id:run.jobID}));
          }
          await received(run,data,'La propuesta está lista para continuar.');complete=true;return {...proposed,copy_saved:run.saveCopy};
        }
        if(data.status==='archived'&&run.archive){const receipt=archived(run,data);await received(run,data,'Agenda recibida y guardada para comparación.');complete=true;promptState(run,'Agenda guardada en Temporal para comparación.');return receipt;}
        if(['failed','stale','cancelled'].includes(data.status)){const error=new Error(plain(data.error,500)?data.error:'La IA no pudo completar la propuesta. Puedes volver a intentarlo cuando esté disponible.');error.notice=error.message;throw error;}
        if(data.status==='questions'){
          if(clarified)throw new Error('Hace falta revisar la ficha antes de continuar. No enviaré más solicitudes automáticamente.');
          clarified=true;const questions=checkQuestions(data);await received(run,data,'Necesito tu elección para completar la agenda.');
          await narrate(`Tengo ${questions.length===1?'una pregunta breve':questions.length+' preguntas breves'} para completar la propuesta.`);guard(run);
          const answers=await collectAnswers(run,questions);guard(run);
          await narrate('Gracias. Envío tus respuestas juntas para completar la agenda, la preparación y los mensajes.');guard(run);
          const parentID=run.jobID;await preview(run,{parent_job_id:parentID,answers});guard(run);
          run.requestKey=crypto.randomUUID();run.jobID=null;
          data=await request(run,{operation:'answers',run_id:runID,event_id:pilot,expected_revision:expectedRevision,request_key:run.requestKey,parent_job_id:parentID,answers});run.jobID=data.job_id;await delay(run,350);deadline=Date.now()+180000;continue;
        }
        if(!['queued','running'].includes(data.status))throw new Error('La IA devolvió un estado que requiere revisión.');
        const model=plain(data.model,80)&&/^[a-z0-9._/-]+$/i.test(data.model)?` · ${data.model}`:'';
        const label=run.provider==='openai'?'OpenAI':'IA';
        window.SparkXGicaWaiting?.update?.({phase:data.status==='queued'?'queued':'generating',provider:data.provider,model:run.model,message:data.status==='queued'?'Solicitud en cola de ArquiGica.':'Solicitud enviada; esperando la respuesta del modelo.'});
        promptState(run,`Esperando ${label}${model}${data.status==='queued'?' · en cola':''}`);
        await delay(run,1400);data=await request(run,null,`/assistant/pilot-ai/?job_id=${encodeURIComponent(run.jobID)}&run_id=${encodeURIComponent(runID)}`);
        if(data.job_id!==run.jobID)throw new Error('Cambió la referencia de la solicitud.');
      }
    } catch(error) {
      if(run.cancelledByChoice)error.notice='Cancelaste la solicitud. La ficha del evento se conserva.';
      if(!run.signal.aborted)promptState(run,'La solicitud no se completó. Revisa el aviso de Gica.');
      throw error;
    } finally {
      clearCredentialPause(run);
      window.SparkXGicaWaiting?.stop();document.querySelectorAll('[data-gica-ai-question]').forEach((node)=>node.remove());
      parentSignal?.removeEventListener('abort',abort);
      if(!run.archive||run.signal.aborted)run.promptBox?.remove();
      if(!complete)await cancel(run);if(active===run)active=null;
      if(run.archive&&run.promptBox?.isConnected)run.promptBox.querySelector('[data-gica-ai-prompt-hide]').hidden=false;
    }
  }
  window.SparkXGicaPilotAI=Object.freeze({generate,isActive:()=>!!active,isCredentialPaused:()=>!!(active&&valid(active)&&active.credentialPaused),canConfigure:(link)=>!!(active&&valid(active)&&active.credentialPaused&&link===active.credentialConfigure&&link?.isConnected&&active.credentialBox?.contains(link)),canExecute:(button)=>!!(active&&valid(active)&&active.promptReady&&button===active.promptExecute&&button?.isConnected&&!button.disabled&&active.promptBox?.contains(button))});
  new MutationObserver(()=>{if(active&&!valid(active))active.controller.abort();}).observe(document.body,{attributes:true,attributeFilter:['data-voice-user','data-portal-role'],childList:true});
})();

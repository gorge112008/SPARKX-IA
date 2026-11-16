/* Original local waiting music: no recordings, downloads or model requests.
 * Audio starts only after a gesture. Optional consented recognition accepts
 * music pause/resume only; progress reflects caller observations, never a %. */
(() => {
  'use strict';
  const presence=document.querySelector('[data-romeo-presence]'),owner=document.body.dataset.voiceUser,role=document.body.dataset.portalRole;
  if(!presence||!/^[1-9][0-9]{0,18}$/.test(owner||'')||!['admin','organizer'].includes(role))return;
  const phases=Object.freeze({preparing:'Preparando la solicitud',queued:'Solicitud en cola',generating:'La IA está creando tu agenda',validating:'Comprobando la propuesta',saving:'Guardando la propuesta',received:'Respuesta recibida'});
  const providers=Object.freeze({openai:'OpenAI',opencode:'OpenCode',groq:'Groq',gemini:'Gemini',ollama:'Ollama'});
  const MASTER_GAIN=.25,DUCK_GAIN=.025;
  const tracks=Object.freeze([
    {id:'orbita-pop',name:'Órbita pop',bpm:124,chords:[[60,64,67,71],[57,60,64,67],[65,69,72,76],[55,59,62,65]],bass:[48,45,41,43],melody:[76,null,79,81,null,79,76,74,72,null,76,79,81,null,79,76,77,null,81,84,null,81,79,77,74,77,null,79,83,81,79,null]},
    {id:'brisa-groove',name:'Brisa groove',bpm:119,chords:[[62,66,69,73],[59,62,66,69],[55,59,62,66],[57,61,64,67]],bass:[38,47,43,45],melody:[78,null,81,85,81,null,78,76,74,78,null,81,83,81,null,78,74,null,78,81,78,null,76,74,73,76,null,81,85,81,78,null]},
    {id:'chispa-latina',name:'Chispa latina',bpm:128,chords:[[65,69,72,76],[62,65,69,72],[58,62,65,69],[60,64,67,70]],bass:[41,50,46,48],melody:[77,81,null,84,81,null,79,77,74,null,77,81,84,81,null,77,74,77,null,81,77,null,74,72,76,null,79,84,79,null,76,74]}
  ]);
  let context=null,master=null,compressor=null,noise=null,state=null,timer=0,suspendTimer=0,track=0,nextAt=0,step=0,prepared=false,narrating=false;
  const sources=new Set(),Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  let recognition=null,listenTimer=0,voiceRequest=0;
  const box=document.createElement('aside');box.className='gica-waiting';box.dataset.gicaWaiting='';box.hidden=true;box.tabIndex=-1;box.setAttribute('aria-label','Seguimiento de la propuesta de Gica');
  const header=document.createElement('div');header.className='gica-waiting-heading';
  const activity=document.createElement('span');activity.className='gica-waiting-orbit';activity.setAttribute('aria-hidden','true');
  for(let index=0;index<3;index++)activity.append(document.createElement('i'));
  const heading=document.createElement('div');heading.className='gica-waiting-heading-copy';
  const label=document.createElement('strong');label.textContent=phases.preparing;
  const model=document.createElement('span');model.className='gica-waiting-model';model.dataset.gicaWaitingModel='';model.hidden=true;
  heading.append(label,model);
  const collapse=document.createElement('button');collapse.type='button';collapse.className='gica-waiting-collapse';collapse.textContent='Minimizar';collapse.setAttribute('aria-expanded','true');collapse.setAttribute('aria-controls','gica-waiting-controls');
  header.append(activity,heading,collapse);
  const status=document.createElement('p');status.className='gica-waiting-status';status.dataset.gicaWaitingStatus='';status.setAttribute('role','status');status.setAttribute('aria-live','polite');status.setAttribute('aria-atomic','true');
  const beam=document.createElement('div');beam.className='gica-waiting-beam';beam.setAttribute('role','progressbar');beam.setAttribute('aria-label','Solicitud en curso, progreso indeterminado');beam.append(document.createElement('span'));
  const scene=document.createElement('div');scene.className='gica-waiting-scene';scene.setAttribute('aria-hidden','true');
  // Fixed local vector art. Remote content never enters SVG or HTML.
  scene.innerHTML=`<svg class="gica-workshop" viewBox="0 0 480 174" focusable="false">
    <ellipse class="gica-workshop-ground" cx="131" cy="153" rx="98" ry="7"/>
    <g class="gica-workshop-robot"><path class="gica-workshop-antenna" d="M100 37V25"/><circle class="gica-workshop-light" cx="100" cy="21" r="5"/>
      <rect class="gica-workshop-body" x="64" y="91" width="72" height="54" rx="20"/>
      <path class="gica-workshop-seam" d="M89 119h22M90 129h20"/>
      <rect class="gica-workshop-ear" x="49" y="57" width="13" height="25" rx="6"/><rect class="gica-workshop-ear" x="138" y="57" width="13" height="25" rx="6"/>
      <g class="gica-workshop-head"><rect class="gica-workshop-head-shell" x="58" y="38" width="84" height="65" rx="23"/>
        <rect class="gica-workshop-face" x="69" y="51" width="62" height="38" rx="15"/>
        <g class="gica-workshop-eyes"><path d="M84 65v7M116 65v7"/></g><path class="gica-workshop-smile" d="M94 77q6 5 12 0"/></g>
      <path class="gica-workshop-arm left" d="M71 110q-12 19 10 26l18-4"/><path class="gica-workshop-arm right" d="M128 111q14 0 18 18l18 3"/>
    </g>
    <g class="gica-workshop-laptop"><path class="gica-workshop-laptop-screen" d="M122 92h65l-10 49h-65z"/><path class="gica-workshop-laptop-base" d="M102 142h88l9 7h-99z"/><path class="gica-workshop-laptop-mark" d="m145 111-7 6 5 6m15-12 5 6-7 6"/></g>
    <path class="gica-workshop-route" d="M206 96h95"/>
    <g class="gica-workshop-packets"><rect x="211" y="91" width="14" height="10" rx="3"/><rect x="238" y="91" width="14" height="10" rx="3"/><rect x="265" y="91" width="14" height="10" rx="3"/></g>
    <g class="gica-workshop-provider"><rect class="gica-workshop-provider-shell" x="319" y="33" width="121" height="119" rx="23"/>
      <circle class="gica-workshop-provider-ring" cx="379" cy="70" r="21"/><path class="gica-workshop-star" d="m379 55 4 11 11 4-11 4-4 11-4-11-11-4 11-4z"/>
      <g class="gica-workshop-lines"><path d="M340 111h72M340 123h52M340 135h64"/></g>
      <path class="gica-workshop-check" d="m362 119 10 10 24-26"/>
    </g></svg>`;
  const captions=document.createElement('div');captions.className='gica-waiting-captions';
  const botCaption=document.createElement('span');botCaption.textContent='Gica';
  const exchange=document.createElement('span');exchange.className='gica-waiting-exchange';exchange.textContent='Solicitud preparada';
  const providerCaption=document.createElement('span');providerCaption.textContent='IA';
  captions.append(botCaption,exchange,providerCaption);scene.append(captions);
  const controls=document.createElement('div');controls.id='gica-waiting-controls';
  const music=document.createElement('p');music.className='gica-waiting-music';music.dataset.gicaWaitingMusic='';
  const actions=document.createElement('div');actions.className='gica-waiting-actions';
  function button(text,hook){const node=document.createElement('button');node.type='button';node.className='button button-secondary';node.textContent=text;node.dataset[hook]='';actions.append(node);return node;}
  const pause=button('Detener música','gicaWaitingPause'),play=button('Continuar música','gicaWaitingPlay'),change=button('Cambiar pista','gicaWaitingChange'),speak=button('Hablar','gicaWaitingSpeak');
  speak.hidden=!Recognition;speak.setAttribute('aria-label','Decir detener o continuar para la música');
  const help=document.createElement('small');help.textContent='Puedes detener o cambiar la música. La solicitud seguirá trabajando.';
  controls.append(music,actions,help);box.append(header,scene,status,beam,controls);document.body.append(box);
  const eligible=()=>!document.hidden&&presence.isConnected&&document.body.dataset.voiceUser===owner&&document.body.dataset.portalRole===role;
  const valid=()=>!!state&&!state.signal?.aborted&&eligible();
  const plain=(value,limit)=>typeof value==='string'&&value.length<=limit&&!/[\p{Cf}\p{Cs}\x00-\x1f\x7f]/u.test(value)?value.trim():'';
  function emit(){document.dispatchEvent(new CustomEvent('sparkx:gica-ai-wait',{detail:{active:!!state,musicPlaying:!!state?.playing,user:owner}}));}
  function refresh(){
    box.hidden=!state;if(!state)return;
    box.dataset.phase=state.phase;label.textContent=phases[state.phase];
    const identity=[providers[state.provider],state.model].filter(Boolean).join(' · ');model.hidden=!identity;model.textContent=identity;
    providerCaption.textContent=providers[state.provider]||'IA';
    exchange.textContent=({preparing:'Preparando el mensaje',queued:'En cola de ArquiGica',generating:'Esperando respuesta',validating:'Respuesta recibida',saving:'Guardando en ArquiGica',received:'Respuesta conseguida'})[state.phase];
    beam.hidden=state.phase==='received';
    status.textContent=state.message||'Puedes seguir el proceso aquí. El tiempo depende del modelo.';
    pause.disabled=!state.playing;play.disabled=state.playing;
    music.textContent=state.playing?`♫ ${tracks[track].name} · música original`:`Música en pausa · ${tracks[track].name}`;
    box.classList.toggle('has-music',state.playing);
  }
  function update(detail={}){
    if(!valid()||state.completion||!detail||typeof detail!=='object'||Array.isArray(detail))return false;
    // Only complete() may enter the received hold after the caller validates
    // a real response. Late polling updates cannot restart its animation.
    if(Object.hasOwn(phases,detail.phase)&&detail.phase!=='received')state.phase=detail.phase;
    if(Object.hasOwn(providers,detail.provider)){if(state.provider!==detail.provider)state.model='';state.provider=detail.provider;}
    if(detail.model===null)state.model='';
    else if(typeof detail.model==='string'&&/^[a-z0-9._/-]{1,80}$/i.test(detail.model))state.model=detail.model;
    if(typeof detail.message==='string'){const message=plain(detail.message,220);if(message)state.message=message;}
    refresh();return true;
  }
  function ramp(value,seconds=.10){
    if(!master||!context||context.state==='closed')return;
    const now=context.currentTime;master.gain.cancelScheduledValues(now);master.gain.setValueAtTime(master.gain.value,now);master.gain.linearRampToValueAtTime(value,now+seconds);
  }
  function stopNotes(grace=.06){
    clearTimeout(timer);timer=0;
    const until=context?context.currentTime+grace:0;
    for(const source of sources){try{source.stop(until);}catch(_){/* Already ended. */}}
  }
  function idleAudio(delay=120){
    clearTimeout(suspendTimer);
    const prior=context;suspendTimer=setTimeout(()=>{suspendTimer=0;if(context===prior&&prior?.state==='running'&&!state?.playing)prior.suspend().catch(()=>{});},delay);
  }
  function tone(midi,at,length,level,type='sine'){
    const source=context.createOscillator(),envelope=context.createGain();
    source.type=type;source.frequency.value=440*2**((midi-69)/12);
    envelope.gain.setValueAtTime(.0001,at);envelope.gain.linearRampToValueAtTime(level,at+.012);envelope.gain.exponentialRampToValueAtTime(.0001,at+length);
    source.connect(envelope);envelope.connect(master);sources.add(source);
    source.onended=()=>{sources.delete(source);source.disconnect();envelope.disconnect();};source.start(at);source.stop(at+length+.02);
  }
  function brush(at,accent){
    if(!noise||!context.createBufferSource||!context.createBiquadFilter)return;
    const source=context.createBufferSource(),filter=context.createBiquadFilter(),envelope=context.createGain();
    source.buffer=noise;filter.type='highpass';filter.frequency.value=accent?1400:5200;
    envelope.gain.setValueAtTime(accent ? .065 : .024,at);envelope.gain.exponentialRampToValueAtTime(.0001,at+(accent ? .085 : .035));
    source.connect(filter);filter.connect(envelope);envelope.connect(master);sources.add(source);
    source.onended=()=>{sources.delete(source);source.disconnect();filter.disconnect();envelope.disconnect();};source.start(at);source.stop(at+.10);
  }
  function kick(at){
    const source=context.createOscillator(),envelope=context.createGain();source.type='sine';
    source.frequency.setValueAtTime(118,at);source.frequency.exponentialRampToValueAtTime(45,at+.12);
    envelope.gain.setValueAtTime(.12,at);envelope.gain.exponentialRampToValueAtTime(.0001,at+.15);
    source.connect(envelope);envelope.connect(master);sources.add(source);
    source.onended=()=>{sources.delete(source);source.disconnect();envelope.disconnect();};source.start(at);source.stop(at+.16);
  }
  function schedule(){
    if(!valid()||!state.playing||!context||context.state!=='running')return;
    const song=tracks[track],interval=60/song.bpm/2;
    // Do not catch up on missed time with a burst of notes after a slow frame.
    nextAt=Math.max(nextAt,context.currentTime+.025);
    while(nextAt<context.currentTime+.40){
      const bar=Math.floor(step/8)%4,beat=step%8,midi=song.melody[step%song.melody.length];
      if([0,3,6].includes(beat))for(const pitch of song.chords[bar])tone(pitch,nextAt,interval*.80,.022,'triangle');
      if([0,3,4,7].includes(beat))tone(song.bass[bar]+(beat===7?12:0),nextAt,interval*.72,.11,'triangle');
      if(midi!==null){tone(midi,nextAt,interval*.72,beat%2===0 ? .065 : .048,'triangle');tone(midi+12,nextAt+.012,interval*.45,.014);}
      if(beat%2===0)kick(nextAt);
      brush(nextAt,beat===2||beat===6);
      step+=1;nextAt+=interval;
    }
    timer=setTimeout(schedule,100);
  }
  async function prepareFromGesture(){
    if(!eligible())return false;
    try{
      const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return false;
      clearTimeout(suspendTimer);suspendTimer=0;
      if(!context||context.state==='closed'){
        context=new Audio();master=context.createGain();master.gain.value=0;
        if(context.createDynamicsCompressor){compressor=context.createDynamicsCompressor();compressor.threshold.value=-16;compressor.knee.value=18;compressor.ratio.value=3;compressor.attack.value=.01;compressor.release.value=.15;master.connect(compressor);compressor.connect(context.destination);}
        else master.connect(context.destination);
        if(context.createBuffer){noise=context.createBuffer(1,Math.floor(context.sampleRate*.12),context.sampleRate);const samples=noise.getChannelData(0);for(let index=0;index<samples.length;index++)samples[index]=(Math.random()*2-1)*(1-index/samples.length);}
      }
      await context.resume();prepared=context.state==='running';return prepared;
    }catch(_){return false;}
  }
  async function playMusic(){
    if(!valid()||state.phase==='received')return false;
    const waiting=state;clearTimeout(suspendTimer);suspendTimer=0;
    if(context&&prepared&&context.state==='suspended'){try{await context.resume();}catch(_){/* Continue button can retry. */}}
    if(!valid()||state!==waiting||state.phase==='received')return false;
    if(!context||context.state!=='running'){
      state.playing=false;refresh();music.textContent='Pulsa Continuar música para escucharla; la IA sigue trabajando.';emit();return false;
    }
    ramp(0,.025);stopNotes(.035);state.playing=true;nextAt=context.currentTime+.05;
    ramp(recognition||narrating?DUCK_GAIN:MASTER_GAIN,.15);schedule();refresh();emit();return true;
  }
  function pauseMusic(){if(!valid())return false;state.playing=false;ramp(0,.07);stopNotes(.08);idleAudio();refresh();emit();return true;}
  function stopListening(){
    voiceRequest+=1;clearTimeout(listenTimer);listenTimer=0;
    if(recognition){const prior=recognition;recognition=null;prior.onresult=null;prior.onerror=null;prior.onend=null;try{prior.abort();}catch(_){/* Not started. */}}
    ramp(state?.playing?(narrating?DUCK_GAIN:MASTER_GAIN):0,.12);speak.textContent='Hablar';speak.disabled=false;
    document.dispatchEvent(new CustomEvent('sparkx:gica-wait-listening',{detail:{user:owner,listening:false}}));
  }
  function stop(){
    if(!state)return;
    state.completion?.finish(false);
    state.signal?.removeEventListener('abort',stop);state=null;stopListening();ramp(0,.07);stopNotes(.08);idleAudio();refresh();emit();
  }
  async function start({signal,...detail}={}){
    stop();if(signal?.aborted||!eligible())return false;
    box.classList.remove('is-compact');collapse.textContent='Minimizar';collapse.setAttribute('aria-expanded','true');controls.hidden=false;
    state={signal,playing:false,phase:'preparing',provider:'',model:'',message:''};
    signal?.addEventListener('abort',stop,{once:true});update(detail);
    if(document.activeElement===document.body)box.focus({preventScroll:true});
    await playMusic();return !!state;
  }
  function complete({signal,provider,model,message}={}){
    if(!valid())return Promise.resolve(false);
    if(signal?.aborted){stop();return Promise.resolve(false);}
    const waiting=state;if(waiting.completion)return waiting.completion.promise;
    update({provider,model,message:plain(message,220)||'La respuesta está lista. Continúo en un momento.'});
    let resolve;
    const record={promise:new Promise((done)=>{resolve=done;}),timer:0,settled:false,finish:null};
    const abort=()=>{if(state===waiting)stop();else record.finish(false);};
    record.finish=(success)=>{
      if(record.settled)return;record.settled=true;clearTimeout(record.timer);signal?.removeEventListener('abort',abort);
      if(waiting.completion===record)waiting.completion=null;
      if(success&&state===waiting)stop();
      resolve(success);
    };
    waiting.completion=record;signal?.addEventListener('abort',abort,{once:true});
    // Keep the observed result visible for a full three seconds. It does not
    // approve anything, make another request, or outlive the owning run.
    record.timer=setTimeout(()=>{if(state!==waiting||!valid()||signal?.aborted){abort();return;}record.finish(true);},3000);
    waiting.phase='received';waiting.playing=false;stopListening();
    if(record.settled||state!==waiting)return record.promise;
    ramp(0,.25);stopNotes(.30);idleAudio(350);
    box.classList.remove('is-compact');collapse.textContent='Minimizar';collapse.setAttribute('aria-expanded','true');controls.hidden=false;
    refresh();emit();if(state===waiting&&controls.contains(document.activeElement))box.focus({preventScroll:true});
    return record.promise;
  }
  function command(text){
    if(!valid()||typeof text!=='string')return{handled:false};
    const token=text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[¿?¡!.,]/g,'').trim().replace(/^gica\s+/,'');
    if(token==='detener'){pauseMusic();return{handled:true,action:'pause',message:'Música en pausa. La propuesta sigue en curso.'};}
    if(token==='continuar'){playMusic();return{handled:true,action:'play',message:'Continúo la música mientras termina la propuesta.'};}
    return{handled:false,message:'Durante la espera puedes decir detener o continuar.'};
  }
  collapse.addEventListener('click',()=>{const minimized=box.classList.toggle('is-compact');collapse.textContent=minimized?'Controles':'Minimizar';collapse.setAttribute('aria-expanded',String(!minimized));controls.hidden=minimized;});
  pause.addEventListener('click',pauseMusic);
  play.addEventListener('click',async()=>{await prepareFromGesture();await playMusic();});
  change.addEventListener('click',()=>{if(!valid()||state.phase==='received')return;track=(track+1)%tracks.length;step=0;if(state.playing)playMusic();else refresh();});
  speak.addEventListener('click',async()=>{
    if(!Recognition||!valid()||state.phase==='received')return;if(recognition){stopListening();refresh();return;}
    const request=++voiceRequest,waiting=state;
    if(!await window.SparkXVoice?.requestConsent('command-session',speak)||request!==voiceRequest||state!==waiting||!valid())return;
    window.SparkXVoice?.stopDictation();
    const listener=new Recognition();recognition=listener;listener.lang='es-PE';listener.continuous=false;listener.interimResults=false;listener.maxAlternatives=1;
    ramp(DUCK_GAIN,.08);speak.textContent='Apagar mic';music.textContent='Te escucho: sólo detener o continuar la música.';
    document.dispatchEvent(new CustomEvent('sparkx:gica-wait-listening',{detail:{user:owner,listening:true}}));
    listener.onresult=(event)=>{if(recognition!==listener||state!==waiting||!valid())return;const text=event.results?.[event.resultIndex]?.[0]?.transcript;const result=command(text);stopListening();if(state===waiting)music.textContent=result.message||'Durante la espera puedes decir detener o continuar.';};
    listener.onerror=()=>{if(recognition===listener){stopListening();if(state===waiting)music.textContent='No pude escuchar. Puedes usar los botones de música.';}};
    listener.onend=()=>{if(recognition===listener){stopListening();if(state===waiting)refresh();}};
    listenTimer=setTimeout(()=>{if(recognition===listener){stopListening();if(state===waiting)refresh();}},20000);
    try{listener.start();}catch(_){stopListening();if(state===waiting)music.textContent='El micrófono no está disponible. Usa los botones de música.';}
  });
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
  document.addEventListener('sparkx:romeo-speech-state',(event)=>{narrating=event.detail?.state==='speaking';if(valid()&&state.playing)ramp(narrating||recognition?DUCK_GAIN:MASTER_GAIN,.15);});
  window.addEventListener('pagehide',()=>{stop();clearTimeout(suspendTimer);stopNotes(0);const prior=context;context=null;master=null;noise=null;compressor=null;prepared=false;try{prior?.close().catch(()=>{});}catch(_){/* Already closed. */}});
  new MutationObserver(()=>{if(state&&!valid())stop();}).observe(document.body,{attributes:true,attributeFilter:['data-voice-user','data-portal-role'],childList:true});
  window.SparkXGicaWaiting=Object.freeze({prepareFromGesture,start,stop,complete,command,update,getState:()=>Object.freeze({active:!!state,musicPlaying:!!state?.playing,user:owner,phase:state?.phase||null,provider:state?.provider||null,model:state?.model||null,track:tracks[track].id,completing:!!state?.completion})});
})();

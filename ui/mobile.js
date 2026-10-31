'use strict';
window.mountCharlieMobile=function(root){
  if(window.stopCharlieMobile)window.stopCharlieMobile();
  root.innerHTML=`<section class="charlie-mobile"><div class="mobile-heading"><div><div class="eyebrow">ELEGOO · Operator console</div><h1>Mobile Body</h1></div><button id="mc-emergency" class="mobile-stop" disabled>EMERGENCY STOP</button></div>
  <div class="mobile-grid"><section class="mobile-panel"><h2>Live view <span id="mc-health">/ disconnected</span></h2><div class="mobile-view" id="mc-view"><canvas id="mc-canvas" width="640" height="480" aria-label="ELEGOO camera and object hypotheses"></canvas><div id="mc-stale" class="mobile-stale">Camera unavailable · Connect to Charlie</div></div>
  <div id="mc-metrics" class="mobile-metrics">FPS — · receipt age — · exposure latency unknown</div><div class="mobile-actions"><label><input id="mc-overlay" type="checkbox" checked> Object overlays</label><button id="mc-fullscreen">Fullscreen</button><button id="mc-screenshot" disabled>Screenshot</button></div><p id="mc-detections">Recognition unavailable or stale</p></section>
  <section class="mobile-panel"><h2>Manual control</h2><div id="mc-control" class="mobile-status" role="status" aria-live="polite">Monitoring only · no operator lease</div><div class="mobile-actions"><button id="mc-acquire" disabled>Take control</button><button id="mc-release" disabled>Release</button></div><label>Speed · <output id="mc-speed-value">20</output> PWM (hardware cap 35)<input id="mc-speed" type="range" min="1" max="35" value="20"></label>
  <div class="mobile-pad" aria-label="Hold to drive; release to stop"><button data-dir="FORWARD,LEFT" disabled aria-label="Forward left">↖</button><button data-dir="FORWARD" disabled aria-label="Forward">↑</button><button data-dir="FORWARD,RIGHT" disabled aria-label="Forward right">↗</button><button data-dir="LEFT" disabled aria-label="Left">←</button><button id="mc-stop" disabled>STOP</button><button data-dir="RIGHT" disabled aria-label="Right">→</button><button data-dir="REVERSE,LEFT" disabled aria-label="Reverse left">↙</button><button data-dir="REVERSE" disabled aria-label="Reverse">↓</button><button data-dir="REVERSE,RIGHT" disabled aria-label="Reverse right">↘</button></div><p>Hold WASD, arrows, or a direction. Release stops. Combined steering alternates separately qualified pivot and travel pulses; no unqualified wheel mixing.</p><pre id="mc-command">No motor command</pre></section></div>
  <section class="mobile-panel mobile-sensors"><h2>Shared sensors</h2><div id="mc-distance" class="mobile-range">— cm</div><p id="mc-range-status">Ultrasonic unavailable</p><pre id="mc-sensors">Waiting for shared telemetry</pre></section>
  <details open><summary>Private connection</summary><form id="mc-connect"><label>Charlie endpoint<input id="mc-endpoint" type="url" value="http://127.0.0.1:8768" required></label><label>Monitoring token<input id="mc-monitor" type="password" autocomplete="off" minlength="32" required></label><label>Drive token (optional)<input id="mc-drive" type="password" autocomplete="off"></label><button>Connect</button> <button id="mc-disconnect" type="button">Disconnect</button></form><p>Use Charlie’s existing loopback service through an SSH tunnel, or authenticated private HTTPS. Tokens stay in page memory. A control lease never replaces hardware qualification.</p><p>If browser local-network access is blocked, open <a class="mobile-link" href="http://127.0.0.1:8768/mobile" target="_blank" rel="noopener noreferrer">Mobile Body through your tunnel</a>.</p></details></section>`;
  const el=id=>root.querySelector('#mc-'+id),pads=[...root.querySelectorAll('[data-dir]')];
  let endpoint='',monitor='',drive='',lease=null,boot=null,seq=0,status=null,connected=false,stopped=false;
  let generation=0,pollTimer,driveTimer,frameTimer,staleTimer,busy=false,held=new Set(),pointer=new Map(),turn=0,lastImage=null,lastMeta=null,lastDisplayed=0;
  let displayed=[],displayedId=null,lastStatusAt=0;
  const events=new AbortController();
  const text=(id,value)=>{if(el(id))el(id).textContent=value;};
  async function api(path='/api/mobile',body,driveAuth=false,timeout=1500){
    const r=await fetch(endpoint+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+(driveAuth?drive:monitor),...(body?{'Content-Type':'application/json'}:{})},
      body:body?JSON.stringify(body):undefined,credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(timeout),keepalive:body?.action==='release'});
    if(!r.ok){let v=await r.json();throw Error(v.error||'Connection failed');}return path.startsWith('/api/mobile/frame')?r:r.json();
  }
  function render(){
    const live=connected&&status&&performance.now()-lastStatusAt<1000;
    el('acquire').disabled=!live||!drive||!!lease||!status.control.available;
    el('release').disabled=!lease;el('emergency').disabled=!connected||!drive;
    el('stop').disabled=!lease;pads.forEach(p=>p.disabled=!lease);
    if(live){text('control',(lease?'You hold control':status.control.owned?'Another operator owns control':'Monitoring')+' · '+status.control.reason);
      text('command',JSON.stringify(status.control.command,null,2));
      const u=status.sensors['elegoo-ultrasonic'];text('distance',u?.available&&u.centimeters!=null?u.centimeters.toFixed(1)+' cm':'— cm');
      text('range-status',u?.available?`${u.hz?.toFixed(1)??'—'} Hz · ${(u.age_seconds*1000).toFixed(0)} ms old · ${u.values.valid===false?'invalid':'reported valid; accuracy unqualified'}`:'Ultrasonic stale or unavailable · '+(u?.error||u?.health||'no producer'));
      text('sensors',JSON.stringify({sources:status.sensors,deferred:status.deferred_sensors},null,2));
    }
  }
  function stale(reason){el('stale').hidden=false;text('stale',reason);text('health','/ stale or unavailable');el('screenshot').disabled=true;text('detections','Recognition unavailable or stale');}
  function draw(){
    if(!lastImage||!lastMeta)return;
    const canvas=el('canvas'),ctx=canvas.getContext('2d');canvas.width=lastImage.width;canvas.height=lastImage.height;ctx.drawImage(lastImage,0,0);
    const p=lastMeta.detections||status?.detections;
    const current=p&&p.source===lastMeta.source&&p.frame_id===lastMeta.frame_id&&p.stream_generation===lastMeta.generation&&p.geometry[0]===canvas.width&&p.geometry[1]===canvas.height;
    text('detections',current?p.objects.map(o=>`${o.label} ${(o.confidence*100).toFixed(0)}% · ${o.id}`).join(' / ')||'No objects on this frame':'Recognition unavailable or stale for this frame');
    if(current&&el('overlay').checked){ctx.strokeStyle='#85f4b0';ctx.fillStyle='#85f4b0';ctx.lineWidth=Math.max(2,canvas.width/400);ctx.font=`${Math.max(14,canvas.width/45)}px system-ui`;
      p.objects.forEach(o=>{const [x,y,r,b]=o.box;ctx.strokeRect(x,y,r-x,b-y);ctx.fillText(`${o.label} ${(o.confidence*100).toFixed(0)}% · ${o.id}`,x,Math.max(18,y-5));});}
  }
  async function frames(g){
    const start=performance.now();
    try{const r=await api('/api/mobile/frame'+(el('overlay').checked?'?overlays=1':'')),meta=JSON.parse(r.headers.get('X-Charlie-Frame')),blob=await r.blob(),img=await createImageBitmap(blob);
      if(g!==generation||!connected){img.close();return;}
      if(meta.age_seconds+(performance.now()-start)/1000>.5){img.close();stale('Frame stale in transit');}
      else{lastImage?.close();lastImage=img;lastMeta=meta;lastDisplayed=performance.now();if(displayedId!==meta.frame_id){displayed.push(lastDisplayed);displayedId=meta.frame_id;}displayed=displayed.filter(t=>lastDisplayed-t<5000);draw();el('stale').hidden=true;el('screenshot').disabled=false;text('health','/ receiving');
        const fps=displayed.length>1?(displayed.length-1)*1000/(displayed.at(-1)-displayed[0]):null;
        text('metrics',`${fps?.toFixed(1)??'—'} displayed FPS · ${meta.subscriber_fps?.toFixed(1)??'—'} subscriber FPS · ${(meta.age_seconds*1000).toFixed(0)} ms receipt age · ${(performance.now()-start).toFixed(0)} ms HTTP/decode · exposure latency unknown`);}
    }catch(e){if(g===generation)stale(e.message);}
    if(g===generation&&connected)frameTimer=setTimeout(()=>frames(g),0);
  }
  async function poll(g){
    try{const next=await api();if(g!==generation)return;if(boot&&boot!==next.boot){lose('Charlie restarted');return;}status=next;boot=next.boot;lastStatusAt=performance.now();
      if(lease&&(!next.control.owned||next.control.expires_in<=0)){lose('Control lease ended');return;}render();draw();
    }catch(e){if(g!==generation)return;lose(e.message);return;}
    if(g===generation&&connected)pollTimer=setTimeout(()=>poll(g),250);
  }
  function payload(action){return {action,boot,lease,sequence:++seq};}
  function clearHeld(){held.clear();pointer.clear();pads.forEach(p=>p.dataset.held='false');}
  async function release(reason='Control released'){
    clearHeld();const body=lease?payload('release'):null;lease=null;render();text('control',reason);
    if(body&&connected)try{await api('/api/mobile',body,true);}catch(e){text('control','Release unconfirmed · server watchdog remains active');}
  }
  function lose(reason){
    // Stop command production before attempting the independent release path.
    release(reason);connected=false;generation++;clearTimeout(pollTimer);clearTimeout(frameTimer);render();stale(reason);
  }
  function directions(){
    const all=new Set([...held,...[...pointer.values()].flat()]);
    if(all.has('FORWARD')&&all.has('REVERSE')){all.delete('FORWARD');all.delete('REVERSE');}
    if(all.has('LEFT')&&all.has('RIGHT')){all.delete('LEFT');all.delete('RIGHT');}
    return [...all];
  }
  async function tick(){
    if(lease&&connected&&!busy){busy=true;const g=generation,choices=directions(),direction=choices.length?choices[(turn++)%choices.length]:null;
      try{await api('/api/mobile',{...payload(direction?'drive':'heartbeat'),...(direction?{direction,pwm:Number(el('speed').value)}:{})},true);}
      catch(e){if(g===generation&&lease)lose(e.message);}finally{busy=false;}}
    if(!stopped)driveTimer=setTimeout(tick,100);
  }
  function halt(){clearHeld();if(lease&&connected)api('/api/mobile',payload('stop'),true).catch(e=>lose(e.message));}
  const keymap={w:'FORWARD',ArrowUp:'FORWARD',s:'REVERSE',ArrowDown:'REVERSE',a:'LEFT',ArrowLeft:'LEFT',d:'RIGHT',ArrowRight:'RIGHT'};
  window.addEventListener('keydown',e=>{if(!lease||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;if(e.key===' '){e.preventDefault();halt();return;}const d=keymap[e.key]||keymap[e.key.toLowerCase()];if(d){e.preventDefault();held.add(d);}},{signal:events.signal});
  window.addEventListener('keyup',e=>{const d=keymap[e.key]||keymap[e.key.toLowerCase()];if(d){held.delete(d);if(lease){e.preventDefault();halt();}}},{signal:events.signal});
  window.addEventListener('blur',()=>release('Focus lost · control released'),{signal:events.signal});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)release('Page hidden · control released');},{signal:events.signal});
  window.addEventListener('pagehide',()=>release('Page closed'),{signal:events.signal});
  pads.forEach(p=>{p.onpointerdown=e=>{if(!lease)return;e.preventDefault();p.setPointerCapture(e.pointerId);pointer.set(e.pointerId,p.dataset.dir.split(','));p.dataset.held='true';};
    p.onpointerup=p.onpointercancel=p.onlostpointercapture=e=>{pointer.delete(e.pointerId);p.dataset.held='false';halt();};});
  el('connect').onsubmit=e=>{e.preventDefault();const m=el('monitor').value,d=el('drive').value,target=el('endpoint').value;
    release();generation++;connected=false;clearTimeout(pollTimer);clearTimeout(frameTimer);
    try{const u=new URL(target);if(u.username||u.password||u.search||u.hash||!['','/'].includes(u.pathname)||!(u.protocol==='https:'||(u.protocol==='http:'&&['localhost','127.0.0.1'].includes(u.hostname))))throw Error('Use private HTTPS or a loopback SSH tunnel');
      if(m.length<32||(d&&d.length<32))throw Error('Credential too short');endpoint=u.origin;monitor=m;drive=d;el('monitor').value=el('drive').value='';boot=null;status=null;lease=null;connected=true;poll(generation);frames(generation);
    }catch(err){text('control',err.message);}}
  el('disconnect').onclick=()=>{lose('Disconnected');monitor=drive='';};
  el('acquire').onclick=async()=>{try{const g=generation,r=await api('/api/mobile',{action:'acquire',boot},true);if(g!==generation)return;lease=r.lease;seq=0;render();}catch(e){text('control',e.message);}};
  el('release').onclick=()=>release();el('stop').onclick=halt;
  el('emergency').onclick=()=>{clearHeld();lease=null;render();api('/api/mobile',{action:'emergency'},true).then(()=>text('control','Emergency STOP latched · physical stop unobserved')).catch(e=>text('control','STOP unconfirmed · '+e.message));};
  el('speed').oninput=()=>text('speed-value',el('speed').value);el('overlay').onchange=draw;
  el('fullscreen').onclick=()=>el('view').requestFullscreen?.();
  el('screenshot').onclick=()=>{const a=document.createElement('a');a.download=`charlie-${lastMeta?.frame_id?.replace(/[^a-zA-Z0-9_-]/g,'_')||'frame'}.png`;a.href=el('canvas').toDataURL('image/png');a.click();};
  staleTimer=setInterval(()=>{if(performance.now()-lastDisplayed>500)stale('No current frame · waiting for shared camera');if(connected&&lastStatusAt&&performance.now()-lastStatusAt>1000)lose('Status connection stale');},100);
  window.stopCharlieMobile=()=>{if(stopped)return;release('Page left');stopped=true;generation++;connected=false;clearTimeout(pollTimer);clearTimeout(frameTimer);clearTimeout(driveTimer);clearInterval(staleTimer);events.abort();lastImage?.close();monitor=drive='';};
  if(location.protocol==='http:'&&['localhost','127.0.0.1'].includes(location.hostname))el('endpoint').value=location.origin;
  tick();
};

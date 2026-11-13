'use strict';
// Shared by the existing hosted dashboard and the application's loopback fallback.
window.mountCharlieAbilities = function(root) {
  if(window.stopCharlieAbilities)window.stopCharlieAbilities();
  root.innerHTML = `<section class="panel"><h2>Show me what you see</h2><p>Pi 5 camera · 15 seconds · pico:ed object names · no motion requested</p>
    <p>Connect to your running Charlie application. A project website alone cannot control the robot.</p>
    <form id="ability-connect"><label>Charlie endpoint <input id="ability-endpoint" type="url" value="http://127.0.0.1:8768" required></label>
    <label>Operator token <input id="ability-token" type="password" autocomplete="off" required minlength="32"></label>
    <button>Connect</button> <button id="ability-disconnect" type="button">Disconnect</button></form>
    <p><button id="ability-start" disabled>Show me what you see</button> <button id="ability-cancel" disabled>Cancel demonstration</button></p>
    <p id="ability-state" role="status" aria-live="polite">Unavailable — not connected</p>
    <dl><dt>Session</dt><dd id="ability-session">—</dd><dt>Recognition observations</dt><dd id="ability-observations">—</dd>
    <dt>Display acknowledgments</dt><dd id="ability-delivery">—</dd><dt>Physical display</dt><dd>Unobserved by this dashboard. Confirm on the pico:ed.</dd></dl>
    <pre id="ability-details" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>
    <details><summary>Connection help</summary><p>Charlie must be started with the authenticated abilities endpoint. Use an SSH tunnel to its loopback port 8768. Your token is kept only in this page’s memory.</p>
    <p>If your browser blocks this site’s local-network access, open <a href="http://127.0.0.1:8768/" target="_blank" rel="noopener noreferrer">Charlie’s local abilities page</a> through the same tunnel. Cancellation takes effect in Charlie’s application loop. Closing this page does not cancel an accepted request; its 15-second deadline remains active.</p></details></section>`;
  const el=id=>root.querySelector('#ability-'+id);
  let token='', endpoint='', status=null, timer=null, busy=false, generation=0;
  const stop=()=>{generation++;token='';status=null;clearTimeout(timer);if(el('token'))el('token').value='';if(el('start'))el('start').disabled=true;if(el('cancel'))el('cancel').disabled=true;};
  window.stopCharlieAbilities=stop;
  async function api(method='GET',body) {
    const response=await fetch(endpoint+'/api/abilities',{method,headers:{Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},
      body:body?JSON.stringify(body):undefined,cache:'no-store',credentials:'omit',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(5000)});
    const data=await response.json();if(!response.ok)throw Error(data.error||'Request failed');return data;
  }
  function render() {
    const s=status.session;
    el('state').textContent=s?`${s.state} — ${s.reason||'awaiting attention dispatch'}`:(status.available?'Available':`Unavailable — ${status.reason}`);
    el('session').textContent=s?`${s.id} / execution ${s.execution_id}`:'—';
    el('observations').textContent=s?`${s.observations} frames; ${s.objects} object hypotheses`:'—';
    el('delivery').textContent=s?String(s.display_acknowledgments):'—';
    el('details').textContent=s?JSON.stringify({last_objects:s.last_objects||[],last_evidence_id:s.last_evidence_id||null,
      elapsed_seconds:s.elapsed_seconds??null,evidence_database:s.evidence_database,events_database:s.events_database},null,2):'';
    el('start').disabled=busy||!status.available;
    el('cancel').disabled=busy||!s||!['requested','running'].includes(s.state);
  }
  async function poll(g=generation) {
    if(!root.isConnected||!el('state')){stop();return;}
    try {const next=await api();if(g!==generation)return;status=next;render();}
    catch(e){if(g!==generation)return;el('state').textContent='Unavailable — '+e.message;el('start').disabled=el('cancel').disabled=true;}
    if(token&&g===generation)timer=setTimeout(()=>poll(g),700);
  }
  el('connect').onsubmit=e=>{e.preventDefault();const entered=el('token').value;const target=el('endpoint').value;stop();
    try {const u=new URL(target);if(u.username||u.password||u.search||u.hash||!['','/'].includes(u.pathname)||
      !(u.protocol==='https:'||(u.protocol==='http:'&&['localhost','127.0.0.1'].includes(u.hostname))))throw Error('Use HTTPS or a loopback SSH tunnel');
      if(entered.length<32)throw Error('Operator token required');endpoint=u.origin;token=entered;poll();
    }catch(err){el('state').textContent=err.message;}
  };
  el('disconnect').onclick=()=>{stop();el('state').textContent='Unavailable — disconnected; accepted requests retain their deadline';};
  async function send(action) {
    if(busy||!status)return;busy=true;render();clearTimeout(timer);const g=generation;
    try {const challenge=await api();if(g!==generation)return;
      const id=action==='cancel'?challenge.session?.id:crypto.randomUUID();
      await api('POST',{id,ability:'demonstrate-object-identification',camera:'pi-primary',duration:15,
        boot:challenge.boot,nonce:challenge.nonce,action});
      if(g===generation)el('state').textContent='Requested — waiting for runtime evidence';
    } catch(e){if(g===generation)el('state').textContent='Request not confirmed — '+e.message;}
    finally {busy=false;if(g===generation&&token)timer=setTimeout(()=>poll(g),300);}
  }
  el('start').onclick=()=>send('start');el('cancel').onclick=()=>send('cancel');
  if(location.protocol==='http:'&&['127.0.0.1','localhost'].includes(location.hostname))el('endpoint').value=location.origin;
};

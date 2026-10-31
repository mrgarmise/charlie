// Controller tests with DOM doubles; no browser or robot connection.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();let mounted=true,posts=[],timers=[],network=true;
const element=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',disabled:true});return elements.get(id)};
const root={isConnected:true,innerHTML:'',querySelector:id=>mounted?element(id):null};
let status={available:true,boot:'fixture-boot',nonce:'fixture-nonce',session:null};
const context={window:{},URL,Error,JSON,AbortSignal,crypto:{randomUUID:()=> 'fixture-request-id'},
  location:{protocol:'https:',hostname:'dashboard.example',origin:'https://dashboard.example'},
  setTimeout:fn=>{timers.push(fn);return timers.length},clearTimeout:()=>{},
  fetch:async(url,options)=>{assert(!url.includes('token'));assert(options.credentials==='omit');
    if(!network)throw Error('fixture connection lost');
    if(options.method==='POST'){posts.push(JSON.parse(options.body));return {ok:true,json:async()=>({state:'requested'})};}
    return {ok:true,json:async()=>status};}};
vm.createContext(context);vm.runInContext(fs.readFileSync('ui/abilities.js','utf8'),context);
const flush=()=>new Promise(setImmediate);
(async()=>{
  context.window.mountCharlieAbilities(root);
  element('#ability-endpoint').value='http://127.0.0.1:8768';element('#ability-token').value='fixture-secret-1234567890123456789012345';
  element('#ability-connect').onsubmit({preventDefault(){}});await flush();
  assert.equal(element('#ability-token').value,'');assert.equal(element('#ability-start').disabled,false);
  await element('#ability-start').onclick();assert.equal(posts.length,1);assert.equal(posts[0].duration,15);assert.equal(posts[0].action,'start');
  assert.equal(element('#ability-state').textContent,'Requested — waiting for runtime evidence');
  status={...status,available:false,session:{id:'fixture-request-id',execution_id:'e',state:'running',observations:3,objects:5,display_acknowledgments:1}};
  await timers.pop()();await flush();assert.equal(element('#ability-cancel').disabled,false);
  await element('#ability-cancel').onclick();assert.equal(posts[1].action,'cancel');assert.equal(posts[1].id,'fixture-request-id');
  network=false;await timers.pop()();await flush();assert(element('#ability-state').textContent.includes('Unavailable'));assert(element('#ability-start').disabled);
  context.window.stopCharlieAbilities();mounted=false;context.window.stopCharlieAbilities(); // Repeated route cleanup must be safe.
  mounted=true;context.window.mountCharlieAbilities(root);element('#ability-endpoint').value='http://remote.example';element('#ability-token').value='fixture-secret-1234567890123456789012345';
  element('#ability-connect').onsubmit({preventDefault(){}});assert(element('#ability-state').textContent.includes('HTTPS'));
  console.log('Abilities UI: authentication memory, request/receipt distinction, cancellation, network failure, route cleanup and endpoint validation passed (DOM double).');
})().catch(e=>{console.error(e);process.exitCode=1});

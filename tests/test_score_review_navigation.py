"""Real browser JS, DOM/HTTP doubles; no claim of rendered-browser acceptance."""
import os,shutil,subprocess
from pathlib import Path
import pytest


def test_stale_photo_guard_saved_review_and_acknowledged_advance(tmp_path):
    node=shutil.which('node') or os.environ.get('CODEX_PRIMARY_RUNTIME_NODE')
    if not node:pytest.skip('Node unavailable')
    source=(Path(__file__).parents[1]/'experiments/ppal/score-review.html').read_text().split('<script>')[1].split('</script>')[0]
    script=tmp_path/'ui.js';script.write_text(source)
    harness=tmp_path/'run.js';harness.write_text(r'''
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const elements={};const element=()=>({value:'',hidden:false,disabled:false,checked:false,style:{},children:[],textContent:'',
 removeAttribute(k){delete this[k]},replaceChildren(){this.children=[]},append(x){this.children.push(x)},click(){this.onclick?.()},focus(){}});
const games=[{id:'g1',session:'session',number:1,proposal_id:'p1',proposed_score:1200,confidence:.99,reader_status:'fixture',review_status:'corrected',annotations:[{annotator:'Alex',value:1300,reason:'Saved correction',independence_attested:true}],review:{not_final_score:true}},
 {id:'g2',session:'session',number:2,proposal_id:null,proposed_score:null,confidence:null,review_status:'pending'},
 {id:'g3',session:'session',number:3,proposal_id:'p3',proposed_score:1500,confidence:.9,review_status:'pending',annotations:[]}];
let pending=[],saved=[],fail=false;
const context={document:{getElementById(id){return elements[id]??=element()},createElement:element},localStorage:{getItem(){return 'Alex'},setItem(){}},
 URL:{createObjectURL(x){return x.id},revokeObjectURL(){}},Image:class{set src(x){this.onload()}},fetch:async(url,opt)=>{
 if(url==='/queue')return {ok:true,json:async()=>({games,history:{}})};
 if(url.startsWith('/image'))return new Promise(resolve=>pending.push({url,resolve}));
 if(fail)return {ok:false,json:async()=>({error:'controlled failed save'})};
 const data=JSON.parse(opt.body);saved.push(data);games.find(g=>g.id===data.id).review_status='confirmed';return {ok:true,json:async()=>({id:'saved'})}}};
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
const tick=()=>new Promise(r=>setImmediate(r));
(async()=>{elements.filter.value='all';await vm.runInContext('load()',context);
 // HTMLInputElement.value is a string; exact visible digits preserve "00".
 assert.equal(elements.value.value,'1300');assert.equal(elements.note.value,'Saved correction');assert.equal(elements.not_final.checked,true);
 assert.equal(elements.image.hidden,true);assert.equal(elements.confirm.disabled,true);
 const old=pending.splice(0);elements.next.click();assert.equal(elements.image.hidden,true);assert.equal(elements.image.src,undefined);assert.match(elements.game.textContent,/Game 2/);
 for(const p of old)p.resolve({ok:true,blob:async()=>({id:'old-photo'})});await tick();assert.equal(elements.image.hidden,true);
 elements.next.click();assert.match(elements.game.textContent,/Game 3/);const fresh=pending.splice(0);for(const p of fresh)p.resolve({ok:true,blob:async()=>({id:'current-photo'})});await tick();
 assert.equal(elements.image.src,'current-photo');assert.equal(elements.confirm.disabled,false);
 fail=true;await vm.runInContext("save('confirm')",context);assert.match(elements.game.textContent,/Game 3/);assert.equal(saved.length,0);
 fail=false;elements.finality_unknown.checked=true;await vm.runInContext("save('confirm')",context);assert.equal(saved.length,1);assert.equal(saved[0].finality_unknown,true);
 elements.prev.click();assert.equal(elements.image.hidden,true);console.log('stale responses, missing original, restored label/finality and failed-save controls passed');})().catch(e=>{console.error(e);process.exitCode=1});
''')
    subprocess.run([node,'--check',str(script)],check=True,capture_output=True,text=True)
    process=subprocess.run([node,str(harness),str(script)],capture_output=True,text=True,timeout=10)
    assert process.returncode==0,process.stderr

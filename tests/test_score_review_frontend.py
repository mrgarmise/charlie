"""Real UI JavaScript with a DOM test double; no rendered-browser assertion."""
import os,shutil,subprocess
from pathlib import Path
import pytest


def test_batch_navigation_correction_filters_and_keyboard(tmp_path):
    node=shutil.which('node') or os.environ.get('CODEX_PRIMARY_RUNTIME_NODE')
    if not node:pytest.skip('Node unavailable; browser logic test requires JavaScript runtime')
    page=(Path(__file__).parents[1]/'experiments/ppal/score-review.html').read_text()
    source=page.split('<script>')[1].split('</script>')[0]
    script=tmp_path/'review.js';script.write_text(source)
    subprocess.run([node,'--check',str(script)],check=True,capture_output=True,text=True)
    harness=tmp_path/'harness.js';harness.write_text(r'''
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const elements={};const element=()=>({value:'',hidden:false,disabled:false,style:{},children:[],textContent:'',
 replaceChildren(){this.children=[]},append(x){this.children.push(x)},click(){this.onclick?.()},focus(){}});
const games=Array.from({length:30},(_,i)=>({id:'game-'+i,number:i+1,session:'fixture-session',
 proposed_score:i*100,confidence:i===4?.5:.99,reader_status:'fixture',review_status:'pending',
 complete_game_claim:i!==9,proposal_id:i===9?null:'photo-'+i,annotations:[]}));
const context={document:{getElementById(id){return elements[id]??=(element())},createElement:element},
 localStorage:{getItem(){return ''},setItem(){}},fetch:async(url,opt)=>{
 if(url==='/queue')return {ok:true,json:async()=>({games,history:{},baselines:[]})};
 assert.equal(url,'/review');const data=JSON.parse(opt.body);const g=games.find(g=>g.id===data.id);
 g.review_status={confirm:'confirmed',correct:'corrected',unreadable:'unreadable',defer:'pending'}[data.verdict];
 g.annotations=[data];return {ok:true,json:async()=>({id:'saved'})};}};
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
elements.filter.value='all';
async function run(){await vm.runInContext('load()',context);assert.equal(elements.list.children.length,30);
 assert.equal(elements.progress.textContent,'0 of 30 reviewed');elements.reviewer.value='fixture reviewer';
 await vm.runInContext("save('confirm')",context);assert.equal(games[0].review_status,'confirmed');
 assert.equal(elements.progress.textContent,'1 of 30 reviewed');
 elements.list.children[4].click();assert.match(elements.game.textContent,/Game 5/);
 elements.value.value='1234';await vm.runInContext("save('correct')",context);
 assert.equal(games[4].annotations[0].value,1234);assert.equal(games[4].proposed_score,400);
 elements.filter.value='pending';elements.filter.onchange();assert.equal(elements.list.children.length,28);
 elements.filter.value='incomplete';elements.filter.onchange();assert.equal(elements.list.children.length,1);
 assert.equal(elements.confirm.disabled,true);assert.equal(elements.missing.hidden,false);
 elements.filter.value='all';elements.filter.onchange();elements.zoom.value='3';elements.zoom.oninput();
 assert.equal(elements.image.style.width,'300%');
 context.document.onkeydown({key:'ArrowRight',target:{tagName:'BODY'}});assert.match(elements.game.textContent,/Game 2/);
 console.log('30-game JavaScript batch, correction, filter, missing-photo and navigation checks passed; DOM double only');}
run().catch(e=>{console.error(e);process.exitCode=1});
''')
    subprocess.run([node,str(harness),str(script)],check=True,capture_output=True,text=True)

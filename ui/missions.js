'use strict';
document.querySelector('#mission-connect').addEventListener('submit', async event => {
  event.preventDefault();
  const input=document.querySelector('#mission-token'), token=input.value;
  input.value='';
  const status=document.querySelector('#mission-status'), list=document.querySelector('#mission-list');
  list.replaceChildren();
  try {
    const response=await fetch('/api/missions',{headers:{Authorization:'Bearer '+token},cache:'no-store'});
    if(!response.ok)throw new Error('Checkpoint unavailable ('+response.status+')');
    const data=await response.json(), register=data.register;
    status.textContent='Verified checkpoint: '+register.observed_utc+' · master '+register.master+' · '+data.freshness+' · '+data.installed;
    function field(parent,label,value){
      const term=document.createElement('dt'), detail=document.createElement('dd');
      term.textContent=label;detail.textContent=typeof value==='string'?value:JSON.stringify(value??'UNKNOWN');parent.append(term,detail);
    }
    function link(parent,label,value){
      if(!value)return;
      try{const url=new URL(value);if(url.protocol!=='https:')return;
        const a=document.createElement('a');a.textContent=label+' ';a.href=url.href;a.rel='noopener noreferrer';parent.append(a);
      }catch(_){}
    }
    const development=data.development_organization;
    if(development){
      const card=document.createElement('section');card.className='mobile-panel';
      const title=document.createElement('h2');title.textContent='Development organization';card.append(title);
      const fields=document.createElement('dl');
      field(fields,'Goal',development.goal);
      field(fields,'State',development.state);
      if(development.seconds!=null)field(fields,'Deadline budget (seconds)',development.seconds);
      if(development.work_budget!=null)field(fields,'Work units',development.consumed_work_units+' / '+development.work_budget);
      if(development.decision)field(fields,'Organization selection',development.decision);
      for(const assignment of development.assignments??[]){
        const evidence=assignment.evidence, result=evidence?.payload?.result;
        field(fields,assignment.name,{
          capability:assignment.capability,supervisor:assignment.supervisor,
          dependencies:assignment.depends_on,attempts:assignment.attempts,
          evidence:evidence?.digest,mode:result?.mode??evidence?.payload?.mode,
          outcome:result?.outcome??result?.goal_achieved,follow_up:result?.next_question
        });
      }
      card.append(fields);list.append(card);
    }
    for(const item of [...register.capabilities].sort((a,b)=>(a.priority??99)-(b.priority??99))){
      const card=document.createElement('section');card.className='mobile-panel';
      const title=document.createElement('h2');title.textContent=item.description;card.append(title);
      const fields=document.createElement('dl');
      field(fields,'Priority',item.priority);
      for(const [dimension,value] of Object.entries(item.status??{}))field(fields,dimension.replaceAll('_',' '),value);
      for(const key of ['head','target','last_tested_revision','blockers','dependencies','owner','safe_next_action','date','library_mission'])field(fields,key.replaceAll('_',' '),item[key]);
      field(fields,'Origin chat',item.origin_chat?.title??'UNKNOWN/PENDING EXPORT');
      card.append(fields);link(card,'PR',item.pr_url);link(card,'Linear',item.linear_url);link(card,'Origin',item.origin_chat?.url);
      for(const [index,url] of (item.evidence??[]).entries())link(card,'Evidence '+(index+1),url);
      list.append(card);
    }
  }catch(error){status.textContent=error.message;}
});

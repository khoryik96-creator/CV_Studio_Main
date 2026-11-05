/* Lead Finder's DeepSeek route: observe browser cards, then review those IDs. */
(function(){
  'use strict';
  async function run({payload,rpc,request,status,signal,onCompanies,wait=ms=>new Promise(resolve=>setTimeout(resolve,ms)),makeID=()=>crypto.randomUUID().replaceAll('-','')}) {
    const check=()=>{if(signal?.aborted)throw Error('People search stopped.');};
    check();const companion=await rpc('jobStatus');check();
    if(companion?.lead_people_revision!==1)throw Error('Update the LinkedIn companion, refresh CV Studio and LinkedIn, then reconnect it in Chrome or Brave.');
    if(companion.busy)throw Error('Finish the current companion search first.');
    status('Confirming job-ad employers…');
    const planned=await request({...payload,action:'companion_plan'});check();
    if(!Array.isArray(planned.plan) || planned.plan.length>16 || !Array.isArray(planned.companies))throw Error('The people search plan could not be confirmed.');
    onCompanies?.(planned.companies);
    const observed=[],seen=new Set();
    for(const item of planned.plan) {
      check();if(observed.length>=80)break;
      if(typeof item.company!=='string' || typeof item.query!=='string')throw Error('The people search plan is invalid.');
      const runID=makeID();let attempted=false,failed=false;
      status('Finding HR and hiring managers · '+item.company+'…');
      try {
        attempted=true;const source=await rpc('leadPeopleBegin',{run_id:runID,query:item.query});check();
        if(!Number.isInteger(source?.tab_id))throw Error('The people search did not open.');
        let snapshot=null,previous='',stable=0;
        for(let attempt=0;attempt<60;attempt++) {
          check();const value=await rpc('leadPeopleRead',{run_id:runID,tab_id:source.tab_id});check();
          if(value && !value.loading && Array.isArray(value.profiles)) {
            if(value.empty){snapshot=value;break;}
            if(value.signature && value.signature===previous)stable++;else stable=0;
            previous=value.signature || '';
            if(stable>=1){snapshot=value;break;}
          }
          await wait(500);
        }
        if(!snapshot)throw Error('LinkedIn people results did not finish loading. Wait for them in Chrome or Brave, then retry.');
        for(const profile of snapshot.profiles) {
          const key=item.company+'|'+profile.url;
          if(!seen.has(key) && observed.length<80){seen.add(key);observed.push({...profile,company:item.company});}
        }
      } catch(error){failed=true;throw error;}
      finally {
        if(attempted){try{if(await rpc('end',{run_id:runID})!==true)throw Error('Cleanup not confirmed.');}catch(error){if(!failed)throw Error('The companion could not confirm tab cleanup. Reconnect it before retrying.');}}
      }
    }
    check();status('Reviewing observed people with DeepSeek…');
    const reviewed=await request({...payload,companies:planned.companies,action:'companion_review',observed_people:observed});check();
    return reviewed;
  }
  window.cvStudioLeadFinderPeople={run};
})();

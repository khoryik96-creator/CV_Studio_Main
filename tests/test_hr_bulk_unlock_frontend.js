/* HR people: Email filter and bulk unlock. Fictional people; Apollo is a stub,
 * so no account, credit or network is used. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/people-dashboards.js'),'utf8');

class Element {
  constructor(tag='div'){Object.assign(this,{tagName:tag.toUpperCase(),children:[],handlers:{},dataset:{},attributes:{},textContent:'',value:'',checked:false,disabled:false,hidden:false,open:false,options:[]});}
  addEventListener(type,fn){(this.handlers[type] ||= []).push(fn);}
  dispatch(type){return Promise.all((this.handlers[type]||[]).map(fn=>fn({preventDefault(){},target:this})));}
  append(...items){this.children.push(...items);} replaceChildren(...items){this.children=items;}
  setAttribute(name,value){this.attributes[name]=String(value);} getAttribute(name){return this.attributes[name] ?? null;} removeAttribute(name){delete this.attributes[name];}
  querySelectorAll(){return [];} click(){return this.dispatch('click');}
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function settle(){for(let n=0;n<30;n++)await tick();}
const hr=(n,result)=>({id:String(n).repeat(32).slice(0,32),revision:1,name:'Fictional Person '+n,title:'HR',company:'Example Company',company_id:'41',company_url:'https://www.linkedin.com/company/example/',
  location:'Malaysia',url:'https://www.linkedin.com/in/fictional-'+n,employment:'Not checked',ads:1,job_url:'https://www.linkedin.com/jobs/view/'+n,...(result?{email_result:result}:{})});

function fixture(rows,{answers={},confirm=true}={}){
  const ids=new Map(),posts=[],unlocks=[],confirms=[];
  const document={getElementById:id=>{if(!ids.has(id))ids.set(id,new Element(/Company|Email|Sort|Order|Read|Folder/.test(id)?'select':'div'));return ids.get(id);},
    createElement:tag=>new Element(tag),querySelectorAll:()=>[]};
  const el=name=>document.getElementById('people'+name);
  for(const id of ['jobLeadsApolloAdsPanel','jobLeadsApolloContactsPanel','jobLeadsApolloAdsTab','jobLeadsApolloContactsTab'])document.getElementById(id);
  let served=structuredClone(rows);
  const fetch=async(url,init)=>{
    const body=JSON.parse(init.body);posts.push({url,body});
    if(body.action==='hr_people')return {ok:true,json:async()=>({people:structuredClone(served)})};
    if(body.action==='candidates')return {ok:true,json:async()=>({candidates:[]})};
    throw Error('unexpected '+body.action);
  };
  const apollo={connected:()=>true,openSettings(){},contactsChanged:async()=>{apollo.refreshed=(apollo.refreshed||0)+1;},
    // The stub records each paid lookup and how it was confirmed.
    async unlockSaved(source,person,previous,notify,complete,options){
      unlocks.push({url:person.url,previous,options:{...options}});
      const answer=answers[person.url] || {state:'found',email:person.url.split('/').pop()+'@example.test',message:'Email found.'};
      if(answer==='lost'){notify('The result could not be confirmed.');return false;}
      complete(answer);served=served.map(row=>row.url===person.url?{...row,email_result:answer}:row);notify(answer.message || '');return true;
    }};
  const window={addEventListener(){},cvStudioJobLeads:null,cvStudioApollo:apollo,confirm:text=>{confirms.push(text);return confirm;}};
  const context=vm.createContext({window,document,fetch,localStorage:{getItem:()=>null,setItem(){}},console,structuredClone,Intl,
    URL:{createObjectURL:()=>'blob:x',revokeObjectURL(){}},setTimeout,crypto:{randomUUID:()=>'00000000-0000-4000-8000-000000000000'}});
  vm.runInContext(source,context);
  const names=()=>el('HRRows').children.map(tr=>tr.children[0].children[0].textContent);
  return {el,posts,unlocks,confirms,names,apollo};
}

(async()=>{
  const done={state:'found',email:'known@example.test'},empty={state:'not_found',message:'No email from Apollo.'},pending={state:'unconfirmed',message:'Check the previous lookup.'};
  const rows=[hr(1,done),hr(2),hr(3,empty),hr(4,pending),hr(5)];
  const f=fixture(rows);await f.el('HRTab').click();await settle();
  // Email filter: No email yet / Has email.
  f.el('HREmail').value='none';await f.el('HREmail').dispatch('change');
  assert.deepEqual(f.names(),['Fictional Person 2','Fictional Person 3','Fictional Person 4','Fictional Person 5']);
  f.el('HREmail').value='found';await f.el('HREmail').dispatch('change');assert.deepEqual(f.names(),['Fictional Person 1']);
  f.el('HREmail').value='';await f.el('HREmail').dispatch('change');
  assert(!f.el('HRUnlockAll').disabled && !f.el('HRUnlockAll').hidden);
  // One confirmation names the people and the most credits; finished lookups are skipped.
  await f.el('HRUnlockAll').click();await settle();
  assert.equal(f.confirms.length,1);assert.match(f.confirms[0],/for 3 people shown/);assert.match(f.confirms[0],/up to 2 Apollo credits/);
  assert.match(f.confirms[0],/1 earlier lookup is checked without a credit/);
  assert.deepEqual(f.unlocks.map(u=>u.url.split('-').pop()),['2','4','5'],'people with an email or a finished lookup are skipped');
  assert(f.unlocks.every(u=>u.options.confirmed===true && u.options.batch===true),'each lookup carries the bulk confirmation');
  assert.deepEqual(f.unlocks.map(u=>u.previous?.state ?? null),[null,'unconfirmed',null],'an earlier lookup is checked, not paid again');
  assert.match(f.el('HRMessage').textContent,/^Finished\. 3 emails unlocked, 0 without an email\. Emails are checked automatically\.$/);
  assert(!f.el('HRNextStep').hidden && f.apollo.refreshed===1,'contacts refresh once and the next step shows');
  assert(f.el('HRUnlockAll').disabled,'nobody shown is left to unlock');
  // Cancelling the confirmation unlocks nobody.
  const no=fixture([hr(6)],{confirm:false});await no.el('HRTab').click();await settle();await no.el('HRUnlockAll').click();await settle();
  assert.equal(no.confirms.length,1);assert.equal(no.unlocks.length,0);
  // An unconfirmed (possibly charged) lookup stops the run: never replayed, never continued.
  const lost=fixture([hr(7),hr(8),hr(9)],{answers:{'https://www.linkedin.com/in/fictional-8':'lost'}});await lost.el('HRTab').click();await settle();
  await lost.el('HRUnlockAll').click();await settle();
  assert.deepEqual(lost.unlocks.map(u=>u.url.split('-').pop()),['7','8']);assert.match(lost.el('HRMessage').textContent,/^Stopped: The result could not be confirmed\. 1 email unlocked/);
  // A returned (not lost) unfinished result also stops the run: the server
  // answers pending/unconfirmed/reconnect/limit normally, so success alone is not enough.
  for(const state of ['unconfirmed','pending','auth_required','limited']){
    const r=fixture([hr(7),hr(8),hr(9)],{answers:{'https://www.linkedin.com/in/fictional-8':{state,message:'Apollo did not confirm this lookup ('+state+').'}}});
    await r.el('HRTab').click();await settle();await r.el('HRUnlockAll').click();await settle();
    assert.deepEqual(r.unlocks.map(u=>u.url.split('-').pop()),['7','8'],state+' stops before the next paid lookup');
    assert.equal(r.el('HRMessage').textContent,'Stopped: Apollo did not confirm this lookup ('+state+'). 1 email unlocked, 0 without an email. Emails are checked automatically.');
  }
  const mixed=fixture([hr(7),hr(8),hr(9)],{answers:{'https://www.linkedin.com/in/fictional-7':{state:'mismatch',message:'No match.'},'https://www.linkedin.com/in/fictional-8':{state:'not_found',message:'No email.'}}});
  await mixed.el('HRTab').click();await settle();await mixed.el('HRUnlockAll').click();await settle();
  assert.equal(mixed.unlocks.length,3);assert.match(mixed.el('HRMessage').textContent,/^Finished\. 1 email unlocked, 2 without an email\./,'finished answers without an email continue the run');
  // Stop ends the run between lookups; filters decide who is included; at most 25 per run.
  const many=fixture(Array.from({length:30},(_,i)=>hr(10+i)));await many.el('HRTab').click();await settle();
  let stopAfter=2;const original=many.apollo.unlockSaved;many.apollo.unlockSaved=async(...args)=>{const result=await original(...args);if(--stopAfter===0)await many.el('HRUnlockStop').click();return result;};
  await many.el('HRUnlockAll').click();await settle();
  assert.match(many.confirms[0],/for 25 people shown/);assert.match(many.confirms[0],/The first 25 are unlocked now; run it again for the other 5/);
  assert.equal(many.unlocks.length,2,'Stop ends the run after the current lookup');assert.match(many.el('HRMessage').textContent,/^Stopped\. 2 emails unlocked/);
  console.log('HR people: Email filter, one counted confirmation, skipped finished lookups, free re-checks, stop on lost or unfinished results, Stop and a 25-person cap passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});

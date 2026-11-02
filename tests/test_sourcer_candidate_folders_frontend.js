/* Sourcer Candidates dashboard: folders, shortlist and Trash. Fictional people. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/people-dashboards.js'),'utf8');

class Element {
  constructor(tag='div'){Object.assign(this,{tagName:tag.toUpperCase(),children:[],handlers:{},dataset:{},attributes:{},textContent:'',value:'',checked:false,disabled:false,hidden:false,open:false});}
  addEventListener(type,fn){(this.handlers[type] ||= []).push(fn);}
  dispatch(type){return Promise.all((this.handlers[type]||[]).map(fn=>fn({preventDefault(){},target:this})));}
  append(...items){this.children.push(...items);} replaceChildren(...items){this.children=items;}
  setAttribute(name,value){this.attributes[name]=String(value);} getAttribute(name){return this.attributes[name] ?? null;} removeAttribute(name){delete this.attributes[name];}
  querySelectorAll(selector){
    const found=[],walk=node=>{for(const child of node.children || []){if(selector==='[data-organise]' && child.dataset && 'organise' in child.dataset)found.push(child);walk(child);}};
    walk(this);return found;
  }
  click(){return this.dispatch('click');}
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function settle(){for(let n=0;n<30;n++)await tick();}
const key=letter=>letter.repeat(64);
const person=(letter,name,patch={})=>({key:key(letter),name,location:'Kuala Lumpur',score:80,read:'Profile detail',saved_at:'2026-10-0'+'abcd'.indexOf(letter)+'T00:00:00+00:00',
  title:'SAP FICO Consultant',url:'https://www.linkedin.com/in/demo-'+letter,evidence:['Fictional evidence'],unknowns:[],notes:'',brief:'Fictional brief',run_id:'r'.repeat(32),
  revision:1,folder:'',shortlisted:false,deleted:false,deleted_at:'',...patch});

function fixture(){
  const ids=new Map(),posts=[],confirms=[];
  const server={folders:['Finance'],rows:[person('a','Demo Alpha'),person('b','Demo Beta'),person('c','Demo Gamma',{folder:'Finance'}),person('d','Demo Delta',{deleted:true,deleted_at:'2026-10-20T00:00:00+00:00'})],reject:null};
  const document={getElementById:id=>{if(!ids.has(id))ids.set(id,new Element(/Sort|Order|MinScore|Read|Search|Company|Folder$|MoveTo/.test(id)?'select':'div'));return ids.get(id);},
    createElement:tag=>new Element(tag),querySelectorAll:()=>[]};
  const el=name=>document.getElementById('people'+name);
  el('CandidatesSort').value='saved_at';el('CandidatesOrder').value='desc';el('CandidatesMinScore').value='0';el('CandidatesRead').value='';el('CandidatesFolder').value='*';
  for(const [name,values] of [['Sort',['saved_at','score','name','location','read']],['Order',['desc','asc']]])
    el('Candidates'+name).options=values.map(value=>({value}));
  const reply=data=>({ok:true,json:async()=>structuredClone(data)}),fail=error=>({ok:false,json:async()=>({error})});
  const current=(items)=>items.every(item=>server.rows.some(row=>row.key===item.key && row.revision===item.revision));
  // server.gate holds one action's request until server.open(): the change is
  // applied then, standing for a request the service handles later.
  const fetch=(url,init)=>{
    const action=JSON.parse(init.body).action;
    if(server.gate===action)return new Promise(resolve=>{server.open=()=>{server.gate=null;resolve(answer(url,init));};});
    return answer(url,init);
  };
  const answer=async(url,init)=>{
    const body=JSON.parse(init.body);posts.push({url,body});
    if(body.action==='hr_people')return reply({people:[]});
    // The service returns folder names sorted, as SourcerCandidates.folders() does.
    if(body.action==='candidates'){
      if(server.failList)return fail('Saved candidates could not be read securely. Keep the existing files and check local storage.');
      // Copied now: a held read answers with what the service saw when asked.
      const snapshot=reply(structuredClone({candidates:server.rows,folders:[...server.folders].sort()}));
      return server.hold?new Promise(resolve=>{server.release=()=>resolve(snapshot);}):snapshot;
    }
    if(body.action==='export_candidates')return {ok:true,blob:async()=>'xlsx'};
    if(server.reject)return fail(server.reject);
    const bump=row=>{row.revision++;return row;};
    if(body.action==='candidate_folder_create'){const name=body.name.replace(/[\s\u0085]+$/u,'');if(!server.folders.includes(name))server.folders.push(name);return reply({folder:name});}
    if(body.action==='candidate_move'){
      if(!current(body.items))return fail('A selected candidate changed in another window. Refresh before trying again.');
      for(const item of body.items)bump(Object.assign(server.rows.find(row=>row.key===item.key),{folder:body.folder}));
      return reply({changed:body.items.length});
    }
    if(body.action==='candidate_trash'){
      for(const item of body.items)bump(Object.assign(server.rows.find(row=>row.key===item.key),{deleted:body.deleted,deleted_at:body.deleted?'2026-10-31T00:00:00+00:00':''}));
      return reply({changed:body.items.length});
    }
    if(body.action==='candidate_shortlist'){
      const row=server.rows.find(value=>value.key===body.key);assert.equal(body.revision,row.revision,'the shortlist uses the current revision');
      return reply({candidate:bump(Object.assign(row,{shortlisted:body.shortlisted}))});
    }
    if(body.action==='candidate_note'){
      const row=server.rows.find(value=>value.key===body.key);
      if(body.revision!==row.revision)return fail('This candidate changed. Copy your note, refresh the dashboard and try again.');
      return reply({candidate:bump(Object.assign(row,{notes:body.notes}))});
    }
    if(body.action==='candidate_folder_delete'){
      const inside=server.rows.filter(row=>row.folder===body.name);
      assert.deepEqual(body.items.map(item=>item.key).sort(),inside.map(row=>row.key).sort(),'every candidate in the folder is confirmed, even in Trash');
      for(const row of inside)bump(Object.assign(row,{folder:''}));
      server.folders=server.folders.filter(name=>name!==body.name);return reply({changed:inside.length});
    }
    throw Error('unexpected '+body.action);
  };
  const localStorage={getItem:()=>null,setItem(){}};
  const window={addEventListener(){},cvStudioJobLeads:null,confirm:text=>{confirms.push(text);return true;}};
  const context=vm.createContext({window,document,fetch,localStorage,console,structuredClone,Intl,URL:{createObjectURL:()=>'blob:x',revokeObjectURL(){}},
    setTimeout,crypto:{randomUUID:()=>'00000000-0000-4000-8000-000000000000'}});
  vm.runInContext(source,context);
  const rows=()=>el('CandidatesRows').children;
  const names=()=>rows().map(tr=>tr.children[1].children[0].textContent);
  const row=name=>rows().find(tr=>tr.children[1].children[0].textContent===name);
  const select=async name=>{const box=row(name).children[0].children[0];box.checked=!box.checked;await box.dispatch('change');};
  const star=name=>row(name).children[0].children[1];
  const choose=async(name,value)=>{el('Candidates'+name).value=value;await el('Candidates'+name).dispatch('change');};
  const labels=name=>el('Candidates'+name).children.map(option=>option.textContent);
  return {el,posts,confirms,server,names,row,select,star,choose,labels,win:window,last:action=>posts.filter(post=>post.body.action===action).at(-1)?.body};
}

let finished=false;
process.on('exit',()=>{if(!finished){console.error('Candidate folders test did not finish: a pending step never settled.');process.exitCode=1;}});
(async()=>{
  const f=fixture();
  await f.el('CandidatesTab').click();await settle();
  // Trash is hidden until chosen; folders and counts come with the list.
  assert.deepEqual(f.names(),['Demo Gamma','Demo Beta','Demo Alpha']);
  assert.deepEqual(f.labels('Folder'),['All folders (3)','Unfiled (2)','Finance (1)','Trash (1)']);
  assert.deepEqual(f.labels('MoveTo'),['Unfiled','Finance']);
  assert.equal(f.row('Demo Gamma').children[1].children[1].textContent,'Finance','the folder shows under the name');
  assert(f.el('CandidatesMove').disabled && f.el('CandidatesTrash').disabled && f.el('CandidatesRestore').hidden,'nothing selected yet');
  assert(f.el('CandidatesDeleteFolder').disabled,'only a chosen folder can be deleted');

  // Create a folder, then move two selected candidates into it.
  assert(f.el('CandidatesCreateFolder').disabled);
  await f.select('Demo Alpha');await f.select('Demo Beta');
  f.el('CandidatesNewFolder').value=' Controlling ';await f.el('CandidatesNewFolder').dispatch('input');assert(!f.el('CandidatesCreateFolder').disabled);
  await f.el('CandidatesCreateFolder').click();await settle();
  assert.equal(f.el('CandidatesSelected').textContent,'2 selected','creating a folder keeps the selection for Move selected');
  assert.deepEqual(f.last('candidate_folder_create'),{action:'candidate_folder_create',name:'Controlling'});
  assert.equal(f.el('CandidatesMoveTo').value,'Controlling','the new folder is ready in Move to');assert.equal(f.el('CandidatesNewFolder').value,'');
  assert.match(f.el('CandidatesMessage').textContent,/Folder Controlling created/);
  assert.equal(f.el('CandidatesSelected').textContent,'2 selected');assert(!f.el('CandidatesMove').disabled && !f.el('CandidatesTrash').disabled);
  await f.el('CandidatesMove').click();await settle();
  assert.deepEqual(f.last('candidate_move'),{action:'candidate_move',items:[{key:'a'.repeat(64),revision:1},{key:'b'.repeat(64),revision:1}],folder:'Controlling'});
  assert.match(f.el('CandidatesMessage').textContent,/Moved 2 candidates to Controlling\./);
  assert.equal(f.el('CandidatesSelected').textContent,'0 selected','a finished move clears the selection');
  assert.deepEqual(f.labels('Folder'),['All folders (3)','Unfiled (0)','Controlling (2)','Finance (1)','Trash (1)']);

  // Folder view, then shortlist one candidate and filter to the shortlist.
  await f.choose('Folder','Controlling');
  assert.deepEqual(f.names(),['Demo Beta','Demo Alpha']);assert(!f.el('CandidatesDeleteFolder').disabled);
  const draft=f.row('Demo Alpha').children.at(-1).children[0].children[1];
  draft.value='Strong in CO-PA';await draft.dispatch('input');
  assert.equal(f.star('Demo Alpha').textContent,'☆');
  await f.star('Demo Alpha').click();await settle();
  assert.deepEqual(f.last('candidate_shortlist'),{action:'candidate_shortlist',key:'a'.repeat(64),revision:2,shortlisted:true});
  assert.equal(f.star('Demo Alpha').textContent,'★');assert.equal(f.star('Demo Alpha').getAttribute('aria-pressed'),'true');
  assert.match(f.el('CandidatesMessage').textContent,/Demo Alpha is shortlisted/);
  await f.select('Demo Beta');await f.star('Demo Beta').click();await settle();
  assert.equal(f.el('CandidatesSelected').textContent,'1 selected','the owner\'s own shortlist change keeps the selection');
  await f.star('Demo Beta').click();await settle();await f.select('Demo Beta');
  f.el('CandidatesShortlisted').checked=true;await f.el('CandidatesShortlisted').dispatch('change');
  assert.deepEqual(f.names(),['Demo Alpha']);
  // A note typed before the owner's own shortlist change still saves.
  const pending=f.row('Demo Alpha').children.at(-1).children[0];
  await pending.children[2].click();await settle();
  assert.equal(f.last('candidate_note').revision,3,'the note draft follows the owner\'s own change');assert.match(f.el('CandidatesMessage').textContent,/Note saved/);
  f.el('CandidatesShortlisted').checked=false;await f.el('CandidatesShortlisted').dispatch('change');

  // Delete moves to Trash after a confirmation; Restore brings it back.
  await f.select('Demo Beta');await f.el('CandidatesTrash').click();await settle();
  assert.match(f.confirms.at(-1),/Move 1 candidate to Trash\? You can restore them/);
  assert.deepEqual(f.last('candidate_trash'),{action:'candidate_trash',items:[{key:'b'.repeat(64),revision:4}],deleted:true});
  assert.deepEqual(f.names(),['Demo Alpha'],'Trash is hidden from the folder');
  await f.choose('Folder','!trash');
  assert.deepEqual(f.names(),['Demo Delta','Demo Beta'],'Trash keeps the chosen order (newest assessed first)');assert(f.el('CandidatesTrash').hidden && !f.el('CandidatesRestore').hidden);
  assert.equal(f.row('Demo Delta').children[1].children[1].textContent,'Unfiled · In Trash');
  const before=f.posts.length;await f.star('Demo Delta').click();await settle();
  assert.equal(f.posts.length,before,'a candidate in Trash cannot be shortlisted');assert(f.star('Demo Delta').disabled);
  await f.select('Demo Beta');
  assert(f.el('CandidatesMove').disabled && !f.el('CandidatesRestore').disabled,'Trash cannot be moved before it is restored');
  await f.el('CandidatesRestore').click();await settle();
  assert.deepEqual(f.last('candidate_trash'),{action:'candidate_trash',items:[{key:'b'.repeat(64),revision:5}],deleted:false});
  assert.deepEqual(f.names(),['Demo Delta']);assert.match(f.el('CandidatesMessage').textContent,/Restored 1 candidate to its folder\./);

  // Select all on this page; a filter change starts a new selection.
  await f.choose('Folder','*');
  f.el('CandidatesSelectPage').checked=true;await f.el('CandidatesSelectPage').dispatch('change');
  assert.equal(f.el('CandidatesSelected').textContent,'3 selected');
  await f.choose('MinScore','90');assert.equal(f.el('CandidatesSelected').textContent,'0 selected');await f.choose('MinScore','0');

  // A refresh drops a selected candidate that left the view and keeps one
  // still in view, which then acts on the latest revision this window saw.
  await f.select('Demo Gamma');await f.select('Demo Alpha');
  const gamma=f.server.rows.find(row=>row.key==='c'.repeat(64)),alpha=f.server.rows.find(row=>row.key==='a'.repeat(64));
  gamma.deleted=true;alpha.revision+=5;
  await f.el('CandidatesRefresh').click();await settle();
  assert.equal(f.el('CandidatesSelected').textContent,'1 selected','a candidate trashed elsewhere leaves the selection');
  gamma.deleted=false;gamma.revision++;await f.el('CandidatesRefresh').click();await settle();
  // A refused change keeps the selection.
  f.server.reject='A selected candidate changed in another window. Refresh before trying again.';
  await f.el('CandidatesMove').click();await settle();
  assert.equal(f.last('candidate_move').items[0].revision,alpha.revision,'the latest revision this window saw is sent');
  assert.match(f.el('CandidatesMessage').textContent,/changed in another window/);assert.equal(f.el('CandidatesSelected').textContent,'1 selected');
  f.server.reject=null;await f.select('Demo Alpha');

  // Excel follows the folder and shortlist view.
  await f.choose('Folder','Controlling');await f.el('CandidatesExport').click();await settle();
  const exported=f.last('export_candidates');assert.equal(exported.folder,'Controlling');assert.equal(exported.shortlisted,false);

  // Deleting a folder moves its candidates (including Trash) to Unfiled.
  f.server.rows.find(row=>row.key==='b'.repeat(64)).deleted=true;await f.el('CandidatesRefresh').click();await settle();
  await f.el('CandidatesDeleteFolder').click();await settle();
  assert.match(f.confirms.at(-1),/Delete the folder Controlling\? Its 2 candidates move to Unfiled; none are deleted\./);
  assert.equal(f.last('candidate_folder_delete').name,'Controlling');
  assert.equal(f.el('CandidatesFolder').value,'*');assert.match(f.el('CandidatesMessage').textContent,/Folder Controlling deleted\. 2 candidates moved to Unfiled\./);
  assert.deepEqual(f.labels('Folder'),['All folders (2)','Unfiled (1)','Finance (1)','Trash (2)']);

  // A note saved on a selected candidate does not make the selection stale.
  {const n=fixture();await n.el('CandidatesTab').click();await settle();
   await n.select('Demo Alpha');
   const note=n.row('Demo Alpha').children.at(-1).children[0];note.children[1].value='Strong CO-PA';await note.children[1].dispatch('input');
   await note.children[2].click();await settle();
   n.el('CandidatesMoveTo').value='Finance';await n.el('CandidatesMove').click();await settle();
   assert.deepEqual(n.last('candidate_move').items,[{key:'a'.repeat(64),revision:2}]);assert.match(n.el('CandidatesMessage').textContent,/Moved 1 candidate to Finance\./);}

  // Un-starring in "Shortlisted only" hides the candidate, so it leaves the selection.
  {const h=fixture();await h.el('CandidatesTab').click();await settle();
   await h.star('Demo Alpha').click();await settle();
   h.el('CandidatesShortlisted').checked=true;await h.el('CandidatesShortlisted').dispatch('change');
   await h.select('Demo Alpha');await h.star('Demo Alpha').click();await settle();
   assert.deepEqual(h.names(),[]);assert.equal(h.el('CandidatesSelected').textContent,'0 selected');assert(h.el('CandidatesTrash').disabled,'nothing hidden can be deleted');}

  // A change whose reload fails says so, and the selection is cleared.
  {const r=fixture();await r.el('CandidatesTab').click();await settle();
   await r.select('Demo Alpha');r.el('CandidatesMoveTo').value='Finance';r.server.failList=true;
   await r.el('CandidatesMove').click();await settle();
   assert.match(r.el('CandidatesMessage').textContent,/^Moved 1 candidate to Finance\. The list could not be reloaded \(Saved candidates could not be read securely.*\)\. Click Refresh\.$/);
   assert.equal(r.el('CandidatesSelected').textContent,'0 selected');}

  // A search result refresh that starts while a folder is being created makes
  // Create folder wait for a fresh list; Move to uses the name the service saved.
  {const w=fixture();await w.el('CandidatesTab').click();await settle();
   await w.select('Demo Alpha');
   w.el('CandidatesNewFolder').value='Controlling\u0085';await w.el('CandidatesNewFolder').dispatch('input');
   w.server.gate='candidate_folder_create';const created=w.el('CandidatesCreateFolder').click();await settle();
   w.server.hold=true;w.win.cvStudioPeople.sourcerChanged();await settle();const release=w.server.release;w.server.hold=false;
   w.server.open();await settle();release();await created;await settle();
   assert.equal(w.el('CandidatesMoveTo').value,'Controlling','the saved folder name is chosen in Move to');
   assert.match(w.el('CandidatesMessage').textContent,/Folder Controlling created/);assert.equal(w.el('CandidatesSelected').textContent,'1 selected');}

  // A star saved after an older read began is not undone when that read arrives.
  {const s=fixture();await s.el('CandidatesTab').click();await settle();
   s.server.gate='candidate_shortlist';const starred=s.star('Demo Beta').click();await settle();
   s.server.hold=true;s.win.cvStudioPeople.sourcerChanged();await settle();const release=s.server.release;s.server.hold=false;
   s.server.open();await starred;await settle();release();await settle();
   assert.equal(s.star('Demo Beta').textContent,'\u2605','the star stays after the older read arrives');}

  // A refresh that finishes while a star is saving does not hide the saved star,
  // and the next star click uses the saved revision.
  {const q=fixture();await q.el('CandidatesTab').click();await settle();
   q.server.gate='candidate_shortlist';const starred=q.star('Demo Beta').click();await settle();
   q.win.cvStudioPeople.sourcerChanged();await settle();
   assert.equal(q.star('Demo Beta').textContent,'\u2606','the finished refresh shows the row before the save');
   q.server.open();await starred;await settle();
   assert.equal(q.star('Demo Beta').textContent,'\u2605','the saved star shows on the current row');
   await q.star('Demo Beta').click();await settle();
   assert.deepEqual(q.last('candidate_shortlist'),{action:'candidate_shortlist',key:'b'.repeat(64),revision:2,shortlisted:false});
   assert.match(q.el('CandidatesMessage').textContent,/removed from the shortlist/);}

  // A refused note save works after a refresh, once the newer note was shown.
  {const c=fixture();await c.el('CandidatesTab').click();await settle();
   const editor=c.row('Demo Beta').children.at(-1).children[0];editor.children[1].value='Mine';await editor.children[1].dispatch('input');
   c.server.rows.find(row=>row.key==='b'.repeat(64)).notes='Theirs';c.server.rows.find(row=>row.key==='b'.repeat(64)).revision=2;
   await editor.children[2].click();await settle();assert.match(c.el('CandidatesMessage').textContent,/This candidate changed/);
   await c.el('CandidatesRefresh').click();await settle();
   const again=c.row('Demo Beta').children.at(-1).children[0];assert.equal(again.children[0].textContent,'Theirs','the newer note is shown');
   await again.children[2].click();await settle();
   assert.equal(c.last('candidate_note').revision,2);assert.equal(c.last('candidate_note').notes,'Mine');assert.match(c.el('CandidatesMessage').textContent,/Note saved/);}

  finished=true;
  console.log('Candidate folders: create, move selected, folder view with counts, shortlist and filter, notes with organising, Trash and Restore, select page, refresh and stale selections, failed reloads, in-flight reads, canonical folder names, export view and folder deletion passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});

/* Sourcer Candidates dashboard: sort, order and filters. Fictional people. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/people-dashboards.js'),'utf8');

class Element {
  constructor(tag='div'){Object.assign(this,{tagName:tag.toUpperCase(),children:[],handlers:{},dataset:{},attributes:{},textContent:'',value:'',checked:false,disabled:false,hidden:false,open:false});}
  addEventListener(type,fn){(this.handlers[type] ||= []).push(fn);}
  dispatch(type){return Promise.all((this.handlers[type]||[]).map(fn=>fn({preventDefault(){},target:this})));}
  append(...items){this.children.push(...items);} replaceChildren(...items){this.children=items;}
  setAttribute(name,value){this.attributes[name]=String(value);} getAttribute(name){return this.attributes[name] ?? null;} removeAttribute(name){delete this.attributes[name];}
  querySelectorAll(){return [];} click(){return this.dispatch('click');}
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function settle(){for(let n=0;n<20;n++)await tick();}
const person=(name,location,score,read,saved_at)=>({key:name.toLowerCase().replace(/\W/g,'').padEnd(64,'0').slice(0,64),name,location,score,read,saved_at,
  title:'Data Analyst',url:'https://www.linkedin.com/in/'+name.toLowerCase().replace(/\W/g,'-'),evidence:['Fictional evidence'],unknowns:[],notes:'',brief:'Fictional brief',run_id:'r'.repeat(32),revision:1});
const ROWS=[person('Zara Demo','Penang',62,'Search card','2026-10-05T00:00:00+00:00'),person('adam Demo','Kuala Lumpur',91,'Profile detail','2026-10-04T00:00:00+00:00'),
  person('Mia Demo','',75,'Search card','2026-10-03T00:00:00+00:00'),person('Ben Demo','Johor',48,'Profile detail','2026-10-02T00:00:00+00:00'),
  person('Kai Demo','Ipoh',91,'Search card','2026-10-01T00:00:00+00:00')];

function fixture(stored=new Map(),rows=ROWS){
  const ids=new Map(),posts=[];
  const document={getElementById:id=>{if(!ids.has(id))ids.set(id,new Element(/Sort|Order|MinScore|Read|Search|Company/.test(id)?'select':'div'));return ids.get(id);},
    createElement:tag=>new Element(tag),querySelectorAll:()=>[]};
  const el=name=>document.getElementById('people'+name);
  el('CandidatesSort').value='saved_at';el('CandidatesOrder').value='desc';el('CandidatesMinScore').value='0';el('CandidatesRead').value='';
  for(const [name,values] of [['Sort',['saved_at','score','name','location','read']],['Order',['desc','asc']]])
    el('Candidates'+name).options=values.map(value=>({value}));
  const fetch=async(url,init)=>{
    const body=JSON.parse(init.body);posts.push({url,body});
    if(body.action==='candidates')return {ok:true,json:async()=>({candidates:structuredClone(rows)})};
    if(body.action==='hr_people')return {ok:true,json:async()=>({people:[]})};
    if(body.action==='export_candidates')return {ok:true,blob:async()=>'xlsx'};
    throw Error('unexpected '+body.action);
  };
  const localStorage={getItem:key=>stored.get(key) ?? null,setItem:(key,value)=>stored.set(key,String(value))};
  const window={addEventListener(){},cvStudioJobLeads:null};
  const context=vm.createContext({window,document,fetch,localStorage,console,structuredClone,Intl,URL:{createObjectURL:()=>'blob:x',revokeObjectURL(){}},
    setTimeout,crypto:{randomUUID:()=>'00000000-0000-4000-8000-000000000000'}});
  vm.runInContext(source,context);
  const names=()=>el('CandidatesRows').children.map(tr=>tr.children[0].children[0].textContent);
  const choose=async(name,value)=>{el('Candidates'+name).value=value;await el('Candidates'+name).dispatch('change');};
  return {el,posts,names,choose,stored};
}

(async()=>{
  const f=fixture();
  await f.el('CandidatesTab').click();await settle();
  assert.deepEqual(f.names(),['Zara Demo','adam Demo','Mia Demo','Ben Demo','Kai Demo'],'default is newest assessed first');
  await f.choose('Sort','score');
  assert.deepEqual(f.names(),['adam Demo','Kai Demo','Mia Demo','Zara Demo','Ben Demo'],'highest match first; ties keep newest first');
  await f.choose('Order','asc');
  assert.deepEqual(f.names(),['Ben Demo','Zara Demo','Mia Demo','adam Demo','Kai Demo']);
  await f.choose('Sort','name');
  assert.deepEqual(f.names(),['adam Demo','Ben Demo','Kai Demo','Mia Demo','Zara Demo'],'names ignore letter case');
  await f.choose('Order','desc');
  assert.deepEqual(f.names(),['Zara Demo','Mia Demo','Kai Demo','Ben Demo','adam Demo']);
  await f.choose('Sort','location');
  assert.equal(f.names().at(-1),'Mia Demo','a blank location stays last when descending');
  await f.choose('Order','asc');
  assert.deepEqual(f.names(),['Kai Demo','Ben Demo','adam Demo','Zara Demo','Mia Demo'],'and last when ascending');
  await f.choose('MinScore','75');
  assert.deepEqual(f.names(),['Kai Demo','adam Demo','Mia Demo'],'filters keep the chosen location order');assert.equal(f.el('CandidatesCount').textContent,'3');
  await f.choose('Read','Profile detail');
  assert.deepEqual(f.names(),['adam Demo']);
  await f.el('CandidatesExport').click();await settle();
  const exported=f.posts.find(post=>post.body.action==='export_candidates').body;
  assert.deepEqual({min_score:exported.min_score,read:exported.read,sort:exported.sort,order:exported.order},{min_score:75,read:'Profile detail',sort:'location',order:'asc'},'Excel uses the same view');
  // Sort and order are remembered per viewer; filters are not.
  const again=fixture(f.stored);
  assert.equal(again.el('CandidatesSort').value,'location');assert.equal(again.el('CandidatesOrder').value,'asc');
  const unknown=fixture(new Map([['cvstudio_candidates_sort','email']]));
  assert.equal(unknown.el('CandidatesSort').value,'saved_at','an unknown remembered choice is ignored');
  // Same names and expected order as tests/test_people_dashboards.py, so the
  // screen and the Excel export agree (case, accents, numbers, blank last).
  const NAMES=['Zara Lim','\u00c9milie Tan','Candidate 10','Candidate 9','adam Ong','  Bee Ng','\u00c5ngstr\u00f6m Lee','   ','\u00c9va Kumar','Eve Tan','Ezra Lim'];
  const ASC=['adam Ong','\u00c5ngstr\u00f6m Lee','  Bee Ng','Candidate 9','Candidate 10','\u00c9milie Tan','\u00c9va Kumar','Eve Tan','Ezra Lim','Zara Lim','   '];
  const DESC=['Zara Lim','Ezra Lim','Eve Tan','\u00c9va Kumar','\u00c9milie Tan','Candidate 10','Candidate 9','  Bee Ng','\u00c5ngstr\u00f6m Lee','adam Ong','   '];
  const parity=fixture(new Map(),NAMES.map((name,index)=>({...person('P'+index,'',50,'Search card','2026-10-01T00:00:00+00:00'),name})));
  await parity.el('CandidatesTab').click();await settle();
  await parity.choose('Sort','name');await parity.choose('Order','asc');assert.deepEqual(parity.names(),ASC);
  await parity.choose('Order','desc');assert.deepEqual(parity.names(),DESC);
  console.log('Candidate dashboard: sort by date, match, name and location both ways, blank-last, minimum match, profile read, export view, remembered order and screen/Excel order parity passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});

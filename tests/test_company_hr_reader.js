const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/reader.js'),'utf8');
const element=(innerText='',extra={})=>({innerText,getClientRects:()=>[{}],getAttribute:()=>null,querySelector:()=>null,querySelectorAll:()=>[],...extra});
const location={origin:'https://www.linkedin.com',href:'https://www.linkedin.com/company/example/people/',pathname:'/company/example/people/'};
const state={company:'Example Company',country:'Malaysia',companyIds:['123'],clicks:[],input:null,selected:true,empty:false,restricted:false};
const employee=id=>element('Employees',{href:'https://www.linkedin.com/search/results/people/?currentCompany='+encodeURIComponent(JSON.stringify([id]))});
const header=element('',{querySelectorAll:()=>state.companyIds.map(employee)});
const heading=element('Example Company',{closest:()=>header});
const toolbar=element('',{querySelectorAll:selector=>{
  if(selector==='button' || selector==='button, [role="button"]')return state.modern && selector==='button'?[]:[element('Locations',{click:()=>state.clicks.push('open')})];
  if(selector.includes('checkbox'))return [state.company,...(!state.modern&&state.selected?[state.country]:[])].map(label=>element('',{checked:true,labels:state.modern?[element(label)]:[],getAttribute:name=>name==='aria-label'&&!state.modern?label:null}));
  if(selector==='a, button')return state.modern?[]:[element('Show results',{click:()=>state.clicks.push('apply')})];
  return [];
}});
class Input{dispatchEvent(event){state.inputEvent=event.type}}
Object.defineProperty(Input.prototype,'value',{set(value){state.input=value}});
const input=new Input();input.getClientRects=()=>[{}];input.getAttribute=()=>null;
const popup=element('',{querySelectorAll:selector=>selector.includes('checkbox')?[element('',{checked:state.selected,labels:[element(state.country)]})]:selector==='a, button'?[element('Show results',{click:()=>state.clicks.push('apply')})]:[]});
input.closest=()=>state.modern?popup:null;
const suggestions=element('',{querySelectorAll:selector=>state.modern&&selector==='button'?[]:!state.modern&&selector==='[role="option"]'?[]:[element('Malaysia',{querySelector:()=>state.modern?element('',{click:()=>state.clicks.push('pick')}):null,click:()=>state.clicks.push('pick')}),element('Selangor, Malaysia',{click:()=>{throw Error('must not select partial country match')}})]});
const card=(name,title,where,url='https://www.linkedin.com/in/'+name)=>{
  const link=element(name,{href:url}),paras=[element(name,{querySelector:()=>link}),element(title),element(where)];
  return element(name+' '+title,{querySelectorAll:s=>s==='p'?paras:[],querySelector:()=>null});
};
state.cards=[card('sample','Senior HRBP | Talent Acquisition','Malaysia'),card('person','CHRO and Chief People Officer','Singapore'),
  card('decoy','Data Architect at Example Company','Malaysia'),card('word','Data platform specialist','Malaysia'),card('sample','Recruiter','Malaysia'),card('bad','HR Manager','Malaysia','https://attacker.invalid/in/bad')];
const pageButton=element('Page 1');const pager={querySelector:()=>pageButton};
const next=element('Next',{parentElement:pager,click:()=>state.clicks.push('next')});
const main=element('',{querySelectorAll:s=>s==='button'?[next]:s.includes('listitem')?
  state.wrapped&&!s.includes('[role="list"] > * > [role="listitem"]')?state.cards.slice(0,1):state.cards:[]});
Object.defineProperty(main,'innerText',{get:()=>state.restricted?'You have reached the commercial search limit':state.empty?'No results found':'Visible employee results'});
const document={body:main,querySelector:selector=>{
  if(selector==='main')return main;
  if(selector==='main [aria-label="Primary content"]')return state.wrapped&&!state.noPrimary?main:null;
  if(selector.includes('FilterBar'))return state.missingToolbar?null:toolbar;
  return null;
},querySelectorAll:selector=>{
  if(selector==='main h1, h1')return [heading];
  if(selector.startsWith('input[placeholder'))return [input];
  if(selector==='[role="listbox"]')return [suggestions];
  return [];
}};
const context=vm.createContext({document,location,URL,URLSearchParams,HTMLInputElement:Input,Event:class{constructor(type){this.type=type}},getComputedStyle:()=>({visibility:'visible'})});
vm.runInContext(source,context);const reader=context.SourcerReader;
assert.equal(reader.readHRCompany('https://www.linkedin.com/company/example/','Example Company').company_id,'123');
assert.throws(()=>reader.readHRCompany('https://www.linkedin.com/company/example/','Other Company'));
state.companyIds=['123','999'];assert(reader.readHRCompany('https://www.linkedin.com/company/example/','Example Company').loading);state.companyIds=['123'];
location.pathname='/search/results/people/';location.href='https://www.linkedin.com/search/results/people/?currentCompany=%5B%22123%22%5D';
assert(reader.hrCountryOpen('Malaysia'));assert(reader.hrCountryType('Malaysia'));assert.equal(state.input,'Malaysia');assert.equal(state.inputEvent,'input');
assert(reader.hrCountryPick('Malaysia'));assert(!reader.hrCountryPick('Singapore'));assert(reader.hrCountryApply('Malaysia'));
const keywords='HR, HRBP, CHRO, chief people officer, TA, talent acquisition, recruiter';
let snapshot=reader.readHRSearch('Example Company','Malaysia',keywords);
assert.equal(snapshot.people.length,2);assert.equal(snapshot.people[0].name,'sample');assert.match(snapshot.people[0].matched,/HRBP/);
assert.equal(snapshot.people[0].location,'Malaysia');assert(!snapshot.people.some(p=>p.name==='word'),'TA cannot match data');
assert(snapshot.hasNext);assert(reader.nextHRSearch(snapshot.signature,'Example Company','Malaysia',keywords));
assert.deepEqual(state.clicks,['open','pick','apply','next']);
assert.throws(()=>reader.nextHRSearch('stale','Example Company','Malaysia',keywords));
state.selected=false;assert(reader.readHRSearch('Example Company','Malaysia',keywords).loading);assert(!reader.hrCountryApply('Malaysia'));
assert.equal(reader.readHRSearch('Example Company','',keywords).people.length,2,'Any country requires no geography badge');
assert(reader.readHRSearch('Different Company','',keywords).loading);state.selected=true;
state.cards=[card('nonhr','Developer','Malaysia')];snapshot=reader.readHRSearch('Example Company','Malaysia',keywords);assert.equal(snapshot.people.length,0);assert.equal(snapshot.loading,undefined,'valid page with zero HR matches still paginates');
state.cards=[];assert(reader.readHRSearch('Example Company','Malaysia',keywords).loading);state.empty=true;assert(reader.readHRSearch('Example Company','Malaysia',keywords).empty);
state.modern=true;
assert(reader.readHRSearch('Example Company','',keywords).empty,'a checked company filter can get its name from an associated visible label');
assert(reader.readHRSearch('Other Company','',keywords).loading,'another company label is not accepted');
assert(reader.hrCountryOpen('Malaysia'),'modern Locations is a role=button div');
assert(reader.hrCountryPick('Malaysia'),'modern suggestions are role=option rows containing role=button controls');
assert(reader.hrCountryApply('Malaysia'),'the exact selected country and Show results can be in a portal outside the toolbar');
state.selected=false;assert(!reader.hrCountryApply('Malaysia'),'an unchecked country cannot be applied');
state.selected=true;state.empty=false;state.wrapped=true;
state.cards=Array.from({length:10},(_,i)=>card('synthetic-'+i,'Talent Acquisition Specialist','Malaysia'));
assert.equal(reader.readHRSearch('Example Company','',keywords).people.length,10,'modern list wrappers have a component key on the first result only; all ten result items must be read');
state.noPrimary=true;
assert.equal(reader.readHRSearch('Example Company','',keywords).people.length,1,'the new wrapper fallback is restricted to a recognized primary-results region');
state.noPrimary=false;
state.missingToolbar=true;
assert.equal(reader.hrCountryOpen('Malaysia'),false,'a delayed filter bar causes no click and can be polled safely');
state.restricted=true;assert.throws(()=>reader.readHRSearch('Example Company','Malaysia',keywords));
console.log('Company HR reader: observed company ID, exact country suggestions/badges, native-only controls, scoped fields, HR word boundaries, loading/empty distinction, pagination and restrictions passed');

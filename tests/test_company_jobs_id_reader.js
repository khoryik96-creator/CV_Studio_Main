/* Observed company Jobs links only. No network, private API or guessed ID. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const root='https://www.linkedin.com/company/fictional-client/';
const node=(text='',extra={})=>({innerText:text,getClientRects:()=>[{}],getAttribute:()=>null,querySelector:()=>null,querySelectorAll:()=>[],...extra});
const state={links:[],headerLinks:[],heading:true,actions:[],clicks:0};
const header=node('Fictional Client',{querySelectorAll:()=>state.headerLinks});
const heading=node('Fictional Client',{closest:()=>header});
const main=node('Fictional Client jobs',{querySelectorAll:selector=>selector==='button, [role="button"], a[href]'?state.actions:state.links});
const location={href:root+'jobs/',pathname:'/company/fictional-client/jobs/'};
const document={body:main,querySelector:s=>s==='main'?main:null,querySelectorAll:()=>state.heading?[heading]:[]};
const context=vm.createContext({document,location,URL,URLSearchParams,Date,Number,getComputedStyle:()=>({visibility:'visible'})});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/reader.js'),'utf8'),context);
const read=()=>context.SourcerReader.readCompanyJobsID(root);
const link=(label,url,extra={})=>node(label,{href:url,...extra});
const jobs=id=>'https://www.linkedin.com/jobs/search/?f_C='+id;
assert(read().loading);state.heading=false;state.links=[link('See all jobs',jobs('42'))];assert(read().loading);state.heading=true;
assert.equal(read().company_id,'42');assert.equal(read().company_url,root);
state.links=[link('See all 1,234 jobs',jobs('42')),link('See all jobs',jobs('42'))];assert.equal(read().company_id,'42');
for(const bad of ['https://attacker.invalid/jobs/search/?f_C=42',jobs('1,2'),jobs('1')+'&f_C=2','https://user@www.linkedin.com/jobs/search/?f_C=42',jobs('42')+'#bad']){
 state.links=[link('See all jobs',bad)];assert(read().loading);
}
state.links=[link('See all jobs',jobs('42'),{getClientRects:()=>[]})];assert(read().loading);
state.links=[link('Recommended company',jobs('99')),link('Individual vacancy','https://www.linkedin.com/jobs/view/42')];assert(read().loading);
state.links=[link('See all jobs',jobs('42'))];state.headerLinks=[link('See employees','https://www.linkedin.com/search/results/people/?currentCompany=%5B%2242%22%5D')];assert.equal(read().company_id,'42');
state.links=[];assert.equal(read().company_id,'42','company-header fallback');
state.links=[link('See all jobs',jobs('99'))];assert.throws(read,/different company numbers/);
state.headerLinks=[];state.links.push(link('See all jobs',jobs('42')));assert.throws(read,/different company numbers/);
location.href=root.replace('fictional-client','other')+'jobs/';assert.throws(read,/changed/);
location.href=root+'people/';location.pathname='/company/fictional-client/people/';assert.throws(read,/changed/);
location.href='https://www.linkedin.com/login';location.pathname='/login';assert.throws(read,/sign in/);
location.href=root+'jobs/';location.pathname='/company/fictional-client/jobs/';
// Corroborated company-header connections links use the same rules as HR.
state.links=[];
const people=(ids,protocol='https:',extra='')=>protocol+'//www.linkedin.com/search/results/people/?currentCompany='+encodeURIComponent(JSON.stringify(ids))+'&origin=COMPANY_PAGE_CANNED_SEARCH'+extra;
const group=link('Associated members',people(['42','99']));
const connection=link('Connections',people(['42'],'http:','&network=%5B%22F%22%5D'));
state.headerLinks=[group,connection];assert.equal(read().company_id,'42');
state.headerLinks=[connection];assert(read().loading,'an uncorroborated HTTP link is never company evidence');
state.headerLinks=[link('Associated members',people(['11','99'])),connection];assert(read().loading,'the group must corroborate the exact company id');
state.headerLinks=[group,link('Connections',people(['42'],'http:'))];assert(read().loading,'the exact connections-filter evidence is required');
state.headerLinks=[group];assert(read().loading,'a multi-company group never selects an arbitrary member');
state.headerLinks=[group,connection];state.links=[link('See all jobs',jobs('99'))];assert.throws(read,/different company numbers/);
// Native Jobs buttons can expose the numeric filter only after activation.
state.links=[];state.headerLinks=[];
const button=(label='See all jobs',extra={})=>node(label,{click:()=>state.clicks++,...extra});
const open=()=>context.SourcerReader.openCompanyJobs(root);
state.actions=[button()];assert.equal(read().jobs_action,true);assert(open());assert.equal(state.clicks,1);
state.actions=[button('',{getAttribute:name=>name==='aria-label'?'View all 123 jobs at Fictional Client':null})];assert(open());assert.equal(state.clicks,2);
for(const control of [button('See all jobs',{disabled:true}),button('See all jobs',{getClientRects:()=>[]}),button('See all jobs',{getAttribute:name=>name==='aria-disabled'?'true':null}),button('Follow'),
 button('See all jobs',{closest:selector=>selector.startsWith('aside')?{}:null}),
 button('See all jobs',{closest:selector=>selector==='section'?node('',{querySelectorAll:()=>[link('Other employer','https://www.linkedin.com/company/other/')] }):null}),
 link('See all jobs','https://evil.invalid/jobs/search/'),link('See all jobs',jobs('1,2')),
 link('See all jobs','https://www.linkedin.com/jobs/search/',{getAttribute:name=>name==='target'?'_blank':null})]){
 state.actions=[control];assert(!read().jobs_action);assert.equal(open(),false);
}
state.actions=[button(),button('View all jobs')];assert(!read().jobs_action,'multiple calls to action never choose an arbitrary company');assert.equal(open(),false);
state.actions=[button()];state.links=[link('See all jobs',jobs('42'))];assert.equal(open(),false,'observed IDs avoid unnecessary clicks');
state.links=[];location.href=root.replace('fictional-client','other')+'jobs/';assert.throws(open,/changed/);
location.href=root+'jobs/';state.heading=false;assert.equal(open(),false,'a loading header cannot authorize a click');state.heading=true;
assert.equal(state.clicks,2,'all unsafe, ambiguous or changed controls remained untouched');
console.log('Company Jobs reader: visible CTA/header identity, same-root authority, loading, ambiguity and hostile links passed.');

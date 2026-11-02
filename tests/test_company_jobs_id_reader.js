/* Observed company Jobs links only. No network, private API or guessed ID. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const root='https://www.linkedin.com/company/fictional-client/';
const node=(text='',extra={})=>({innerText:text,getClientRects:()=>[{}],getAttribute:()=>null,querySelector:()=>null,querySelectorAll:()=>[],...extra});
const state={links:[],headerLinks:[],heading:true};
const header=node('Fictional Client',{querySelectorAll:()=>state.headerLinks});
const heading=node('Fictional Client',{closest:()=>header});
const main=node('Fictional Client jobs',{querySelectorAll:()=>state.links});
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
console.log('Company Jobs reader: visible CTA/header identity, same-root authority, loading, ambiguity and hostile links passed.');

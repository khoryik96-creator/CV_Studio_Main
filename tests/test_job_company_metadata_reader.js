const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const expected='https://www.linkedin.com/jobs/view/1234567890',companyURL='https://www.linkedin.com/company/example/';
const element=(innerText='',extra={})=>({innerText,getClientRects:()=>[{}],querySelector:()=>null,querySelectorAll:()=>[],getAttribute:()=>null,matches:()=>false,...extra});
const companyLink=element('ABC Corporate Business Solutions',{href:companyURL+'life/'}),alias=element('ABC',{href:companyURL});
const state={links:[companyLink],header:'ABC Corporate Business Solutions Following'};
const company=element('',{querySelectorAll:()=>state.links});Object.defineProperty(company,'innerText',{get:()=>state.header});
const title=element('SAP Consultant',{querySelector:()=>({href:expected})});
const panel=element('',{querySelector:()=>title,querySelectorAll:selector=>selector.includes('job-title')?[title]:selector.includes('company-name')?[company]:[]});
const main=element('Visible job ad');
const document={body:main,querySelector:selector=>selector==='main'?main:null,querySelectorAll:selector=>selector.includes('jobs-details')?[panel]:[]};
const location={origin:'https://www.linkedin.com',pathname:'/jobs/view/1234567890',href:expected,search:''};
const context=vm.createContext({document,location,URL,URLSearchParams,Date,Number,getComputedStyle:()=>({visibility:'visible'})});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/reader.js'),'utf8'),context);const reader=context.SourcerReader;
let result=reader.readJob(expected,true);assert.equal(result.company,'ABC Corporate Business Solutions');assert.equal(result.company_url,companyURL);assert.equal(result.description,'','Follow controls do not become the employer name');
state.links=[companyLink,alias];assert.equal(reader.readJob(expected,true).company_url,companyURL,'different observed labels on the exact same company link are one identity');
for(const bad of ['https://attacker.invalid/company/example/','https://www.linkedin.com/company/other/']){
  state.links=[companyLink,element('Another label',{href:bad})];assert.throws(()=>reader.readJob(expected,true),error=>error.cvstudioJobLoading===true,'ambiguous or hostile employer links cannot be selected');
}
console.log('Job company metadata: scoped employer links, Follow controls, same-URL labels, exact ad identity and ambiguous/hostile company rejection passed.');

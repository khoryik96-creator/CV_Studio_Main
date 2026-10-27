const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/reader.js'),'utf8');
const employee=(ids,patch={})=>({ids,scheme:'https:',text:'1K-5K employees',origin:'COMPANY_PAGE_CANNED_SEARCH',...patch});
const connection=(ids,patch={})=>employee(ids,{scheme:'http:',text:'Connections work here',network:'["F"]',...patch});
function read(links, outside=[]){
  const element=(innerText,extra={})=>({innerText,getClientRects:()=>[{}],getAttribute:()=>null,...extra});
  const link=data=>{
    const url=new URL(data.scheme+'//'+(data.host || 'www.linkedin.com')+(data.path || '/search/results/people/'));
    url.searchParams.set('currentCompany',JSON.stringify(data.ids));
    if(data.origin)url.searchParams.set('origin',data.origin);
    if(data.network)url.searchParams.set('network',data.network);
    if(data.duplicate)url.searchParams.append('currentCompany','["999"]');
    return element(data.text,{href:url.href,click(){throw Error('Reading company identity must never navigate an HTTP link')}});
  };
  const header=element('header',{querySelectorAll:()=>links.map(link)}),heading=element('Example Company',{closest:()=>header});
  const main=element('Company people',{querySelectorAll:()=>outside.map(link)});
  const document={body:main,querySelector:s=>s==='main'?main:null,querySelectorAll:s=>s==='main h1, h1'?[heading]:outside.map(link)};
  const location={origin:'https://www.linkedin.com',href:'https://www.linkedin.com/company/example/people/',pathname:'/company/example/people/'};
  const context=vm.createContext({document,location,URL,getComputedStyle:()=>({visibility:'visible'})});
  vm.runInContext(source,context);return context.SourcerReader.readHRCompany('https://www.linkedin.com/company/example/','Example Company');
}
assert.equal(read([employee(['123','456']),connection(['123'])]).company_id,'123','a grouped employee link plus exact header connection identifies the company');
assert.equal(read([employee(['123','456','789']),connection(['789'])]).company_id,'789','never select the first group member by order');
assert.equal(read([employee(['123'])]).company_id,'123','existing HTTPS identity stays compatible');
for(const links of [
  [connection(['123'])],
  [employee(['123','456'])],
  [employee(['123','456']),connection(['789'])],
  [employee(['123','456']),connection(['123']),connection(['456'])],
  [employee(['123','456']),connection(['123'],{network:'["S"]'})],
  [employee(['123','456']),connection(['123'],{origin:''})],
  [employee(['123','456']),connection(['123'],{host:'www.linkedin.com.attacker.test'})],
  [employee(['123','456']),connection(['123'],{host:'user@www.linkedin.com'})],
  [employee(['123','456']),connection(['123'],{path:'/jobs/'})],
  [employee(['123','456']),connection(['123'],{duplicate:true})],
  [employee(['123','456'],{text:'Recommended companies'}),connection(['123'])],
  [employee(['123','456']),connection(['123','456'])]
])assert(read(links).loading,'unsupported/ambiguous header evidence must stay unconfirmed');
assert(read([employee(['123','456'])],[connection(['123'])]).loading,'a recommendation outside the company header cannot resolve identity');
console.log('Company HR HTTP identity: observed primary ID, grouped memberships, no first-ID guess, header scope and hostile links passed.');

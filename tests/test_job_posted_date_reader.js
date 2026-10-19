const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/reader.js'),'utf8');
const expected='https://www.linkedin.com/jobs/view/1234567890';
function read(rawDate) {
  const visible=innerText=>({innerText,getClientRects:()=>[{}]});
  const title={...visible('Finance Manager'),matches:()=>false,querySelector:()=>({href:expected})};
  const company=visible('Example Company'),locationText=visible('Penang'),description=visible('Build partnerships.\nManage reporting.');
  const panel={getClientRects:()=>[{}],
    querySelector:selector=>selector.includes('datePosted')?rawDate===null?null:{getAttribute:name=>name==='datetime'?rawDate:''}:selector.includes('job-title')?title:null,
    querySelectorAll:selector=>selector.includes('job-title')?[title]:selector.includes('company-name')?[company]:selector.includes('primary-description')?[locationText]:selector.includes('#job-details')?[description]:[]};
  const main=visible('The current job is available.');
  const document={body:main,
    querySelector:selector=>selector==='main'?main:selector.includes('datePosted')?{getAttribute:()=> '1999-01-01'}:null,
    querySelectorAll:selector=>selector.includes('jobs-details')?[panel]:[]};
  const context=vm.createContext({document,location:{origin:'https://www.linkedin.com',href:expected,pathname:'/jobs/view/1234567890',search:''},URL,URLSearchParams,Date,Number,getComputedStyle:()=>({visibility:'visible'})});
  vm.runInContext(source,context);
  return context.SourcerReader.readJob(expected);
}
for (const [raw,wanted] of [['2026-10-02','2026-10-02'],['2026-10-02T00:15:00+08:00','2026-10-02'],['2026-10-02T23:30:00-04:00','2026-10-02'],['2024-02-29','2024-02-29'],['2026-02-29',''],['2026-10-02T25:00:00Z',''],['2 weeks ago',''],['20261002',''],[null,'']]) {
  const row=read(raw);assert.equal(row.date_posted,wanted,String(raw));
  assert.equal(row.role,'Finance Manager');assert.equal(row.description,'Build partnerships.\nManage reporting.');
}
console.log('Job posted-date reader: same-panel exact dates, timezone calendar, invalid/relative/missing dates and outside-panel date isolation passed');

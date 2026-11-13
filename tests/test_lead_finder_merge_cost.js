// Lead Finder people are recognised by email or profile link, and email-search
// cost adds up across runs. Pure page logic; no network or AI.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/lead-finder.js'),'utf8');
const grab=name=>{const start=source.indexOf('function '+name+'(');assert(start>=0,name);let depth=0;for(let i=source.indexOf('{',start);i<source.length;i++){if(source[i]==='{')depth++;else if(source[i]==='}'&&--depth===0)return source.slice(start,i+1);}throw Error(name);};
const context=vm.createContext({});
vm.runInContext(['leadPeopleMergeKey','leadPeopleMergeKeys','leadMergePeople'].map(grab).join('\n'),context);
const merge=(a,b)=>JSON.parse(JSON.stringify(vm.runInContext('leadMergePeople',context)(a,b)));
const link='https://www.linkedin.com/in/sample-person';
// Found by profile link, then given an email, then found again without one.
let rows=merge([{name:'Sample Person',company:'Example Co',profile_url:link,email:'sample@example.com',status:'Contacted'}],[{name:'Sample Person',company:'Example Co',profile_url:link+'/',title:'HR Manager'}]);
assert.equal(rows.length,1,'the same profile is not added twice after its email was found');
assert.deepEqual(rows[0],{name:'Sample Person',company:'Example Co',profile_url:link,email:'sample@example.com',status:'Contacted',title:'HR Manager'},'blank fields are filled; existing values are kept');
// Same email under a different link is still one person, as before.
assert.equal(merge([{name:'A',email:'One@Example.com',profile_url:link}],[{name:'A',email:'one@example.com',profile_url:link+'-2'}]).length,1);
// A later row can connect by either identity.
rows=merge([{name:'A',profile_url:link}],[{name:'A',email:'a@example.com',profile_url:link},{name:'A',email:'a@example.com'}]);
assert.equal(rows.length,1);assert.equal(rows[0].email,'a@example.com');
// Different people stay separate, with or without links.
assert.equal(merge([{name:'A',profile_url:link}],[{name:'B',profile_url:link+'-other'}]).length,2);
assert.equal(merge([{name:'A',company:'X',title:'HR'}],[{name:'A',company:'X',title:'HR'},{name:'A',company:'Y',title:'HR'}]).length,2,'rows without email or link still match on name, company and title only');
assert.equal(merge([{}],[{name:''}]).length,0,'empty rows are ignored');
// Email-search cost is added to the running total and each run is recorded once.
assert.match(source,/_leadCosts\.email_usd = \(Number\(_leadCosts\.email_usd\) \|\| 0\) \+ emailRunCost;/);
assert.match(source,/statsRecord\('Lead Finder Email Search', 'lead', emailRunCost \|\| 0,/);
assert(!/statsRecord\('Lead Finder Email Search', 'lead', _leadCosts\.email_usd/.test(source),'the cumulative total is never recorded as one run');
console.log('Lead Finder merge and email cost passed.');

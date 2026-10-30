/* Real broker parser; fictional profiles, accounts and addresses only. */
const assert=require('assert/strict'),path=require('path');
const {pathToFileURL}=require('url');
(async()=>{
 const {emailResult}=await import(pathToFileURL(path.join(__dirname,'../integrations/apollo-broker/worker.mjs')));
 const expected={url:'https://www.linkedin.com/in/sample-person',name:'Sample Person',company:'Example Company',company_url:'https://www.linkedin.com/company/example/',company_id:'123'};
 const person={id:'fictional-person',organization_id:'fictional-org',linkedin_url:expected.url,organization:{name:expected.company,linkedin_url:expected.company_url},email:null};
 const contact={id:'fictional-contact',person_id:person.id,organization_id:person.organization_id,email:'person@example.test',email_status:'verified'};
 const read=patch=>emailResult({match_confidence:'high',person:{...person,...patch}},expected);
 const saved=read({contact});
 assert.equal(saved.state,'found','a matched saved-contact email must not be discarded when the primary person email is empty');
 assert.equal(saved.email,contact.email);assert.equal(saved.email_status,'verified');assert.equal(saved.email_source,'saved_contact');
 assert.equal(read({email:'primary@example.test',email_status:'catch_all',contact}).email,'primary@example.test','a returned primary business email remains authoritative');
 for(const bad of [{...contact,person_id:'someone-else'},{...contact,linkedin_url:'https://www.linkedin.com/in/other'},
   {...contact,organization:{name:'Another Company'}},{...contact,person_id:undefined},
   {...contact,organization_id:'previous-employer'},{...contact,organization_id:undefined}])
  assert.notEqual(read({contact:bad}).state,'found','an unbound or conflicting contact never lends its address');
 assert.equal(read({contact:{...contact,person_id:undefined,linkedin_url:'http://www.linkedin.com/in/Sample-Person/'}}).state,'found');
 assert.equal(read({email:'email_not_unlocked@domain.com'}).state,'not_found','an Apollo redaction placeholder is not a deliverable email');
 assert.equal(read({email:'email_not_unlocked@domain.com',contact}).email,contact.email,'a positively matched real contact can replace a placeholder');
 // A business domain sharing a provider's brand is not that mail provider.
 assert.equal(read({email:'person@proton.com',email_status:'verified'}).state,'found');
 assert.equal(read({contact:{...contact,email:'person@proton.com'}}).state,'found');
 for(const domain of ['proton.me','protonmail.com','protonmail.ch','pm.me'])
  assert.equal(read({email:'person@'+domain}).reason,'personal_email_only','actual Proton Mail domains stay excluded');
 assert.equal(read({email:'person@PROTON.COM'}).state,'found');
 for(const brand of ['gmail','googlemail','yahoo','hotmail','outlook','live','aol','icloud','mail','gmx']) {
  assert.equal(read({email:'person@'+brand+'.example'}).state,'found','a provider-like corporate brand must not be excluded');
  assert.equal(read({email:'person@'+brand+'.com'}).reason,'personal_email_only');
 }
 assert.equal(read({email:'person@company-outlook.com'}).state,'found');
 assert.equal(read({email:'person@outlook.com.example'}).state,'found');

 assert.equal(read({contact:{...contact,email:'person@gmail.com'}}).reason,'personal_email_only');
 assert.equal(read({contact:{...contact,email:'bad address'}}).reason,'email_unusable');
 assert.equal(read({}).reason,'email_not_returned');
 assert.equal(emailResult({person:null,match_confidence:'none'},expected).reason,'profile_not_found');
 for(const malformed of [null,[],{}, {error:'private detail'}, {person:[]},{person:'broken'}])
  assert.equal(emailResult(malformed,expected).state,'unconfirmed','a malformed successful response is not proof that no email exists');
 assert.equal(read({match_confidence:'low',contact}).state,'mismatch','person-level confidence is enforced too');
 console.log('Apollo result shapes: bound saved-contact fallback, primary precedence, identity/company conflicts, redaction/personal exclusions and malformed/unknown outcomes passed.');
})().catch(error=>{console.error(error);process.exitCode=1});

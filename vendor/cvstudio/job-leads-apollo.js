/* Per-account Apollo controls for saved HR cards. No tokens or emails in browser storage. */
(function () {
  'use strict';
  const el=name=>document.getElementById('jobLeadsApollo'+name);
  let ready=false, account={available:false,connected:false}, row=null, rowKey='', sequence=0;
  let working=false, appBusy=false, polling=false, pollGeneration=0, cache={}, views=[];
  const statusLabels={verified:'Verified by Apollo',unverified:'Unverified by Apollo',catch_all:'Catch-all · reported by Apollo',unavailable:'Unavailable',user_managed:'User-managed in Apollo',unknown:'Status not provided by Apollo'};
  async function api(body) {
    const response=await fetch('/apollo',body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),timeout:30000}:{cache:'no-store'});
    const data=await response.json();
    if(!response.ok || !data.ok) throw Error(data.error || 'Apollo could not complete this action.');
    return data;
  }
  function text(tag,value,cls) {const n=document.createElement(tag);n.textContent=value;if(cls)n.className=cls;return n;}
  function message(value) {el('Message').textContent=value;}
  function controls() {
    if(!ready) return;
    el('State').textContent=account.connected?'Connected as '+account.name:account.available?'Use your own Apollo account and credits':'Apollo connection needs owner setup';
    el('Connect').hidden=account.connected;
    el('Connect').disabled=working || appBusy || !account.available;
    el('Connect').textContent=account.connecting?'Continue sign-in':'Connect Apollo';
    el('Disconnect').hidden=!account.connected && !account.connecting;
    el('Disconnect').disabled=working || appBusy;
    el('Disconnect').textContent=account.connecting?'Cancel sign-in':'Disconnect';
    for(const view of views) {
      const result=cache[view.person.url], found=result?.state==='found';
      window.cvStudioEmailVerifier?.forCard(view.card)?.suggest(found?result.email:'');
      view.result.replaceChildren();
      if(found) {
        view.result.append(text('span',result.email,'job-leads-apollo-email'),text('small',statusLabels[result.email_status] || statusLabels.unknown,'job-leads-muted'));
      } else if(result) view.result.append(text('small',result.message,'job-leads-muted'));
      view.button.hidden=!!result && !['pending','unconfirmed'].includes(result.state);
      view.button.textContent=result?'Check lookup':'Unlock email';
      view.button.disabled=working || appBusy || !account.connected || !view.saved;
      view.copy.hidden=!found;view.copy.disabled=working;
    }
  }
  async function refreshEmails(current, token) {
    if(!current?.hr || !account.connected) return;
    try {
      const data=await api({action:'emails',id:current.id,revision:current.revision});
      if(token===sequence) {cache=data.emails || {};controls();}
    } catch(error) {if(token===sequence) message(error.message);}
  }
  async function poll(generation) {
    if(polling) return;
    polling=true;
    try {
      for(let attempt=0;attempt<300 && generation===pollGeneration;attempt++) {
        const result=await api({action:'poll'});
        if(generation!==pollGeneration) return;
        if(result.connected) {
          account={...account,connected:true,connecting:false,name:result.name};cache={};
          el('Continue').hidden=true;message('Apollo connected. Choose Unlock email on a saved HR card.');
          await refreshEmails(row,sequence);controls();return;
        }
        await new Promise(resolve=>setTimeout(resolve,2000));
      }
      if(generation===pollGeneration) message('Sign-in is still waiting. Continue sign-in or cancel and connect again.');
    } catch(error) {if(generation===pollGeneration) {account.connecting=false;message(error.message);controls();}}
    finally {polling=false;if(account.connecting && generation!==pollGeneration) void poll(pollGeneration);}
  }
  async function connect() {
    if(working || appBusy || !account.available) return;
    // Open from the click itself, so the asynchronous response does not lose
    // the browser's popup permission. The visible link is a fallback.
    const popup=window.open('about:blank','_blank');if(popup) popup.opener=null;
    working=true;controls();
    try {
      const data=await api({action:'connect'});
      account.connecting=true;el('Continue').href=data.authorization_url;el('Continue').hidden=false;
      if(popup) popup.location.href=data.authorization_url;
      message('Sign in with Apollo in the new tab, then return here. Your Apollo password stays with Apollo.');
      const generation=polling?pollGeneration:++pollGeneration;
      // An old polling loop exits before another one starts.
      if(!polling) void poll(generation);
    } catch(error) {popup?.close();message(error.message);}
    finally {working=false;controls();}
  }
  async function disconnect() {
    if(working || appBusy) return;
    if(account.connected && !window.confirm('Disconnect this Apollo account and clear its revealed emails from this device? Saved job ads and HR profiles stay.')) return;
    working=true;++pollGeneration;controls();
    try {
      const data=await api({action:'disconnect'});
      account={...account,connected:false,connecting:false,name:''};cache={};el('Continue').hidden=true;
      message(data.warning || 'Apollo disconnected. Saved job ads and HR profiles were kept.');
    } catch(error) {message(error.message);}
    finally {working=false;controls();}
  }
  async function unlock(person) {
    if(working || appBusy || !account.connected || !row) return;
    const current=row, token=sequence, previous=cache[person.url];
    if(!previous && !window.confirm('Unlock the business email for '+person.name+' using your Apollo account? This sends their LinkedIn profile, name and company to Apollo and may use an Apollo credit even if only profile data is returned.')) return;
    working=true;message(previous?'Checking the previous lookup without spending another credit…':'Looking up this person in Apollo…');controls();
    try {
      const data=await api({action:'reveal',id:current.id,revision:current.revision,url:person.url,confirmed:!previous});
      if(token===sequence) {cache[person.url]=data.result;message(data.result.message);}
    } catch(error) {
      if(token===sequence) {
        // The response may have been lost after charging/saving. A follow-up
        // reads the protected record; it never sends another paid operation.
        cache[person.url]={state:'unconfirmed',message:'The result could not be confirmed. Check the previous lookup before trying again.'};
        message(error.message);await refreshEmails(current,token);
      }
    } finally {working=false;controls();}
  }
  window.cvStudioApollo={
    async init() {
      if(ready) return;ready=true;
      el('Connect').addEventListener('click',connect);el('Disconnect').addEventListener('click',disconnect);
      window.addEventListener('pagehide',()=>{++pollGeneration;account.connecting=false;});
      try {
        account=await api();
        if(!account.available) message('Your CV Studio owner needs to finish the one-time Apollo sign-in setup.');
        await refreshEmails(row,sequence);
        if(account.connecting) void poll(++pollGeneration);
      } catch(error) {message(error.message);}
      controls();
    },
    busy(value) {appBusy=value;controls();},
    begin(current) {
      row=current || null;views=[];
      const key=row?.hr?row.id+'|'+row.revision:'';
      if(key!==rowKey) {rowKey=key;cache={};++sequence;if(ready) void refreshEmails(row,sequence);}
    },
    decorate(card,person) {
      if(!ready) return;
      const wrap=text('div','','job-leads-apollo-person'), result=text('div',''), button=text('button','Unlock email','sec'), copy=text('button','Copy email','sec');
      button.type=copy.type='button';copy.hidden=true;
      const saved=!!row?.hr?.people.some(p=>p.url===person.url);
      button.addEventListener('click',()=>unlock(person));
      copy.addEventListener('click',async()=>{try {await navigator.clipboard.writeText(cache[person.url].email);message('Email copied.');}catch{message('Select the email address and copy it manually.');}});
      wrap.append(result,button,copy);card.append(wrap);views.push({card,person,result,button,copy,saved});controls();
    }
  };
})();

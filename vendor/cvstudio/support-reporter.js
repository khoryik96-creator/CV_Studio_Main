/* Independent support capture. No AI key, automatic email or CV-file access. */
(function(){
  'use strict';
  const el=name=>document.getElementById('cvSupport'+name);
  let initialized=false,busy=false,phase='edit',prepared=null,screenshot='',sequence=0,blocked=false;
  const recent=[];
  const API='/diagnostics/support_bundle';
  function clean(value){
    return String(value || '').replace(/\bsk-(?:ant-api\d+-|proj-)?[A-Za-z0-9_-]{10,}/g,'[key redacted]')
      .replace(/\bBearer\s+[A-Za-z0-9._~+\/-]+=*/gi,'Bearer [redacted]')
      .replace(/((?:access_token|refresh_token|client_secret|api_key|password|authorization_code)\s*["']?\s*[:=]\s*)["']?[^\s,;}"']+/gi,'$1[redacted]')
      .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g,'[email redacted]')
      .replace(/\b[A-Za-z0-9_-]{48,}\b/g,'[token redacted]')
      .replace(/https?:\/\/[^\s?#"'<>]+\?[^\s"'<>]*/gi,value=>value.split('?')[0]+'?[query redacted]')
      .replace(/\b[A-Z]:\\Users\\[^\r\n]+/gi,'[home path redacted]')
      .replace(/\/(?:Users|home)\/[^/\s]+(?:\/[^\s]*)?/g,'[home path redacted]');
  }
  const moduleName=()=>String(document.querySelector('.page-tab.active .tab-label')?.textContent || document.querySelector('.page-view.active')?.id?.replace(/^view/,'') || 'General').trim().slice(0,80);
  function doctor(){
    try{return clean(window.cvDoctor?.supportReport?.() || window.cvDoctor?.report?.() || 'Doctor recorder is unavailable.').slice(0,150000);}
    catch{return 'Doctor report could not be collected. Browser diagnostic recorder is unavailable.';}
  }
  function recordIssue(value={}){
    const item={at:new Date().toISOString()};
    for(const name of ['module','operation','code','request_id','http_status','result_reason'])item[name]=clean(value[name] ?? '').slice(0,160);
    recent.push(item);while(recent.length>20)recent.shift();
    if(el('Badge'))el('Badge').textContent='Report issue'+(recent.length?' · '+recent.length:'');
  }
  async function api(action,body={},binary=false){
    const response=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json','X-CV-Studio-Request':'1'},body:JSON.stringify({action:'issue_'+action,...body}),cache:'no-store'});
    if(binary && response.ok)return response.blob();
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw Object.assign(Error(data.error || 'The support action could not be completed.'),{data,status:response.status});
    return data;
  }
  const ticket=()=>({report_id:prepared?.report_id,preview_token:prepared?.preview_token});
  function note(value){el('Message').textContent=value;}
  function controls(){
    if(!initialized)return;
    const editing=phase==='edit';
    for(const name of ['Module','Title','Description','Steps','Capture','Attach','Remove'])el(name).disabled=busy || !editing;
    el('Close').disabled=busy;el('Review').disabled=busy;el('Review').hidden=!editing;
    el('Form').hidden=!editing;el('Preview').hidden=editing;
    el('Send').hidden=phase!=='review';el('Send').disabled=busy || blocked || !prepared?.delivery?.can_send;
    el('Edit').hidden=editing || !['review'].includes(phase);el('Edit').disabled=busy;
    el('Download').disabled=busy || !prepared;el('SaveDoctor').disabled=busy;
    el('Check').hidden=!['sending','unconfirmed'].includes(phase);el('Check').disabled=busy;
    el('New').hidden=!['accepted','rejected','unconfirmed'].includes(phase);el('New').disabled=busy;
    el('Connect').hidden=!!prepared?.delivery?.can_send && !blocked;el('Connect').disabled=busy;
    el('Screenshot').hidden=!screenshot;el('Screenshot').src=screenshot || '';
    el('Remove').hidden=!screenshot;
  }
  function showDelivery(data){
    el('Recipient').textContent=data.recipient || 'Support inbox is not configured';
    el('Sender').textContent=data.sender || 'Connect Outlook to send';
  }
  function preview(data){
    showDelivery(data.delivery || {});el('Text').textContent=data.text || '';
    el('Doctor').textContent=data.doctor || '';el('Runtime').textContent=JSON.stringify(data.runtime || {},null,2);
    el('Attachments').textContent=(data.attachments || []).map(file=>file.name+' · '+Math.ceil(file.bytes/1024)+' KB').join(' · ');
    const image=el('PreviewImage'),source=data.screenshot || '';
    image.hidden=!/^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(source);image.src=image.hidden?'':source;
  }
  function discard(){
    if(prepared){const prior=ticket();prepared=null;void api('discard',prior).catch(()=>{});}
    blocked=false;
  }
  async function review(){
    if(busy || phase!=='edit')return;
    if(!el('Description').value.trim()){note('Describe what happened first.');el('Description').focus();return;}
    busy=true;const token=++sequence;controls();note('Collecting Doctor and runtime diagnostics…');
    try{
      let timezone='';try{timezone=Intl.DateTimeFormat().resolvedOptions().timeZone || '';}catch{}
      const data=await api('prepare',{module:el('Module').value,title:el('Title').value || 'Issue report',description:el('Description').value,
        steps:el('Steps').value,doctor:doctor(),screenshot,browser:{user_agent:navigator.userAgent,timezone,active_view:moduleName()},recent_issues:recent.slice(-20)});
      if(token!==sequence)return;
      prepared=data;blocked=false;phase='review';preview(data);
      note(data.delivery?.can_send?'Review the report and screenshot, then send.':'Report prepared. Connect Outlook and enable sending, or download the report.');
    }catch(error){if(token===sequence)note(error.message+' You can still save the Doctor report.');}
    finally{if(token===sequence){busy=false;controls();}}
  }
  async function send(){
    if(busy || phase!=='review' || !prepared?.delivery?.can_send || blocked)return;
    if(!window.confirm('Send this issue report to '+prepared.delivery.recipient+' from '+prepared.delivery.sender+'?\n\nIt includes the reviewed diagnostics'+(prepared.screenshot?' and screenshot':'')+'.'))return;
    busy=true;phase='sending';controls();note('Sending the issue report through Outlook…');
    try{
      const result=await api('send',{...ticket(),confirmed:true});
      phase=result.state==='accepted'?'accepted':'unconfirmed';note(phase==='accepted'?'Outlook accepted your issue report.':'The send result is not confirmed. Check the report status or Outlook Sent Items.');
    }catch(error){
      if(error.data?.retry_safe){phase='review';blocked=true;note(error.message);}
      else{phase=error.data?.state==='rejected'?'rejected':'unconfirmed';note(error.message+' No send will be repeated automatically.');}
    }finally{busy=false;controls();}
  }
  async function check(){
    if(busy || !prepared)return;busy=true;controls();
    try{const result=await api('result',ticket());phase=result.state==='accepted'?'accepted':result.state==='rejected'?'rejected':'unconfirmed';note(phase==='accepted'?'Outlook accepted your issue report.':result.error || 'Delivery is not confirmed. Check Outlook Sent Items before starting another report.');}
    catch(error){note(error.message);}
    finally{busy=false;controls();}
  }
  function save(blob,name){const url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=name;document.body.appendChild(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  async function download(){
    if(busy || !prepared)return;busy=true;controls();
    try{save(await api('download',ticket(),true),'cv-studio-issue-'+prepared.report_id.slice(0,12)+'.zip');note('Report downloaded. No email was sent.');}
    catch(error){note(error.message+' You can still save the Doctor report.');}
    finally{busy=false;controls();}
  }
  function saveDoctor(){
    save(new Blob(['CV Studio issue\nModule: '+clean(el('Module').value)+'\n\n'+clean(el('Description').value)+'\n\n'+doctor()],{type:'text/plain;charset=utf-8'}),'cv-studio-doctor-report.txt');note('Doctor report saved. No email was sent.');
  }
  function setScreenshot(value){discard();phase='edit';screenshot=value;controls();note('Screenshot attached. Review it before sending.');}
  function imageData(image){
    if(image.width*image.height>12000000)throw Error('Use a screenshot with fewer than 12 million pixels.');
    const scale=Math.min(1,1600/Math.max(image.width,image.height)),canvas=document.createElement('canvas');
    canvas.width=Math.max(1,Math.round(image.width*scale));canvas.height=Math.max(1,Math.round(image.height*scale));
    const context=canvas.getContext('2d');context.fillStyle='white';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(image,0,0,canvas.width,canvas.height);
    const value=canvas.toDataURL('image/jpeg',.85);if(value.length>2700000)throw Error('Use a smaller screenshot.');return value;
  }
  async function attach(file){
    if(busy || phase!=='edit' || !file)return;
    if(!['image/png','image/jpeg'].includes(file.type) || file.size>6000000){note('Attach a PNG or JPEG screenshot up to 6 MB.');return;}
    busy=true;controls();let url='';
    try{
      url=URL.createObjectURL(file);const image=new Image();image.src=url;
      await image.decode();setScreenshot(imageData(image));
    }catch(error){note(error.message || 'The screenshot could not be opened.');}
    finally{if(url)URL.revokeObjectURL(url);busy=false;el('File').value='';controls();}
  }
  async function capture(){
    if(busy || phase!=='edit')return;
    if(!navigator.mediaDevices?.getDisplayMedia){note('Screen capture is unavailable in this browser. Attach or paste a screenshot instead.');return;}
    busy=true;controls();let stream=null,video=null,timer=null;
    el('Dialog').close();
    try{
      stream=await navigator.mediaDevices.getDisplayMedia({video:{displaySurface:'browser'},audio:false,preferCurrentTab:true,selfBrowserSurface:'include'});
      video=document.createElement('video');video.muted=true;video.playsInline=true;video.srcObject=stream;
      await Promise.race([video.play(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Screen capture did not finish. Attach a screenshot instead.')),10000);})]);
      await new Promise(resolve=>setTimeout(resolve,180));
      if(!video.videoWidth || !video.videoHeight)throw Error('No screen image was available. Attach a screenshot instead.');
      const canvas=document.createElement('canvas'),scale=Math.min(1,1600/Math.max(video.videoWidth,video.videoHeight));canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
      canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);setScreenshot(canvas.toDataURL('image/jpeg',.85));
    }catch(error){note(error.name==='NotAllowedError'?'Capture cancelled. You can attach or paste a screenshot.':error.message || 'Screen capture failed. Attach a screenshot instead.');}
    finally{
      if(timer)clearTimeout(timer);if(stream)for(const track of stream.getTracks())track.stop();if(video)video.srcObject=null;
      busy=false;el('Dialog').showModal();controls();
    }
  }
  function edit(){if(busy)return;discard();phase='edit';++sequence;controls();note('Update the report, then review it again.');}
  function fresh(){
    if(busy)return;
    if(phase==='unconfirmed' && !window.confirm('Check Outlook Sent Items first: the previous report may have been sent. Start a new report?'))return;
    discard();phase='edit';++sequence;controls();note('Review the updated details before sending a new report.');
  }
  function connect(event){
    event?.stopPropagation?.();
    if(busy)return;
    if(document.getElementById('jobLeadsJAClose')?.disabled){note('Wait for the current contact request, then connect Outlook. You can still download this report.');return;}
    edit();el('Dialog').close();
    try{for(const dialog of document.querySelectorAll('dialog[open]'))dialog.close();if(document.getElementById('settingsPanel')?.style.display!=='block')window.toggleSettings?.();window.showSettingsTab?.('integrations');}
    catch{}
  }
  function init(){
    if(initialized)return;initialized=true;
    const badge=document.createElement('button');badge.id='cvSupportBadge';badge.type='button';badge.className='cv-support-badge';badge.textContent='Report issue';badge.addEventListener('click',open);document.body.appendChild(badge);
    const dialog=document.createElement('dialog');dialog.id='cvSupportDialog';dialog.setAttribute('aria-labelledby','cvSupportHeading');
    dialog.innerHTML='<div class="cv-support-head"><h2 id="cvSupportHeading">Report an issue</h2><button type="button" class="sec" id="cvSupportClose">Close</button></div>'+
      '<p class="job-leads-muted">To: <strong id="cvSupportRecipient"></strong><br>From: <span id="cvSupportSender">Connect Outlook to send</span></p>'+
      '<div id="cvSupportForm"><label>Module<input id="cvSupportModule" maxlength="80"></label><label>Issue title<input id="cvSupportTitle" maxlength="160" value="Issue report"></label>'+
      '<label>What happened?<textarea id="cvSupportDescription" rows="4" maxlength="4000"></textarea></label><label>Steps to reproduce (optional)<textarea id="cvSupportSteps" rows="3" maxlength="4000"></textarea></label>'+
      '<div class="cv-support-actions"><button type="button" class="sec" id="cvSupportCapture">Capture screenshot</button><button type="button" class="sec" id="cvSupportAttach">Attach screenshot</button><button type="button" class="sec" id="cvSupportRemove" hidden>Remove screenshot</button></div>'+
      '<input type="file" id="cvSupportFile" accept="image/png,image/jpeg" hidden><p class="job-leads-muted">Choose the CV Studio tab when capturing. You can also paste a screenshot. Review candidate details before sharing.</p><img id="cvSupportScreenshot" alt="Screenshot to review" hidden></div>'+
      '<div id="cvSupportPreview" hidden><pre id="cvSupportText"></pre><p id="cvSupportAttachments" class="job-leads-muted"></p><img id="cvSupportPreviewImage" alt="Screenshot included in the report" hidden><details><summary>Doctor report (redacted)</summary><pre id="cvSupportDoctor"></pre></details><details><summary>Runtime diagnostics</summary><pre id="cvSupportRuntime"></pre></details></div>'+
      '<p id="cvSupportMessage" role="status" aria-live="polite"></p><div class="cv-support-actions"><button type="button" class="primary" id="cvSupportReview">Prepare and review</button><button type="button" class="primary" id="cvSupportSend" hidden>Send report</button><button type="button" class="sec" id="cvSupportEdit" hidden>Edit report</button><button type="button" class="sec" id="cvSupportCheck" hidden>Check send status</button><button type="button" class="sec" id="cvSupportNew" hidden>Edit as new report</button><button type="button" class="sec" id="cvSupportConnect">Connect / enable Outlook</button><button type="button" class="sec" id="cvSupportDownload" disabled>Download report</button><button type="button" class="sec" id="cvSupportSaveDoctor">Save Doctor report</button></div>';
    document.body.appendChild(dialog);
    for(const [name,handler] of Object.entries({Review:review,Send:send,Edit:edit,Check:check,New:fresh,Connect:connect,Download:download,SaveDoctor:saveDoctor,Capture:capture,Attach:()=>el('File').click(),Remove:()=>setScreenshot(''),Close:()=>{if(!busy)dialog.close();}}))el(name).addEventListener('click',handler);
    dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
    el('File').addEventListener('change',()=>attach(el('File').files?.[0]));
    dialog.addEventListener('paste',event=>{if(phase!=='edit' || busy)return;const item=Array.from(event.clipboardData?.items || []).find(value=>['image/png','image/jpeg'].includes(value.type));if(item){event.preventDefault();void attach(item.getAsFile());}});
    document.addEventListener('click',event=>{if(event.target?.closest?.('[data-cv-support]'))open();});
    controls();if(recent.length)badge.textContent='Report issue · '+recent.length;
  }
  async function open(){
    init();if(busy)return;if(!el('Module').value)el('Module').value=moduleName();
    if(!el('Dialog').open)el('Dialog').showModal();controls();
    try{const data=await api('status');if(phase==='edit')showDelivery(data);}
    catch{note('Support connection unavailable. You can still save the Doctor report.');}
  }
  window.cvStudioSupport={open,recordIssue,doctorReport:doctor};
  window.addEventListener('error',()=>recordIssue({module:moduleName(),operation:'Browser script',code:'BROWSER_ERROR'}));
  window.addEventListener('unhandledrejection',()=>recordIssue({module:moduleName(),operation:'Browser task',code:'UNHANDLED_PROMISE'}));
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();

(() => {
  if (window.top !== window) return;
  if (location.origin === 'https://www.linkedin.com') {
    if (!location.pathname.startsWith('/jobs/') || globalThis.cvstudioJobButtons) return;
    globalThis.cvstudioJobButtons = true;
    let timer;
    const scan = () => {
      if (document.hidden) return;
      let targets;
      try { targets = globalThis.SourcerReader.jobTargets(); } catch { return; }
      for (const {element,url,floating} of targets) {
        const previous = element.querySelector('[data-cvstudio-job-controls]');
        if (previous?.dataset.url === url) continue;
        previous?.remove();
        const controls = document.createElement('div'), button = document.createElement('button'), note = document.createElement('span');
        controls.dataset.cvstudioJobControls = '1'; controls.dataset.url = url;
        controls.style.cssText = floating ? 'position:fixed;bottom:28px;left:24px;z-index:1000;background:white;padding:12px;border:1px solid #ccc;border-radius:8px;max-width:320px' : 'padding:8px 0;display:flex;gap:8px;align-items:center;flex-wrap:wrap';
        button.type = 'button'; button.textContent = 'Add to CV Studio';
        button.style.cssText = 'background:#087c83;color:white;border:0;border-radius:6px;padding:7px 12px;font:600 13px Arial;cursor:pointer';
        note.style.cssText = 'font:12px Arial;color:#444'; note.setAttribute('role','status');
        for (const type of ['mousedown','pointerdown']) controls.addEventListener(type,event => event.stopPropagation());
        button.addEventListener('click',event => {
          event.preventDefault(); event.stopPropagation();
          if (!event.isTrusted || button.disabled || controls.dataset.url !== url) return;
          button.disabled = true; button.textContent = 'Adding…'; note.textContent = '';
          try {
            chrome.runtime.sendMessage({kind:'sourcer_job_pick',url},reply => {
              const error = chrome.runtime.lastError;
              if (error || reply?.error || !reply?.result?.ok) {
                button.disabled = false; button.textContent = 'Add to CV Studio';
                note.textContent = reply?.error || 'Reload this LinkedIn page and reconnect CV Studio.';
              } else {
                button.textContent = reply.result.duplicate ? 'Already saved' : 'Added';
                note.textContent = 'CV Studio · ' + (reply.result.folder || 'Unfiled');
              }
            });
          } catch {
            button.disabled = false; button.textContent = 'Add to CV Studio'; note.textContent = 'Reload this LinkedIn page and reconnect CV Studio.';
          }
        });
        controls.append(button,note); element.appendChild(controls);
      }
    };
    const schedule = () => { clearTimeout(timer); timer = setTimeout(scan,300); };
    new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true});
    document.addEventListener('visibilitychange',schedule); scan(); return;
  }
  if (location.pathname !== '/' || window.top !== window) return;
  const captures = new Map();
  chrome.runtime.onMessage.addListener((message,sender,reply) => {
    if (sender.id !== chrome.runtime.id || message?.type !== 'CVSTUDIO_JOB_CAPTURE' || !/^[a-f0-9]{32}$/.test(message.id || '')) return false;
    const channel = document.getElementById('viewJobLeads')?.dataset.companionChannel;
    if (!/^[a-f0-9]{32}$/.test(channel || '') || captures.size) { reply({error:'Open Job Leads in this CV Studio tab and wait for the current action to finish.'}); return false; }
    const timer = setTimeout(() => { captures.delete(message.id); reply({error:'CV Studio did not confirm the save. Check its saved list before adding the ad again.'}); },12000);
    captures.set(message.id,{channel,reply,timer});
    window.postMessage({type:'CVSTUDIO_LINKEDIN_CAPTURE',id:message.id,channel,record:message.record},location.origin);
    return true;
  });
  window.addEventListener('message', event => {
    const message = event.data;
    if (event.source === window && event.origin === location.origin && message?.type === 'CVSTUDIO_LINKEDIN_CAPTURE_RESULT') {
      const capture = captures.get(message.id);
      if (!capture || capture.channel !== message.channel) return;
      clearTimeout(capture.timer); captures.delete(message.id); capture.reply(message.result); return;
    }
    if (event.source !== window || event.origin !== location.origin || !message ||
        message.type !== 'CVSTUDIO_LINKEDIN_REQUEST' || !/^[a-f0-9]{32}$/.test(message.channel || '') ||
        !/^[a-f0-9]{32}$/.test(message.id || '')) return;
    chrome.runtime.sendMessage({kind: 'sourcer', action: message.action, args: message.args}, reply => {
      const error = chrome.runtime.lastError;
      window.postMessage({type: 'CVSTUDIO_LINKEDIN_RESPONSE', channel: message.channel, id: message.id,
                          ...(error ? {error: 'Reconnect the browser companion from its toolbar icon.'} : reply)}, location.origin);
    });
  });
})();

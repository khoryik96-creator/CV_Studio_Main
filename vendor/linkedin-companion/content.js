(() => {
  if (window.top !== window) return;
  if (location.origin === 'https://www.linkedin.com') {
    if (!location.pathname.startsWith('/jobs/') || globalThis.cvstudioJobButtons) return;
    globalThis.cvstudioJobButtons = true;
    let timer, preferredFolder;
    const mountFor = (element, floating) => {
      if (floating) return element;
      const fields = [...element.querySelectorAll('p')].slice(0,2);
      const column = candidate => {
        const style = getComputedStyle(candidate);
        return !['flex','inline-flex','grid','inline-grid'].includes(style.display) ||
          ['flex','inline-flex'].includes(style.display) && style.flexDirection === 'column';
      };
      for (let candidate=fields[0]?.parentElement;candidate && element.contains(candidate);candidate=candidate.parentElement) {
        if (fields.every(field => candidate.contains(field)) && column(candidate)) return candidate;
      }
      return column(element) ? element : null;
    };
    const send = message => new Promise((resolve,reject) => {
      try { chrome.runtime.sendMessage(message,reply => {
        const error = chrome.runtime.lastError;
        if (error || reply?.error || !reply?.result?.ok) reject(Error(reply?.error || 'Reload this LinkedIn page and reconnect CV Studio.'));
        else resolve(reply.result);
      }); } catch { reject(Error('Reload this LinkedIn page and reconnect CV Studio.')); }
    });
    const scan = () => {
      if (document.hidden) return;
      let targets;
      try { targets = globalThis.SourcerReader.jobTargets(); } catch { return; }
      for (const {element,url,floating} of targets) {
        const previous = element.querySelector('[data-cvstudio-job-controls]');
        if (previous?.dataset.url === url) continue;
        previous?.remove();
        const mount = mountFor(element,floating); if (!mount) continue;
        const controls = document.createElement('div'), button = document.createElement('button'), note = document.createElement('span');
        const folders = document.createElement('select'), create = document.createElement('button'), editor = document.createElement('div');
        const name = document.createElement('input'), saveFolder = document.createElement('button');
        let added = false, foldersLoaded = false, working = false;
        controls.dataset.cvstudioJobControls = '1'; controls.dataset.url = url;
        controls.style.cssText = (floating ? 'position:fixed;bottom:28px;left:24px;z-index:1000;background:white;padding:12px;border:1px solid #ccc;border-radius:8px;' : 'padding:8px 0;') + 'display:flex;gap:8px;align-items:center;flex-wrap:wrap;min-width:0;width:100%;contain:inline-size;white-space:normal;max-width:'+(floating?'min(320px,calc(100vw - 48px))':'100%')+';box-sizing:border-box';
        button.type = 'button'; button.textContent = 'Add to CV Studio';
        button.style.cssText = 'background:#087c83;color:white;border:0;border-radius:6px;padding:7px 12px;font:600 13px Arial;cursor:pointer;min-width:0;max-width:100%;white-space:normal;overflow-wrap:anywhere';
        folders.setAttribute('aria-label','Save to CV Studio folder'); folders.dataset.cvstudioJobFolder = '1';
        folders.style.cssText = 'width:170px;max-width:100%;min-width:0;font:13px Arial;padding:5px;box-sizing:border-box';
        const option = (text,value) => { const el=document.createElement('option');el.textContent=text;el.value=value;return el; };
        const choose = value => {
          preferredFolder=value;
          for (const select of document.querySelectorAll('[data-cvstudio-job-folder]')) {
            if (![...select.querySelectorAll('option')].some(item=>item.value===value)) select.append(option(value || 'Unfiled',value));
            select.value=value;
          }
        };
        folders.append(option(preferredFolder === undefined ? 'CV Studio folder' : preferredFolder || 'Unfiled',preferredFolder || ''));
        create.type='button';create.textContent='New folder';create.style.cssText='font:13px Arial;padding:5px;min-width:0;max-width:100%;white-space:normal';
        editor.hidden=true;editor.style.cssText='flex-basis:100%;min-width:0';
        name.setAttribute('aria-label','New folder name');name.maxLength=80;name.style.cssText='width:170px;max-width:100%;min-width:0;font:13px Arial;box-sizing:border-box';
        saveFolder.type='button';saveFolder.textContent='Create';editor.append(name,saveFolder);
        note.style.cssText = 'font:12px Arial;color:#444;flex-basis:100%;min-width:0;max-width:100%;white-space:normal;overflow-wrap:anywhere'; note.setAttribute('role','status');
        const display = () => { button.textContent=added?'Added — click to remove':'Add to CV Studio';button.setAttribute('aria-pressed',String(added)); };
        const populate = result => {
          folders.replaceChildren(option('Unfiled',''),...(result.folders || []).map(value=>option(value,value)));
          folders.value = preferredFolder !== undefined && ['',...(result.folders || [])].includes(preferredFolder) ? preferredFolder : result.folder || '';
          foldersLoaded = true;
        };
        const action = async (operation,folder) => {
          if (working) return;
          working=true;button.disabled=true;create.disabled=true;saveFolder.disabled=true;folders.disabled=operation!=='folders';note.textContent='';
          try {
            const result=await send({kind:'sourcer_job_pick',url,operation,...(folder===undefined?{}:{folder})});
            if (result.folders) populate(result);
            if (operation!=='create_folder') added=result.saved !== false;
            if (operation==='create_folder') { choose(result.folder);folders.value=result.folder;editor.hidden=true;name.value=''; }
            note.textContent=result.warning || (operation==='remove'?'Removed · recoverable in CV Studio Trash':operation==='create_folder'?'Folder created · '+result.folder:operation==='folders'?(added?'Already saved in '+(result.folder || 'Unfiled')+'. Click Added to remove.':'Choose a folder before adding.'):'CV Studio · '+(result.folder || 'Unfiled'));
          } catch (error) { note.textContent=error.message; }
          finally { working=false;button.disabled=false;create.disabled=false;saveFolder.disabled=false;folders.disabled=false;display(); }
        };
        for (const type of ['mousedown','pointerdown']) controls.addEventListener(type,event => event.stopPropagation());
        button.addEventListener('click',event => {
          event.preventDefault(); event.stopPropagation();
          if (!event.isTrusted || button.disabled || controls.dataset.url !== url) return;
          return action(added?'remove':'add',foldersLoaded?folders.value:preferredFolder);
        });
        folders.addEventListener('focus',event => { if(event.isTrusted && !foldersLoaded && !working) return action('folders'); });
        folders.addEventListener('change',event => { event.stopPropagation();if(event.isTrusted && foldersLoaded) choose(folders.value); });
        controls.addEventListener('click',event=>event.stopPropagation());
        create.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();if(event.isTrusted&&!working){editor.hidden=!editor.hidden;if(!editor.hidden)name.focus();}});
        saveFolder.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();if(event.isTrusted&&!working)return action('create_folder',name.value.trim());});
        controls.append(button,folders,create,editor,note); mount.appendChild(controls);
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
    if (message.request && (message.request.action !== 'add' || message.request.folder !== undefined) && document.getElementById('viewJobLeads')?.dataset.companionActions !== '1') {
      reply({error:'Update CV Studio and refresh its tab to use LinkedIn folders and remove controls.'}); return false;
    }
    if (!/^[a-f0-9]{32}$/.test(channel || '') || captures.size) { reply({error:'Open Job Leads in this CV Studio tab and wait for the current action to finish.'}); return false; }
    const timer = setTimeout(() => { captures.delete(message.id); reply({error:'CV Studio did not confirm the save. Check its saved list before adding the ad again.'}); },12000);
    captures.set(message.id,{channel,reply,timer});
    window.postMessage({type:'CVSTUDIO_LINKEDIN_CAPTURE',id:message.id,channel,record:message.record,request:message.request},location.origin);
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

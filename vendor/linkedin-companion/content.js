(() => {
  if (window.top !== window) return;
  if (location.origin === 'https://www.linkedin.com') {
    if (!location.pathname.startsWith('/jobs/') || globalThis.cvstudioJobButtons) return;
    globalThis.cvstudioJobButtons = true;
    let timer, preferredFolder, folderCatalog = null, folderRead = null, catalogAttempted = false, catalogError = '';
    const folderMenus = new Map();
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
    const publishFolders = names => {
      if (!Array.isArray(names) || names.some(name => typeof name !== 'string' || !name || name.length > 80)) throw Error('CV Studio did not return its folders. Try Refresh folders.');
      folderCatalog = [...new Set(names)];
      catalogError = '';
      if (preferredFolder && !folderCatalog.includes(preferredFolder)) preferredFolder = '';
      for (const [controls,menu] of folderMenus) {
        if (!document.body.contains(controls)) { folderMenus.delete(controls); continue; }
        menu.populate({folders:folderCatalog});
      }
    };
    const fetchFolders = url => new Promise((resolve,reject) => {
        const timeout = setTimeout(() => reject(Error('Folders did not finish loading. Try Refresh folders.')),12000);
        send({kind:'sourcer_job_pick',url,operation:'folders'}).then(resolve,reject).finally(() => clearTimeout(timeout));
    });
    const readFolders = url => {
      if (!folderRead) folderRead = fetchFolders(url).then(result => {
        publishFolders(result.folders); return {...result,sourceUrl:url};
      }).catch(error => {
        catalogError = error.message;
        for (const menu of folderMenus.values()) menu.fail(catalogError);
        throw error;
      }).finally(() => { folderRead = null; });
      return folderRead;
    };
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
        const refresh = document.createElement('button');
        let added = false, foldersLoaded = false, working = false, activeOperation = '';
        controls.dataset.cvstudioJobControls = '1'; controls.dataset.url = url;
        const controlStyle = 'min-height:34px;border:1px solid #bdd7db;border-radius:8px;padding:7px 10px;font:600 12px/18px Arial,sans-serif;box-sizing:border-box;min-width:0;max-width:100%;white-space:normal;overflow-wrap:anywhere;';
        controls.style.cssText = (floating ? 'position:fixed;bottom:28px;left:24px;z-index:1000;box-shadow:0 6px 24px #123b4426;' : 'margin:8px 0 2px;') + 'background:#f4f9fa;border:1px solid #dcebed;border-radius:12px;padding:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;min-width:0;width:100%;contain:inline-size;white-space:normal;max-width:'+(floating?'min(340px,calc(100vw - 48px))':'100%')+';box-sizing:border-box';
        button.type = 'button'; button.textContent = 'Add to CV Studio';
        button.style.cssText = controlStyle + 'background:#087c83;color:white;border-color:#087c83;cursor:pointer;';
        folders.setAttribute('aria-label','Save to CV Studio folder'); folders.dataset.cvstudioJobFolder = '1';
        folders.style.cssText = controlStyle + 'flex:1 1 145px;width:145px;background-color:white;color:#254c53;font-weight:400;padding-right:28px;appearance:none;background-image:linear-gradient(45deg,transparent 50%,#53747a 50%),linear-gradient(135deg,#53747a 50%,transparent 50%);background-position:calc(100% - 15px) 14px,calc(100% - 10px) 14px;background-size:5px 5px;background-repeat:no-repeat;cursor:pointer;white-space:nowrap;text-overflow:ellipsis;';
        const option = (text,value) => { const el=document.createElement('option');el.textContent=text;el.value=value;return el; };
        const choose = value => {
          preferredFolder=value;
          for (const select of document.querySelectorAll('[data-cvstudio-job-folder]')) {
            if (![...select.querySelectorAll('option')].some(item=>item.value===value)) select.append(option(value || 'Unfiled',value));
            select.value=value;
          }
        };
        folders.append(option('Loading folders…',''));folders.disabled=true;
        refresh.type='button';refresh.textContent='↻';refresh.title='Refresh folders';refresh.setAttribute('aria-label','Refresh folders');refresh.style.cssText=controlStyle+'background:white;color:#08747c;cursor:pointer;flex:0 0 34px;padding:7px;';
        create.type='button';create.textContent='+ New folder';create.style.cssText=controlStyle+'background:white;color:#08747c;cursor:pointer;order:1;';
        editor.hidden=true;editor.style.cssText='flex-basis:100%;min-width:0;order:2';
        name.setAttribute('aria-label','New folder name');name.maxLength=80;name.style.cssText=controlStyle+'width:170px;background:white;color:#254c53;font-weight:400;margin:0 6px 6px 0;vertical-align:top;';
        saveFolder.type='button';saveFolder.textContent='Create';saveFolder.style.cssText=controlStyle+'background:#087c83;border-color:#087c83;color:white;cursor:pointer;vertical-align:top;';editor.append(name,saveFolder);
        note.style.cssText = 'font:12px/17px Arial,sans-serif;color:#526b70;flex-basis:100%;min-width:0;max-width:100%;white-space:normal;overflow-wrap:anywhere;order:3'; note.setAttribute('role','status');
        const display = () => { button.textContent=added?'Added':'Add to CV Studio';button.title=added?'Click to remove from CV Studio':'Add to CV Studio';button.setAttribute('aria-label',added?'Added — click to remove from CV Studio':'Add to CV Studio');button.setAttribute('aria-pressed',String(added)); };
        const populate = result => {
          const selected = preferredFolder !== undefined ? preferredFolder : result.folder !== undefined ? result.folder : foldersLoaded ? folders.value : '';
          folders.replaceChildren(option('Unfiled',''),...(result.folders || []).map(value=>option(value,value)));
          folders.value = ['',...(result.folders || [])].includes(selected) ? selected : '';
          foldersLoaded = true;
          folders.disabled = working && activeOperation !== 'folders';
        };
        const action = async (operation,folder) => {
          if (working) return;
          working=true;activeOperation=operation;button.disabled=true;create.disabled=true;saveFolder.disabled=true;refresh.disabled=true;folders.disabled=!foldersLoaded||operation!=='folders';note.textContent=operation==='folders'?'Loading folders…':'';
          try {
            if (operation!=='folders' && folderRead) await folderRead.catch(() => {});
            if (operation==='add') {
              // A shared catalog says nothing about this card's saved state.
              // Check this exact ad before sending any destination folder/write.
              const current = await fetchFolders(url);
              if (typeof current.saved !== 'boolean') throw Error('The saved ad could not be checked. Refresh folders and try again.');
              publishFolders(current.folders);
              if (current.saved) {
                added=true;populate(current);
                note.textContent='Already saved in '+(current.folder || 'Unfiled')+'. No changes made.';
                return;
              }
            }
            const result=operation==='folders' ? await readFolders(url) : await send({kind:'sourcer_job_pick',url,operation,...(folder===undefined?{}:{folder})});
            if (result.folders && operation!=='folders') publishFolders(result.folders);
            if (operation==='folders' && result.sourceUrl!==url) { note.textContent='Folders refreshed.'; return; }
            if (result.folders) populate(result);
            if (operation!=='create_folder') added=result.saved !== false;
            if (operation==='create_folder') { choose(result.folder);folders.value=result.folder;editor.hidden=true;name.value=''; }
            note.textContent=result.warning || (operation==='remove'?'Removed · recoverable in CV Studio Trash':operation==='create_folder'?'Folder created · '+result.folder:operation==='folders'?(added?'Already saved in '+(result.folder || 'Unfiled')+'. Click Added to remove.':'Folder ready · '+(folders.value || 'Unfiled')):'CV Studio · '+(result.folder || 'Unfiled'));
          } catch (error) { note.textContent=error.message;if(!foldersLoaded)folders.replaceChildren(option('Folders unavailable','')); }
          finally { working=false;activeOperation='';button.disabled=false;create.disabled=false;saveFolder.disabled=false;refresh.disabled=false;folders.disabled=!foldersLoaded;display(); }
        };
        for (const type of ['mousedown','pointerdown']) controls.addEventListener(type,event => event.stopPropagation());
        button.addEventListener('click',event => {
          event.preventDefault(); event.stopPropagation();
          if (!event.isTrusted || button.disabled || controls.dataset.url !== url) return;
          return action(added?'remove':'add',foldersLoaded?folders.value:preferredFolder);
        });
        folders.addEventListener('focus',event => { if(event.isTrusted && !working) return action('folders'); });
        folders.addEventListener('pointerdown',event => { event.stopPropagation();if(event.isTrusted && !working) return action('folders'); });
        refresh.addEventListener('click',event => { event.preventDefault();event.stopPropagation();if(event.isTrusted&&!working)return action('folders'); });
        folders.addEventListener('change',event => { event.stopPropagation();if(event.isTrusted && foldersLoaded) choose(folders.value); });
        controls.addEventListener('click',event=>event.stopPropagation());
        create.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();if(event.isTrusted&&!working){editor.hidden=!editor.hidden;if(!editor.hidden)name.focus();}});
        saveFolder.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();if(event.isTrusted&&!working)return action('create_folder',name.value.trim());});
        controls.append(button,folders,create,editor,note,refresh); mount.appendChild(controls);
        const menu = {url,populate,refresh:() => action('folders'),fail:message => { if(!foldersLoaded && !working){folders.replaceChildren(option('Folders unavailable',''));note.textContent=message;} }};
        folderMenus.set(controls,menu);
        if(folderCatalog)populate({folders:folderCatalog});
        else if(catalogError)menu.fail(catalogError);
      }
      for(const [controls] of folderMenus)if(!document.body.contains(controls))folderMenus.delete(controls);
      if(!catalogAttempted && folderMenus.size){catalogAttempted=true;folderMenus.values().next().value.refresh();}
    };
    const schedule = () => { clearTimeout(timer); timer = setTimeout(scan,300); };
    new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true});
    document.addEventListener('visibilitychange',() => { if(!document.hidden){catalogAttempted=false;schedule();} }); scan(); return;
  }
  if (location.pathname !== '/' || window.top !== window) return;
  // The verified worker binding is renewed for each page document. The
  // After one explicit toolbar pairing, no repeated toggle is needed.
  let connecting, recoveryTimer, recoveryAttempts=0, recoveryStopped=false;
  const connect = () => {
    if (!connecting) connecting = new Promise(resolve => {
      try { chrome.runtime.sendMessage({kind:'sourcer',action:'connect'},reply=>{
        resolve(chrome.runtime.lastError ? {error:'Refresh CV Studio after updating the companion.'} : reply);
      }); }
      catch { resolve({error:'Refresh CV Studio after updating the companion.'}); }
    }).finally(()=>{connecting=null;});
    return connecting;
  };
  const recover = () => Promise.resolve(connecting).then(()=>connect()).then(reply=>{
    if(reply?.loading && !recoveryStopped && !recoveryTimer && recoveryAttempts<20){
      recoveryAttempts++;
      recoveryTimer=setTimeout(()=>{recoveryTimer=null;recover();},250);
    }
    return reply;
  });
  connect().then(reply=>{if(reply?.loading && document.readyState==='complete')recover();});
  // Chrome may omit/delay its tab-complete event. The document's own load
  // event supplies an independent bounded, read-only handshake recovery.
  window.addEventListener('load',recover,{once:true});
  window.addEventListener('pagehide',()=>{recoveryStopped=true;clearTimeout(recoveryTimer);recoveryTimer=null;},{once:true});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)connect();});
  const captures = new Map();
  chrome.runtime.onMessage.addListener((message,sender,reply) => {
    if (sender.id === chrome.runtime.id && message?.type === 'CVSTUDIO_COMPANION_READY') {
      // Do not coalesce the completion signal into a loading-time attempt
      // that is still returning its rejection. Probe again after it settles.
      recover().then(reply);
      return true;
    }
    if (sender.id !== chrome.runtime.id || message?.type !== 'CVSTUDIO_JOB_CAPTURE' || !/^[a-f0-9]{32}$/.test(message.id || '')) return false;
    const channel = document.getElementById('viewJobLeads')?.dataset.companionChannel;
    if (message.request?.action === 'folders' && document.getElementById('viewJobLeads')?.dataset.companionFolders !== '2') {
      reply({error:'Update CV Studio, refresh its tab and open Job Leads to load folders.'});return false;
    }
    if (message.request && (message.request.action !== 'add' || message.request.folder !== undefined) && document.getElementById('viewJobLeads')?.dataset.companionActions !== '1') {
      reply({error:'Update CV Studio and refresh its tab to use LinkedIn folders and remove controls.'}); return false;
    }
    const foldersOnly = message.request?.action === 'folders';
    if (!/^[a-f0-9]{32}$/.test(channel || '') || captures.size >= 8 || !foldersOnly && [...captures.values()].some(capture => !capture.foldersOnly)) { reply({error:'Open Job Leads in this CV Studio tab and wait for the current action to finish.'}); return false; }
    const timer = setTimeout(() => { captures.delete(message.id); reply({error:'CV Studio did not confirm the save. Check its saved list before adding the ad again.'}); },12000);
    captures.set(message.id,{channel,reply,timer,foldersOnly});
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
    connect().then(connection=>{
      const respond=reply=>window.postMessage({type:'CVSTUDIO_LINKEDIN_RESPONSE',channel:message.channel,id:message.id,...reply},location.origin);
      if(connection?.error){respond({error:connection.error});return;}
      try { chrome.runtime.sendMessage({kind: 'sourcer', scope:message.scope, action: message.action, args: message.args}, reply => {
      const error = chrome.runtime.lastError;
      respond(error ? {error:'Refresh CV Studio after updating the companion.'} : reply);
      }); } catch {respond({error:'Refresh CV Studio after updating the companion.'});}
    });
  });
})();

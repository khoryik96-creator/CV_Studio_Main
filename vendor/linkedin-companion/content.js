(() => {
  if (location.pathname !== '/' || window.top !== window) return;
  window.addEventListener('message', event => {
    const message = event.data;
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

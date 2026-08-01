(function () {
  'use strict';

  var loads = Object.create(null);

  function runCallbacks(callbacks) {
    var firstError = null;
    callbacks.forEach(function (callback) {
      try { callback(); } catch (error) { if (!firstError) firstError = error; }
    });
    if (firstError) window.setTimeout(function () { throw firstError; }, 0);
  }

  function fail(key, entry) {
    if (entry.element && entry.element.parentNode) entry.element.parentNode.removeChild(entry.element);
    delete loads[key];
    runCallbacks(entry.failures);
  }

  function loadClassicScript(key, url, ready, onReady, onFailure) {
    if (ready()) { onReady(); return; }
    var entry = loads[key];
    if (entry) {
      entry.successes.push(onReady);
      entry.failures.push(onFailure);
      return;
    }
    var script = document.createElement('script');
    entry = {element: script, successes: [onReady], failures: [onFailure]};
    loads[key] = entry;
    script.src = url;
    script.async = true;
    script.setAttribute('data-cvstudio-lazy-asset', key);
    script.onload = function () {
      if (!ready()) { fail(key, entry); return; }
      delete loads[key];
      runCallbacks(entry.successes);
    };
    script.onerror = function () { fail(key, entry); };
    document.head.appendChild(script);
  }

  window.cvStudioLoadClassicScript = loadClassicScript;
  window.cvStudioLoadJSPDF = function (onReady, onFailure) {
    loadClassicScript(
      'jspdf',
      '/vendor/jspdf.umd.min.js?v=24.6.79',
      function () { return !!(window.jspdf && window.jspdf.jsPDF); },
      onReady,
      onFailure
    );
  };
}());

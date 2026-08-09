// ── Generic AI proxy + anonymisation safety helpers ─────────────────────
async function callAIProxy(prompt, maxTokens, useTools, maxUses, feature) {
  var route = aiRoutePayload(feature || 'cv_single');
  var key = route.api_key;
  if (!key) throw new Error('Save an API key for ' + (AI_ROUTE_FEATURES[feature] ? AI_ROUTE_FEATURES[feature].label : 'this feature'));
  try {
    var isAiCrawler = feature === 'the_spider';
    var aiHeaders = { 'Content-Type': 'application/json' };
    if (isAiCrawler) aiHeaders['X-AI-Crawler-Code'] = aiCrawlerLockPayload();
    var r = await fetchWithTimeout('/generate-ai', {
      method: 'POST',
      headers: aiHeaders,
      body: JSON.stringify({
        api_key: key,
        model: route.model,
        provider: route.provider,
        prompt: prompt,
        max_tokens: maxTokens || 4000,
        use_tools: !!useTools,
        max_uses: maxUses || 3,
        feature: feature || 'cv_single',
        crawler_lock_code: isAiCrawler ? aiCrawlerLockPayload() : ''
      })
    }, 180000);
    var d = await r.json().catch(function(){ return {}; });
    if (!r.ok || d.error) {
      var featureLabel = (AI_ROUTE_FEATURES[feature] && AI_ROUTE_FEATURES[feature].label) || feature || 'AI action';
      recordPaidAiFailure(featureLabel + ' failed output', d, route.model, route.provider);
      var aiErr = new Error(normalizeAiProviderError(d.error || ('API error ' + r.status), route));
      aiErr.aiResponse = d;
      throw aiErr;
    }
    if (d.warning) showToast(d.warning, 'info');
    return d;
  } catch(e) {
    var msg = normalizeAiProviderError(e.message || e, route);
    if (aiProviderDownMessage(e.message || e, route)) showToast(msg.split('\n')[0], 'err');
    throw new Error(msg);
  }
}
function aiText(data) {
  return ((data && data.content) || []).filter(function(b){ return b.type === 'text'; }).map(function(b){ return b.text; }).join('');
}

function polishAnonScaleText(s) {
  if (!s) return s;
  return String(s)
    // Glue / spacing fixes created by adjacent regex replacements.
    .replace(/\b(across|in|with|and|or|of|to)(a|an|the|multiple|broad|substantial|large-scale|significant)\b/gi, '$1 $2')
    .replace(/\boperating\s+across\s+a\s+broad\s+international\s+footprint\b/gi, 'operating with a broad international footprint')
    .replace(/\bspanning\s+a\s+broad\s+international\s+footprint\b/gi, 'with a broad international footprint')
    .replace(/\bpresent\s+in\s+a\s+broad\s+international\s+footprint\b/gi, 'present across a broad international footprint')
    .replace(/\bserving\s+a\s+broad\s+international\s+footprint\b/gi, 'with a broad international footprint')

    // Rebuild common phrase combinations into readable English.
    .replace(/\bwith\s+a\s+broad\s+operational\s+footprint\s+(?:with|in|across)\s+a\s+broad\s+international\s+footprint\b/gi, 'with a broad international and operational footprint')
    .replace(/\bwith\s+a\s+broad\s+international\s+footprint\s+(?:with|and)\s+a\s+broad\s+operational\s+footprint\b/gi, 'with a broad international and operational footprint')
    .replace(/\ba\s+broad\s+international\s+footprint\s+and\s+multiple\s+regions\b/gi, 'a broad international footprint across multiple regions')
    .replace(/\bacross\s+multiple\s+regions\s+and\s+a\s+broad\s+international\s+footprint\b/gi, 'with a broad international footprint across multiple regions')
    .replace(/\ba\s+broad\s+international\s+footprint\s+across\s+multiple\s+regions\s+with\s+a\s+broad\s+operational\s+footprint\b/gi, 'a broad international and operational footprint across multiple regions')
    .replace(/\blarge-scale\s+transaction\s+volumes\s+across\s+a\s+broad\s+international\s+footprint\s+across\s+multiple\s+digital\s+asset\s+rails\b/gi, 'large-scale transaction volumes across a broad international footprint and multiple digital asset rails')
    .replace(/\ba\s+broad\s+international\s+footprint\s+across\s+multiple\s+digital\s+asset\s+rails\b/gi, 'a broad international footprint and multiple digital asset rails')
    .replace(/\bmultiple\s+digital\s+asset\s+rails\s+(?:and|across)\s+a\s+broad\s+international\s+footprint\b/gi, 'multiple digital asset rails across a broad international footprint')

    // Action-verb cleanup after replacing exact amounts.
    .replace(/\bprocesses\s+(?:monthly\s+|annual\s+|yearly\s+)?large-scale\s+transaction\s+volumes\b/gi, 'handles large-scale transaction volumes')
    .replace(/\bprocessing\s+(?:monthly\s+|annual\s+|yearly\s+)?large-scale\s+transaction\s+volumes\b/gi, 'handling large-scale transaction volumes')
    .replace(/\bprocessed\s+large-scale\s+transaction\s+volumes\b/gi, 'handled large-scale transaction volumes')
    .replace(/\bhandles\s+large-scale\s+transaction\s+volumes\b/gi, 'handles large-scale transaction volumes')

    // Duplicate / awkward replacement cleanup.
    .replace(/\bsubstantial\s+global\s+scale\s+(?:and|,)\s+substantial\s+global\s+scale\b/gi, 'substantial global scale')
    .replace(/\blarge-scale\s+transaction\s+volumes\s+(?:and|,)\s+large-scale\s+transaction\s+volumes\b/gi, 'large-scale transaction volumes')
    .replace(/\bsignificant\s+funding\s+raised\s+(?:and\s+(?:closed|raised|secured)\s+)?significant\s+funding\s+raised\b/gi, 'significant funding raised across multiple rounds')
    .replace(/\braised\s+significant\s+funding\s+(?:and\s+)?(?:closed|secured|raised)?\s*significant\s+funding\s+raised\b/gi, 'raised significant funding across multiple rounds')
    .replace(/\bsignificant\s+funding\s+raised\s+significant\s+funding\b/gi, 'significant funding raised')
    .replace(/\braised\s+significant\s+funding\s+funding\b/gi, 'raised significant funding')
    .replace(/\bsubstantial\s+global\s+scale\s+(?:revenue|revenues|turnover|sales|AUM|wealth\s+AUM|assets\s+under\s+management)\b/gi, 'substantial global scale')
    .replace(/\b(?:revenue|revenues|turnover|sales|AUM|wealth\s+AUM|assets\s+under\s+management)\s+substantial\s+global\s+scale\b/gi, 'substantial global scale')
    .replace(/\bAUM\s+surpassing\s+substantial\s+global\s+scale\b/gi, 'substantial global scale')
    .replace(/\bwith\s+wealth\s+substantial\s+global\s+scale\b/gi, 'with substantial global scale')
    .replace(/\blarge\s+multinational\s+leading\s+global\s+player\b/gi, 'large multinational and leading global player')
    .replace(/\ba\s+major\s+processors\b/gi, 'a major global player')
    .replace(/\ba\s+major\s+providers\b/gi, 'a major global player')
    .replace(/\ba\s+major\s+operators\b/gi, 'a major global player')
    .replace(/\ba\s+major\s+companies\b/gi, 'a major global organisation')

    // Cleaner conjunctions.
    .replace(/\bwith\s+substantial\s+global\s+scale,\s+with\s+a\s+large\s+global\s+workforce,\s+with\s+a\s+broad\s+international\s+footprint(?:\s+across\s+multiple\s+regions)?\b/gi, 'with substantial global scale, a large global workforce, and a broad international footprint')
    .replace(/\bwith\s+substantial\s+global\s+scale,\s+with\s+a\s+large\s+global\s+workforce\b/gi, 'with substantial global scale and a large global workforce')
    .replace(/\bwith\s+a\s+large\s+global\s+workforce,\s+with\s+a\s+broad\s+international\s+footprint\b/gi, 'with a large global workforce and a broad international footprint')
    .replace(/\band\s+with\s+a\s+large\s+global\s+workforce\b/gi, 'and a large global workforce')
    .replace(/\band\s+with\s+a\s+broad\s+international\s+footprint\b/gi, 'and a broad international footprint')
    .replace(/\bwith\s+with\b/gi, 'with')
    .replace(/\b(?:processes|processing|processed|handles?|handling)\s+monthlylarge-scale\s+transaction\s+volumes\b/gi, 'handles large-scale transaction volumes')
    .replace(/\bmonthlylarge-scale\s+transaction\s+volumes\b/gi, 'large-scale transaction volumes')
    .replace(/\bannuallarge-scale\s+transaction\s+volumes\b/gi, 'large-scale transaction volumes')
    .replace(/\bsignificant\s+funding\s+raised\s+(?:funding|investment|financing|rounds?|raised)(?:\s+raised)?\b/gi, 'significant funding raised')
    .replace(/\braised\s+significant\s+funding\s+(?:funding|investment|financing|rounds?|raised)(?:\s+raised)?\b/gi, 'raised significant funding')
    .replace(/\byearlylarge-scale\s+transaction\s+volumes\b/gi, 'large-scale transaction volumes')
    .replace(/\bsignificant\s+funding\s+raised\s+across\s+multiple\s+rounds\+?\s+(?:Payment\s*&\s*OTC|Payment\s+and\s+OTC|payments?|transactions?|trading|OTC)?\s*(?:Volume|Volumes|Throughput)(?:\s*\([^)]*\))?\b/gi, 'significant funding raised and large-scale transaction volumes')
    .replace(/\bsignificant\s+funding\s+raised\+?\s+(?:Payment\s*&\s*OTC|Payment\s+and\s+OTC|payments?|transactions?|trading|OTC)?\s*(?:Volume|Volumes|Throughput)(?:\s*\([^)]*\))?\b/gi, 'significant funding raised and large-scale transaction volumes')
    .replace(/\bserving\s+a\s+broad\s+client\s+base\s+substantial\s+global\s+scale\b/gi, 'serving a broad client base with substantial global scale')
    .replace(/\bsubstantial\s+global\s+scale\s+serving\s+a\s+broad\s+client\s+base\b/gi, 'substantial global scale and a broad client base')
    .replace(/\ba\s+broad\s+client\s+base,\s+a\s+large\s+global\s+workforce,\s+substantial\s+global\s+scale\b/gi, 'a broad client base, a large global workforce, and substantial global scale')
    .replace(/\bacross\s+multiple\s+digital\s+asset\s+rails\s+across\s+a\s+broad\s+international\s+footprint\b/gi, 'across multiple digital asset rails and a broad international footprint')
    .replace(/\braised\s+significant\s+funding\s+and\s+closed\s+significant\s+funding\s+raised\b/gi, 'raised significant funding across multiple rounds')
    .replace(/\braised\s+significant\s+funding\s+and\s+secured\s+significant\s+funding\s+raised\b/gi, 'raised significant funding across multiple rounds')
    .replace(/\bleading\s+global\s+player\s+(?:provider|player|merchant|processor)\b/gi, 'leading global player')
    .replace(/#\s*leading\s+market\s+position/gi, 'leading market position')
    .replace(/\b(has|have|had)with\b/gi, '$1 with')
    .replace(/\b(has|have|had)\s+with\s+a\s+broad\b/gi, '$1 a broad')
    .replace(/\blarge-scale\s+transaction\s+volumes\s*\(\d{4}\)/gi, 'large-scale transaction volumes')
    .replace(/\blarge-scale\s+transaction\s+volumes\s+serving\s+a\s+broad\s+client\s+base\s+with\s+substantial\s+global\s+scale\b/gi, 'large-scale transaction volumes, a broad client base, and substantial global scale')
    .replace(/\b(has|have|had)\s+a\s+broad\s+operational\s+footprint\s+with\s+a\s+broad\s+international\s+footprint\b/gi, '$1 a broad international and operational footprint')
    .replace(/\b(has|have|had)\s+a\s+broad\s+international\s+footprint\s+with\s+a\s+broad\s+operational\s+footprint\b/gi, '$1 a broad international and operational footprint')
    .replace(/\bcompleted\s+within\s+\d+\s+(?:months?|years?)\b/gi, 'completed over a short period')
    .replace(/\bwithin\s+\d+\s+(?:months?|years?)\b/gi, 'over a short period')
    .replace(/^With\s+a\s+broad\s+international\s+and\s+operational\s+footprint/i, 'Broad international and operational footprint')
    .replace(/^With\s+a\s+broad\s+international\s+footprint/i, 'Broad international footprint')
    .replace(/^With\s+substantial\s+global\s+scale/i, 'Substantial global scale')
    .replace(/\b(Client|The\s+company|Company|The\s+firm|The\s+organisation|The\s+organization)\s+substantial\s+global\s+scale(?:\s+annual\s+sales)?\b/gi, '$1 has substantial global scale')
    .replace(/\bsubstantial\s+global\s+scale\s+annual\s+sales\b/gi, 'substantial global scale')
    .replace(/\bsubstantial\s+global\s+scale\s+large-scale\s+transaction\s+volumes\b/gi, 'substantial global scale and large-scale transaction volumes')
    .replace(/\bsignificant\s+funding\s+raised\s+funding\s+raised(?:,\s*significant\s+funding\s+raised)+\b/gi, 'significant funding raised across multiple rounds')
    .replace(/\bsignificant\s+funding\s+raised(?:,\s*significant\s+funding\s+raised)+\b/gi, 'significant funding raised across multiple rounds')
    .replace(/\b(has|have|had)\s+a\s+broad\s+client\s+base\s+and\s+a\s+broad\s+client\s+base\b/gi, '$1 a broad client base')
    .replace(/\bwith\s+a\s+broad\s+operational\s+footprint\s+with\s+a\s+large\s+global\s+workforce\b/gi, 'with a broad operational footprint and a large global workforce')
    .replace(/^With\s+a\s+broad\s+operational\s+footprint\s+with\s+a\s+large\s+global\s+workforce/i, 'Broad operational footprint and large global workforce')
    .replace(/\bPresent\s+across\s+multiple\s+regions,\s*a\s+broad\s+international\s+footprint,\s*and\s*with\s+a\s+broad\s+operational\s+footprint\b/gi, 'Present with a broad international and operational footprint across multiple regions')
    .replace(/\bworkforce\s+of\s+a\s+large\s+global\s+workforce(?:\s+(?:worldwide|globally))?\b/gi, 'large global workforce')
    .replace(/\ba\s+large\s+global\s+workforce\s+(?:worldwide|globally)\b/gi, 'a large global workforce')
    .replace(/\bwith\s+a\s+broad\s+client\s+base\s+with\s+a\s+broad\s+international\s+footprint\b/gi, 'with a broad client base and a broad international footprint')
    .replace(/\ba\s+broad\s+client\s+base\s+with\s+a\s+broad\s+international\s+footprint\b/gi, 'a broad client base and a broad international footprint')
    .replace(/\boperations\s+with\s+a\s+broad\s+international\s+footprint\b/gi, 'a broad international footprint')
    .replace(/\boperates\s+with\s+a\s+broad\s+international\s+and\s+operational\s+footprint\s+and\s+a\s+large\s+global\s+workforce\b/gi, 'operates with a broad international and operational footprint and a large global workforce')
    .replace(/\bmajor\s+([^.,;]{0,40}?)\s+group\s+by\s+assets\s+with\s+substantial\s+global\s+scale\b/gi, 'major $1 group with substantial global scale')
    .replace(/\b(Client|The\s+company|Company|The\s+firm|The\s+organisation|The\s+organization)\s+has\s+substantial\s+global\s+scale,\s+with\s+a\s+broad\s+operational\s+footprint,\s+a\s+large\s+global\s+workforce,\s+and\s+a\s+broad\s+international\s+footprint\b/gi, '$1 has substantial global scale, a broad international and operational footprint, and a large global workforce')
    .replace(/\b(?:Revenue|Revenues|Turnover|Sales|AUM|Wealth\s+AUM|Assets\s+under\s+management)\s*:\s*substantial\s+global\s+scale\b/gi, 'substantial global scale')
    .replace(/\bsignificant\s+funding\s+raised\s+across\s+multiple\s+rounds\s+completed\s+over\s+a\s+short\s+period\b/gi, 'significant funding raised across multiple rounds over a short period')
    .replace(/\bhandled\s+large-scale\s+transaction\s+volumes\b/gi, 'handles large-scale transaction volumes')
    .replace(/\b(and|or|supports?|has|have|had)\s*(multiple|a|an|the|with|broad|substantial|large-scale|significant)\b/gi, '$1 $2')

    // Remaining punctuation / spacing polish.
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([,.;:])/g, '$1')
    .replace(/([;:])(?=\S)/g, '$1 ')
    .replace(/,(?=\S)(?!\d)/g, ', ')
    .replace(/(\d),\s+(\d{3}\b)/g, '$1,$2')
    .replace(/\s+\./g, '.')
    .replace(/\.{2,}/g, '.')
    .replace(/\bglobal\s+global\b/gi, 'global')
    .replace(/^with\s+/i, 'With ')
    .replace(/^and\s+/i, '')
    .trim();
}

function escapeRegExpAnon(s) {
  return String(s || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function anonCompanyAliasNorms(companyName) {
  var aliases = Object.create(null);
  var base = String(companyName || '').trim();
  function add(v) {
    var n = jdAnonNormalizeTerm(v || '');
    if (n && n.length >= 2) aliases[n] = true;
  }
  add(base);
  var noSuffix = base.replace(/\b(?:sdn\.?\s*bhd\.?|bhd\.?|pte\.?\s*ltd\.?|private\s+limited|limited|ltd\.?|inc\.?|corp\.?|corporation|company|co\.?|group|holdings?|plc|llc|llp|se|ag|gmbh)\b/gi, '').replace(/\s{2,}/g, ' ').trim();
  add(noSuffix);
  // For known tech-company names, also treat the first token as an alias so
  // "Oracle Corporation" / "SAP SE" do not leak through as Oracle/SAP.
  var first = noSuffix.split(/\s+/)[0] || '';
  var firstNorm = jdAnonNormalizeTerm(first);
  if (/^(oracle|sap|salesforce|workday|microsoft|amazon|google|servicenow)$/i.test(firstNorm)) add(first);
  return aliases;
}

function anonIsProtectedTechCompanyAlias(name) {
  return /^(oracle|sap|salesforce|workday|microsoft|amazon|google|servicenow)$/i.test(jdAnonNormalizeTerm(name || ''));
}

function anonIsProtectedTechContext(fullText, matchIndex, name) {
  var norm = jdAnonNormalizeTerm(name || '');
  if (!anonIsProtectedTechCompanyAlias(norm)) return false;
  var text = String(fullText || '');
  var idx = Math.max(0, Number(matchIndex || 0));
  var len = String(name || '').length;
  // Anchor checks to this exact occurrence, not the whole sentence/window.
  // This prevents "Oracle is hiring... Oracle Database" from preserving the
  // first identity mention just because a later technical phrase exists.
  var afterCtx = text.slice(idx, Math.min(text.length, idx + len + 85));
  var beforeCtx = text.slice(Math.max(0, idx - 60), idx + len);
  if (norm === 'oracle') {
    return /^oracle\s+(?:database|db|sql|dba|developer|engineer|cloud|erp|applications?|forms?|reports?|r12|e[- ]?business|ebs|fusion|financials?|rac|asm|data\s+guard|rman|exadata|pl\/sql)\b/i.test(afterCtx)
      || /\b(?:database|db|sql|dba|pl\/sql)\s+oracle$/i.test(beforeCtx);
  }
  if (norm === 'sap') {
    return /^sap\s+(?:fico|fi\/?co|mm|sd|hcm|hr|abap|basis|bw|bi|hana|s\/4hana|s4hana|erp|crm|successfactors|ariba|concur|b1|business\s+one|consultant|developer|functional|technical|module|modules)\b/i.test(afterCtx)
      || /\b(?:s\/4hana|s4hana|abap|hana)\s+sap$/i.test(beforeCtx);
  }
  if (norm === 'salesforce') {
    return /^salesforce\s+(?:crm|platform|cloud|admin|administrator|developer|consultant|lightning|apex|service\s+cloud|sales\s+cloud|marketing\s+cloud)\b/i.test(afterCtx);
  }
  if (norm === 'workday') {
    return /^workday\s+(?:hcm|financials?|hris|integration|integrations?|adaptive|studio|reporting|consultant|developer|implementation|platform)\b/i.test(afterCtx);
  }
  if (norm === 'microsoft') {
    return /^microsoft\s+(?:azure|365|dynamics|power\s+bi|power\s+platform|fabric|sql\s+server|sharepoint|teams|excel)\b/i.test(afterCtx);
  }
  if (norm === 'amazon') {
    return /^amazon\s+(?:web\s+services|aws|s3|redshift|athena|glue|emr|lambda)\b/i.test(afterCtx);
  }
  if (norm === 'google') {
    return /^google\s+(?:cloud|cloud\s+platform|gcp|bigquery|dataflow|pub\/sub|dataproc)\b/i.test(afterCtx);
  }
  if (norm === 'servicenow') {
    return /^servicenow\s+(?:itsm|cmdb|itam|csm|hrsd|platform|developer|administrator|admin|implementation|workflow|modules?)\b/i.test(afterCtx);
  }
  return false;
}

function scrubAnonCompanyNameText(text, companyName) {
  if (!text || !companyName) return text;
  var names = [];
  var base = String(companyName).trim();
  if (base.length >= 3) names.push(base);
  var noSuffix = base.replace(/\b(?:sdn\.?\s*bhd\.?|bhd\.?|pte\.?\s*ltd\.?|private\s+limited|limited|ltd\.?|inc\.?|corp\.?|corporation|company|co\.?|group|holdings?|plc|llc|llp|se|ag|gmbh)\b/gi, '').replace(/\s{2,}/g, ' ').trim();
  if (noSuffix.length >= 3 && noSuffix.toLowerCase() !== base.toLowerCase()) names.push(noSuffix);
  var first = noSuffix.split(/\s+/)[0] || '';
  if (/^(oracle|sap|salesforce|workday|microsoft|amazon|google|servicenow)$/i.test(first) && names.indexOf(first) < 0) names.push(first);
  names.sort(function(a,b){ return b.length - a.length; }).forEach(function(n) {
    var re = new RegExp('\\b' + escapeRegExpAnon(n) + '\\b', 'gi');
    text = String(text).replace(re, function(match, offset, full) {
      // Preserve true technical uses such as Oracle Database / SAP FICO even
      // when the company field is Oracle/SAP. Strip standalone identity uses.
      if (anonIsProtectedTechContext(full, offset, match)) return match;
      return 'the client';
    });
  });
  return text
    .replace(/\bthe\s+client\s+the\s+client\b/gi, 'the client')
    .replace(/\bThe\s+the\s+client\b/g, 'The client')
    .replace(/\bthe\s+the\s+client\b/gi, 'the client')
    .replace(/\bthe\s+client\s+large-scale\s+transaction\s+volumes\b/gi, 'the client handles large-scale transaction volumes')
    .replace(/\bthe\s+client\s+substantial\s+global\s+scale\b/gi, 'the client has substantial global scale')
    .replace(/\bthe\s+client\s+significant\s+funding\s+raised\b/gi, 'the client has raised significant funding')
    .replace(/\bthe\s+client\s+a\s+broad\s+client\s+base\b/gi, 'the client serves a broad client base')
    .replace(/\bthe\s+client\s+serving\s+a\s+broad\s+client\s+base\b/gi, 'the client serves a broad client base')
    .replace(/\bthe\s+client\s+serves\s+a\s+broad\s+client\s+base\b/gi, 'the client serves a broad client base')
    .replace(/\bthe\s+client\s+with\s+/gi, 'the client with ');
}

function scrubAnonCompanyNameData(data, companyName) {
  if (!data || typeof data !== 'object' || !companyName) return data;
  Object.keys(data).forEach(function(k) {
    if (k === 'tech_stack') return;
    var v = data[k];
    if (typeof v === 'string') data[k] = scrubAnonCompanyNameText(v, companyName);
    else if (Array.isArray(v)) data[k] = v.map(function(item){ return typeof item === 'string' ? scrubAnonCompanyNameText(item, companyName) : item; });
    else if (v && typeof v === 'object') scrubAnonCompanyNameData(v, companyName);
  });
  return data;
}

function softenAnonScaleText(text) {
  if (!text) return text;
  var s = String(text);

  // Whole-phrase replacements first: these avoid half-cleaned fragments like "funding+" or "acrossa".
  s = s.replace(/(^|[^A-Za-z0-9])(?:[A-Z]{2,3}\s*)?[\$€£¥₹RM]+\s*\d+(?:\.\d+)?\s*(?:billion|bn|million|m|trillion|tn|b|m)\+?\s+(?:pre[-\s]?a|seed|series\s+[a-f]|funding|investment|rounds?|raised|financing)(?:\s+raised)?\b/gi, '$1significant funding raised');
  s = s.replace(/\b(?:pre[-\s]?a|seed|series\s+[a-f]|funding|investment|financing|rounds?)\s+(?:raised|secured|closed)?\s*(?:of|:)?\s*(?:[A-Z]{2,3}\s*)?[\$€£¥₹RM]+\s*\d+(?:\.\d+)?\s*(?:billion|bn|million|m|trillion|tn|b|m)\+?\b/gi, 'significant funding raised');
  s = s.replace(/\b(?:raised|secured|closed|completed)\s+(?:around|approximately|approx\.?|about|over|more\s+than)?\s*(?:[A-Z]{2,3}\s*)?[\$€£¥₹RM]+\s*\d+(?:\.\d+)?\s*(?:billion|bn|million|m|trillion|tn|b|m)\+?(?:\s+(?:in\s+)?(?:pre[-\s]?a|seed|series\s+[a-f]|funding|investment|financing|rounds?))?\b/gi, 'raised significant funding');

  // Volumes / throughput, both "Volume $10B" and "$10B Volume" order.
  s = s.replace(/\b(?:payment\s*&\s*OTC|payment\s+and\s+OTC|payments?|transactions?|trading|OTC)?\s*(?:volume|volumes|throughput)(?:\s*\([^)]*\))?\s*(?:of|:|exceeding|over|more\s+than|around|approximately|approx\.?|about)?\s*(?:[A-Z]{2,3}\s*)?[\$€£¥₹RM]*\s*\d+(?:\.\d+)?\s*(?:billion|bn|million|m|trillion|tn|b|m)\+?(?=\s|[.,;:]|$)/gi, 'large-scale transaction volumes');
  s = s.replace(/(^|[^A-Za-z0-9])(?:[A-Z]{2,3}\s*)?[\$€£¥₹RM]+\s*\d+(?:\.\d+)?\s*(?:billion|bn|million|m|trillion|tn|b|m)\+?\s+(?:payment\s*&\s*OTC|payment\s+and\s+OTC|payments?|transactions?|trading|OTC)?\s*(?:volume|volumes|throughput)(?:\s*\([^)]*\))?\b/gi, '$1large-scale transaction volumes');
  s = s.replace(/\b(?:processing|processed|handles?|handling)\s+(?:monthly\s+|annual\s+|yearly\s+)?(?:volumes|transactions|payments)\s+(?:of|exceeding|over|more\s+than|around|approximately|approx\.?|about)?\s*(?:[A-Z]{2,3}\s*)?[\$€£¥₹RM]*\s*\d+(?:\.\d+)?\s*(?:billion|bn|million|m|trillion|tn|b|m)\+?(?=\s|[.,;:]|$)/gi, 'handling large-scale transaction volumes');

  // Revenue / AUM / turnover / sales: both metric-first and amount-first order.
  s = s.replace(/\b(?:annual\s+)?(?:revenue|revenues|turnover|sales|AUM|wealth\s+AUM|assets\s+under\s+management)\s*(?:of|in\s+the\s+range\s+of|around|approximately|approx\.?|about|exceeding|surpassing|reaching|at|over|more\s+than)?\s*(?:around|approximately|approx\.?|about)?\s*(?:[A-Z]{2,3}\s*)?[\$€£¥₹RM]*\s*\d+(?:\.\d+)?\s*(?:billion|bn|million|m|trillion|tn|b|m)\+?(?=\s|[.,;:]|$)/gi, 'substantial global scale');
  s = s.replace(/(^|[^A-Za-z0-9])(?:[A-Z]{2,3}\s*)?[\$€£¥₹RM]+\s*\d+(?:\.\d+)?\s*(?:billion|bn|million|m|trillion|tn|b|m)\+?\s+(?:revenue|revenues|turnover|sales|AUM|wealth\s+AUM|assets\s+under\s+management)\b/gi, '$1substantial global scale');
  s = s.replace(/(^|[^A-Za-z0-9])(?:[A-Z]{2,3}\s*)?[\$€£¥₹RM]+\s*\d+(?:\.\d+)?\s*(?:billion|bn|million|m|trillion|tn|b|m)\+?\s+(?:annual\s+)?(?:revenue|revenues|turnover|sales|AUM|wealth\s+AUM|assets\s+under\s+management)\b/gi, '$1substantial global scale');

  // Generic currency/scale amount after specific patterns, to remove remaining searchable financial fingerprints.
  s = s.replace(/(^|[^A-Za-z0-9])(?:[A-Z]{2,3}\s*)?[\$€£¥₹RM]+\s*\d+(?:\.\d+)?\s*(?:billion|bn|million|m|trillion|tn|b|m)\+?(?=\s|[.,;:]|$)/gi, '$1substantial global scale');

  // Labelled dashboard-style metrics and magnitude-based client/headcount clues.
  s = s.replace(/\b(?:customers|clients|client\s+base|partners|merchants|institutions)\s*:\s*(?:over|more\s+than|around|approximately|approx\.?|about)?\s*\d[\d,]*(?:\+)?\b/gi, 'broad client base');
  s = s.replace(/\b(?:offices|locations|branches|sites|facilities)\s*:\s*(?:over|more\s+than|around|approximately|approx\.?|about)?\s*\d[\d,]*(?:\+)?\b/gi, 'broad operational footprint');
  s = s.replace(/\b(?:countries|markets|jurisdictions|territories)\s*:\s*(?:over|more\s+than|around|approximately|approx\.?|about)?\s*\d[\d,]*(?:\+)?\b/gi, 'broad international footprint');
  s = s.replace(/\b(?:over|more\s+than|around|approximately|approx\.?|about)?\s*\d+(?:\.\d+)?\s*(?:million|billion|m|bn)\+?\s+(?:clients|customers|institutions|partners|merchants)\b/gi, 'a broad client base');
  s = s.replace(/\b(?:over|more\s+than|around|approximately|approx\.?|about)?\s*\d{1,3},\d{3,}(?:\+)?\s+(?:professionals|employees|people|staff|team\s+members|colleagues)\b/gi, 'a large global workforce');
  s = s.replace(/\b(?:over|more\s+than|around|approximately|approx\.?|about)?\s*\d{4,}(?:\+)?\s+(?:professionals|employees|people|staff|team\s+members|colleagues)\b/gi, 'a large global workforce');
  // Customers / clients / merchants.
  s = s.replace(/\b(?:serving|serves|supporting|supports|with|across)\s+(?:over|more\s+than|around|approximately|approx\.?|about)?\s*\d[\d,]*(?:\+)?\s+(?:institutional\s+and\s+accredited\s+|institutional\s+|accredited\s+|enterprise\s+)?(?:clients|customers|institutions|partners|merchants)(?:\s+(?:globally|worldwide|across\s+[^.,;]+))?\b/gi, 'serving a broad client base');
  s = s.replace(/\b(?:over|more\s+than|around|approximately|approx\.?|about)?\s*\d[\d,]*(?:\+)?\s+(?:institutional\s+and\s+accredited\s+|institutional\s+|accredited\s+|enterprise\s+)?(?:clients|customers|institutions|partners|merchants)(?:\s+(?:globally|worldwide))?\b/gi, 'a broad client base');

  // Digital rails and geographic footprint combinations must be replaced before standalone markets/countries.
  s = s.replace(/\b(?:more\s+than|over|around|approximately|approx\.?|about)?\s*\d+(?:\+)?\s+(?:stablecoins|digital\s+asset\s+rails|payment\s+rails|asset\s+rails)\s+(?:and|across|in|with)\s+(?:more\s+than|over|around|approximately|approx\.?|about)?\s*\d+(?:\+)?\s+(?:markets|countries|jurisdictions|territories)\b/gi, 'multiple digital asset rails across a broad international footprint');
  s = s.replace(/\b(?:more\s+than|over|around|approximately|approx\.?|about)?\s*\d+(?:\+)?\s+(?:markets|countries|jurisdictions|territories)\s+(?:and|across|with|in)\s+(?:more\s+than|over|around|approximately|approx\.?|about)?\s*\d+(?:\+)?\s+(?:stablecoins|digital\s+asset\s+rails|payment\s+rails|asset\s+rails)\b/gi, 'a broad international footprint and multiple digital asset rails');
  s = s.replace(/\b(?:across|in|over|more\s+than|around|approximately|approx\.?|about)?\s*\d+(?:\+)?\s+(?:stablecoins|digital\s+asset\s+rails|payment\s+rails|asset\s+rails)\b/gi, 'multiple digital asset rails');

  // Countries/markets/continents and offices/location counts.
  s = s.replace(/\b(?:spanning|operating\s+across|present\s+in|across|in|serving)\s+(?:more\s+than|over|around|approximately|approx\.?|about)?\s*\d+\+?\s+(?:countries|markets|jurisdictions|territories|locations|offices)\s+(?:across|and|in|throughout)\s+(?:all\s+)?(?:one|two|three|four|five|six|seven|\d+)\s+continents\b/gi, 'with a broad international footprint across multiple regions');
  s = s.replace(/\b(?:across|spanning|in|throughout|covering)\s+(?:all\s+)?(?:one|two|three|four|five|six|seven|\d+)\s+continents\s+(?:and|across|in|with)\s+(?:more\s+than|over|around|approximately|approx\.?|about)?\s*\d+\+?\s+(?:countries|markets|jurisdictions|territories|locations|offices)\b/gi, 'with a broad international footprint across multiple regions');
  s = s.replace(/\b(?:with\s+)?(?:over|more\s+than|around|approximately|approx\.?|about)?\s*\d[\d,]*(?:\+)?\s+(?:offices|locations|stores|branches|factories|facilities|sites)(?:\s+(?:worldwide|globally|across\s+the\s+world))?\b/gi, 'with a broad operational footprint');
  s = s.replace(/\b(?:spanning|operating\s+across|present\s+in|across|in|serving)\s+(?:more\s+than|over|around|approximately|approx\.?|about)?\s*\d+\+?\s+(?:countries|markets|jurisdictions|territories|locations|offices)\b/gi, 'with a broad international footprint');
  s = s.replace(/\b(?:more\s+than|over|around|approximately|approx\.?|about)?\s*\d+\+?\s+(?:countries|markets|jurisdictions|territories)\b/gi, 'a broad international footprint');
  s = s.replace(/\b(?:across|spanning|in|throughout|covering)\s+(?:all\s+)?(?:one|two|three|four|five|six|seven|\d+)\s+continents\b/gi, 'across multiple regions');
  s = s.replace(/\b(?:and|,)\s+(?:all\s+)?(?:one|two|three|four|five|six|seven|\d+)\s+continents\b/gi, ' and multiple regions');

  // Headcount and rankings.
  s = s.replace(/\b(?:with\s+)?(?:a\s+)?workforce\s+of\s+(?:over|more\s+than|around|approximately|approx\.?|about)?\s*\d[\d,]*(?:\+)?\s+(?:professionals|employees|people|staff|team\s+members|colleagues)(?:\s+(?:worldwide|globally|across\s+the\s+world))?\b/gi, 'with a large global workforce');
  s = s.replace(/\b(?:over|more\s+than|around|approximately|approx\.?|about)?\s*\d[\d,]*(?:\+)?\s+(?:professionals|employees|people|staff|team\s+members|colleagues)\s+(?:worldwide|globally|across\s+the\s+world)\b/gi, 'a large global workforce');
  s = s.replace(/\bFortune\s*(?:Global\s*)?\d+\b/gi, 'large multinational');
  s = s.replace(/\b(?:top|#|number\s+)?\s*\d+\s*(?:largest|ranked|ranking|player|provider|merchant|processor)\b/gi, 'leading global player');
  s = s.replace(/(?:\btop\s*|#\s*|\bnumber\s+)?\d+\s*(?:market\s+position|market\s+share|rank|ranking)\b/gi, 'leading market position');

  // "World's largest" phrases should be replaced as whole phrases where possible.
  s = s.replace(/\bone\s+of\s+the\s+world['’]?s\s+largest\s+(?:[a-z][a-z-]*\s+){0,6}(?:providers?|players?|merchants?|processors?|banks?|insurers?|companies|organisations|organizations|firms|groups|operators|merchants\s+and\s+processors)\b/gi, 'a major global player');
  s = s.replace(/\bworld['’]?s\s+largest\s+(?:[a-z][a-z-]*\s+){0,6}(?:providers?|players?|merchants?|processors?|banks?|insurers?|companies|organisations|organizations|firms|groups|operators|merchants\s+and\s+processors)\b/gi, 'major global player');
  s = s.replace(/\bone\s+of\s+the\s+world['’]?s\s+largest\b/gi, 'a major');
  s = s.replace(/\bworld['’]?s\s+largest\b/gi, 'major');

  return polishAnonScaleText(s);
}

function softenAnonScaleData(data) {
  if (!data || typeof data !== 'object') return data;
  Object.keys(data).forEach(function(k) {
    if (k === 'tech_stack') return;
    var v = data[k];
    if (typeof v === 'string') data[k] = softenAnonScaleText(v);
    else if (Array.isArray(v)) data[k] = v.map(function(item){ return typeof item === 'string' ? softenAnonScaleText(item) : item; });
    else if (v && typeof v === 'object') softenAnonScaleData(v);
  });
  return data;
}

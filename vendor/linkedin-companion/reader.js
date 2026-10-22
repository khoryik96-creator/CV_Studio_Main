/* Runs only in Chrome's isolated extension world. No network or credentials. */
(() => {
  const compact = value => String(value || '').replace(/\s+/g, ' ').trim();
  const visible = el => !!el && !!el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const text = el => compact(el?.innerText || '');
  function jobSummary(card) {
    const value = text(card), controls = text(card.querySelector?.('[data-cvstudio-job-controls]'));
    const index = controls ? value.indexOf(controls) : -1;
    return index >= 0 ? compact(value.slice(0,index) + ' ' + value.slice(index+controls.length)) : value;
  }
  function profileURL(value) {
    try {
      const u = new URL(value, location.href);
      if (u.protocol !== 'https:' || u.hostname !== 'www.linkedin.com' || u.port || u.username || u.password) return '';
      const path = u.pathname.replace(/\/+$/, '');
      if (!/^\/(in\/[^/]+|talent\/(?:hire\/)?profile\/[^/]+)$/.test(path)) return '';
      if (/[\x00-\x20\\]/.test(decodeURIComponent(path))) return '';
      return u.origin + path;
    } catch { return ''; }
  }
  function issue() {
    const path = location.pathname;
    if (/^\/(checkpoint|challenge|authwall|login|uas)(\/|$)/i.test(path)) return 'LinkedIn needs you to sign in or complete a check. The agent will stop.';
    if (document.querySelector('iframe[src*="captcha"], [data-test-id="captcha-internal"], #captcha-internal')) return 'LinkedIn needs a verification check. The agent will stop.';
    if (/unusual activity|temporarily restricted|security verification|you(?:.ve| have) reached.*(?:search|commercial).*limit|too many requests/i.test(text(document.querySelector('main') || document.body).slice(0, 5000))) return 'LinkedIn is showing an access or usage restriction. The agent will stop.';
    return '';
  }
  function assertPage(mode, type = 'search') {
    if (location.origin !== 'https://www.linkedin.com') throw Error('This is not a supported LinkedIn page.');
    const problem = issue();
    if (problem) throw Error(problem);
    if (type === 'profile') {
      if (!profileURL(location.href)) throw Error('The profile page changed. Nothing will be read.');
    } else if (mode === 'standard' ? !/^\/search\/results\/people\/?$/.test(location.pathname) :
               !/^\/talent\//.test(location.pathname) || !!profileURL(location.href)) {
      throw Error('Open a People search or the selected Recruiter search first.');
    }
  }
  const cardSelectors = {
    standard: 'li.reusable-search__result-container, [data-view-name="search-entity-result-universal-template"], .entity-result',
    lite: '[data-test-search-result], [data-test-candidate-card], [data-live-test-candidate-card], .candidate-card, .artdeco-list__item',
    recruiter: '[data-test-candidate-card], [data-test-search-result], [data-live-test-candidate-card], .candidate-card, .artdeco-list__item'
  };
  function readSearch(mode) {
    assertPage(mode);
    const scope = document.querySelector('main') || document.body;
    const rows = [], seen = new Set();
    for (const link of scope.querySelectorAll('a[href]')) {
      const url = profileURL(link.href);
      if (!url || seen.has(url) || !visible(link)) continue;
      const card = link.closest(cardSelectors[mode]) || link.closest('li, article, [role="listitem"]');
      if (!card || !visible(card)) continue;
      const words = text(card);
      if (words.length < 8 || words.length > 6500) continue;
      // A whole results container is never treated as one candidate card.
      const links = new Set([...card.querySelectorAll('a[href]')].map(a => profileURL(a.href)).filter(Boolean));
      if (links.size !== 1) continue;
      const nameElement = card.querySelector('[data-test-candidate-name], [data-test-search-result-name]') || link;
      let name = compact((nameElement.innerText || '').split('\n')[0]).replace(/\s*[·•]\s*(?:1st|2nd|3rd).*$/i, '').slice(0, 150);
      if (!name || /^(view|open).*profile/i.test(name)) name = 'LinkedIn member';
      seen.add(url);
      rows.push({id: 'p' + rows.length, name, url, text: words});
      if (rows.length >= 40) break;
    }
    const mainText = text(scope).slice(0, 2000);
    const empty = !rows.length && /no results|no candidates|couldn.t find any|0 results/i.test(mainText);
    const button = nextButton();
    return {url: location.href, profiles: rows, empty, paginationKnown: !!button, hasNext: !!button && !disabled(button),
            signature: rows.map(p => p.url).join('|')};
  }
  function disabled(el) { return el.disabled || el.getAttribute('aria-disabled') === 'true'; }
  function nextButton() {
    const selector = '.artdeco-pagination__button--next, [data-test-pagination-next], [data-test-pagination-page-btn="next"]';
    const direct = [...document.querySelectorAll(selector)].find(visible);
    if (direct) return direct;
    const containers = document.querySelectorAll('.artdeco-pagination, .pagination, [data-test-pagination], nav[aria-label*="pagination" i]');
    for (const container of containers) {
      const match = [...container.querySelectorAll('button')].find(b => visible(b) && /^(next|next page|seterusnya)$/i.test(compact(b.getAttribute('aria-label') || b.innerText)));
      if (match) return match;
    }
    return null;
  }
  function next(mode, signature) {
    const snapshot = readSearch(mode);
    if (!signature || snapshot.signature !== signature) throw Error('The search changed while the agent was working. Start a new run.');
    const button = nextButton();
    if (!button || disabled(button)) return false;
    button.click();
    return true;
  }
  function search(mode, query) {
    assertPage(mode);
    if (mode === 'standard') throw Error('Standard search is opened by the extension.');
    // Recruiter variants have different routes. Use their visible keyword
    // search field, rather than inventing a private route or calling an API.
    const selectors = 'input[placeholder*="keyword" i], input[aria-label*="keyword" i], textarea[placeholder*="keyword" i], input[data-test-keywords-input]';
    const inputs = [...document.querySelectorAll(selectors)].filter(visible);
    if (inputs.length !== 1) throw Error('The Recruiter keyword field is not recognized. Paste the generated query into Keywords, run the search, then choose Review open search.');
    const input = inputs[0];
    const descriptor = Object.getOwnPropertyDescriptor(input.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value');
    descriptor.set.call(input, query);
    input.dispatchEvent(new Event('input', {bubbles: true}));
    input.dispatchEvent(new Event('change', {bubbles: true}));
    const form = input.closest('form');
    const buttons = [...(form || document).querySelectorAll('button')].filter(b => visible(b) && !disabled(b) && /^(search|search candidates|apply)$/i.test(text(b)));
    if (buttons.length !== 1) throw Error('The Recruiter search button is not recognized. Run the search yourself, then choose Review open search.');
    buttons[0].click();
    return true;
  }
  function readProfile(expectedURL) {
    assertPage('', 'profile');
    if (profileURL(location.href) !== expectedURL) throw Error('The profile changed while the agent was working.');
    const main = document.querySelector('main');
    if (!main) throw Error('The profile layout is not recognized.');
    const words = text(main).slice(0, 14000);
    if (words.length < 30) throw Error('The profile has not loaded or is unavailable.');
    const topcard = main.querySelector('[data-test-profile-topcard], [data-test-candidate-profile-header], .profile-topcard, header');
    const publicLink = location.pathname.startsWith('/in/') ? profileURL(location.href) :
      [...(topcard?.querySelectorAll('[data-test-public-profile-link], [data-test-profile-public-url], a[aria-label*="public profile" i]') || [])]
        .map(a => profileURL(a.href)).find(u => /\/in\//.test(u));
    const name = text(main.querySelector('h1, [data-test-profile-name]')).slice(0, 150);
    return {text: words, publicUrl: publicLink || '', name};
  }
  function readJob(expectedURL) {
    const loading = message => { const error = Error(message); error.cvstudioJobLoading = true; throw error; };
    if (location.origin !== 'https://www.linkedin.com') throw Error('Choose a LinkedIn job ad.');
    const problem = issue(); if (problem) throw Error(problem);
    const view = location.pathname.match(/^\/jobs\/view\/(?:[^/]*-)?([0-9]{1,24})\/?$/);
    const ids = new URLSearchParams(location.search).getAll('currentJobId');
    const id = view ? view[1] : /^\/jobs(?:\/search(?:-results)?|\/collections\/[^/]+)?\/?$/.test(location.pathname) && ids.length === 1 ? ids[0] : '';
    const url = /^[0-9]{1,24}$/.test(id) ? 'https://www.linkedin.com/jobs/view/' + id : '';
    if (!url || url !== expectedURL) throw Error('The selected job changed. Refresh job tabs.');
    // Read only a recognized job detail panel, excluding neighboring result cards.
    const panels = [...document.querySelectorAll('.jobs-search__job-details--container, .jobs-details, .job-view-layout, .top-card-layout')].filter(visible);
    const panel = panels.find(value => value.querySelector('.job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, .top-card-layout__title'));
    if (!panel) {
      const modern = readModernJob(url);
      if (modern) return modern;
      loading('This job layout has not loaded or is not recognized.');
    }
    const first = selector => [...panel.querySelectorAll(selector)].find(visible);
    const roleNode = first('.job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, .top-card-layout__title');
    const roleLink = roleNode?.matches('a[href]') ? roleNode : roleNode?.querySelector('a[href]');
    const linkedId = roleLink ? new URL(roleLink.href, location.href).pathname.match(/^\/jobs\/view\/(?:[^/]*-)?([0-9]{1,24})\/?$/)?.[1] : '';
    if ((linkedId && linkedId !== id) || (!view && linkedId !== id)) loading('The selected job details are still changing.');
    const role = text(roleNode).slice(0, 240);
    const company = text(first('.job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name, .topcard__org-name-link')).slice(0, 200);
    const locationText = text(first('.job-details-jobs-unified-top-card__primary-description-container .tvm__text, .jobs-unified-top-card__bullet, .topcard__flavor--bullet')).slice(0, 240);
    const descriptionNode = first('#job-details, .jobs-description__content, .description__text') ||
      [...document.querySelectorAll('.description__text')].find(visible);
    const captured = visible(descriptionNode) ? jobDescription(descriptionNode) : {description:'',description_html:'',description_truncated:false};
    const posted = panel.querySelector('time[itemprop="datePosted"], meta[itemprop="datePosted"], time[data-test-job-posted-date]');
    const rawDate = posted?.getAttribute('datetime') || posted?.getAttribute('content') || '';
    let datePosted = '';
    if (/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:\d{2})?)?$/.test(rawDate)) {
      const day = rawDate.slice(0,10), value = new Date(rawDate), calendar = new Date(day + 'T00:00:00Z');
      if (Number.isFinite(value.getTime()) && Number.isFinite(calendar.getTime()) && calendar.toISOString().slice(0,10) === day && (rawDate.length === 10 || Number(rawDate.slice(11,13)) < 24)) datePosted = day;
    }
    if (!role || !company) loading('The company or role has not loaded.');
    return {url, role, company, company_url:jobCompanyURL(panel,company), location:locationText, date_posted:datePosted, ...captured};
  }
  function jobLink(value) {
    try {
      const url = new URL(value, location.href);
      const match = url.pathname.match(/^\/jobs\/view\/(?:[^/]*-)?([0-9]{1,24})\/?$/);
      return url.origin === 'https://www.linkedin.com' && !url.username && !url.password && match ? url.origin + '/jobs/view/' + match[1] : '';
    } catch { return ''; }
  }
  function readModernJob(url) {
    const workspace = document.querySelector('main#workspace');
    if (!workspace) return null;
    const id = url.split('/').at(-1);
    const abouts = [...workspace.querySelectorAll('[componentkey="JobDetails_AboutTheJob_' + id + '"]')].filter(visible);
    const title = [...workspace.querySelectorAll('a[href]')].find(link => visible(link) && jobLink(link.href) === url && text(link));
    if (abouts.length !== 1 || !title) return null;
    let header = title;
    for (let step=0;step<12 && header && header !== workspace;step++,header=header.parentElement) {
      const companies = [...new Set([...header.querySelectorAll('a[href*="/company/"]')].filter(visible).map(text).filter(Boolean))];
      if (!companies.length) continue;
      if (companies.length !== 1) return null;
      const role = compact(String(title.innerText || '').split('\n')[0]).replace(/\s*\(Verified job\)\s*$/i,'').slice(0,240);
      if (!role) return null;
      const paragraphs = [...header.querySelectorAll('p')], titleParagraph = title.closest('p'), index = paragraphs.indexOf(titleParagraph);
      const where = index >= 0 ? text(paragraphs[index+1]).split(/\s*·\s*/)[0].slice(0,240) : '';
      const captured = jobDescription(abouts[0]);
      if (!captured.description.replace(/^About the job\b\s*/i,'').trim()) return null;
      return {url,role,company:companies[0].slice(0,200),company_url:jobCompanyURL(header,companies[0]),location:where,date_posted:'',...captured};
    }
    return null;
  }
  function jobDescription(root) {
    // Derive both representations from the same passive DOM. In modern pages
    // the aria-hidden "… more" button can sit before benefits, not at the end.
    // Keeping it in innerText but dropping it from HTML invalidated all rich text.
    const allowed = new Set(['p','div','h1','h2','h3','h4','h5','h6','ul','ol','li','strong','b','em','i','br','blockquote']);
    const blocked = new Set(['button','script','style','svg','math','iframe','object','template','form','noscript','select','textarea','input']);
    const blocks = new Set(['p','div','h1','h2','h3','h4','h5','h6','ul','ol','li','blockquote']);
    const escape = value => value.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    const weight = value => value === 'bold' ? 700 : Number.parseInt(value || '400',10);
    let count=0;
    function visit(node,depth=0) {
      if (++count > 4000 || depth > 32) throw Error('The job description is too complex to capture.');
      if (node.nodeType === 3) return {plain:node.nodeValue || '',html:escape(node.nodeValue || '')};
      if (node.nodeType !== 1) return {plain:'',html:''};
      const tag=String(node.tagName || '').toLowerCase(), style=getComputedStyle(node);
      if (blocked.has(tag) || node.hasAttribute?.('hidden') || node.getAttribute?.('aria-hidden') === 'true' || style.display === 'none' || style.visibility === 'hidden') return {plain:'',html:''};
      const children=[...node.childNodes].map(child=>visit(child,depth+1));
      let plain=children.map(child=>child.plain).join(''), html=children.map(child=>child.html).join('');
      const parentStyle=node.parentElement ? getComputedStyle(node.parentElement) : {};
      if (!['strong','b'].includes(tag) && !/^h[1-6]$/.test(tag) && weight(style.fontWeight) >= 600 && weight(parentStyle.fontWeight) < 600) html='<strong>'+html+'</strong>';
      if (!['em','i'].includes(tag) && style.fontStyle === 'italic' && parentStyle.fontStyle !== 'italic') html='<em>'+html+'</em>';
      const role=node.getAttribute?.('role');
      const mapped = role === 'list' ? 'ul' : role === 'listitem' ? 'li' : allowed.has(tag) ? tag : style.display === 'block' ? 'div' : '';
      if (mapped === 'br') return {plain:'\n',html:'<br>'};
      if (mapped) html='<'+mapped+'>'+html+'</'+mapped+'>';
      if ((blocks.has(mapped) || blocks.has(tag)) && plain && !plain.endsWith('\n')) plain+='\n';
      return {plain,html};
    }
    const parts=[...root.childNodes].map(node=>visit(node));
    const plain=parts.map(part=>part.plain).join('').replace(/\r\n?/g,'\n').replace(/[\t ]+\n/g,'\n').replace(/\n[\t ]+/g,'\n').replace(/\n{3,}/g,'\n\n').trim();
    const html=parts.map(part=>part.html).join('');
    const more=[...root.querySelectorAll('button')].some(button=>visible(button) && /^(?:(?:show|see)\s+|(?:…|\.\.\.)\s*)?more$/i.test(text(button)));
    return {description:plain.slice(0,20000),description_html:html.length <= 80000 ? html : '',description_truncated:more || plain.length > 20000};
  }
  function jobScope() {
    if (location.origin !== 'https://www.linkedin.com' || !/^\/jobs\/search(?:-results)?\/?$/.test(location.pathname)) throw Error('Open a LinkedIn Jobs search.');
    const problem = issue(); if (problem) throw Error(problem);
    return [...document.querySelectorAll('.jobs-search-results-list, .jobs-search__results-list, .scaffold-layout__list, [componentkey="SearchResultsMainContent"]')].find(visible);
  }
  function jobScroller(scope) {
    return [scope, ...document.querySelectorAll('.jobs-search-results-list, .scaffold-layout__list')]
      .find(value => value && visible(value) && value.contains(scope) && value.clientHeight > 0 && value.scrollHeight > value.clientHeight + 5) || scope;
  }
  function jobNextButton(scope) {
    if (scope?.getAttribute?.('componentkey') === 'SearchResultsMainContent') {
      return [...scope.querySelectorAll('button')].filter(visible).find(button =>
        /^(next|next page|seterusnya)$/i.test(compact(button.getAttribute('aria-label') || button.innerText)) &&
        button.parentElement?.querySelector('ul button[aria-label^="Page "]')) || null;
    }
    const containers = [...document.querySelectorAll('.jobs-search-pagination, .jobs-search-results-list .artdeco-pagination, .scaffold-layout__list .artdeco-pagination')].filter(visible);
    for (const container of containers) {
      const buttons = [...container.querySelectorAll('button')].filter(visible);
      const next = buttons.find(button => button.matches('.jobs-search-pagination__button--next, .artdeco-pagination__button--next') || /^(view next page|next|next page|seterusnya)$/i.test(compact(button.getAttribute('aria-label') || button.innerText)));
      if (next) return next;
      const current = buttons.find(button => ['page','true'].includes(button.getAttribute('aria-current')) || button.matches('.jobs-search-pagination__indicator-button--active'));
      const number = value => Number(compact(value?.getAttribute('aria-label') || value?.innerText).match(/^(?:Page\s+)?(\d+)$/i)?.[1] || 0);
      if (current && number(current)) return buttons.find(button => number(button) === number(current) + 1) || null;
    }
    return null;
  }
  function readJobSearch() {
    const scope = jobScope(), jobs = [], seen = new Set();
    const mainText = text(scope || document.querySelector('main')).slice(0,3000);
    const empty = /no (?:matching )?(?:jobs|results)(?: found)?|couldn.t find any jobs|(?:^|[^\w.,])0 jobs\b/i.test(mainText);
    if (!scope) return {loading:!empty,empty,jobs,signature:'',hasNext:false,atBottom:true};
    if (scope.getAttribute?.('componentkey') === 'SearchResultsMainContent') {
      for (const card of scope.querySelectorAll('[role="button"][componentkey^="job-card-component-ref-"]')) {
        const id = card.getAttribute('componentkey')?.match(/^job-card-component-ref-([0-9]{1,24})$/)?.[1];
        if (!id || !visible(card)) continue;
        const url = 'https://www.linkedin.com/jobs/view/' + id;
        const identities = [...card.querySelectorAll('[componentkey^="job-card-component-ref-"]')].map(value => value.getAttribute('componentkey'));
        const links = [...card.querySelectorAll('a[href]')].map(value => jobLink(value.href)).filter(Boolean);
        if (seen.has(url) || identities.some(value => value !== 'job-card-component-ref-' + id) || links.some(value => value !== url)) continue;
        const paragraphs = [...card.querySelectorAll('p')];
        if (!visible(paragraphs[0]) || !visible(paragraphs[1])) continue;
        const role = compact(String(paragraphs[0].innerText || '').split('\n')[0]).replace(/\s*\(Verified job\)\s*$/i,'').slice(0,240);
        const company = text(paragraphs[1]).slice(0,200), where = text(paragraphs[2]).slice(0,240);
        if (!role || !company) continue;
        seen.add(url); jobs.push({url,role,company,location:where,date_posted:'',description:jobSummary(card).slice(0,6500),description_truncated:true});
        if (jobs.length >= 40) break;
      }
    }
    for (const link of scope.querySelectorAll('a[href]')) {
      if (jobs.length >= 40) break;
      const url = jobLink(link.href);
      if (!url || seen.has(url) || !visible(link)) continue;
      const card = link.closest('.jobs-search-results__list-item, .job-card-container, .job-card-list, .base-search-card, li');
      if (!visible(card)) continue;
      const identities = new Set([...card.querySelectorAll('a[href]')].map(value => jobLink(value.href)).filter(Boolean));
      if (identities.size !== 1) continue;
      const first = selector => [...card.querySelectorAll(selector)].find(visible);
      const roleNode = first('.job-card-list__title--link, .job-card-list__title, .base-search-card__title, .job-search-card__title, .job-card-container__link') || link;
      const role = compact(String(roleNode.innerText || '').split('\n')[0]).slice(0,240);
      const company = text(first('.job-card-container__primary-description, .artdeco-entity-lockup__subtitle, .base-search-card__subtitle, .job-card-container__company-name')).slice(0,200);
      if (!role || !company) continue;
      const where = text(first('.job-card-container__metadata-item, .artdeco-entity-lockup__caption, .job-search-card__location')).slice(0,240);
      const posted = first('time[datetime]')?.getAttribute('datetime') || '';
      const validDate = /^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:\d{2})?)?$/.test(posted) && Number.isFinite(new Date(posted).getTime()) && (posted.length === 10 || Number(posted.slice(11,13)) < 24);
      const day = validDate ? posted.slice(0,10) : '';
      const calendar = new Date(day + 'T00:00:00Z');
      const datePosted = day && Number.isFinite(calendar.getTime()) && calendar.toISOString().slice(0,10) === day ? day : '';
      seen.add(url); jobs.push({url,role,company,location:where,date_posted:datePosted,description:jobSummary(card).slice(0,6500),description_truncated:true});
      if (jobs.length >= 40) break;
    }
    const scroller = jobScroller(scope), next = jobNextButton(scope);
    return {url:location.href,jobs,empty:!jobs.length && empty,loading:!jobs.length && !empty,signature:jobs.map(row => row.url).join('|'),
      hasNext:!!next && !disabled(next),atBottom:!scroller.clientHeight || scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 5};
  }
  function scrollJobSearch(signature) {
    const snapshot = readJobSearch();
    if (!signature || snapshot.signature !== signature) throw Error('The job search changed before scrolling.');
    if (snapshot.atBottom) return false;
    const target = jobScroller(jobScope());
    target.scrollBy({top:Math.max(300,target.clientHeight * .85),behavior:'instant'}); return true;
  }
  function nextJobSearch(signature) {
    const snapshot = readJobSearch();
    if (!signature || snapshot.signature !== signature) throw Error('The job search changed before paging.');
    const button = jobNextButton(jobScope());
    if (!button || disabled(button)) return false;
    button.click(); return true;
  }
  function jobSearchContext() {
    jobScope();
    const header = document.querySelector('[componentkey="searchResultsHeaderComponent"]');
    const locationLabel = el => /^location(?:\s|$)/i.test(compact(el.getAttribute('aria-label')));
    const locations = header ? [...header.querySelectorAll('[role="button"][aria-expanded]')].filter(el => visible(el) &&
      (locationLabel(el) || [...el.querySelectorAll('[aria-label]')].some(label => visible(label) && locationLabel(label)))).map(text).filter(Boolean) : [];
    const fields = [...document.querySelectorAll('.jobs-search-box__location input, input[aria-label*="location" i], input[aria-label*="City" i]')].filter(visible).map(el => compact(el.value)).filter(Boolean);
    const values = [...new Set([...locations,...fields])];
    return {location:values.length === 1 ? values[0].slice(0,240) : ''};
  }
  function readJobPick(expected) {
    if (/^\/jobs\/search(?:-results)?\/?$/.test(location.pathname)) {
      const row = readJobSearch().jobs.find(value => value.url === expected);
      if (!row) throw Error('This ad is no longer in the visible results.');
      try { return readJob(expected); } catch { return row; }
    }
    return readJob(expected);
  }
  function jobTargets() {
    if (/^\/jobs\/search(?:-results)?\/?$/.test(location.pathname)) {
      const scope = jobScope(), snapshot = readJobSearch();
      return snapshot.jobs.map(row => {
        const id = row.url.split('/').at(-1);
        const keyed = [...scope.querySelectorAll('[role="button"][componentkey="job-card-component-ref-' + id + '"]')].find(card => {
          const paragraphs = [...card.querySelectorAll('p')];
          return visible(card) && visible(paragraphs[0]) && visible(paragraphs[1]) &&
            compact(String(paragraphs[0].innerText || '').split('\n')[0]).replace(/\s*\(Verified job\)\s*$/i,'').slice(0,240) === row.role && text(paragraphs[1]).slice(0,200) === row.company &&
            [...card.querySelectorAll('[componentkey^="job-card-component-ref-"]')].every(value => value.getAttribute('componentkey') === 'job-card-component-ref-' + id) &&
            [...card.querySelectorAll('a[href]')].map(value => jobLink(value.href)).filter(Boolean).every(value => value === row.url);
        });
        const link = keyed ? null : [...scope.querySelectorAll('a[href]')].find(value => {
          const card = value.closest('.jobs-search-results__list-item, .job-card-container, .job-card-list, .base-search-card, li');
          return jobLink(value.href) === row.url && visible(card) && [...card.querySelectorAll('a[href]')].map(link => jobLink(link.href)).filter(Boolean).every(url => url === row.url);
        });
        return {url:row.url,element:keyed || link?.closest('.jobs-search-results__list-item, .job-card-container, .job-card-list, .base-search-card, li')};
      }).filter(value => value.element && visible(value.element));
    }
    const match = location.pathname.match(/^\/jobs\/view\/(?:[^/]*-)?([0-9]{1,24})\/?$/), ids = new URLSearchParams(location.search).getAll('currentJobId');
    const id = match ? match[1] : /^\/jobs(?:\/collections\/[^/]+)?\/?$/.test(location.pathname) && ids.length === 1 ? ids[0] : '';
    if (!/^[0-9]{1,24}$/.test(id)) return [];
    const url = 'https://www.linkedin.com/jobs/view/' + id;
    readJob(url);
    return [{url,element:document.querySelector('main') || document.body,floating:true}];
  }
  function companyURL(value) {
    try {
      const u = new URL(value);
      const match = u.pathname.match(/^\/company\/([A-Za-z0-9_-]+)(?:\/.*)?$/);
      return u.origin === 'https://www.linkedin.com' && !u.username && !u.password && match ? u.origin+'/company/'+match[1]+'/' : '';
    } catch { return ''; }
  }
  function jobCompanyURL(scope, company) {
    const urls = [...new Set([...scope.querySelectorAll('a[href*="/company/"]')].filter(n=>visible(n) && text(n) === company).map(n=>companyURL(n.href)).filter(Boolean))];
    return urls.length === 1 ? urls[0] : '';
  }
  const normalized = value => compact(value).toLocaleLowerCase();
  function readHRCompany(expected, company) {
    const problem = issue(); if (problem) throw Error(problem);
    if (companyURL(location.href) !== expected || !/\/people\/?$/.test(location.pathname)) throw Error('The company page changed.');
    const heading = [...document.querySelectorAll('main h1, h1')].find(visible);
    if (!heading) return {loading:true};
    if (normalized(text(heading)) !== normalized(company)) throw Error('The company page does not match the saved ad company.');
    // Scope to the company header, excluding suggested/affiliated companies.
    const scope = heading.closest('section, .org-top-card') || heading.parentElement?.parentElement;
    const ids = [...new Set([...(scope?.querySelectorAll('a[href]') || [])].filter(visible).map(link=>{
      try {
        const u = new URL(link.href), ids = JSON.parse(u.searchParams.get('currentCompany'));
        return u.origin === 'https://www.linkedin.com' && /^\/search\/results\/people\/?$/.test(u.pathname) &&
          Array.isArray(ids) && ids.length === 1 && /^[0-9]{1,24}$/.test(ids[0]) ? ids[0] : '';
      } catch { return ''; }
    }).filter(Boolean))];
    return ids.length === 1 ? {company_id:ids[0]} : {loading:true};
  }
  function hrToolbar() { return document.querySelector('[componentkey="SearchResults_SearchResultsFilterBar"], [role="toolbar"], .search-reusables__filters-bar'); }
  function hrCountryOpen(country) {
    assertPage('standard','search');
    const toolbar = hrToolbar();
    const button = [...(toolbar?.querySelectorAll('button') || [])].find(n=>visible(n) && /^(?:Filter by )?Locations$/i.test(n.getAttribute('aria-label') || text(n)));
    if (!button) throw Error('LinkedIn location controls are not recognized.');
    button.click();
    return true;
  }
  function hrCountryType(country) {
    assertPage('standard','search');
    const field = [...document.querySelectorAll('input[placeholder="Add a location"], input[aria-label="Add a location"]')].find(visible);
    if (!field) return false;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(field,country);
    field.dispatchEvent(new Event('input',{bubbles:true})); return true;
  }
  function hrCountryPick(country) {
    assertPage('standard','search');
    const list = [...document.querySelectorAll('[role="listbox"]')].find(visible);
    const choices = [...(list?.querySelectorAll('button') || [])].filter(n=>visible(n) && normalized(text(n)) === normalized(country));
    if (choices.length !== 1) return false;
    choices[0].click(); return true;
  }
  function hrCountryApply(country) {
    assertPage('standard','search');
    const toolbar = hrToolbar();
    const selected = [...(toolbar?.querySelectorAll('input[type="checkbox"], [role="checkbox"]') || [])].filter(n=>visible(n) && (n.checked || n.getAttribute('aria-checked') === 'true') && normalized(n.getAttribute('aria-label')) === normalized(country));
    const actions = [...(toolbar?.querySelectorAll('a, button') || [])].filter(n=>visible(n) && text(n) === 'Show results');
    if (selected.length !== 1 || actions.length !== 1) return false;
    actions[0].click(); return true;
  }
  function readHRSearch(company, country, keywords) {
    assertPage('standard','search');
    const toolbar = hrToolbar();
    const labels = [...(toolbar?.querySelectorAll('input[type="checkbox"], [role="checkbox"]') || [])].filter(n=>visible(n) && (n.checked || n.getAttribute('aria-checked') === 'true')).map(n=>normalized(n.getAttribute('aria-label') || text(n)));
    if (!labels.includes(normalized(company)) || country && !labels.includes(normalized(country))) return {loading:true};
    const scope = document.querySelector('main [role="region"][aria-label="Primary content"]') || document.querySelector('main');
    if (!scope) return {loading:true};
    const cards = [...scope.querySelectorAll('[componentkey^="SearchResults_"] [role="listitem"], [role="list"] > [role="listitem"], li.reusable-search__result-container, .entity-result')].filter(visible);
    const people = [], seen = new Set();
    for (const card of cards) {
      const paragraphs = [...card.querySelectorAll('p')].filter(visible);
      const nameLink = paragraphs[0]?.querySelector('a[href*="/in/"]') || card.querySelector('.entity-result__title-text a[href*="/in/"]');
      const url = profileURL(nameLink?.href);
      const name = text(nameLink).slice(0,200);
      const title = text(paragraphs[1] || card.querySelector('.entity-result__primary-subtitle')).slice(0,500);
      const where = text(paragraphs[2] || card.querySelector('.entity-result__secondary-subtitle')).slice(0,240);
      if (!url || !name || !title || seen.has(url)) continue;
      seen.add(url);
      const matched = keywords.split(',').map(compact).filter(word=>word && new RegExp('(?:^|[^a-z0-9])'+word.replace(/[.*+?^${}()|[\]\\]/g,'\\$&').replace(/\s+/g,'\\s+')+'(?:$|[^a-z0-9])','i').test(title));
      if (matched.length) people.push({url,name,title,location:where,matched:matched.join(', ')});
      if (seen.size >= 40) break;
    }
    const empty = /\b(?:no results|no people found|0 results)\b/i.test(text(scope));
    if (!seen.size && !empty) return {loading:true};
    const next = hrNextButton();
    return {people,signature:[...seen].join('|'),empty,hasNext:!!next && !next.disabled && next.getAttribute('aria-disabled') !== 'true'};
  }
  function hrNextButton() {
    return nextButton() || [...(document.querySelector('main')?.querySelectorAll('button') || [])].find(button=>visible(button) && /^(next|next page)$/i.test(button.getAttribute('aria-label') || text(button)) && button.parentElement?.querySelector('ul button[aria-label^="Page "]'));
  }
  function prepareHRJoined(expectedURL) {
    assertPage('', 'profile');
    if (profileURL(location.href) !== expectedURL) throw Error('The HR profile identity changed.');
    const main=document.querySelector('main'); if (!main) return false;
    const experience=main.querySelector('[componentkey^="profileCardsExperienceOnly"], #experience');
    if (experience) experience.scrollIntoView({block:'start',behavior:'instant'});
    else main.scrollBy({top:Math.min(main.clientHeight || 600,900),behavior:'instant'});
    return true;
  }
  function readHRJoined(expectedURL, expectedCompany, companyId) {
    assertPage('', 'profile');
    if (profileURL(location.href) !== expectedURL || !companyURL(expectedCompany) || !/^[0-9]{1,24}$/.test(companyId)) throw Error('The HR profile identity changed.');
    const main = document.querySelector('main');
    const heading = [...document.querySelectorAll('main h2, h2')].find(n=>visible(n) && text(n) === 'Experience');
    if (!main || !heading) return {loading:true};
    // Modern company groups have a stable entity key; legacy groups live in
    // the Experience section. Never scan About, activity, education or captions
    // in free-form role descriptions for dates.
    const scope = heading.getAttribute('componentkey') === 'ProfileNullStateCardAnchor_Experience' ? heading.parentElement?.parentElement :
      document.querySelector('main #experience')?.closest('section');
    if (!scope) return {joined:''};
    const selector = '[componentkey^="entity-collection-item-"], li.artdeco-list__item';
    const cards = [...scope.querySelectorAll(selector)].filter(n=>visible(n) && !n.parentElement?.closest?.(selector));
    if (!cards.length) return {loading:true};
    const months = ['january','february','march','april','may','june','july','august','september','october','november','december'];
    const date = value => {
      const match = compact(value).match(/^(?:([A-Za-z]+) )?((?:19|20)\d{2})$/);
      if (!match) return null;
      const month = match[1] ? months.findIndex(name=>[name,name.slice(0,3),'september' === name ? 'sept' : name].includes(match[1].toLowerCase()))+1 : 0;
      if (match[1] && !month) return null;
      return {value:match[2]+(month ? '-'+String(month).padStart(2,'0') : ''), month, year:Number(match[2]), order:Number(match[2])*12+(month || 1)};
    };
    const ranges = words => {
      const match = compact(words).match(/^((?:[A-Za-z]+ )?(?:19|20)\d{2})\s*[-–—]\s*(Present|(?:[A-Za-z]+ )?(?:19|20)\d{2})(?:\s*·.*)?$/i);
      if (!match) return null;
      const start=date(match[1]), current=/^present$/i.test(match[2]), end=current ? null : date(match[2]);
      return start && (current || end && end.order >= start.order) ? {start,end,current} : null;
    };
    const matches = [];
    for (const card of cards) {
      const links = [...card.querySelectorAll('a[href*="/company/"]')].filter(n=>visible(n) && [expectedCompany,'https://www.linkedin.com/company/'+companyId+'/'].includes(companyURL(n.href)));
      if (!links.length) continue;
      // An expandable group may hide the actual first role. A current role's
      // date alone must not be presented as the company joining date.
      if ([...card.querySelectorAll('a, button')].some(n=>visible(n) && /(?:show|see) all|more (?:positions|roles|experiences)/i.test(text(n)))) continue;
      const linked = n=>[...n.querySelectorAll('a[href*="/company/"]')].some(a=>visible(a) && [expectedCompany,'https://www.linkedin.com/company/'+companyId+'/'].includes(companyURL(a.href)));
      const roles=[...card.querySelectorAll('ul > li, [role="list"] > [role="listitem"]')].filter(n=>visible(n) && linked(n));
      if (roles.some(n=>![...n.querySelectorAll('a[href*="/company/"] p, .pvs-entity__caption-wrapper')].filter(visible).some(n=>ranges(text(n))))) continue;
      const observed = links.flatMap(n=>[...n.querySelectorAll('p, .pvs-entity__caption-wrapper')].filter(visible).map(n=>ranges(text(n))).filter(Boolean));
      // Legacy date captions can sit beside the company link, within the same
      // bounded Experience item, rather than inside that link.
      if (!observed.length && card.matches?.('li.artdeco-list__item')) {
        observed.push(...[...card.querySelectorAll('.pvs-entity__caption-wrapper')].filter(visible).map(n=>ranges(text(n))).filter(Boolean));
      }
      const unique = [...new Map(observed.map(r=>[r.start.value+'|'+(r.current?'present':r.end.value),r])).values()];
      const current = unique.filter(r=>r.current);
      if (current.length > 1) return {joined:''};
      if (current.length !== 1) continue;
      let first=current[0].start;
      // Walk only directly adjacent/overlapping roles in this current group.
      // A gap (or imprecise end date) cannot prove continuity after rejoining.
      let complete=true;
      for (const role of unique.filter(r=>!r.current).sort((a,b)=>b.start.order-a.start.order)) {
        if (role.start.order < first.order) {
          if (!first.month || !role.end.month || role.end.order < first.order-1) { complete=false; break; }
          first=role.start;
        }
      }
      if (complete) matches.push(first.value);
    }
    return {joined:matches.length === 1 ? matches[0] : ''};
  }
  function nextHRSearch(signature, company, country, keywords) {
    const snapshot = readHRSearch(company,country,keywords);
    if (snapshot.loading || !signature || snapshot.signature !== signature) throw Error('The HR results changed before paging.');
    const button = hrNextButton(); if (!snapshot.hasNext || !button) return false;
    button.click(); return true;
  }
  globalThis.SourcerReader = {readSearch, next, search, readProfile, profileURL, readJob, readJobSearch, nextJobSearch, scrollJobSearch, jobSearchContext, readJobPick, jobTargets,
    readHRCompany, hrCountryOpen, hrCountryType, hrCountryPick, hrCountryApply, readHRSearch, nextHRSearch, readHRJoined, prepareHRJoined};
})();

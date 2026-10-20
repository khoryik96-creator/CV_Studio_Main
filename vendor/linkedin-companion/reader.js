/* Runs only in Chrome's isolated extension world. No network or credentials. */
(() => {
  const compact = value => String(value || '').replace(/\s+/g, ' ').trim();
  const visible = el => !!el && !!el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const text = el => compact(el?.innerText || '');
  function jobSummary(card) {
    const value = text(card), controls = text(card.querySelector?.('[data-cvstudio-job-controls]'));
    return controls && value.endsWith(controls) ? value.slice(0,-controls.length).trim() : value;
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
    const description = visible(descriptionNode) ? String(descriptionNode.innerText || '').trim() : '';
    const posted = panel.querySelector('time[itemprop="datePosted"], meta[itemprop="datePosted"], time[data-test-job-posted-date]');
    const rawDate = posted?.getAttribute('datetime') || posted?.getAttribute('content') || '';
    let datePosted = '';
    if (/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:\d{2})?)?$/.test(rawDate)) {
      const day = rawDate.slice(0,10), value = new Date(rawDate), calendar = new Date(day + 'T00:00:00Z');
      if (Number.isFinite(value.getTime()) && Number.isFinite(calendar.getTime()) && calendar.toISOString().slice(0,10) === day && (rawDate.length === 10 || Number(rawDate.slice(11,13)) < 24)) datePosted = day;
    }
    if (!role || !company) loading('The company or role has not loaded.');
    const sourceHTML = visible(descriptionNode) ? String(descriptionNode.innerHTML || '') : '';
    return {url, role, company, location:locationText, date_posted:datePosted, description:description.slice(0, 20000),
      description_html:sourceHTML.length <= 80000 ? sourceHTML : '', description_truncated:description.length > 20000};
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
      const about = abouts[0]; let description = String(about.innerText || '').trim(), truncated = false;
      for (const button of about.querySelectorAll('button')) {
        const label = text(button);
        if (/^(show|see) (more|less)$/i.test(label) && description.endsWith(label)) {
          description = description.slice(0,-label.length).trim(); truncated ||= /more$/i.test(label);
        }
      }
      if (!description.replace(/^About the job\b\s*/i,'').trim()) return null;
      const html = String(about.innerHTML || '');
      return {url,role,company:companies[0].slice(0,200),location:where,date_posted:'',description:description.slice(0,20000),
        description_html:html.length <= 80000 ? html : '',description_truncated:truncated || description.length > 20000};
    }
    return null;
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
    const locations = header ? [...header.querySelectorAll('[role="button"][aria-expanded]')].filter(visible).map(text).filter(Boolean) : [];
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
  globalThis.SourcerReader = {readSearch, next, search, readProfile, profileURL, readJob, readJobSearch, nextJobSearch, scrollJobSearch, jobSearchContext, readJobPick, jobTargets};
})();

/* Runs only in Chrome's isolated extension world. No network or credentials. */
(() => {
  const compact = value => String(value || '').replace(/\s+/g, ' ').trim();
  const visible = el => !!el && !!el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const text = el => compact(el?.innerText || '');
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
    if (/unusual activity|temporarily restricted|security verification|you.ve reached.*(?:search|commercial).*limit/i.test(text(document.querySelector('main') || document.body).slice(0, 5000))) return 'LinkedIn is showing an access or usage restriction. The agent will stop.';
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
  globalThis.SourcerReader = {readSearch, next, search, readProfile, profileURL};
})();

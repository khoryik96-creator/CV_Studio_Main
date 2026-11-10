/* One LinkedIn Jobs search, read page by page through the companion. Job Leads'
 * search and the Signed clients pull both use it, so they keep the same page,
 * scroll and loading bounds and the same checks on every result. */
(() => {
  'use strict';
  function jobLink(value) {
    try {
      if (value.length > 2048 || value.includes('\\')) return '';
      const u = new URL(value.trim());
      if (u.protocol !== 'https:' || !['www.linkedin.com', 'linkedin.com', 'my.linkedin.com', 'sg.linkedin.com'].includes(u.hostname) || u.username || u.password || u.port) return '';
      const view = u.pathname.match(/^\/jobs\/view\/(?:[^/]*-)?([0-9]{1,24})\/?$/), ids = u.searchParams.getAll('currentJobId');
      const id = view ? view[1] : /^\/jobs(?:\/search(?:-results)?|\/collections\/[^/]+)?\/?$/.test(u.pathname) && ids.length === 1 ? ids[0] : '';
      return /^[0-9]{1,24}$/.test(id) ? 'https://www.linkedin.com/jobs/view/' + id : '';
    } catch { return ''; }
  }
  // The checked fields of one results page; anything unexpected is skipped.
  function companyLink(value) {
    try {
      if (typeof value !== 'string' || value.length > 2048 || /[\\\x00-\x20\x7f]/.test(value)) return '';
      const u = new URL(value), match = u.pathname.match(/^\/company\/([A-Za-z0-9_-]+)(?:\/(?:about|jobs|people))?\/?$/);
      const result = match ? 'https://www.linkedin.com/company/'+match[1]+'/' : '';
      return u.protocol === 'https:' && ['www.linkedin.com','linkedin.com','my.linkedin.com','sg.linkedin.com'].includes(u.hostname) &&
        !u.username && !u.password && !u.port && result.length <= 300 ? result : '';
    } catch { return ''; }
  }
  function rows(snapshot) {
    if (!snapshot || !Array.isArray(snapshot.jobs) || snapshot.jobs.length > 40) throw Error('The job-search results could not be confirmed.');
    const result = [];
    for (const raw of snapshot.jobs) {
      const url = jobLink(raw?.url || '');
      if (!url || url !== raw.url || typeof raw.company !== 'string' || !raw.company.trim() || typeof raw.role !== 'string' || !raw.role.trim()) continue;
      result.push({url,company:raw.company.slice(0,200),...(companyLink(raw.company_url)?{company_url:companyLink(raw.company_url)}:{}),role:raw.role.slice(0,240),location:typeof raw.location === 'string' ? raw.location.slice(0,240) : '',
        date_posted:typeof raw.date_posted === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(raw.date_posted) ? raw.date_posted : '',
        date_posted_estimate:typeof raw.date_posted_estimate === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(raw.date_posted_estimate) ? raw.date_posted_estimate : '',
        description:typeof raw.description === 'string' ? raw.description.slice(0,6500) : ''});
    }
    return result;
  }
  const pause = () => new Promise(resolve => setTimeout(resolve,350));
  // keep(snapshot) receives every read page; check() throws to stop; page(i)
  // reports a finished page; full() ends paging early.
  async function walk({rpc, run, tab, pages, check, keep, page, full, waiting}) {
    const number = snapshot => Number.isInteger(snapshot?.page) && snapshot.page > 0 && snapshot.page <= 10000 ? snapshot.page : 0;
    const read = async (previous = null, currentPage = 0) => {
      let settled = '';
      const deadline = Date.now() + 45000;
      // Bound elapsed time and reads; an in-flight RPC keeps its own timeout.
      // Retry only observations:
      // a slow/unchanged page must never cause a second Next click.
      for (let attempt=0;attempt<130 && Date.now()<deadline;attempt++) {
        check();
        const result = await rpc('read',{run_id:run,tab_id:tab,method:'readJobSearch',values:[]});
        check();
        if (result && !result.loading) {
          if (result.empty) return result;
          const before = number(previous), after = number(result);
          if (currentPage && after && after !== currentPage || before && after && after !== before && after !== before+1)
            throw Error('The job results changed to a different page. Start a new search. Ads already found are kept.');
          // Prefer the visible active-page marker. Card signatures alone cannot
          // distinguish repeated promoted ads or a virtualized old-page redraw.
          const ready = !previous || (before ? after === before+1 : result.signature !== previous.signature);
          const key = after + '|' + result.signature;
          if (ready && (!currentPage || after === currentPage)) {
            if (!before || settled === key) return result;
            settled = key; // let a changed pager/cards settle over two reads
          } else settled = '';
        } else settled = '';
        if (attempt % 10 === 9) waiting?.(previous ? 'next' : 'results');
        await pause();
      }
      throw Error(previous ? 'LinkedIn did not finish loading the next results page. Ads already found are kept.' :
        'LinkedIn did not finish loading the job results. Ads already found are kept.');
    };
    let previous = null;
    for (let index=0;index<pages;index++) {
      let snapshot = await read(previous);
      if (snapshot.empty) break;
      keep(snapshot);
      for (let scroll=0;scroll<8 && !snapshot.atBottom;scroll++) {
        check();
        const moved = await rpc('read',{run_id:run,tab_id:tab,method:'scrollJobSearch',values:[snapshot.signature]});
        check();
        if (typeof moved !== 'boolean') throw Error('LinkedIn is still loading before scrolling. Start the search again. Ads already found are kept.');
        if (!moved) break;
        await pause(); snapshot = await read(null, number(snapshot));
        if (snapshot.empty) break;
        keep(snapshot);
      }
      page?.(index);
      if (index+1 === pages || !snapshot.hasNext || full()) break;
      previous = snapshot; check();
      const advanced = await rpc('read',{run_id:run,tab_id:tab,method:'nextJobSearch',values:[previous.signature]});
      check();
      // Older companions can return a loading envelope without dispatching the
      // click. Never mistake that truthy object for successful navigation.
      if (typeof advanced !== 'boolean') throw Error('LinkedIn is still loading before changing pages. Start the search again. Ads already found are kept.');
      if (!advanced) break;
    }
  }
  window.cvStudioJobSearch = {jobLink, companyLink, rows, walk};
})();

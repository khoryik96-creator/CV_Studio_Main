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
  function rows(snapshot) {
    if (!snapshot || !Array.isArray(snapshot.jobs) || snapshot.jobs.length > 40) throw Error('The job-search results could not be confirmed.');
    const result = [];
    for (const raw of snapshot.jobs) {
      const url = jobLink(raw?.url || '');
      if (!url || url !== raw.url || typeof raw.company !== 'string' || !raw.company.trim() || typeof raw.role !== 'string' || !raw.role.trim()) continue;
      result.push({url,company:raw.company.slice(0,200),role:raw.role.slice(0,240),location:typeof raw.location === 'string' ? raw.location.slice(0,240) : '',
        date_posted:typeof raw.date_posted === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(raw.date_posted) ? raw.date_posted : '',
        description:typeof raw.description === 'string' ? raw.description.slice(0,6500) : ''});
    }
    return result;
  }
  const pause = () => new Promise(resolve => setTimeout(resolve,350));
  // keep(snapshot) receives every read page; check() throws to stop; page(i)
  // reports a finished page; full() ends paging early.
  async function walk({rpc, run, tab, pages, check, keep, page, full}) {
    const read = async (previous = '') => {
      for (let attempt=0;attempt<35;attempt++) {
        check();
        const result = await rpc('read',{run_id:run,tab_id:tab,method:'readJobSearch',values:[]});
        check();
        if (!result?.loading && (!previous || result.empty || result.signature !== previous)) return result;
        await pause();
      }
      throw Error('The job-search page did not finish changing. The ads already found are kept.');
    };
    let previous = '';
    for (let index=0;index<pages;index++) {
      let snapshot = await read(previous);
      if (snapshot.empty) break;
      keep(snapshot);
      for (let scroll=0;scroll<8 && !snapshot.atBottom;scroll++) {
        check();
        const moved = await rpc('read',{run_id:run,tab_id:tab,method:'scrollJobSearch',values:[snapshot.signature]});
        check(); if (!moved) break;
        await pause(); snapshot = await read(); keep(snapshot);
      }
      page?.(index);
      if (index+1 === pages || !snapshot.hasNext || full()) break;
      previous = snapshot.signature; check();
      if (!await rpc('read',{run_id:run,tab_id:tab,method:'nextJobSearch',values:[previous]})) break;
    }
  }
  window.cvStudioJobSearch = {jobLink, rows, walk};
})();

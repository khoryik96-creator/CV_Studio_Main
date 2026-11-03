"""Optional Chromium check of native company Jobs controls on fictional pages.

Run from the repository root. All browser requests are intercepted; no account
or network access is used. Requires Playwright and Chromium.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
root='https://www.linkedin.com/company/fictional-client/'
source=Path('vendor/linkedin-companion/reader.js').read_text()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CVSTUDIO_CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 page=b.new_page();page.route('**/*',lambda r:r.fulfill(status=200,content_type='text/html',body='<main><h1>Fictional Client</h1>'+page.fixture_body+'</main>'))
 for label,body,ready in [
  ('native','<section><h2>Jobs</h2><button onclick="location.href=\'/jobs/search/?f_C=4242\'">See all jobs</button></section>',True),
  ('aria','<section><h2>Jobs</h2><button aria-label="View all 123 jobs at Fictional Client" onclick="location.href=\'/jobs/search/?f_C=4242\'">↗</button></section>',True),
  ('ambiguous','<section><button>See all jobs</button><button>View all jobs</button></section>',False),
  ('recommendation','<section><a href="/company/other/">Other Employer</a><button>See all jobs</button></section>',False),
  ('hidden','<section><button hidden>See all jobs</button></section>',False)]:
  page.fixture_body=body;page.goto(root+'jobs/');page.add_script_tag(content=source)
  assert bool(page.evaluate('(root)=>SourcerReader.readCompanyJobsID(root).jobs_action',root))==ready,label
  if ready:
   with page.expect_navigation():assert page.evaluate('(root)=>SourcerReader.openCompanyJobs(root)',root)
   assert page.url=='https://www.linkedin.com/jobs/search/?f_C=4242',label
  else:
   assert not page.evaluate('(root)=>SourcerReader.openCompanyJobs(root)',root)
   assert page.url==root+'jobs/'
 print('Chromium native company Jobs fallback passed: visible and aria-label buttons navigate to the exact filter; hidden, ambiguous and other-employer controls remain untouched. All navigation intercepted with fictional pages.')
 b.close()

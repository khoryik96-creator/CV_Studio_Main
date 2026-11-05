"""Bounded JobStreet detail checks for Lead Finder; no inferred employer/expiry."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from time import monotonic
import json
import re
from urllib.parse import urlsplit, urljoin, parse_qsl

from bs4 import BeautifulSoup
import requests

HOSTS = {'my.jobstreet.com','sg.jobstreet.com','id.jobstreet.com','ph.jobstreet.com',
         'www.jobstreet.com.my','www.jobstreet.com.sg','www.jobstreet.com.ph','www.jobstreet.co.id',
         'jobstreet.com','www.jobstreet.com'}
MAX_BYTES = 2 * 1024 * 1024


def jobstreet_id(url):
    try:
        u=urlsplit(str(url or ''))
        if u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password or u.port:
            return ''
        m=re.fullmatch(r'/job/([0-9]{1,24})/?',u.path)
        ids=[value for key,value in parse_qsl(u.query,keep_blank_values=True) if re.fullmatch(r'job[_-]?id',key,re.I)]
        if ids and (any(not re.fullmatch(r'[0-9]{1,24}',value) for value in ids) or len(set(ids))!=1):return ''
        if m:return m[1] if not ids or ids[0]==m[1] else ''
        return ids[0] if u.path.rstrip('/')=='/jobs' and ids else ''
    except ValueError:
        return ''


def jobstreet_detail_url(url):
    ident=jobstreet_id(url)
    return 'https://'+urlsplit(url).hostname+'/job/'+ident if ident else ''


def is_jobstreet(url):
    try:return 'jobstreet' in (urlsplit(str(url or '')).hostname or '')
    except ValueError:return False


def parse_jobstreet(html, url, now=None):
    """Only detail-page evidence can establish employer and current availability."""
    ident=jobstreet_id(url)
    if not ident or not isinstance(html,str) or len(html.encode('utf-8'))>MAX_BYTES:
        return {'state':'unverified'}
    now=now or datetime.now(timezone.utc)
    soup=BeautifulSoup(html,'html.parser')
    canonical=soup.select_one('link[rel="canonical"]')
    if canonical and jobstreet_id(canonical.get('href')) != ident:
        return {'state':'unverified'}
    raw_scripts=[str(script.string or script.get_text()) for script in soup.select('script[type="application/ld+json"]')[:16]]
    main=soup.select_one('main') or soup
    for tag in main.select('script,style,nav,footer'):tag.decompose()
    # Expiry is explicit, never guessed from ad age or a role mentioning expiry.
    notices=main.select('[data-automation*="expired" i], [data-automation*="unavailable" i], [role="alert"], h1, h2, h3')
    expired=re.compile(r'(?:this (?:job|ad|advertisement|job ad|job advertisement) (?:has expired|is no longer (?:available|advertised)|is expired)|(?:job|advertisement) (?:has expired|no longer available)|no longer accepting applications)',re.I)
    if any(expired.search(n.get_text(' ',strip=True)) for n in notices):return {'state':'expired'}
    # Some portal layouts render the notice as an ordinary paragraph above the ad.
    if expired.search(main.get_text(' ',strip=True)):return {'state':'expired'}
    postings=[]
    def walk(v,depth=0):
        if depth>8:return
        if isinstance(v,list):
            for x in v[:100]:walk(x,depth+1)
        elif isinstance(v,dict):
            types=v.get('@type',[]);types=[types] if isinstance(types,str) else types
            if isinstance(types,list) and 'JobPosting' in types:postings.append(v)
            else:
                for x in list(v.values())[:100]:
                    if isinstance(x,(dict,list)):walk(x,depth+1)
    for raw in raw_scripts:
        if len(raw)>512*1024:continue
        try:walk(json.loads(raw))
        except (ValueError,TypeError):continue
    found=[]
    for post in postings:
        ref=post.get('url')
        if ref and jobstreet_id(urljoin(url,str(ref)))!=ident:continue
        identifier=post.get('identifier');identifier=identifier.get('value') if isinstance(identifier,dict) else identifier
        if identifier is not None and str(identifier).isdigit() and str(identifier)!=ident:continue
        if post.get('validThrough'):
            try:
                deadline=datetime.fromisoformat(str(post['validThrough']).replace('Z','+00:00'))
                if deadline.tzinfo is None:deadline=deadline.replace(tzinfo=timezone.utc)
                if (deadline.date()<now.date() if re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(post['validThrough'])) else deadline<=now):return {'state':'expired'}
            except ValueError:return {'state':'unverified'}
        org=post.get('hiringOrganization') or {};company=org.get('name') if isinstance(org,dict) else ''
        title=post.get('title');body=post.get('description')
        if not all(isinstance(x,str) and x.strip() for x in (company,title,body)):continue
        if not ref and not (identifier is not None and str(identifier)==ident):
            header=soup.select_one('[data-automation="job-detail-title"]')
            advertiser=soup.select_one('[data-automation="advertiser-name"], [data-automation="job-detail-advertiser"]')
            if not header or not advertiser or header.get_text(' ',strip=True)!=title.strip() or advertiser.get_text(' ',strip=True)!=unescape(company).strip():continue
        locations=post.get('jobLocation') or {};locations=locations[0] if isinstance(locations,list) and locations else locations
        address=locations.get('address',{}) if isinstance(locations,dict) else {}
        country=address.get('addressCountry','') if isinstance(address,dict) else ''
        if isinstance(country,dict):country=country.get('name','')
        country={'MY':'Malaysia','SG':'Singapore','ID':'Indonesia','PH':'Philippines'}.get(country,country) if isinstance(country,str) else ''
        location=', '.join(dict.fromkeys(str(x) for x in [address.get('addressLocality',''),address.get('addressRegion',''),country] if isinstance(x,str) and x)) if isinstance(address,dict) else ''
        found.append({'state':'active','company_name':unescape(company).strip()[:200],'title':title.strip()[:200],
                      'location':location[:300],'published_date':str(post.get('datePosted') or '')[:100],
                      'snippet':BeautifulSoup(body,'html.parser').get_text(' ',strip=True)[:3000]})
    if len(found)==1:return found[0]
    if found:return {'state':'unverified'}
    employer=soup.select_one('[data-automation="advertiser-name"], [data-automation="job-detail-advertiser"]')
    title=soup.select_one('[data-automation="job-detail-title"]')
    body=soup.select_one('[data-automation="jobAdDetails"]')
    if employer and title and body and employer.get_text(strip=True) and title.get_text(strip=True) and body.get_text(strip=True):
        return {'state':'active','company_name':employer.get_text(' ',strip=True)[:200],
                'title':title.get_text(' ',strip=True)[:200],'snippet':body.get_text(' ',strip=True)[:3000]}
    return {'state':'unverified'}


def parse_extracted_jobstreet(raw, url):
    evidence=parse_jobstreet(raw,url)
    if evidence['state']!='unverified' or not isinstance(raw,str) or not jobstreet_id(url):return evidence
    if len(raw)>MAX_BYTES:return {'state':'unverified'}
    plain=BeautifulSoup(raw,'html.parser').get_text(' ',strip=True) if '<' in raw else raw
    if re.search(r"this (?:job|ad|job ad|advertisement) (?:has expired|is no longer (?:available|advertised))|no longer accepting applications",plain,re.I):return {'state':'expired'}
    # Tavily Extract returns Markdown/text. Only the primary ad header with its
    # adjacent advertiser + View all jobs control is accepted, not body mentions.
    match=re.search(r'^# ([^\n]{3,200})\n+([^\n]{2,200})\n+[^\n]*View all jobs',raw,re.I|re.M)
    if not match or len(raw)<300 or not re.search(r'\bPosted\b',raw,re.I) or not re.search(r'\b(?:Quick apply|Apply now|Apply)\b',raw,re.I):return {'state':'unverified'}
    company=unescape(re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',match[2])).strip(' *_')
    if not company or company.lower() in {'view all jobs','location','malaysia','singapore','penang island'}:return {'state':'unverified'}
    return {'state':'active','company_name':company,'title':match[1].strip(),'snippet':raw[match.end():][:3000]}


def fetch_jobstreet(url):
    """No credentials, redirects, arbitrary hosts or unbounded response bodies."""
    url=jobstreet_detail_url(url)
    if not url:return ''
    response=None
    try:
        response=requests.get(url,timeout=(3,6),allow_redirects=False,stream=True,
                              headers={'User-Agent':'Mozilla/5.0','Accept':'text/html'},auth=lambda request:request,cookies={})
        if response.status_code in (404,410):return '<main><h1>This job is no longer available</h1></main>'
        if response.status_code!=200 or jobstreet_id(response.url)!=jobstreet_id(url):return ''
        if 'text/html' not in response.headers.get('Content-Type','').lower():return ''
        data=bytearray();deadline=monotonic()+8
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data)>MAX_BYTES or monotonic()>deadline:return ''
        return bytes(data).decode('utf-8',errors='replace')
    except requests.RequestException:return ''
    finally:
        if response is not None:response.close()


class JobstreetVerifier:
    def __init__(self, provider, fetch=fetch_jobstreet, extract=None):
        self.provider=provider;self.fetch=fetch;self.extract=extract;self.cache={};self.calls=0;self.extract_failed=False

    def check_many(self, urls):
        wanted={jobstreet_id(url):jobstreet_detail_url(url) for url in urls if jobstreet_id(url) and jobstreet_id(url) not in self.cache}
        # At most 12 unique ads per request; unknown/unverified ads are excluded.
        wanted=dict(list(wanted.items())[:max(0,12-len(self.cache))])
        def check(item):
            ident,url=item
            try:return ident,parse_jobstreet(self.fetch(url),url)
            except Exception:return ident,{'state':'unverified'}
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.cache.update(pool.map(check,wanted.items()))
        missing=[url for ident,url in wanted.items() if self.cache[ident]['state']=='unverified']
        if missing and self.extract and self.provider.get('provider')=='tavily' and self.provider.get('api_key') and self.calls<1:
            self.calls+=1
            try:
                data=self.extract(self.provider['api_key'],missing)
                for result in data.get('results') or []:
                    ident=jobstreet_id(result.get('url'))
                    if ident not in wanted or wanted[ident] not in missing:continue
                    raw=result.get('raw_content')
                    if isinstance(raw,str):self.cache[ident]=parse_extracted_jobstreet(raw,wanted[ident])
            except Exception:
                # Keep failed evidence unavailable and expose a safe diagnostic;
                # provider error text can contain credentials or request data.
                self.extract_failed=True

    def results(self, rows):
        self.check_many([r.get('url') for r in rows if isinstance(r,dict)])
        out=[];removed=0
        for row in rows:
            url=row.get('url') if isinstance(row,dict) else ''
            if not is_jobstreet(url):out.append(row);continue
            evidence=self.cache.get(jobstreet_id(url),{'state':'unverified'})
            if evidence['state']!='active':removed+=1;continue
            out.append({**row,**{k:v for k,v in evidence.items() if k!='state' and v},'jobstreet_verified':True})
        warning=f'Skipped {removed} expired or unconfirmed JobStreet ad(s).' if removed else ''
        if removed and self.extract_failed:warning+=' JobStreet extraction was unavailable. Check the selected search provider or retry later.'
        return out,warning

    def leads(self, parsed):
        rows=parsed.get('companies') or []
        verified,warning=self.results([{**r,'url':r.get('job_url')} for r in rows if isinstance(r,dict)])
        parsed['companies']=[{k:v for k,v in r.items() if k!='url'} for r in verified]
        for row in parsed['companies']:
            if is_jobstreet(row.get('job_url')) and row.get('jobstreet_verified'):
                row['company']=row['company_name'];row['matched_role']=row['title']
                if row.get('location'):row['country']=row['region']=row['location']
        return parsed,warning

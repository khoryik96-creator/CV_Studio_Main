"""Bounded, unauthenticated public LinkedIn job pages; no AI or browser session."""
from __future__ import annotations

import json
from datetime import datetime
import re
import threading
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
import requests

from cvstudio_job_leads import JobLeadsError, job_url, format_description

MAX_HTML_BYTES = 4 * 1024 * 1024


def _posted_date(value):
    """Keep the source's calendar date; never infer it from relative age."""
    if not isinstance(value, str) or len(value) > 40:
        return ''
    value = value.strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:\d{2})?)?', value):
        return ''
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).date().isoformat()
    except ValueError:
        return ''


def _without_credentials(request):
    # A truthy explicit auth callback also prevents requests from consulting
    # the user's .netrc for this public read.
    request.headers.pop('Authorization', None)
    request.headers.pop('Cookie', None)
    return request


def _unavailable():
    return JobLeadsError("LinkedIn's public job details could not be read. Try the Chrome companion below for ads requiring sign-in, or enter the details manually.", 422, "JOB_AD_UNAVAILABLE")


def _text(value, limit):
    if not isinstance(value, str):
        return ""
    soup = BeautifulSoup(value, "html.parser")
    for node in soup.select('script, style, button, .show-more-less-html__button'):
        node.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()[:limit]


def _description(value):
    if not isinstance(value, str):
        return ""
    soup = BeautifulSoup(value, "html.parser")
    for node in soup.select('script, style, button, .show-more-less-html__button'):
        node.decompose()
    return soup.get_text("\n", strip=True)


def _postings(value, depth=0):
    if depth > 8:
        return []
    if isinstance(value, list):
        return [row for item in value[:100] for row in _postings(item, depth + 1)]
    if not isinstance(value, dict):
        return []
    types = value.get('@type', [])
    if types == 'JobPosting' or isinstance(types, list) and 'JobPosting' in types:
        return [value]
    return _postings(value.get('@graph'), depth + 1)


def _location(value):
    locations = value if isinstance(value, list) else [value]
    result = []
    for item in locations[:10]:
        address = item.get('address') if isinstance(item, dict) else None
        if not isinstance(address, dict):
            continue
        parts = []
        for key in ['addressLocality', 'addressRegion', 'addressCountry']:
            part = address.get(key)
            if isinstance(part, dict):
                part = part.get('name')
            part = _text(part, 240)
            if part and part not in parts:
                parts.append(part)
        if parts:
            result.append(', '.join(parts))
    return '; '.join(dict.fromkeys(result))[:240]


def parse_public_job(html, expected_url):
    expected = job_url(expected_url)
    if not expected or not isinstance(html, bytes) or len(html) > MAX_HTML_BYTES:
        raise _unavailable()
    soup = BeautifulSoup(html, 'html.parser', from_encoding='utf-8')
    if soup.select_one('iframe[src*="captcha"], #captcha-internal, [data-test-id="captcha-internal"]'):
        raise _unavailable()
    identities = [job_url(node.get('href', '')) for node in soup.select('link[rel="canonical"]')]
    identities += [job_url(node.get('content', '')) for node in soup.select('meta[property="og:url"]')]
    if any(identity and identity != expected for identity in identities):
        raise _unavailable()
    canonical = expected in identities
    expected_id = expected.rsplit('/', 1)[-1]
    postings = []
    for node in soup.select('script[type="application/ld+json"]')[:16]:
        raw = node.string or node.get_text()
        if len(raw) > 512 * 1024:
            continue
        try:
            postings += _postings(json.loads(raw))
        except (ValueError, RecursionError):
            continue
    candidates = []
    for posting in postings:
        identity = posting.get('identifier')
        identity = identity.get('value') if isinstance(identity, dict) else identity
        identity = str(identity) if isinstance(identity, (str, int)) and not isinstance(identity, bool) else ''
        posting_url = job_url(posting.get('url'))
        if posting_url and posting_url != expected or identity.isdigit() and identity != expected_id:
            continue
        if not (posting_url == expected or identity == expected_id or canonical and len(postings) == 1):
            continue
        company = posting.get('hiringOrganization')
        company = company.get('name') if isinstance(company, dict) else ''
        role, company = _text(posting.get('title'), 240), _text(company, 200)
        if role and company:
            words = _description(posting.get('description'))
            candidates.append({'url':expected, 'company':company, 'role':role,
                               'location':_location(posting.get('jobLocation')),
                               'date_posted':_posted_date(posting.get('datePosted')),
                               'description':words[:20000], 'description_rich':format_description(words[:20000], posting.get('description', '')),
                               'description_truncated':len(words) > 20000})
    if candidates:
        if len({(row['company'], row['role']) for row in candidates}) != 1:
            raise _unavailable()
        return candidates[0]
    # Public markup fallback is confined to the canonical job's top card.
    # Search headers and recommended jobs are never used as field guesses.
    card = soup.select_one('.top-card-layout') if canonical and not postings else None
    if card:
        role = card.select_one('.top-card-layout__title')
        company = card.select_one('.topcard__org-name-link')
        location = card.select_one('.topcard__flavor--bullet')
        description = soup.select_one('.description__text')
        posted = card.select_one('time[itemprop="datePosted"], meta[itemprop="datePosted"], time[data-test-job-posted-date]')
        if role and company:
            words = _description(str(description)) if description else ''
            return {'url':expected, 'role':_text(str(role),240), 'company':_text(str(company),200),
                    'location':_text(str(location),240) if location else '',
                    'date_posted':_posted_date(posted.get('datetime') or posted.get('content')) if posted else '',
                    'description':words[:20000], 'description_rich':format_description(words[:20000], str(description)) if description else [],
                    'description_truncated':len(words)>20000}
    raise _unavailable()


class PublicLinkedInJobs:
    def __init__(self, get=None, clock=None):
        self.get = get or requests.get
        self.clock = clock or time.monotonic
        self.slots = threading.BoundedSemaphore(2)

    def read(self, value):
        expected = job_url(value)
        if not expected:
            raise JobLeadsError('Paste a valid LinkedIn job ad link.')
        if not self.slots.acquire(blocking=False):
            raise JobLeadsError('Job details are being read in another window. Wait a moment, then try again.', 409, 'JOB_AD_BUSY')
        try:
            current = expected
            deadline = self.clock() + 20
            for _ in range(4):
                if self.clock() >= deadline:
                    raise _unavailable()
                # Each hop is a fresh unauthenticated request: cookies, tokens
                # and user-supplied tracking/query values are never forwarded.
                with self.get(current, allow_redirects=False, stream=True,
                              headers={'Accept':'text/html'}, auth=_without_credentials,
                              timeout=(5, 8)) as response:
                    if response.status_code == 429:
                        raise JobLeadsError('LinkedIn is temporarily limiting public job reads. Try again later, or open this CV Studio address in Chrome and connect the companion to read an ad you can view there. Saved ads can still be opened below.', 429, 'JOB_AD_RATE_LIMITED')
                    if response.status_code in {301,302,303,307,308}:
                        target = urljoin(current, response.headers.get('Location', ''))
                        if job_url(target) != expected or not urlsplit(target).path.startswith('/jobs/view/'):
                            raise _unavailable()
                        u = urlsplit(target)
                        current = urlunsplit((u.scheme, u.netloc, u.path, '', ''))
                        continue
                    if response.status_code != 200 or not response.headers.get('Content-Type', '').lower().startswith('text/html'):
                        raise _unavailable()
                    length = response.headers.get('Content-Length', '')
                    if length.isdigit() and int(length) > MAX_HTML_BYTES:
                        raise _unavailable()
                    chunks, size = [], 0
                    for chunk in response.iter_content(chunk_size=16384):
                        size += len(chunk)
                        if size > MAX_HTML_BYTES or self.clock() >= deadline:
                            raise _unavailable()
                        chunks.append(chunk)
                    return parse_public_job(b''.join(chunks), expected)
            raise _unavailable()
        except (requests.RequestException, OSError, ValueError) as error:
            if isinstance(error, JobLeadsError):
                raise
            raise _unavailable() from None
        finally:
            self.slots.release()

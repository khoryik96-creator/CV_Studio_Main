"""Bounded local people dashboards. No provider transport or credentials."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import re
import threading
import unicodedata
from urllib.parse import urlsplit, unquote


class PeopleError(Exception):
    pass


def _folder(value, allow_unfiled=False):
    """A candidate folder name, under the same rules as Job Leads folders."""
    from cvstudio_job_leads import JobLeadsError, clean_folder
    try:
        return clean_folder(value, allow_unfiled)
    except JobLeadsError as exc:
        raise PeopleError(str(exc)) from None


def workbook(rows, fields, title):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    book = Workbook()
    sheet = book.active
    sheet.title = title
    sheet.append(list(fields.values()))
    for cell in sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='16365D')
    for number, row in enumerate(rows, 2):
        for column, key in enumerate(fields, 1):
            value = row.get(key, '')
            if isinstance(value, list):
                value = '\n'.join(value)
            cell = sheet.cell(number, column, re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', str(value)))
            cell.data_type = 's'
            cell.alignment = Alignment(vertical='top', wrap_text=True)
    sheet.freeze_panes = 'B2'
    sheet.auto_filter.ref = sheet.dimensions
    for column, key in enumerate(fields, 1):
        sheet.column_dimensions[get_column_letter(column)].width = 48 if key in {'evidence', 'unknowns', 'notes', 'brief'} else 28
    output = BytesIO()
    book.save(output)
    return output.getvalue()


CANDIDATE_FIELDS = {'name':'Name', 'title':'Headline / title', 'location':'Location',
    'url':'LinkedIn URL', 'score':'Evidence match / 100', 'read':'Profile read',
    'evidence':'Supporting evidence', 'unknowns':'Still unknown', 'notes':'Notes',
    'brief':'Search brief', 'saved_at':'Last assessed (UTC)'}
CANDIDATE_EXPORT_FIELDS = {**CANDIDATE_FIELDS, 'folder':'Folder', 'shortlisted':'Shortlisted', 'deleted':'In Trash'}
HR_FIELDS = {'name':'Name','title':'Position','company':'Company','location':'Observed location',
    'country':'Country (scan filter)','employment':'Employment','url':'LinkedIn URL',
    'matched':'Matched HR keywords','job_url':'Source ad','scanned_at':'Last scan (UTC)','employment_confirmation':'Date confirmation'}


def _filter(rows, query, selected, field, fields):
    if not isinstance(query,str) or len(query)>240 or not isinstance(selected,str) or len(selected)>240:
        raise PeopleError('Use a shorter dashboard search.')
    query=query.strip().lower()
    return [row for row in rows if (not selected or row.get(field)==selected) and
            (not query or query in ' '.join(' '.join(row.get(k,[])) if isinstance(row.get(k),list) else str(row.get(k,'')) for k in fields).lower())]


CANDIDATE_SORTS = {'saved_at', 'score', 'name', 'location', 'read'}
CANDIDATE_READS = {'', 'Profile detail', 'Search card'}
_SORT_SPACE = ' \t\n\r\f\v\u00a0'


def _sort_key(value):
    """Case-, accent- and number-aware sort key ("Candidate 9" before "Candidate 10").

    people-dashboards.js applies exactly the same steps, so the dashboard and
    its Excel export list candidates in the same order. An empty key is blank.
    """
    text = unicodedata.normalize('NFKD', str(value if value is not None else '')).strip(_SORT_SPACE).lower()
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return tuple(int(part) if index % 2 else part for index, part in enumerate(re.split(r'([0-9]+)', text)))


def _score(row):
    value = row.get('score')
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def filter_candidates(rows, query='', search='', *, min_score=0, read='', sort='saved_at', order='desc',
                      folder='*', shortlisted=False):
    """Dashboard rows in the chosen order. Blank values always sort last.

    ``folder`` is '*' for every folder, '' for Unfiled, '!trash' for Trash or
    one folder's name; Trash only appears when it is chosen.
    """
    if (type(min_score) is not int or not 0 <= min_score <= 100 or not isinstance(read, str) or read not in CANDIDATE_READS or
            not isinstance(sort, str) or sort not in CANDIDATE_SORTS or order not in ('asc', 'desc') or
            not isinstance(shortlisted, bool) or not isinstance(folder, str)):
        raise PeopleError('Choose a valid candidate sort or filter.')
    if folder not in {'*', '!trash'}:
        folder = _folder(folder, allow_unfiled=True)
    rows=[row for row in _filter(rows,query,search,'run_id',CANDIDATE_FIELDS)
          if (_score(row) or 0)>=min_score and (not read or row.get('read')==read)
          and (row.get('deleted') is True if folder == '!trash' else row.get('deleted') is not True and (folder == '*' or row.get('folder', '') == folder))
          and (not shortlisted or row.get('shortlisted') is True)]
    if sort == 'score':
        key, blank = _score, lambda row: _score(row) is None
    else:
        key = lambda row: _sort_key(row.get(sort))
        blank = lambda row: key(row) == ('',)
    # sorted() is stable, so equal values keep the newest-first archive order.
    return sorted([row for row in rows if not blank(row)],key=key,reverse=order=='desc')+[row for row in rows if blank(row)]


def candidate_export_rows(rows):
    """Readable folder, shortlist and Trash columns for the Excel export."""
    return [{**row, 'folder': row.get('folder') or 'Unfiled', 'shortlisted': 'Yes' if row.get('shortlisted') is True else '',
             'deleted': 'Yes' if row.get('deleted') is True else ''} for row in rows]


def filter_people(rows, query='', company='', email=''):
    """The HR people dashboard filters; email is '' (all), 'none' or 'found'."""
    if email not in {'', 'none', 'found'}:
        raise PeopleError('Choose a supported email filter.')
    rows = _filter(rows,query,company,'company_id',HR_FIELDS)
    return rows if not email else [row for row in rows if ((row.get('email_result') or {}).get('state') == 'found') == (email == 'found')]


def employment_label(person):
    def label(s):
        if not s:
            return ''
        return s if len(s)==4 else ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(s[5:])-1]+' '+s[:4]
    start=label(person.get('joined',''))
    return start+(' to Present' if person.get('current') is True else ' to '+label(person['left']) if person.get('current') is False else '') if start else 'Not confirmed' if person.get('employment_status')=='not_shown' else 'Not checked'


# How the owner organised a candidate; a new assessment keeps every field.
_ORGANISATION = {'folder': '', 'shortlisted': False, 'deleted': False, 'deleted_at': ''}
# Folder names shown by the dashboard itself, so they cannot also be folders.
_BUILT_IN_FOLDERS = {'unfiled', 'trash', 'all folders'}


class SourcerCandidates:
    MAX_ROWS = 5000
    MAX_BYTES = 8 * 1024 * 1024
    MAX_FOLDERS = 200

    def __init__(self, *, load, save):
        self.load, self.save = load, save
        self.lock = threading.RLock()

    @staticmethod
    def _size(value):
        # Keys starting with '_' are added by the secure loader (for example
        # '_storage'), never saved, so reads and writes measure the same bytes.
        return len(json.dumps({key: item for key, item in value.items() if not str(key).startswith('_')}).encode())

    def _load(self):
        """Saved rows and folders. Version 1 is a dashboard nobody organised;
        version 2 adds folders, shortlist and Trash, so an older CV Studio
        refuses it instead of rewriting it without them."""
        try:
            value = self.load()
            if not value:
                return {}, []
            rows, folders = value['rows'], value.get('folders', [])
            if (type(value['version']) is not int or value['version'] not in (1, 2) or not isinstance(rows, dict) or len(rows) > self.MAX_ROWS or
                    self._size(value) > self.MAX_BYTES or not isinstance(folders, list) or
                    len(folders) > self.MAX_FOLDERS or len(set(map(str, folders))) != len(folders) or
                    any(not isinstance(name, str) or not name or _folder(name) != name for name in folders)):
                raise ValueError()
            for key, row in rows.items():
                if not re.fullmatch(r'[a-f0-9]{64}', key) or not isinstance(row, dict):
                    raise ValueError()
                for field, limit in {'name':150,'title':500,'location':240,'url':400,'brief':4000,'run_id':32,'saved_at':40,'notes':2000,'read':20}.items():
                    if not isinstance(row.get(field), str) or len(row[field]) > limit or '\x00' in row[field]:
                        raise ValueError()
                if type(row.get('revision')) is not int or row['revision'] < 1 or type(row.get('score')) is not int or not 0 <= row['score'] <= 100:
                    raise ValueError()
                if row['read'] not in {'Search card', 'Profile detail'}:
                    raise ValueError()
                url=urlsplit(row['url'])
                if (url.scheme!='https' or url.netloc!='www.linkedin.com' or url.query or url.fragment or
                        not re.fullmatch(r'/(?:in/[^/]+|talent/(?:hire/)?profile/[^/]+)',url.path) or
                        re.search(r'[\x00-\x20\\]',unquote(url.path)) or not re.fullmatch(r'[a-f0-9]{32}', row['run_id'])):
                    raise ValueError()
                if key != sha256((row['run_id']+'|'+row['url']).encode()).hexdigest():
                    raise ValueError()
                for field, maximum in [('evidence',4), ('unknowns',6)]:
                    if not isinstance(row.get(field),list) or len(row[field]) > maximum or any(not isinstance(s,str) or len(s)>250 for s in row[field]):
                        raise ValueError()
                folder, stamp = row.get('folder', ''), row.get('deleted_at', '')
                if (not isinstance(folder, str) or _folder(folder, allow_unfiled=True) != folder or
                        not isinstance(row.get('shortlisted', False), bool) or not isinstance(row.get('deleted', False), bool) or
                        not isinstance(stamp, str) or len(stamp) > 40):
                    raise ValueError()
            return deepcopy(rows), list(folders)
        except Exception:
            raise PeopleError('Saved candidates could not be read securely. Keep the existing files and check local storage.') from None

    def _write(self, rows, folders):
        organised = bool(folders) or any(row.get(name, default) != default for row in rows.values()
                                         for name, default in _ORGANISATION.items())
        value = {'version': 2 if organised else 1, 'rows': rows, 'folders': folders}
        if len(rows) > self.MAX_ROWS or self._size(value) > self.MAX_BYTES:
            raise PeopleError('The candidate dashboard is full. Export the current search; its results are still shown in Search.')
        try:
            self.save(value)
        except Exception:
            raise PeopleError('Candidates could not be saved to the dashboard. Export the current search before closing it.') from None

    def remember(self, run, candidates, stage):
        with self.lock:
            rows, folders = self._load()
            target = _folder(getattr(run, 'folder', ''), allow_unfiled=True)
            if target and target not in self._folder_names(rows, folders):
                raise PeopleError('The search folder was deleted. Results are still shown in Search; export them before closing.')
            for person in candidates:
                if '\x00' in person['name'] or '\x00' in run.brief:
                    raise PeopleError('This assessment contains unsupported text. Export the current search; existing saved candidates were kept.')
                key = sha256((run.id+'|'+person['url']).encode()).hexdigest()
                old = rows.get(key)
                if old and old['read'] == 'Profile detail' and stage != 'detail':
                    continue
                rows[key] = {key:person.get(key, '') for key in ['name','title','location','url','score','evidence','unknowns']}
                rows[key].update(run_id=run.id, brief=run.brief,
                    read='Profile detail' if stage == 'detail' else 'Search card',
                    saved_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                    notes=old['notes'] if old else '', revision=old['revision']+1 if old else 1)
                # A new assessment keeps how the owner organised this candidate.
                for name, default in _ORGANISATION.items():
                    initial = target if name == 'folder' else default
                    rows[key][name] = old.get(name, default) if old else initial
            if candidates:
                self._write(rows, folders)

    @staticmethod
    def _listed(rows):
        return sorted(({**row,'key':key} for key,row in rows.items()),
                      key=lambda r:(r['saved_at'],r['run_id'],r['score']), reverse=True)

    @staticmethod
    def _folder_names(rows, folders):
        named = set(folders) | {row.get('folder', '') for row in rows.values()}
        # The name itself breaks ties, so the order is the same on every run.
        return sorted(named - {''}, key=lambda name: (_sort_key(name), name))

    def list(self):
        with self.lock:
            return self._listed(self._load()[0])

    def snapshot(self):
        """Candidates and folders from one read of the store."""
        with self.lock:
            rows, folders = self._load()
            return {'candidates': self._listed(rows), 'folders': self._folder_names(rows, folders)}

    def target_folder(self, name):
        """Validate a new search's destination without creating it implicitly."""
        name = _folder(name, allow_unfiled=True)
        if name:
            with self.lock:
                if name not in self._folder_names(*self._load()):
                    raise PeopleError('This candidate folder no longer exists. Choose a folder again before starting.')
        return name

    def note(self, key, revision, notes):
        if not isinstance(key,str) or not re.fullmatch(r'[a-f0-9]{64}',key) or type(revision) is not int or not isinstance(notes,str) or len(notes)>2000 or '\x00' in notes:
            raise PeopleError('Choose a saved candidate and a note of up to 2000 characters.')
        with self.lock:
            rows, folders = self._load()
            if key not in rows or rows[key]['revision'] != revision:
                raise PeopleError('This candidate changed. Copy your note, refresh the dashboard and try again.')
            rows[key].update(notes=notes,revision=revision+1)
            self._write(rows, folders)
            return {**rows[key],'key':key}

    # Organising: folders, shortlist and recoverable Trash, as in Job Leads.

    def folders(self):
        with self.lock:
            return self._folder_names(*self._load())

    def _selected(self, rows, items, allow_empty=False):
        """Selected keys and revisions; every one must still be current."""
        if not isinstance(items, list) or (not items and not allow_empty) or len(items) > self.MAX_ROWS:
            raise PeopleError('Select saved candidates first.')
        expected = {}
        for item in items:
            if (not isinstance(item, dict) or not isinstance(item.get('key'), str) or
                    not re.fullmatch(r'[a-f0-9]{64}', item['key']) or item['key'] in expected or type(item.get('revision')) is not int):
                raise PeopleError('Invalid candidate selection. Refresh the dashboard.')
            expected[item['key']] = item['revision']
        if any(key not in rows or rows[key]['revision'] != revision for key, revision in expected.items()):
            raise PeopleError('A selected candidate changed in another window. Refresh before trying again.')
        return expected

    def create_folder(self, name):
        name = _folder(name)
        if name.casefold() in _BUILT_IN_FOLDERS:
            raise PeopleError('Unfiled, Trash and All folders are built in. Choose another folder name.')
        with self.lock:
            rows, folders = self._load()
            if name not in folders:
                if len(folders) >= self.MAX_FOLDERS:
                    raise PeopleError('You can keep up to 200 candidate folders. Delete one first.')
                self._write(rows, folders + [name])
            return {'folder': name}

    def delete_folder(self, name, items):
        """Remove a folder; its candidates (even in Trash) become Unfiled."""
        name = _folder(name)
        with self.lock:
            rows, folders = self._load()
            inside = {key: row['revision'] for key, row in rows.items() if row.get('folder', '') == name}
            if name not in folders and not inside:
                raise PeopleError('This folder changed in another window. Refresh before trying again.')
            if self._selected(rows, items, allow_empty=True) != inside:
                raise PeopleError('Candidates in this folder changed in another window. Refresh before deleting it.')
            for key in inside:
                rows[key].update(folder='', revision=rows[key]['revision'] + 1)
            self._write(rows, [folder for folder in folders if folder != name])
            return {'changed': len(inside)}

    def move(self, items, name):
        name = _folder(name, allow_unfiled=True)
        with self.lock:
            rows, folders = self._load()
            if name and name not in folders and not any(row.get('folder', '') == name for row in rows.values()):
                raise PeopleError('This folder no longer exists. Refresh and choose a folder.')
            expected = self._selected(rows, items)
            if any(rows[key].get('deleted') for key in expected):
                raise PeopleError('Restore candidates from Trash before moving them.')
            for key in expected:
                rows[key].update(folder=name, revision=rows[key]['revision'] + 1)
            self._write(rows, folders)
            return {'changed': len(expected)}

    def trash(self, items, deleted):
        """Move to recoverable Trash, or restore to the same folder."""
        if not isinstance(deleted, bool):
            raise PeopleError('Choose whether to delete or restore the candidates.')
        with self.lock:
            rows, folders = self._load()
            expected = self._selected(rows, items)
            stamp = datetime.now(timezone.utc).isoformat(timespec='seconds') if deleted else ''
            for key in expected:
                rows[key].update(deleted=deleted, deleted_at=stamp, revision=rows[key]['revision'] + 1)
            self._write(rows, folders)
            return {'changed': len(expected)}

    def shortlist(self, key, revision, value):
        if not isinstance(value, bool):
            raise PeopleError('Choose whether to shortlist this candidate.')
        with self.lock:
            rows, folders = self._load()
            self._selected(rows, [{'key': key, 'revision': revision}])
            if rows[key].get('deleted'):
                raise PeopleError('Restore this candidate from Trash first.')
            rows[key].update(shortlisted=value, revision=revision + 1)
            self._write(rows, folders)
            return {**rows[key], 'key': key}


def hr_people(rows, cached=None):
    """One current saved observation per person/company, with exact action source."""
    def employment_time(person,hr):
        stamp=person.get('employment_checked_at') or hr.get('scanned_at')
        return datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(timezone.utc) if stamp else datetime.min.replace(tzinfo=timezone.utc)
    def merge_employment(target,person,row):
        for name in ('joined','left','current','employment_status','employment_checked_at','employment_confirmed_by_user'):
            target.pop(name,None)
            if name in person:
                target[name]=person[name]
        target.update(employment=employment_label(person),employment_confirmation='User confirmed' if person.get('employment_confirmed_by_user') else 'LinkedIn company link' if person.get('joined') else '',employment_id=row['id'],
                      employment_revision=row['revision'],employment_company_url=row['hr']['company_url'])
    found, employment_times = {}, {}
    for row in sorted(rows, key=lambda r:(r.get('hr') or {}).get('scanned_at',''), reverse=True):
        hr = row.get('hr')
        if row.get('deleted') or not hr:
            continue
        for person in hr['people']:
            key = sha256((hr['company_id']+'|'+person['url'].rstrip('/').lower()).encode()).hexdigest()
            result=cached(row,person) if cached else None
            rank=lambda value:3 if value and value.get('state')=='found' else 2 if value and value.get('state') in {'pending','unconfirmed'} else 1 if value else 0
            if key in found:
                found[key]['ads'] += 1
                if person.get('joined') and (not found[key].get('joined') or employment_time(person,hr)>employment_times[key]):
                    merge_employment(found[key],person,row)
                    employment_times[key]=employment_time(person,hr)
                if rank(result)>rank(found[key]['email_result']):
                    found[key].update(email_result=result,email_id=row['id'],email_revision=row['revision'])
                continue
            found[key] = {**person, 'key':key, 'id':row['id'], 'revision':row['revision'],
                'company':row['company'], 'company_url':hr['company_url'], 'company_id':hr['company_id'],
                'country':hr['country'], 'scanned_at':hr['scanned_at'], 'ads':1,
                'job_url':row['url'], 'folder':row.get('folder',''), 'employment':employment_label(person),
                'email_result':result,'email_id':row['id'],'email_revision':row['revision']}
            merge_employment(found[key],person,row)
            employment_times[key]=employment_time(person,hr)
    return list(found.values())

"""Local business-development leads, isolated from the existing schema-10 DB.

No Flask, browser, AI or network dependencies. Writes are transactional and
revision-checked; duplicate LinkedIn job IDs never overwrite existing notes.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, urlsplit
import uuid

STATUSES = {"new": "New", "to_contact": "To contact", "contacted": "Contacted",
            "follow_up": "Following up", "won": "Won", "closed": "Closed"}
FIELDS = {"url": 2048, "company": 200, "role": 240, "contact": 400,
          "location": 240, "notes": 10000, "description": 20000,
          "status": 20, "follow_up": 10, "date_posted": 10, "folder": 80}
MAX_RECORDS = 5000
MAX_FOLDERS = 5000
MAX_BYTES = 8 * 1024 * 1024
APPLICATION_ID = 0x43564A4C
RICH_TAGS = {"p", "h3", "h4", "ul", "ol", "li", "strong", "em", "br", "blockquote"}


def clean_rich(nodes):
    """A bounded semantic tree, never source HTML, attributes or URLs."""
    count = size = 0
    def visit(items, depth=0):
        nonlocal count, size
        if not isinstance(items, list) or depth > 16 or len(items) > 2000:
            raise JobLeadsError("The formatted job description is too large or invalid.")
        result = []
        for item in items:
            count += 1
            if count > 4000 or not isinstance(item, dict):
                raise JobLeadsError("The formatted job description is too large or invalid.")
            if set(item) == {"text"} and isinstance(item["text"], str) and "\x00" not in item["text"]:
                size += len(item["text"])
                result.append({"text": item["text"]})
            elif set(item) == {"tag", "children"} and isinstance(item["tag"], str) and item["tag"] in RICH_TAGS:
                result.append({"tag": item["tag"], "children": visit(item["children"], depth + 1)})
            else:
                raise JobLeadsError("The formatted job description is invalid.")
            if size > 20000:
                raise JobLeadsError("The formatted job description is too long.")
        return result
    return visit(nodes)


def rich_text(nodes):
    return ''.join(item['text'] if 'text' in item else rich_text(item['children']) for item in nodes)


def format_description(description, source):
    """Keep typography only when it describes exactly the retained plain text."""
    if not isinstance(description, str) or len(description) > 20000 or not isinstance(source, str) or len(source) > 80000:
        raise JobLeadsError("The job description is too large or invalid.")
    class Reader(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.root, self.stack, self.skip = [], [], []
            self.events = 0
        def handle_starttag(self, tag, attrs):
            self.events += 1
            if self.events > 4000 or len(self.stack) > 16 or len(self.skip) > 16:
                raise JobLeadsError("The formatted job description is too complex.")
            if self.skip or tag in {'script','style','svg','math','iframe','object','template','button','form','noscript','select','textarea'}:
                if tag not in {'img','input','meta','link','hr','br','source','wbr'}:
                    self.skip.append(tag)
                return
            mapped = {'b':'strong','i':'em','h1':'h3','h2':'h3','h5':'h4','h6':'h4'}.get(tag, tag)
            if tag not in {'img','input','meta','link','hr','source','wbr'}:
                node = {'tag':mapped if mapped in RICH_TAGS or tag == 'div' else 'span', 'children':[]}
                (self.stack[-1][1]['children'] if self.stack else self.root).append(node)
                if tag != 'br': self.stack.append((tag,node))
        def handle_endtag(self, tag):
            if self.skip:
                if tag in self.skip:
                    self.skip = self.skip[:len(self.skip)-1-self.skip[::-1].index(tag)]
                return
            for offset in range(len(self.stack)-1, -1, -1):
                if self.stack[offset][0] == tag:
                    self.stack = self.stack[:offset]
                    break
        def handle_data(self, text):
            if not self.skip and text:
                (self.stack[-1][1]['children'] if self.stack else self.root).append({'text':text})
    blocks = {'p','h3','h4','ul','ol','blockquote'}
    def normalize(items):
        result = []
        for item in items:
            if 'text' in item:
                result.append(item)
                continue
            children = normalize(item['children'])
            tag = item['tag']
            if tag == 'span':
                result.extend(children)
            elif tag in {'div','p'}:
                # Layout wrappers are transparent around real paragraphs and
                # lists. Only their own inline runs become paragraphs.
                run = []
                def flush():
                    if any(node.get('tag') or node.get('text', '').strip() for node in run):
                        result.append({'tag':'p','children':list(run)})
                    run.clear()
                for child in children:
                    if child.get('tag') in blocks:
                        flush()
                        result.append(child)
                    else:
                        run.append(child)
                flush()
            else:
                result.append({'tag':tag,'children':children})
        return result
    try:
        parser = Reader()
        parser.feed(source)
        value = normalize(parser.root)
        target = re.sub(r'\s+', '', description)
        actual = re.sub(r'\s+', '', rich_text(value))
        if actual != target:
            # The established capture cap keeps only a plain-text prefix. Clip
            # the matching semantic tree too, rather than discarding all its
            # typography. Short/manual mismatches still fail the exact gate.
            if len(description) != 20000 or not actual.startswith(target):
                return []
            remaining = len(target)
            def prefix(items):
                nonlocal remaining
                result = []
                for item in items:
                    if not remaining:
                        break
                    if 'text' in item:
                        text = item['text']
                        count = len(re.sub(r'\s+', '', text))
                        if count > remaining:
                            positions = [m.end() for m in re.finditer(r'\S', text)]
                            text = text[:positions[remaining-1]]
                            count = remaining
                        remaining -= count
                        if text:
                            result.append({'text':text})
                    else:
                        children = prefix(item['children'])
                        if children:
                            result.append({'tag':item['tag'], 'children':children})
                return result
            value = prefix(value)
        value = clean_rich(value)
        return value if re.sub(r'\s+', '', rich_text(value)) == target else []
    except (JobLeadsError, RecursionError):
        return []  # Plain text remains available when markup cannot be retained.


class JobLeadsError(ValueError):
    def __init__(self, message, status=400, code="JOB_LEADS_INVALID"):
        super().__init__(message)
        self.status, self.code = status, code
        self.retryable = status == 503 and code == "JOB_LEADS_STORAGE"


def job_url(value):
    """Canonical identity for a job view link or the selected job in search."""
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    try:
        u = urlsplit(value.strip())
        if (u.scheme != "https" or u.hostname not in {"linkedin.com", "www.linkedin.com", "my.linkedin.com", "sg.linkedin.com"}
                or u.username or u.password or u.port or "\\" in value):
            return ""
        match = re.fullmatch(r"/jobs/view/(?:[^/]*-)?([0-9]{1,24})/?", u.path)
        if match:
            identity = match.group(1)
        elif re.fullmatch(r"/jobs(?:/search(?:-results)?|/collections/[^/]+)?/?", u.path):
            values = parse_qs(u.query).get("currentJobId", [])
            identity = values[0] if len(values) == 1 else ""
        else:
            return ""
        return "https://www.linkedin.com/jobs/view/" + identity if re.fullmatch(r"[0-9]{1,24}", identity) else ""
    except ValueError:
        return ""


def clean_record(raw):
    if not isinstance(raw, dict):
        raise JobLeadsError("Enter the job details first.")
    result = {}
    for key, limit in FIELDS.items():
        value = raw.get(key, "new" if key == "status" else "")
        if not isinstance(value, str) or len(value) > limit or "\x00" in value:
            raise JobLeadsError("A job field is too long or has an invalid value.")
        result[key] = value.strip()
    result["url"] = job_url(result["url"])
    if not result["url"]:
        raise JobLeadsError("Paste a LinkedIn job ad link, such as https://www.linkedin.com/jobs/view/1234567890.")
    if not result["company"] or not result["role"]:
        raise JobLeadsError("Enter both the company and role before saving.")
    if result["status"] not in STATUSES:
        raise JobLeadsError("Choose a valid lead status.")
    result['folder'] = clean_folder(result['folder'], allow_unfiled=True)
    for key, label in [("follow_up", "follow-up date"), ("date_posted", "posting date")]:
        if result[key]:
            try:
                if date.fromisoformat(result[key]).isoformat() != result[key]:
                    raise ValueError()
            except ValueError:
                raise JobLeadsError("Choose a valid " + label + ".") from None
    truncated = raw.get("description_truncated", False)
    if type(truncated) is not bool:
        raise JobLeadsError("The job description excerpt marker is invalid.")
    result["description_truncated"] = truncated
    deleted = raw.get('deleted', False)
    if type(deleted) is not bool:
        raise JobLeadsError("The saved lead state is invalid.")
    result['deleted'] = deleted
    rich = clean_rich(raw.get('description_rich', []))
    result['description_rich'] = rich if re.sub(r'\s+', '', rich_text(rich)) == re.sub(r'\s+', '', result['description']) else []
    if raw.get('hr'):
        result['hr'] = clean_hr(raw['hr'], result['company'])
    return result


def clean_hr(raw, company):
    """Bounded passive public professional evidence; never executable markup."""
    def invalid():
        raise JobLeadsError('The HR search results are invalid. Saved ad details were kept.')
    if not isinstance(raw, dict):
        invalid()
    result = {}
    for key, limit in {'company':200, 'company_url':300, 'company_id':24, 'country':100,
                       'keywords':600, 'source_url':2048, 'scanned_at':40}.items():
        value = raw.get(key, '')
        if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
            invalid()
        result[key] = value.strip()
    if result['company'] != company or not re.fullmatch(r'[0-9]{1,24}', result['company_id']):
        invalid()
    if not re.fullmatch(r'https://www\.linkedin\.com/company/[A-Za-z0-9_-]+/', result['company_url']):
        invalid()
    try:
        url = urlsplit(result['source_url'])
        query = parse_qs(url.query)
        if (url.scheme != 'https' or url.netloc != 'www.linkedin.com' or
                url.path.rstrip('/') != '/search/results/people' or url.fragment or
                set(query) - {'currentCompany','keywords','geoUrn'} or
                len(query.get('currentCompany', [])) != 1 or
                json.loads(query['currentCompany'][0]) != [result['company_id']]):
            invalid()
        geo = query.get('geoUrn', [])
        if result['country']:
            if len(geo) != 1 or not re.fullmatch(r'\["[0-9]{1,24}"\]', geo[0]):
                invalid()
        elif geo:
            invalid()
    except (ValueError, TypeError):
        invalid()
    if result['scanned_at']:
        result['scanned_at'] = _backup_created({'created_at':result['scanned_at']})
    if type(raw.get('complete')) is not bool or not result['keywords']:
        invalid()
    people = raw.get('people')
    if not isinstance(people, list) or len(people) > 100:
        invalid()
    result['complete'], result['people'] = raw['complete'], []
    seen = set()
    for person in people:
        if not isinstance(person, dict):
            invalid()
        entry = {}
        for key, limit in {'name':200,'title':500,'location':240,'url':400,'matched':600,'joined':7}.items():
            value = person.get(key, '')
            if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
                invalid()
            entry[key] = value.strip()
        if entry['joined'] and not re.fullmatch(r'(?:19|20)\d{2}(?:-(?:0[1-9]|1[0-2]))?', entry['joined']):
            invalid()
        if (not entry['name'] or not entry['title'] or not entry['matched'] or
                not re.fullmatch(r'https://www\.linkedin\.com/in/[A-Za-z0-9_%~-]+/?', entry['url'])):
            invalid()
        if entry['url'].rstrip('/') not in seen:
            seen.add(entry['url'].rstrip('/'))
            result['people'].append(entry)
    return result


def clean_folder(value, allow_unfiled=False):
    if (not isinstance(value, str) or len(value) > 80 or
            any(ord(char) < 32 for char in value) or value.strip() in {'*','!trash'}):
        raise JobLeadsError("Use a folder name of up to 80 characters without line breaks.")
    name = value.strip()
    if not name and not allow_unfiled:
        raise JobLeadsError("Enter a folder name.")
    return name


def _selection(items, allow_empty=False):
    if not isinstance(items, list) or (not items and not allow_empty) or len(items) > MAX_RECORDS:
        raise JobLeadsError("Select saved ads first.")
    result = {}
    for item in items:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or
                not re.fullmatch(r'[a-f0-9]{32}', item['id']) or item['id'] in result or type(item.get('revision')) is not int):
            raise JobLeadsError("Invalid saved ad selection. Refresh the list.")
        result[item['id']] = item['revision']
    return result


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _backup_created(raw):
    value = raw.get('created_at')
    if value is None:
        return None
    try:
        if not isinstance(value, str) or len(value) > 40:
            raise ValueError()
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    except (ValueError, OverflowError):
        raise JobLeadsError("A backup creation date is invalid. Your existing records were preserved.") from None


class JobLeadsStore:
    def __init__(self, path):
        self.path = Path(path)

    @staticmethod
    def _verify(connection):
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise JobLeadsError("Job Leads storage needs repair. Preserve its files and restore a verified database backup before retrying.", 503, "JOB_LEADS_CORRUPT")

    def _initialize(self, connection):
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in {0,1,2} or (version and connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID):
            raise JobLeadsError("This Job Leads database requires a compatible CV Studio version. Preserve it before restoring a backup.", 503, "JOB_LEADS_INCOMPATIBLE")
        self._verify(connection)
        if version < 2:
            # A consistent verified backup precedes BOTH initial creation and
            # the additive folder migration. No lead payload is rewritten.
            backup_dir = self.path.parent / "job_leads_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / ("before-v2-" + uuid.uuid4().hex + ".sqlite3")
            with sqlite3.connect(str(backup)) as destination:
                connection.backup(destination)
                self._verify(destination)
            # Re-check under a cross-process lock: another request may have
            # completed initialization while the backup was being created.
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if tables:
                    raise JobLeadsError("This Job Leads database has an unrecognized format. Preserve it and use a compatible backup.", 503, "JOB_LEADS_INCOMPATIBLE")
                connection.execute("CREATE TABLE leads (id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("PRAGMA application_id=" + str(APPLICATION_ID))
            if version < 2:
                connection.execute("CREATE TABLE folders (name TEXT PRIMARY KEY NOT NULL)")
                for row in connection.execute('SELECT * FROM leads'):
                    name = self._record(row)['folder']
                    if name:
                        connection.execute('INSERT OR IGNORE INTO folders VALUES (?)', (name,))
                connection.execute("PRAGMA user_version=2")
            connection.commit()
        if (connection.execute("PRAGMA user_version").fetchone()[0] != 2 or
                connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID):
            raise JobLeadsError("This Job Leads database requires a compatible CV Studio version. Preserve it before restoring a backup.", 503, "JOB_LEADS_INCOMPATIBLE")
        self._verify(connection)

    @contextmanager
    def _connection(self):
        connection = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=5000")
            self._initialize(connection)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        except (sqlite3.Error, OSError) as error:
            code = getattr(error, "sqlite_errorcode", None)
            if isinstance(code, int) and (code & 0xFF) in {sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB, sqlite3.SQLITE_FORMAT}:
                raise JobLeadsError("Job Leads storage is corrupt. Close CV Studio, preserve its database files, and restore a verified database backup before retrying.", 503, "JOB_LEADS_CORRUPT") from None
            raise JobLeadsError("Job Leads could not read or save local data. Check disk space and folder access, close duplicate windows, then retry. Your existing records were preserved.", 503, "JOB_LEADS_STORAGE") from None
        finally:
            if connection is not None:
                if connection.in_transaction:
                    try:
                        connection.rollback()
                    except sqlite3.Error:
                        pass
                connection.close()

    @staticmethod
    def _record(row):
        if row is None:
            raise JobLeadsError("This lead no longer exists. Refresh your list.", 404)
        try:
            return {**clean_record(json.loads(row["payload"])), "id": row["id"], "revision": row["revision"],
                    "created_at": row["created_at"], "updated_at": row["updated_at"]}
        except (ValueError, TypeError):
            raise JobLeadsError("A saved Job Leads record needs repair. Preserve the database and restore a verified database backup.", 503, "JOB_LEADS_CORRUPT") from None

    @staticmethod
    def _check_capacity(connection):
        count, size = connection.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(CAST(payload AS BLOB))),0) FROM leads").fetchone()
        folders, folder_bytes = connection.execute('SELECT COUNT(*), COALESCE(SUM(LENGTH(CAST(name AS BLOB))),0) FROM folders').fetchone()
        if count > MAX_RECORDS or folders > MAX_FOLDERS or size + folder_bytes > MAX_BYTES:
            raise JobLeadsError("Job Leads storage is full (5,000 leads or 8 MB). Export a backup before making further changes.")

    def list(self):
        return self.snapshot()['records']

    def hr_record(self, identity, revision):
        """Read exact saved evidence before an explicitly requested enrichment."""
        _selection([{'id':identity, 'revision':revision}])
        with self._connection() as connection:
            record = self._record(connection.execute('SELECT * FROM leads WHERE id=?', (identity,)).fetchone())
            if record['revision'] != revision or record['deleted'] or not record.get('hr'):
                raise JobLeadsError('The saved HR results changed. Refresh the ad before unlocking an email.', 409, 'JOB_LEADS_CONFLICT')
            return record

    def snapshot(self):
        with self._connection() as connection:
            connection.execute('BEGIN')
            return {'records':[self._record(row) for row in connection.execute("SELECT * FROM leads ORDER BY updated_at DESC, id")],
                    'folders':[row[0] for row in connection.execute('SELECT name FROM folders ORDER BY name')]}

    def create_folder(self, name):
        name = clean_folder(name)
        with self._connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('INSERT OR IGNORE INTO folders VALUES (?)', (name,))
            self._check_capacity(connection)
            connection.commit()
        return {'folder':name}

    def delete_folder(self, name, selection):
        name = clean_folder(name)
        expected = _selection(selection, allow_empty=True)
        with self._connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if not connection.execute('SELECT 1 FROM folders WHERE name=?', (name,)).fetchone():
                raise JobLeadsError('This folder changed in another window. Refresh before trying again.', 409, 'JOB_LEADS_CONFLICT')
            records = [self._record(row) for row in connection.execute('SELECT * FROM leads')]
            selected = [row for row in records if row['folder'] == name]
            if {row['id']:row['revision'] for row in selected} != expected:
                raise JobLeadsError('Ads in this folder changed in another window. Refresh before deleting it.', 409, 'JOB_LEADS_CONFLICT')
            for row in selected:
                row['folder'] = ''
                connection.execute('UPDATE leads SET payload=?,revision=revision+1,updated_at=? WHERE id=?',
                                   (json.dumps(clean_record(row), ensure_ascii=False), _now(), row['id']))
            connection.execute('DELETE FROM folders WHERE name=?', (name,))
            connection.commit()
        return {'changed':len(selected)}

    def move_to_folder(self, selection, name):
        expected = _selection(selection)
        name = clean_folder(name, allow_unfiled=True)
        with self._connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if name and not connection.execute('SELECT 1 FROM folders WHERE name=?', (name,)).fetchone():
                raise JobLeadsError('This folder no longer exists. Refresh and choose a folder.', 409, 'JOB_LEADS_CONFLICT')
            for identity, revision in expected.items():
                current = connection.execute('SELECT * FROM leads WHERE id=?', (identity,)).fetchone()
                if current is None or current['revision'] != revision:
                    raise JobLeadsError('A selected ad changed in another window. Refresh before moving it.', 409, 'JOB_LEADS_CONFLICT')
                record = self._record(current)
                if record['deleted']:
                    raise JobLeadsError('Restore ads from Trash before moving them.', 409, 'JOB_LEADS_CONFLICT')
                record['folder'] = name
                connection.execute('UPDATE leads SET payload=?,revision=revision+1,updated_at=? WHERE id=?',
                                   (json.dumps(clean_record(record), ensure_ascii=False), _now(), identity))
            self._check_capacity(connection)
            connection.commit()
        return {'changed':len(expected)}

    def save(self, raw):
        # Only save_hr may update search evidence; ordinary forms may be stale.
        data = clean_record({key:value for key,value in raw.items() if key != 'hr'} if isinstance(raw, dict) else raw)
        identity, revision = raw.get("id", ""), raw.get("revision")
        if identity and (not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{32}", identity)):
            raise JobLeadsError("Invalid saved lead. Refresh the list.")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            duplicate = connection.execute("SELECT * FROM leads WHERE url=?", (data["url"],)).fetchone()
            if duplicate and duplicate["id"] != identity:
                return {"record": self._record(duplicate), "duplicate": True}
            now = _now()
            if identity:
                current = connection.execute("SELECT * FROM leads WHERE id=?", (identity,)).fetchone()
                if current is None:
                    raise JobLeadsError("This lead no longer exists. Refresh your list.", 404)
                if self._record(current)['deleted']:
                    raise JobLeadsError("Restore this lead from Trash before editing it.", 409, "JOB_LEADS_CONFLICT")
                if type(revision) is not int or revision != current["revision"]:
                    raise JobLeadsError("This lead changed in another window. Refresh and reopen it before saving. Your draft is still here.", 409, "JOB_LEADS_CONFLICT")
                previous = self._record(current)
                data.pop('hr', None)
                if previous['company'] == data['company'] and previous['url'] == data['url'] and previous.get('hr'):
                    data['hr'] = previous['hr']
                data['deleted'] = False
                connection.execute("UPDATE leads SET url=?,payload=?,revision=revision+1,updated_at=? WHERE id=?", (data["url"], json.dumps(data, ensure_ascii=False), now, identity))
            else:
                data['deleted'] = False
                identity = uuid.uuid4().hex
                connection.execute("INSERT INTO leads VALUES (?,?,?,?,?,?)", (identity, data["url"], json.dumps(data, ensure_ascii=False), 1, now, now))
            if data['folder']:
                connection.execute('INSERT OR IGNORE INTO folders VALUES (?)', (data['folder'],))
            self._check_capacity(connection)
            result = self._record(connection.execute("SELECT * FROM leads WHERE id=?", (identity,)).fetchone())
            connection.commit()
            return {"record": result, "duplicate": False}

    def save_hr(self, identity, revision, raw):
        _selection([{'id':identity, 'revision':revision}])
        with self._connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            current = connection.execute('SELECT * FROM leads WHERE id=?', (identity,)).fetchone()
            if current is None or current['revision'] != revision:
                raise JobLeadsError('This ad changed during the HR search. Refresh and scan again. Its details were kept.', 409, 'JOB_LEADS_CONFLICT')
            record = self._record(current)
            if record['deleted']:
                raise JobLeadsError('Restore this ad before saving HR people.', 409, 'JOB_LEADS_CONFLICT')
            record['hr'] = clean_hr(raw, record['company'])
            record['hr']['scanned_at'] = _now()
            connection.execute('UPDATE leads SET payload=?,revision=revision+1,updated_at=? WHERE id=?',
                               (json.dumps(clean_record(record), ensure_ascii=False), _now(), identity))
            self._check_capacity(connection)
            result = self._record(connection.execute('SELECT * FROM leads WHERE id=?', (identity,)).fetchone())
            connection.commit()
        return {'record':result}

    def set_deleted(self, selection, deleted):
        if not isinstance(selection, list) or not selection or len(selection) > MAX_RECORDS or type(deleted) is not bool:
            raise JobLeadsError("Select saved leads to move or restore.")
        seen = set()
        for item in selection:
            if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or
                    not re.fullmatch(r'[a-f0-9]{32}', item['id']) or item['id'] in seen or type(item.get('revision')) is not int):
                raise JobLeadsError("Invalid saved lead selection. Refresh the list.")
            seen.add(item['id'])
        with self._connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            for item in selection:
                current = connection.execute('SELECT * FROM leads WHERE id=?', (item['id'],)).fetchone()
                if current is None or current['revision'] != item['revision']:
                    raise JobLeadsError("A selected lead changed in another window. Refresh before trying again.", 409, 'JOB_LEADS_CONFLICT')
                record = self._record(current)
                record['deleted'] = deleted
                data = clean_record(record)
                connection.execute('UPDATE leads SET payload=?,revision=revision+1,updated_at=? WHERE id=?',
                                   (json.dumps(data, ensure_ascii=False), _now(), item['id']))
            self._check_capacity(connection)
            connection.commit()
        return {'changed': len(selection)}

    def restore(self, payload):
        if (not isinstance(payload, dict) or payload.get("format") != "cvstudio-job-leads" or
                type(payload.get('version')) is not int or payload['version'] not in {1,2} or
                not isinstance(payload.get("records"), list) or len(payload["records"]) > MAX_RECORDS):
            raise JobLeadsError("Choose a valid Job Leads backup file.")
        folders = payload.get('folders') if payload['version'] == 2 else []
        if not isinstance(folders, list) or len(folders) > MAX_FOLDERS:
            raise JobLeadsError('The backup folder list is invalid.')
        folders = [clean_folder(name) for name in folders]
        rows = [(clean_record(raw), _backup_created(raw)) for raw in payload["records"]]
        added = skipped = 0
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for name in folders:
                connection.execute('INSERT OR IGNORE INTO folders VALUES (?)', (name,))
            for data, created in rows:
                if connection.execute("SELECT 1 FROM leads WHERE url=?", (data["url"],)).fetchone():
                    skipped += 1
                    continue
                now = _now()
                connection.execute("INSERT INTO leads VALUES (?,?,?,?,?,?)", (uuid.uuid4().hex, data["url"], json.dumps(data, ensure_ascii=False), 1, created or now, now))
                if data['folder']:
                    connection.execute('INSERT OR IGNORE INTO folders VALUES (?)', (data['folder'],))
                added += 1
            self._check_capacity(connection)
            connection.commit()
        return {"added": added, "skipped": skipped}

    def backup(self):
        return {"format": "cvstudio-job-leads", "version": 2, **self.snapshot()}

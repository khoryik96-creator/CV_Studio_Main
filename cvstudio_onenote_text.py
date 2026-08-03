"""Pure OneNote content and matching helpers (Phase 7B-6a).

Behaviour-preserving extraction of the stateless OneNote data helpers from the
legacy web shell: HTML-to-text conversion, URL/link parsing, date filtering,
manual notebook/section matching, and OneNote hierarchy XML parsing.

No Flask, no module globals, no network access - these are pure functions of
their inputs. This module never imports ``app``.
"""

import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta


class _OneNoteHtmlTextParser(__import__('html.parser').parser.HTMLParser):
    _BLOCK_TAGS = set("address article aside blockquote br div dl fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hr li main nav ol p pre section table tr ul".split())
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0
    def handle_starttag(self, tag, attrs):
        tag = (tag or "").lower()
        if tag in ("script", "style", "noscript"):
            self._skip += 1
            return
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")
    def handle_endtag(self, tag):
        tag = (tag or "").lower()
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
            return
        # HTMLParser treats <br /> as both a start and end tag.  The start tag
        # already emitted the line break, so emitting another one here creates
        # a blank line after every OneNote line.
        if tag == "br":
            return
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")
    def handle_data(self, data):
        if not self._skip and data:
            self.parts.append(data)
    def text(self):
        txt = "".join(self.parts)
        txt = re.sub(r"[ \t\xa0]+", " ", txt)
        txt = re.sub(r"\n[ \t]+", "\n", txt)
        txt = re.sub(r"\n{3,}", "\n\n", txt)
        return txt.strip()

def _onenote_html_to_text(raw):
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw or "")
    parser = _OneNoteHtmlTextParser()
    try:
        parser.feed(text)
        out = parser.text()
    except Exception:
        out = re.sub(r"<[^>]+>", " ", text)
        out = re.sub(r"\s+", " ", out).strip()
    return out[:60000]


def _onenote_graph_id(value):
    return urllib.parse.quote(str(value or "").strip(), safe='')


def _onenote_normalize_date_mode(value):
    mode = str(value or "created").strip().lower()
    if mode in ("modified", "lastmodified", "last_modified"):
        return "modified"
    if mode in ("either", "both", "created_or_modified", "created/modified"):
        return "either"
    return "created"


def _onenote_date_filtered_items(items, date_from_iso="", date_to_iso="", date_mode="created"):
    mode = _onenote_normalize_date_mode(date_mode)
    return [it for it in (items or []) if _onenote_page_in_date_range(it, date_from_iso, date_to_iso, mode)]


def _onenote_text_search_items(items, search=""):
    q = str(search or "").strip().lower()
    if not q:
        return list(items or [])
    out = []
    for it in (items or []):
        hay = " ".join(str((it or {}).get(k) or "") for k in ("title", "displayName", "name")).lower()
        if q in hay:
            out.append(it)
    return out


def _onenote_extract_urls(raw):
    r"""Return individual http/https/onenote URLs from pasted text.

    Desktop OneNote uses both ``onenote:https://...`` links and local links such
    as ``onenote:///C:\...\Section.one#section-id={...}``.  Older builds only
    recognised the web-shaped form, so a valid local desktop link was silently
    reduced to plain search text before the COM fallback ran.
    """
    text = str(raw or "")
    urls, seen = [], set()
    for m in re.finditer(r"(?i)(onenote:[^\s<>]+|https?://[^\s<>]+)", text):
        u = m.group(1).strip().strip("'\".,;)")
        if u and u not in seen:
            seen.add(u); urls.append(u)
    for line in re.split(r"[\r\n]+", text):
        line = line.strip()
        if not line:
            continue
        cleaned = line
        if not re.match(r"(?i)^(onenote:|https?://)", cleaned):
            cleaned = re.sub(r"^[A-Za-z ]{1,40}:\s*", "", cleaned).strip()
        if re.match(r"(?i)^(onenote:|https?://)", cleaned) and cleaned not in seen:
            seen.add(cleaned); urls.append(cleaned)
    return urls[:20]


def _onenote_url_parts(raw):
    """Extract notebook/section names, local section paths and candidate ids."""
    out = {"urls": _onenote_extract_urls(raw), "terms": [], "section_ids": [], "page_ids": [], "web_urls": [], "local_paths": [], "local_notebook_paths": []}
    def add(arr, v):
        v = urllib.parse.unquote(str(v or "")).strip().strip("'\" \t\r\n/()")
        if not v:
            return
        v = re.sub(r"\.one$", "", v, flags=re.I)
        v = v.replace("^.Documents", "").replace("^Documents", "")
        v = re.sub(r"[\\/]+", "/", v)
        v = re.sub(r"\s+", " ", v).strip(" /-")
        if not v:
            return
        low = v.lower()
        junk = {"http:", "https:", "documents", "d.docs.live.net", "onedrive.live.com", "view.aspx", "id=documents", "end", "()"}
        if low in junk or re.match(r"^[a-f0-9]{8,}$", low):
            return
        if v not in arr:
            arr.append(v)
    for url in out["urls"]:
        out["web_urls"].append(url)
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme.lower() == "onenote" and (parsed.path or "").lower().startswith("http"):
                inner_url = urllib.parse.unquote(parsed.path or "")
                parsed = urllib.parse.urlparse(inner_url)
                out["web_urls"].append(inner_url)
            path_text = urllib.parse.unquote(parsed.path or "")
            if parsed.scheme.lower() == "onenote":
                # Local desktop links commonly parse as /C:\Users\...\Section.one.
                # Preserve the .one path exactly for OneNote.OpenHierarchy.
                local_path = path_text.replace("/", "\\")
                if re.match(r"^\\[A-Za-z]:\\", local_path):
                    local_path = local_path[1:]
                if re.match(r"^[A-Za-z]:\\", local_path):
                    local_path = local_path.rstrip("\\/")
                    if re.search(r"(?i)\.one$", local_path):
                        if local_path not in out["local_paths"]:
                            out["local_paths"].append(local_path)
                    elif local_path and local_path not in out["local_notebook_paths"]:
                        # A pasted local notebook link may end at the notebook
                        # folder rather than a specific Section.one file. Keep
                        # the folder so CV Studio can enumerate every .one
                        # section and let the user choose which one to scan.
                        out["local_notebook_paths"].append(local_path)
            bits = [b for b in re.split(r"[\\/]+", path_text) if b]
            useful = []
            for b in bits:
                clean = urllib.parse.unquote(b).strip()
                if clean.lower() in ("http:", "https:", "documents", "^.documents", "^documents"):
                    continue
                if re.match(r"^[a-f0-9]{8,}$", clean, flags=re.I):
                    continue
                useful.append(clean); add(out["terms"], clean)
            if len(useful) >= 2:
                add(out["terms"], "/".join(useful[-2:]))
            qs = urllib.parse.parse_qs(parsed.query or "")
            frag = urllib.parse.unquote(parsed.fragment or "")
            frag_qs = urllib.parse.parse_qs(frag.replace("&amp;", "&"))
            for qd in (qs, frag_qs):
                for k, vals in qd.items():
                    lk = k.lower().replace("_", "-")
                    for v in vals:
                        dec = urllib.parse.unquote(v)
                        if lk == "wd" and dec.lower().startswith("target("):
                            m = re.search(r"target\(([^|)]+)(?:\|([^/)]+))?", dec, flags=re.I)
                            if m:
                                add(out["terms"], m.group(1))
                                if m.group(2): add(out["section_ids"], m.group(2))
                        elif "target" in lk:
                            add(out["terms"], dec)
                        elif "page" in lk:
                            add(out["page_ids"], dec)
                        elif "section" in lk or lk in ("id", "onenoteid"):
                            add(out["section_ids"], dec)
                        else:
                            add(out["terms"], dec)
            for m in re.finditer(r"section-id=\{?([^}&]+)\}?", frag, flags=re.I):
                add(out["section_ids"], m.group(1))
            for m in re.finditer(r"page-id=\{?([^}&]+)\}?", frag, flags=re.I):
                add(out["page_ids"], m.group(1))
        except Exception:
            continue
    return out


def _onenote_manual_search_terms(raw):
    """Extract readable notebook/section/page terms from pasted OneNote/OneDrive links."""
    parts = _onenote_url_parts(raw)
    terms, seen = [], set()
    def add(v):
        v = urllib.parse.unquote(str(v or "")).strip().strip("'\" \t\r\n/")
        v = re.sub(r"\.one$", "", v, flags=re.I)
        v = v.replace("^.Documents", "").replace("^Documents", "")
        v = re.sub(r"[\\/]+", "/", v)
        v = re.sub(r"\s+", " ", v).strip(" /-)")
        if not v:
            return
        low = v.lower()
        if low in ("http:", "https:", "documents", "d.docs.live.net", "onedrive.live.com", "view.aspx", "id=documents", "end", "()"):
            return
        if low not in seen:
            seen.add(low); terms.append(v)
    for t in parts.get("terms") or []:
        add(t)
    for line in re.split(r"[\r\n]+", str(raw or "")):
        cleaned = re.sub(r"^[A-Za-z ]{1,40}:\s*", "", line).strip()
        if not re.search(r"(?i)(https?://|onenote:)", cleaned):
            add(cleaned)
    return terms[:40]


def _onenote_match_notebook_from_manual(raw, notebooks):
    terms = [str(raw or "").strip().lower()] + [t.lower() for t in _onenote_manual_search_terms(raw)]
    terms = [t for t in terms if t]
    if not terms:
        return None
    best = None
    for nb in notebooks or []:
        name = str((nb or {}).get("displayName") or (nb or {}).get("name") or "").strip().lower()
        nid = str((nb or {}).get("id") or "").strip().lower()
        hrefs = " ".join(_onenote_link_hrefs(nb)).lower()
        for q in terms:
            if q == name or q == nid:
                return nb
            if q and (q in name or (name and name in q) or q in hrefs or (hrefs and hrefs in q)):
                best = best or nb
    return best


def _onenote_link_hrefs(item):
    vals = []
    if not isinstance(item, dict):
        return vals
    for key in ("webUrl", "pagesUrl", "self"):
        if item.get(key): vals.append(str(item.get(key)))
    links = item.get("links")
    if isinstance(links, dict):
        for v in links.values():
            if isinstance(v, dict):
                href = v.get("href") or v.get("url")
                if href: vals.append(str(href))
            elif isinstance(v, str):
                vals.append(v)
    return vals


def _onenote_manual_candidates(raw):
    text = str(raw or "").strip()
    parts = _onenote_url_parts(text)
    section_ids, page_ids = [], []
    def add_unique(arr, value):
        value = urllib.parse.unquote(str(value or "").strip().strip("'\"{}"))
        if value and value.lower() not in (x.lower() for x in arr):
            arr.append(value)
    for v in parts.get("section_ids") or []:
        add_unique(section_ids, v)
    for v in parts.get("page_ids") or []:
        add_unique(page_ids, v)
    for url in parts.get("urls") or []:
        try:
            parsed = urllib.parse.urlparse(url)
            for kind, arr in (("sections", section_ids), ("pages", page_ids)):
                m = re.search(r"/{}/([^/?#]+)".format(kind), parsed.path or "", flags=re.I)
                if m: add_unique(arr, m.group(1))
        except Exception:
            pass
    if not (section_ids or page_ids):
        if re.match(r"^[A-Za-z0-9_.!:%=+\-/]{16,}$", text) and " " not in text:
            add_unique(section_ids, text)
    return {"raw": text, "raw_lower": text.lower(), "section_ids": section_ids[:10], "page_ids": page_ids[:10], "web_urls": parts.get("web_urls", [])[:10], "local_paths": parts.get("local_paths", [])[:10], "local_notebook_paths": parts.get("local_notebook_paths", [])[:10], "terms": _onenote_manual_search_terms(text)[:20]}


def _onenote_match_section_from_manual(raw, sections):
    terms = [str(raw or "").strip().lower()] + [t.lower() for t in _onenote_manual_search_terms(raw)]
    terms = [t for t in terms if t]
    if not terms:
        return None
    best = None
    for sec in sections or []:
        name = str((sec or {}).get("displayName") or (sec or {}).get("name") or "").strip().lower()
        sid = str((sec or {}).get("id") or "").strip().lower()
        hrefs = " ".join(_onenote_link_hrefs(sec)).lower()
        for q in terms:
            if q == name or q == sid:
                return sec
            if q and (q in name or (name and name in q) or q in hrefs or (hrefs and hrefs in q)):
                best = best or sec
    return best


def _onenote_iso(dt):
    if not dt:
        return ""
    text = str(dt).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}T", text):
        return text
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).isoformat() + "Z"
        except Exception:
            pass
    return text


def _onenote_desktop_parse_sections_xml(xml_text, default_notebook_name="", default_notebook_id=""):
    """Parse Notebook/Section nodes from OneNote hierarchy XML."""
    notebooks, sections = [], []
    try:
        root = ET.fromstring(str(xml_text or ""))
    except Exception:
        nodes = _onenote_xml_nodes(xml_text, {"Notebook", "Section", "SectionGroup"})
        current_nb = str(default_notebook_name or "")
        current_nb_id = str(default_notebook_id or "")
        for node in nodes:
            tag = str(node.get("_tag") or "").lower()
            name = node.get("name") or node.get("nickname") or node.get("title") or ""
            if tag == "notebook":
                current_nb = name or current_nb
                current_nb_id = node.get("ID") or node.get("id") or current_nb_id
                notebooks.append({"id": current_nb_id, "displayName": current_nb, "path": node.get("path", ""), "_source": "desktop"})
            elif tag == "section":
                sid = node.get("ID") or node.get("id") or ""
                sections.append({
                    "id": sid,
                    "displayName": name,
                    "path": node.get("path") or "",
                    "createdDateTime": _onenote_iso(node.get("dateTime")),
                    "lastModifiedDateTime": _onenote_iso(node.get("lastModifiedTime")),
                    "_parentNotebookName": current_nb,
                    "_parentNotebookId": current_nb_id,
                    "_source": "desktop",
                })
        return notebooks, sections

    def local_tag(el):
        return str(getattr(el, "tag", "")).split("}", 1)[-1].lower()

    def walk(el, current_nb="", current_nb_id="", section_groups=None):
        section_groups = list(section_groups or [])
        tag = local_tag(el)
        attrs = dict(getattr(el, "attrib", {}) or {})
        name = attrs.get("name") or attrs.get("nickname") or attrs.get("title") or ""
        nb_name = current_nb or str(default_notebook_name or "")
        nb_id = current_nb_id or str(default_notebook_id or "")
        groups = section_groups
        if tag == "notebook":
            nb_name = name or nb_name
            nb_id = attrs.get("ID") or attrs.get("id") or nb_id
            notebooks.append({"id": nb_id, "displayName": nb_name, "path": attrs.get("path", ""), "_source": "desktop"})
        elif tag == "sectiongroup":
            if name:
                groups = section_groups + [name]
        elif tag == "section":
            sid = attrs.get("ID") or attrs.get("id") or ""
            sections.append({
                "id": sid,
                "displayName": name,
                "path": attrs.get("path") or "",
                "createdDateTime": _onenote_iso(attrs.get("dateTime")),
                "lastModifiedDateTime": _onenote_iso(attrs.get("lastModifiedTime")),
                "_parentNotebookName": nb_name,
                "_parentNotebookId": nb_id,
                "_sectionGroupPath": " / ".join(groups),
                "_source": "desktop",
            })
        for child in list(el):
            walk(child, nb_name, nb_id, groups)

    walk(root, str(default_notebook_name or ""), str(default_notebook_id or ""), [])
    return notebooks, sections


def _onenote_xml_nodes(xml_text, wanted=None):
    out = []
    if not xml_text:
        return out
    try:
        root = ET.fromstring(str(xml_text))
    except Exception:
        return out
    wanted_set = {w.lower() for w in wanted} if wanted else None
    for el in root.iter():
        tag = str(el.tag).split('}', 1)[-1]
        if wanted_set and tag.lower() not in wanted_set:
            continue
        attrs = dict(el.attrib or {})
        attrs["_tag"] = tag
        attrs["_text"] = " ".join(el.itertext())
        out.append(attrs)
    return out


def _onenote_page_in_date_range(item, date_from_iso="", date_to_iso="", date_mode="created"):
    """Filter OneNote pages by created/modified/either timestamp for section page scans."""
    if not date_from_iso and not date_to_iso:
        return True
    mode = _onenote_normalize_date_mode(date_mode)
    if mode == "modified":
        keys = ("lastModifiedDateTime",)
    elif mode == "either":
        keys = ("createdDateTime", "lastModifiedDateTime")
    else:
        keys = ("createdDateTime",)
    dates = []
    for k in keys:
        v = str((item or {}).get(k) or "").strip()
        if v:
            dates.append(v)
    if not dates:
        return False
    for v in dates:
        if date_from_iso and v < date_from_iso:
            continue
        if date_to_iso and v > date_to_iso:
            continue
        return True
    return False

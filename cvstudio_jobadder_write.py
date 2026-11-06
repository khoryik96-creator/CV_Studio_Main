"""JobAdder candidate-write service for CV Studio.

The application keeps ownership of the JobAdder OAuth token lifecycle, the
critical-write concurrency guard (the ``_ja_critical_write_route`` decorator
stays on the delegating routes) and the ``JobAdderClient`` transport.  This
module holds the JSON candidate-write handlers behind
``/jobadder/create_candidate`` and ``/jobadder/update_candidate``.  It reaches
the token refresh, request body and transport through injected callbacks and
never imports the application.  Both writes stay non-retryable
(``safe_to_retry=False``); the logic is a verbatim move of the legacy web-shell
handlers. A separate reviewed company-contact service uses protected non-replay
markers and never calls the candidate handlers.
"""

from __future__ import annotations

import json
import re
import sys
import hashlib
import secrets
import threading
import time
import urllib.error
import urllib.parse
from typing import Any, Callable


class JobAdderContactError(Exception):
    def __init__(self, message, code="JOBADDER_CONTACT_INPUT", status=400):
        super().__init__(message)
        self.code, self.status = code, status


class JobAdderContactService:
    """Reviewed company-contact creation; protected markers precede POST.

    No candidate writes, duplicate overrides, outreach or ambiguous replay.
    All account/transport/storage dependencies resolve through injected callbacks.
    """
    def __init__(self, *, client, account, contact, load, save, clock=time.time):
        self.client, self.account, self.contact = client, account, contact
        self.load, self.save, self.clock = load, save, clock
        self.lock = threading.Lock()

    def _store(self):
        try:
            data = self.load()
            if not data:
                return {"version":1, "operations":{}}
            if data.get("version") != 1 or not isinstance(data.get("operations"), dict):
                raise ValueError()
            if len(data["operations"]) > 5000:
                raise ValueError()
            for key, entry in data["operations"].items():
                if not re.fullmatch(r"[a-f0-9]{64}", key) or not isinstance(entry, dict) or entry.get("state") not in {"review", "pending", "unconfirmed", "rejected", "created", "exists"} or type(entry.get("company_id")) is not int or entry["company_id"] <= 0:
                    raise ValueError()
                history=entry.get("attempts",[])
                if (not isinstance(history,list) or len(history)>5 or any(not isinstance(old,dict) or old.get("state") not in {"pending","unconfirmed"} or type(old.get("company_id")) is not int or old["company_id"]<=0 for old in history)):
                    raise ValueError()
                recovery=entry.get("recovery")
                if recovery is not None and (not isinstance(recovery,dict) or not re.fullmatch(r"[a-f0-9]{64}",str(recovery.get("proof",""))) or type(recovery.get("expires")) not in {int,float} or not 0<recovery["expires"]<1e12):
                    raise ValueError()
                if "assignments" in entry:
                    if not isinstance(entry["assignments"],dict):raise ValueError()
                    self._assignments(entry["assignments"])
            defaults=data.get("assignment_defaults")
            if defaults is not None:
                if not isinstance(defaults,dict) or not re.fullmatch(r"[a-f0-9]{64}",defaults.get("account", "")):
                    raise ValueError()
                self._assignments(defaults)
            return data
        except Exception:
            raise JobAdderContactError("JobAdder contact history could not be read securely. No contact was created.", "JOBADDER_CONTACT_STORAGE", 503) from None

    def _write(self, value):
        try:
            self.save(value)
        except Exception:
            raise JobAdderContactError("The contact result could not be saved securely. Check JobAdder before trying again.", "JOBADDER_CONTACT_STORAGE", 503) from None

    def contact_links(self, rows):
        """Project confirmed protected history for the current account, locally."""
        info = self.account()
        scope = info.get('account_cache_namespace', '') if info.get('connected') else ''
        if not scope:
            return {'account':'', 'links':[]}
        operations = self._store()['operations']
        links = []
        for row in rows:
            email, identity = row.get('email'), row.get('contact_key')
            if not isinstance(email, str) or not re.fullmatch(r'[a-f0-9]{64}', str(identity or '')):
                continue
            key = hashlib.sha256(json.dumps([scope,email.strip().lower()]).encode()).hexdigest()
            entry = operations.get(key, {})
            contact_id = entry.get('contact_id')
            if entry.get('state') in {'created','exists'} and type(contact_id) is int and contact_id > 0:
                links.append({'contact_key':identity, 'state':entry['state'], 'contact_id':contact_id})
        return {'account':scope, 'links':links}

    @staticmethod
    def _text(value, name, limit, required=False):
        if not isinstance(value, str) or len(value) > limit or any(ord(c)<32 or ord(c)==127 for c in value) or (required and not value.strip()):
            raise JobAdderContactError("Check the " + name + ".")
        return value.strip()

    @staticmethod
    def _id(value):
        if type(value) is not int or not 0 < value <= 2147483647:
            raise JobAdderContactError("Choose a JobAdder company from the search results.")
        return value

    def _request(self, path, token, **kwargs):
        try:
            return self.client().request_json(path, token=token, timeout=15, fallback=None, **kwargs)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            if status in {401,403}:
                raise JobAdderContactError("Your JobAdder connection cannot access company contacts. Check its permissions or reconnect.", "JOBADDER_CONTACT_AUTH", 403) from None
            raise JobAdderContactError("JobAdder could not complete this check. Try again later.", "JOBADDER_CONTACT_SERVICE", 502) from None
        except Exception:
            raise JobAdderContactError("JobAdder did not confirm this check. No contact was created.", "JOBADDER_CONTACT_NETWORK", 502) from None

    def _duplicates(self, email, token):
        _, data = self._request("contacts", token, params={"Email":email,"Limit":100})
        if not isinstance(data, dict) or not isinstance(data.get("items"), list) or type(data.get("totalCount")) is not int or data["totalCount"] < len(data["items"]):
            raise JobAdderContactError("JobAdder did not confirm the duplicate check. No contact was created.", "JOBADDER_CONTACT_CHECK", 502)
        if data["totalCount"] > len(data["items"]):
            raise JobAdderContactError("Too many matching contacts were returned. Check this email in JobAdder before creating a contact.", "JOBADDER_CONTACT_CHECK", 409)
        matches = []
        for row in data["items"]:
            if not isinstance(row, dict) or not isinstance(row.get("email"),str) or not row["email"].strip():
                raise JobAdderContactError("JobAdder returned an incomplete duplicate check.", "JOBADDER_CONTACT_CHECK", 502)
            if str(row.get("email") or "").strip().lower() == email.lower():
                identity = row.get("contactId")
                if type(identity) is not int or identity <= 0:
                    raise JobAdderContactError("JobAdder returned an incomplete contact.", "JOBADDER_CONTACT_CHECK", 502)
                company = row.get("company") or {}
                if not isinstance(company,dict):
                    raise JobAdderContactError("JobAdder returned an incomplete company.", "JOBADDER_CONTACT_CHECK", 502)
                matches.append({"contact_id":identity, "company":str(company.get("name") or "")[:200], "company_id":company.get("companyId")})
        return matches

    @staticmethod
    def _created_contact_id(result, headers):
        """Accept only a confirmed contact id from JSON or a Created Location."""
        identity=result.get('contactId') if isinstance(result,dict) else None
        identity=identity if type(identity) is int and 0<identity<=2147483647 else None
        location=next((str(value) for key,value in dict(headers or {}).items() if str(key).lower()=='location'),'')
        located=None
        if location and len(location)<=2000:
            try:
                uri=urllib.parse.urlsplit(location)
                allowed=(not uri.netloc and not uri.scheme or
                         uri.scheme=='https' and bool(uri.hostname) and
                         (uri.hostname=='jobadder.com' or uri.hostname.endswith('.jobadder.com')) and
                         not uri.username and not uri.password and uri.port in (None,443))
                match=re.fullmatch(r'/?(?:v2/)?contacts/([1-9]\d*)/?',uri.path)
                if allowed and not uri.query and not uri.fragment and match and int(match[1])<=2147483647:
                    located=int(match[1])
            except (ValueError,TypeError):
                pass
        if identity and located and identity!=located:
            return None,'conflicting_contact_ids'
        return ((identity,'created_json') if identity else (located,'created_location') if located
                else (None,'missing_contact_id'))

    @staticmethod
    def _assignments(body):
        owner, recruiters = body.get("owner_user_id"), body.get("recruiter_user_ids")
        valid_id=lambda value: type(value) is int and 0<value<=2147483647
        if ((owner is not None and not valid_id(owner)) or
                (recruiters is not None and (not isinstance(recruiters,list) or len(recruiters)>1000 or
                not all(valid_id(value) for value in recruiters) or len(set(recruiters))!=len(recruiters))) or
                type(body.get("remember_assignments",False)) is not bool):
            raise JobAdderContactError("Choose one owner and valid recruiters from the JobAdder list.")
        return owner, sorted(recruiters) if recruiters is not None else None

    def _users(self, token):
        _, data=self._request("users",token,params={"Limit":1000})
        if (not isinstance(data,dict) or not isinstance(data.get("items"),list) or
                type(data.get("totalCount")) is not int or data["totalCount"]!=len(data["items"]) or data["totalCount"]>1000):
            raise JobAdderContactError("JobAdder did not return a complete user list.","JOBADDER_CONTACT_USERS",502)
        users,seen=[],set()
        for row in data["items"]:
            identity=row.get("userId") if isinstance(row,dict) else None
            if type(identity) is not int or not 0<identity<=2147483647 or identity in seen:
                raise JobAdderContactError("JobAdder returned an incomplete user list.","JOBADDER_CONTACT_USERS",502)
            seen.add(identity)
            if any(type(row.get(flag,False)) is not bool for flag in ["inactive","deleted"]):
                raise JobAdderContactError("JobAdder did not confirm active users.","JOBADDER_CONTACT_USERS",502)
            if row.get("inactive") or row.get("deleted"):continue
            names=[self._text(row.get(key) or "","JobAdder user name",200) for key in ["firstName","lastName"]]
            users.append({"id":identity,"name":" ".join(value for value in names if value) or "User #"+str(identity)})
        return sorted(users,key=lambda row:(row["name"].casefold(),row["id"]))

    def _validate_users(self, token, owner, recruiters):
        selected=set(recruiters or []) | ({owner} if owner is not None else set())
        if selected and not selected.issubset({row["id"] for row in self._users(token)}):
            raise JobAdderContactError("An owner or recruiter is no longer available. Search for the company and review the choices again.","JOBADDER_CONTACT_USERS",409)

    def perform(self, body, token):
        if not self.lock.acquire(blocking=False):
            raise JobAdderContactError("Finish the current JobAdder contact action first.", "JOBADDER_CONTACT_BUSY", 409)
        try:
            info = self.account()
            scope = info.get("account_cache_namespace", "")
            if not token or not info.get("connected") or not scope:
                raise JobAdderContactError("Connect JobAdder in Settings first.", "JOBADDER_CONTACT_AUTH", 401)
            action = body.get("action")
            if action not in {"companies", "review", "create", "check", "resolve_not_created"}:
                raise JobAdderContactError("Choose a supported contact action.")
            if action == "companies":
                query = self._text(body.get("query"), "company name", 200, True)
                _, data = self._request("companies", token, params={"Name":query,"Limit":50})
                if not isinstance(data, dict) or not isinstance(data.get("items"), list) or type(data.get("totalCount")) is not int or data["totalCount"] < len(data["items"]):
                    raise JobAdderContactError("JobAdder did not return company results.", "JOBADDER_CONTACT_SERVICE", 502)
                rows = []
                for row in data["items"][:50]:
                    if isinstance(row, dict) and type(row.get("companyId")) is int and row["companyId"]>0 and isinstance(row.get("name"), str):
                        rows.append({"id":row["companyId"], "name":row["name"][:200]})
                result={"account":scope, "companies":rows, "more":data.get("totalCount",0)>len(rows)}
                if body.get("include_assignments") is True:
                    try:
                        users=self._users(token);defaults=self._store().get("assignment_defaults")
                        defaults=defaults if defaults and defaults["account"]==scope else None
                        selected=set(defaults.get("recruiter_user_ids") or []) if defaults else set()
                        if defaults and defaults.get("owner_user_id") is not None:selected.add(defaults["owner_user_id"])
                        stale=bool(defaults and not selected.issubset({row["id"] for row in users}))
                        result["assignments"]={"available":True,"users":users,"stale":stale,"defaults":None if not defaults or stale else {key:defaults.get(key) for key in ["owner_user_id","recruiter_user_ids"]}}
                    except JobAdderContactError:
                        result["assignments"]={"available":False,"message":"Owner and recruiter choices could not be loaded. JobAdder defaults will be used."}
                return result
            if body.get("account") != scope:
                raise JobAdderContactError("The JobAdder account changed. Search for the company again.", "JOBADDER_CONTACT_ACCOUNT", 409)
            source = self.contact(body.get("contact_key"))
            email = self._text(source.get("email"), "email address", 100, True)
            if not _JOBADDER_EMAIL_RE.fullmatch(email):
                raise JobAdderContactError("Check the unlocked email address.")
            # A different company choice must not bypass an unresolved email
            # write. The selected company stays in the review fingerprint and
            # protected marker, and recovery checks the original POST company.
            key = hashlib.sha256(json.dumps([scope,email.lower()]).encode()).hexdigest()
            store = self._store()
            previous = store["operations"].get(key)
            if previous and previous["state"] in {"created","exists"}:
                return {"state":previous["state"],"contact_id":previous.get("contact_id"),"message":"This contact is already in JobAdder."}
            if previous and previous["state"] in {"pending","unconfirmed"}:
                matches = self._duplicates(email,token)
                exact = [row for row in matches if row["company_id"]==previous["company_id"]]
                if len(exact)==1:
                    exact=exact[0]
                    previous.pop("recovery",None)
                    previous.update(state="created",contact_id=exact["contact_id"])
                    if "assignments" in previous:
                        store["assignment_defaults"]={"account":scope,**previous.pop("assignments")}
                    self._write(store)
                    return {"state":"created",**exact,"message":"Contact confirmed in JobAdder. No request was repeated."}
                if action=="resolve_not_created":
                    recovery=previous.get("recovery") or {}
                    if matches or body.get("confirmed_not_created") is not True or recovery.get("expires",0)<=self.clock() or not secrets.compare_digest(recovery.get("proof",""),hashlib.sha256(str(body.get("recovery_token","")).encode()).hexdigest()):
                        raise JobAdderContactError("Check the previous result again and confirm in JobAdder that no contact was created. No request was repeated.","JOBADDER_CONTACT_RECOVERY",409)
                    attempts=previous.get("attempts",[])
                    if len(attempts)>=5:
                        raise JobAdderContactError("This contact reached its manual recovery limit. Check it in JobAdder; earlier attempts were kept.","JOBADDER_CONTACT_LIMIT",409)
                    archived={k:v for k,v in previous.items() if k not in {"attempts","recovery"}}
                    archived["confirmed_not_created_at"]=self.clock()
                    store["operations"][key]={"state":"rejected","reason":"user_confirmed_not_created","company_id":previous["company_id"],"attempts":[*attempts,archived]}
                    self._write(store)
                    return {"state":"not_started","message":"The previous attempt is recorded as not created. Click Review contact, then Create contact to start a new request. Nothing has been resent."}
                result={"state":"unconfirmed","message":"A matching email exists in JobAdder, but the previous company could not be confirmed. Check the existing record; no request was repeated.","matches":matches} if matches else {"state":"unconfirmed","message":"No matching contact was found. Check JobAdder before confirming that the previous request was not created."}
                if action=="check" and not matches:
                    nonce=secrets.token_hex(32)
                    previous["recovery"]={"proof":hashlib.sha256(nonce.encode()).hexdigest(),"expires":self.clock()+600}
                    self._write(store);result["recovery_token"]=nonce
                result.update(http_status=previous.get('http_status'),result_reason=previous.get('result_reason'))
                return result
            if action=="resolve_not_created":
                raise JobAdderContactError("Check the previous result before confirming a new request.","JOBADDER_CONTACT_RECOVERY",409)
            if action == "check":
                return {"state":"not_started","message":"No previous create request exists. Review the details first."}
            company_id = self._id(body.get("company_id"))
            first = self._text(body.get("first_name", ""), "first name", 50)
            last = self._text(body.get("last_name", ""), "last name", 50)
            if not first and not last:
                raise JobAdderContactError("Enter the contact's name.")
            position = self._text(body.get("position", ""), "position", 500)
            payload = {"firstName":first,"lastName":last,"email":email,"position":position,"companyId":company_id}
            owner,recruiters=self._assignments(body)
            if owner is not None:payload["ownerUserId"]=owner
            if recruiters is not None:payload["recruiterUserId"]=recruiters
            profile = source.get("profile_url", "")
            if re.fullmatch(r"https://www\.linkedin\.com/in/[A-Za-z0-9_%~-]+/?", profile):
                payload["social"] = {"linkedin":profile}
            encoded = json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
            fingerprint = hashlib.sha256(encoded).hexdigest()
            if action == "review":
                self._validate_users(token,owner,recruiters)
                _, company = self._request("companies/"+str(company_id),token)
                if not isinstance(company, dict) or type(company.get("companyId")) is not int or company["companyId"] != company_id or not isinstance(company.get("name"),str) or not company["name"].strip():
                    raise JobAdderContactError("This company could not be confirmed. Search again.", "JOBADDER_CONTACT_COMPANY", 409)
                matches = self._duplicates(email,token)
                if matches:
                    result={"state":"exists","matches":matches,"message":"A JobAdder contact already uses this email. No new record was created."}
                    match=matches[0] if len(matches)==1 else None
                    if (match and type(match.get('company_id')) is int and match['company_id']>0
                            and (key in store['operations'] or len(store['operations'])<5000)):
                        entry={'state':'exists','company_id':match['company_id'],'contact_id':match['contact_id']}
                        if previous and previous.get('attempts'):entry['attempts']=previous['attempts']
                        store['operations'][key]=entry;self._write(store)
                        result['contact_id']=match['contact_id']
                    return result
                if key not in store["operations"] and len(store["operations"]) >= 5000:
                    raise JobAdderContactError("Local contact-create history is full. No contact was created.", "JOBADDER_CONTACT_LIMIT", 409)
                nonce = secrets.token_hex(32)
                store["operations"][key] = {"state":"review","company_id":company_id,"payload":fingerprint,"proof":hashlib.sha256(nonce.encode()).hexdigest(),"expires":self.clock()+600}
                if previous and previous.get("attempts"):
                    store["operations"][key]["attempts"]=previous["attempts"]
                self._write(store)
                return {"state":"review","review_token":nonce,"company":str(company["name"])[:200],"message":"Review these details, then choose Create contact."}
            if body.get("confirmed") is not True or not previous or previous["state"] != "review" or previous.get("payload") != fingerprint or previous.get("expires",0) <= self.clock() or not secrets.compare_digest(previous.get("proof", ""),hashlib.sha256(str(body.get("review_token", "")).encode()).hexdigest()):
                raise JobAdderContactError("The review changed or expired. Review the details again before creating.", "JOBADDER_CONTACT_REVIEW", 409)
            # Repeat only the safe read immediately before the one unsafe write.
            self._validate_users(token,owner,recruiters)
            matches = self._duplicates(email,token)
            if matches:
                result={"state":"exists","matches":matches,"message":"This email already exists in JobAdder. No new record was created."}
                if len(matches)==1:
                    previous.update(state="exists",contact_id=matches[0]["contact_id"]);self._write(store)
                    result['contact_id']=matches[0]['contact_id']
                return result
            previous.update(state="pending")
            if body.get("remember_assignments") is True:
                previous["assignments"]={"owner_user_id":owner,"recruiter_user_ids":recruiters}
            self._write(store)
            try:
                response = self.client().request_raw("contacts",method="POST",body=encoded,
                    headers={"Content-Type":"application/json","Accept":"application/json"},token=token,timeout=20,
                    safe_to_retry=False,retries=0,refresh_on_401=False)
                status, result = response.status, response.json({})
                identity, reason = self._created_contact_id(result,response.headers)
                previous.update(http_status=status,result_reason=reason if status==201 else 'unexpected_status')
                if status==201 and identity:
                    previous.update(state="created",contact_id=identity)
                else:
                    previous.update(state="unconfirmed")
            except urllib.error.HTTPError as exc:
                status=exc.code;exc.close()
                previous.update(state="rejected" if status in {400,401,403,409,422} else "unconfirmed",http_status=status,result_reason="http_rejected")
                if status==409:previous["reason"]="duplicate_rejected"
            except Exception:
                previous.update(state="unconfirmed",result_reason="transport_unconfirmed")
            if previous["state"]=="created" and "assignments" in previous:
                store["assignment_defaults"]={"account":scope,**previous.pop("assignments")}
            if previous["state"]=="rejected":previous.pop("assignments",None)
            self._write(store)
            state=previous["state"]
            return {"state":state,"contact_id":previous.get("contact_id"),"http_status":previous.get("http_status"),"result_reason":previous.get("result_reason"),"message":{
                "created":"Contact created in JobAdder.",
                "rejected":"JobAdder rejected this request because the email already exists. Search for that email in JobAdder; no duplicate override was used." if previous.get("reason")=="duplicate_rejected" else "JobAdder rejected the details or permissions. Check the required contact fields and connection before reviewing again.",
                "unconfirmed":"JobAdder did not confirm the result. Check the previous request; it will not be repeated."}[state]}
        finally:
            self.lock.release()


class JobAdderContactMatcher:
    """Bounded, read-only possible-contact checks from saved observations.

    Similar names are suggestions, never identity proof or permission to write.
    No Apollo request, contact write, result persistence or email return occurs.
    """
    def __init__(self, *, client, account, source):
        self.client, self.account, self.source = client, account, source

    @staticmethod
    def _tokens(value):
        import unicodedata
        text = ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').casefold())
                       if not unicodedata.combining(c))
        return [word for word in re.findall(r'[^\W_]+', text, re.UNICODE)
                if word not in {'mr', 'mrs', 'ms', 'miss', 'dr', 'prof'}]

    @classmethod
    def _company_match(cls, first, second):
        stop = {'sdn','bhd','pte','ltd','limited','inc','llc','plc','berhad','malaysia','singapore','my','sg','the'}
        a, b = set(cls._tokens(first))-stop, set(cls._tokens(second))-stop
        return bool(a and b and len(a & b)/min(len(a),len(b)) >= .8)

    @classmethod
    def _name_match(cls, source, candidate, same_company):
        from difflib import SequenceMatcher
        a, b = cls._tokens(source), cls._tokens(candidate)
        if not a or not b or len(a)>8 or len(b)>8:
            return None
        if sorted(a)==sorted(b):
            return (100, 'Exact name')
        if min(len(a),len(b))==1:
            word = a[0] if len(a)==1 else b[0]
            return (65, 'First name only; verify') if same_company and len(word)>=3 and word in a and word in b else None
        short, long = (a,b) if len(a)<=len(b) else (b,a)
        used=set(); exact=0; initial=False; spelling=False
        for word in sorted(short,key=lambda part:(len(part)==1,-len(part))):
            choices=[]
            for index, other in enumerate(long):
                if index in used:continue
                if word==other:choices.append((3,index,'exact'))
                elif min(len(word),len(other))==1 and word[0]==other[0]:choices.append((2,index,'initial'))
                elif min(len(word),len(other))>=5 and SequenceMatcher(None,word,other).ratio()>=.8:
                    choices.append((1,index,'spelling'))
            if not choices:return None
            _, index, kind=max(choices);used.add(index)
            exact+=kind=='exact';initial|=kind=='initial';spelling|=kind=='spelling'
        if not exact:return None
        return (80 if spelling else 85 if initial else 90,
                'Similar spelling' if spelling else 'Name and initial' if initial else 'Name components match')

    def find(self, body, token):
        info=self.account();scope=info.get('account_cache_namespace','')
        if not token or not info.get('connected') or not re.fullmatch(r'[a-f0-9]{64}',str(scope)):
            raise JobAdderContactError('Connect JobAdder in Settings to check existing contacts.', 'JOBADDER_CONTACT_AUTH',401)
        if body.get('account')!=scope:
            raise JobAdderContactError('The JobAdder account changed. Check again.', 'JOBADDER_CONTACT_ACCOUNT',409)
        source=self.source(body)
        if not isinstance(source,dict):raise JobAdderContactError('Refresh the saved HR person before checking.', 'JOBADDER_CONTACT_SOURCE',409)
        name=JobAdderContactService._text(source.get('name',''),'saved name',150,True)
        company=JobAdderContactService._text(source.get('company',''),'saved company',200)
        parts=self._tokens(name)
        words=[word for word in parts if len(word)>=3]
        queries=list(dict.fromkeys(([words[0],words[-1]] if words else [])))
        if not queries:
            return {'account':scope,'state':'incomplete','matches':[],'partial':True,
                    'message':'The saved name is too abbreviated to check reliably. Search JobAdder manually.'}
        matches={};partial=False
        reader=JobAdderContactService(client=self.client,account=self.account,contact=lambda _:None,
                                      load=lambda:None,save=lambda _:None)
        for query in queries[:2]:
            status,data=reader._request('contacts',token,params={'Name':query,'Limit':100})
            if (status!=200 or not isinstance(data,dict) or not isinstance(data.get('items'),list)
                    or type(data.get('totalCount')) is not int or data['totalCount']<len(data['items'])):
                raise JobAdderContactError('JobAdder did not confirm the name check. No email was unlocked.', 'JOBADDER_CONTACT_CHECK',502)
            partial|=data['totalCount']>len(data['items']) or len(data['items'])>100
            for row in data['items'][:100]:
                if not isinstance(row,dict) or type(row.get('contactId')) is not int or not 0<row['contactId']<=2147483647:
                    partial=True;continue
                if any(row.get(field) is not None and not isinstance(row[field],str) for field in ('firstName','lastName','name','position')):
                    partial=True;continue
                candidate=' '.join(str(row.get(field) or '').strip() for field in ('firstName','lastName')).strip()
                if not candidate:candidate=str(row.get('name') or '').strip()
                organization=row.get('company') or {}
                if (not isinstance(organization,dict) or not candidate or len(candidate)>200
                        or organization.get('name') is not None and not isinstance(organization['name'],str)):
                    partial=True;continue
                other=str(organization.get('name') or '')[:200]
                same_company=self._company_match(company,other)
                found=self._name_match(name,candidate,same_company)
                if not found:continue
                score,reason=found
                matches[row['contactId']]={'contact_id':row['contactId'],'name':candidate,
                    'company':other,'position':str(row.get('position') or '')[:300],
                    'company_matches':same_company,'reason':reason,'score':min(100,score+(5 if same_company else 0))}
        current=self.account()
        if not current.get('connected') or current.get('account_cache_namespace')!=scope:
            raise JobAdderContactError('The JobAdder account changed. Results were discarded.', 'JOBADDER_CONTACT_ACCOUNT',409)
        found=sorted(matches.values(),key=lambda row:(-row['score'],-int(row['company_matches']),row['name'].casefold(),row['contact_id']))
        partial|=len(found)>10
        return {'account':scope,'state':'matches' if found else 'incomplete' if partial else 'no_matches',
                'matches':found[:10],'partial':partial,
                'message':('Possible contacts already in JobAdder. Open the records to verify the person.' if found
                           else 'The check was incomplete. Search JobAdder before using an email credit.' if partial
                           else 'No matching names found in this check.')}


_JOBADDER_EMAIL_RE = re.compile(
    r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,63}", re.IGNORECASE
)
_JOBADDER_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{6,22}\d")
_JOBADDER_PHONE_LABEL_RE = re.compile(
    r"^(?:phone|mobile|contact|tel|telephone|handphone)\s*[:\-]?\s*",
    re.IGNORECASE,
)


def _jobadder_email_value(value: Any) -> str:
    """Return one valid JobAdder email from common AI/API field shapes."""
    if isinstance(value, list):
        value = value[0] if value else ""
    if isinstance(value, dict):
        value = value.get("address") or value.get("email") or ""
    match = _JOBADDER_EMAIL_RE.search(str(value or "").strip())
    if not match:
        return ""
    email = match.group(0).lower()
    return email if len(email) <= 254 else ""


def _jobadder_phone_value(value: Any) -> str:
    """Keep one plausible optional phone and discard AI-concatenated prose."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    if isinstance(value, dict):
        value = value.get("number") or value.get("value") or ""
    raw = " ".join(str(value or "").split()).strip()
    candidates = [raw] + _JOBADDER_PHONE_RE.findall(raw)
    for candidate in candidates:
        cleaned = _JOBADDER_PHONE_LABEL_RE.sub("", candidate).strip()
        if not re.fullmatch(r"\+?[\d().\-\s]+", cleaned):
            continue
        digits = re.sub(r"\D", "", cleaned)
        if not 8 <= len(digits) <= 15:
            continue
        if re.fullmatch(r"(?:19|20)\d{6,}", digits):
            continue
        if len(cleaned) <= 50:
            return cleaned
    return ""


def _jobadder_error_summary(raw_detail: Any) -> str:
    """Extract JobAdder's readable validation reasons from an HTTP body."""
    detail = str(raw_detail or "").strip()
    if not detail:
        return "JobAdder rejected the candidate data without an explanation."
    try:
        payload = json.loads(detail)
    except (TypeError, ValueError):
        return detail[:1200]
    messages = []
    if isinstance(payload, dict):
        for key in ("message", "error", "detail", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                messages.append(value.strip())
        errors = payload.get("errors")
        if isinstance(errors, list):
            for item in errors:
                if isinstance(item, dict):
                    message = str(item.get("message") or "").strip()
                    fields = item.get("fields")
                    if message and isinstance(fields, list) and fields:
                        message += " ({}).".format(", ".join(map(str, fields)))
                    if message:
                        messages.append(message)
                elif str(item or "").strip():
                    messages.append(str(item).strip())
        elif isinstance(errors, dict):
            for value in errors.values():
                if isinstance(value, list):
                    messages.extend(str(item).strip() for item in value if str(item).strip())
                elif str(value or "").strip():
                    messages.append(str(value).strip())
    if not messages:
        return detail[:1200]
    return " ".join(dict.fromkeys(messages))[:1200]


def _sanitize_jobadder_candidate_contacts(data: dict[str, Any]):
    """Normalize contacts before a create/update can reach JobAdder."""
    if "email" in data:
        email = _jobadder_email_value(data.get("email"))
        if not email and str(data.get("email") or "").strip():
            return "Email is not in a valid format. Enter one email address."
        data["email"] = email
    for key in ("phone", "mobile"):
        if key in data:
            phone = _jobadder_phone_value(data.get(key))
            if phone:
                data[key] = phone
            else:
                data.pop(key, None)
    return ""


class JobAdderWriteService:
    """Explicitly wired handlers behind the JSON candidate-write endpoints."""

    def __init__(
        self,
        *,
        jsonify: Callable[[Any], Any],
        request_json: Callable[[], Any],
        refresh_token: Callable[..., Any],
        client: Callable[[], Any],
    ):
        self._jsonify = jsonify
        self._request_json = request_json
        self._refresh_token = refresh_token
        self._client = client

    def create_candidate(self):
        """Server-side proxy: create a new candidate."""
        token = self._refresh_token(force=False)
        if not token:
            return self._jsonify({"error": "Not authenticated"}), 401
        data = self._request_json() or {}
        if not data:
            return self._jsonify({"error": "Invalid or empty JSON body"}), 400
        contact_error = _sanitize_jobadder_candidate_contacts(data)
        if contact_error:
            return self._jsonify({"error": contact_error}), 400
        try:
            # Build payload — keep non-empty values (dicts/lists are kept if non-empty)
            payload = {}
            for k, v in data.items():
                if v is None or v == "" or v == [] or v == {}: continue
                # For nested dicts, also strip if all values are empty
                if isinstance(v, dict) and all(not vv for vv in v.values()): continue
                payload[k] = v
            body = json.dumps(payload).encode()
            print(f"[JA Create] payload keys: {list(payload.keys())}", file=sys.stderr)
            _status, result = self._client().request_json(
                "candidates",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
                token=token,
                timeout=15,
                fallback={},
                safe_to_retry=False,
                retries=0,
            )
            return self._jsonify(result)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            return self._jsonify({
                "error": f"JobAdder error: {e.code}",
                "detail": body,
                "jobadder_message": _jobadder_error_summary(body),
            }), e.code
        except Exception as e:
            return self._jsonify({"error": str(e)}), 500

    def update_candidate(self):
        """Update existing candidate profile fields via PUT /candidates/{id}."""
        token = self._refresh_token(force=False)
        if not token:
            return self._jsonify({"error": "Not authenticated"}), 401
        data = self._request_json() or {}
        if not data:
            return self._jsonify({"error": "Invalid or empty JSON body"}), 400
        candidate_id = data.pop("candidateId", "")
        if not candidate_id:
            return self._jsonify({"error": "Missing candidateId"}), 400
        contact_error = _sanitize_jobadder_candidate_contacts(data)
        if contact_error:
            return self._jsonify({"error": contact_error}), 400
        try:
            payload = {k: v for k, v in data.items() if v not in (None, "", [], {})}
            body = json.dumps(payload).encode()
            _status, result = self._client().request_json(
                "candidates/{}".format(candidate_id),
                method="PUT",
                body=body,
                headers={"Content-Type": "application/json"},
                token=token,
                timeout=15,
                fallback={},
                safe_to_retry=False,
                retries=0,
            )
            return self._jsonify(result)
        except urllib.error.HTTPError as e:
            body_err = e.read().decode()
            return self._jsonify({
                "error": "JobAdder error: {}".format(e.code),
                "detail": body_err,
                "jobadder_message": _jobadder_error_summary(body_err),
            }), e.code
        except Exception as e:
            return self._jsonify({"error": str(e)}), 500

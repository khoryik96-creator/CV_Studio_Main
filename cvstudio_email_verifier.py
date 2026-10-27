"""First-party, bounded email checks. No verification API, database or mail delivery.

SMTP evidence is deliberately conservative: acceptance is not proof of future
delivery, policy rejection is not a missing mailbox, and DNS errors are unknown.
Only public, resolved IP literals may be contacted, on SMTP port 25 exclusively.
"""
from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import re
import secrets
import smtplib
import ssl
import threading
import time


class VerifierError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class CheckUnavailable(Exception):
    """A check could not establish an answer; never a negative mailbox verdict."""


_LOCAL = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+\Z")
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_ROLE = frozenset("admin accounts billing careers contact hello hiring hr info jobs marketing office recruitment sales support team webmaster".split())
# Small, explicit hints, not a claim to a complete commercial reputation feed.
_DISPOSABLE = frozenset({"mailinator.com", "guerrillamail.com", "guerrillamail.net", "sharklasers.com", "yopmail.com", "10minutemail.com", "trashmail.com", "getnada.com"})
_TYPOS = {"gmial.com": "gmail.com", "gamil.com": "gmail.com", "gmail.con": "gmail.com", "hotmial.com": "hotmail.com", "outlok.com": "outlook.com", "yaho.com": "yahoo.com"}


def domain_name(value):
    try:
        domain = value.encode("idna").decode("ascii").lower()
    except (UnicodeError, AttributeError):
        return ""
    labels = domain.split(".")
    if len(domain) > 253 or len(labels) < 2 or not all(_LABEL.fullmatch(x) for x in labels):
        return ""
    try:
        ipaddress.ip_address(domain)
        return ""
    except ValueError:
        return domain


def address_parts(value):
    """Return canonical address/domain and syntax state without guessing corrections."""
    if not isinstance(value, str) or len(value) > 320:
        return "", "", "invalid"
    value = value.strip()
    if not value or re.search(r"[\x00-\x1f\x7f]", value):
        return value, "", "invalid"
    local, sep, raw_domain = value.rpartition("@")
    domain = domain_name(raw_domain)
    try:
        length = len(local.encode("utf-8"))
    except UnicodeError:
        return value, domain, "invalid"
    if sep and local and raw_domain.startswith("[") and raw_domain.endswith("]"):
        return value, "", "unsupported"
    if not sep or not local or not domain or length > 64:
        return value, domain, "invalid"
    address = local + "@" + domain
    if len(address.encode("utf-8")) > 254:
        return address, domain, "invalid"
    # Quoted and SMTPUTF8 local parts need capabilities this version cannot prove.
    if local.startswith('"') and local.endswith('"') and len(local) >= 2:
        return address, domain, "unsupported"
    if re.search(r"\s", local):
        return address, domain, "invalid"
    if not local.isascii():
        return address, domain, "unsupported"
    if not _LOCAL.fullmatch(local) or local.startswith(".") or local.endswith(".") or ".." in local:
        return address, domain, "invalid"
    return address, domain, "ok"


def public_ip(value):
    try:
        ip = ipaddress.ip_address(value)
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        return ip.is_global and not ip.is_multicast
    except ValueError:
        return False


class MailDNS:
    def __init__(self):
        # Lazy import: a missing optional runtime dependency must not stop CV Studio.
        try:
            import dns.resolver
            self.resolver = dns.resolver.Resolver()
            self.resolver.cache = dns.resolver.LRUCache(max_size=256)
        except Exception:
            self.resolver = None

    def query(self, name, kind, deadline):
        if self.resolver is None:
            raise CheckUnavailable("DNS checks are unavailable. Run CV Studio's installer to repair its dependencies.")
        import dns.exception
        import dns.resolver
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CheckUnavailable("The DNS check timed out. Try this address again later.")
        try:
            return list(self.resolver.resolve(name + ".", kind, search=False, lifetime=min(3.0, remaining)))
        except dns.resolver.NXDOMAIN:
            return None
        except dns.resolver.NoAnswer:
            return []
        except (dns.exception.DNSException, OSError):
            raise CheckUnavailable("The domain's DNS could not be read. This does not mean the address is invalid.") from None

    def hosts(self, domain, deadline):
        answer = self.query(domain, "MX", deadline)
        if answer is None:
            return "no_domain", []
        if answer:
            mx = [(int(item.preference), str(item.exchange).rstrip(".").lower()) for item in answer]
            if len(mx) == 1 and mx[0] == (0, ""):
                return "no_mail", []
            if any(not domain_name(host) for _, host in mx):
                raise CheckUnavailable("The domain publishes an unusable mail-server record.")
            return "mx", list(dict.fromkeys(host for _, host in sorted(mx)))[:2]
        # RFC 5321 implicit MX: absence of MX alone does not reject a domain.
        return "implicit", [domain]

    def addresses(self, host, deadline):
        addresses = []
        for kind in ("A", "AAAA"):
            answer = self.query(host, kind, deadline)
            if answer:
                addresses.extend(str(item.address) for item in answer)
        # Fail closed on mixed public/private answers; connect to the checked
        # literal, never resolve the hostname again at socket creation.
        if any(not public_ip(ip) for ip in addresses):
            raise CheckUnavailable("The mail server resolves to a restricted network address. It was not contacted.")
        unique = list(dict.fromkeys(addresses))
        # Keep one real IPv6 destination when both families are advertised.
        # Otherwise two A answers consume both slots and a blocked IPv4 path
        # prevents trying a working IPv6 path. Validate every answer above
        # before reducing the set; mapped IPv4 is not an independent IPv6 path.
        ipv6 = [ip for ip in unique if ipaddress.ip_address(ip).version == 6
                and ipaddress.ip_address(ip).ipv4_mapped is None]
        ipv4 = [ip for ip in unique if ip not in ipv6]
        return [ipv4[0], ipv6[0]] if ipv4 and ipv6 else unique[:2]


class _DeadlineSMTP(smtplib.SMTP):
    """Bound the whole reply, including a server that drips endless reply lines."""
    def __init__(self, deadline):
        self.deadline = deadline
        super().__init__(timeout=4, local_hostname="[127.0.0.1]")

    def getreply(self):
        lines = []
        for _ in range(16):
            line = bytearray()
            while not line.endswith(b"\n"):
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                self.sock.settimeout(min(4.0, remaining))
                char = self.sock.recv(1)
                if not char:
                    raise smtplib.SMTPServerDisconnected("Verification connection closed")
                line.extend(char)
                if len(line) > 4096:
                    raise smtplib.SMTPResponseException(500, b"Verification reply too long")
            if len(line) < 4 or not line[:3].isdigit():
                raise smtplib.SMTPResponseException(500, b"Unusable verification reply")
            lines.append(bytes(line[4:]).strip())
            if line[3:4] != b"-":
                return int(line[:3]), b"\n".join(lines)
        raise smtplib.SMTPResponseException(500, b"Too many verification reply lines")


def mail_provider(host):
    host = host.lower().rstrip('.')
    if host.endswith('.mail.protection.outlook.com'):
        return 'Microsoft 365'
    if host in {'smtp.google.com', 'aspmx.l.google.com'} or host.endswith('.aspmx.l.google.com') or host.endswith('.aspmx.l.googlemail.com'):
        return 'Google Workspace'
    return 'Other mail server'


def missing_recipient(host, code, text):
    if code not in {550, 551, 553}:
        return False
    if re.match(rb'\s*5\.1\.1\b', text):
        return True
    # Microsoft DBEB: constrain this non-generic code to its documented
    # recipient response AND actual MX suffix, never arbitrary Access denied.
    return code == 550 and mail_provider(host) == 'Microsoft 365' and bool(
        re.match(rb'\s*5\.4\.1 Recipient address rejected: Access denied(?:\s|$)', text, re.I))


class ProbeResult(tuple):
    """Keep the established (status, reason) interface with additive evidence."""
    def __new__(cls, status, reason, **evidence):
        value = super().__new__(cls, (status, reason))
        value.evidence = evidence
        return value


class SMTPProbe:
    """No DATA, AUTH, VRFY or EXPN. Reset each envelope and close every socket."""
    def check(self, host, ip, address, deadline):
        if not public_ip(ip) or not domain_name(host):
            raise CheckUnavailable("The mail server's network address is restricted. It was not contacted.")
        client = _DeadlineSMTP(deadline)

        def budget():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            client.timeout = min(4.0, remaining)
            if client.sock:
                client.sock.settimeout(client.timeout)

        def command(fn, *args):
            budget()
            return fn(*args)

        phase = "connection"
        target = 'unconfirmed'

        def done(status, reason, outcome='policy', retryable=False, control='inconclusive'):
            return ProbeResult(status, reason, outcome=outcome, retryable=retryable,
                               target=target, control=control)

        def declined(code, text, control=False):
            if re.match(rb'\s*[45]\.2\.2\b', text):
                return done('unknown', 'The mailbox is full. This is not evidence of a missing address.', 'mailbox_full')
            if 400 <= code < 500:
                return done('unknown', 'The server temporarily deferred the '+('catch-all check.' if control else 'mailbox check.')+' A later recheck may help.', 'temporary', True)
            return done('unknown', 'The server did not confirm '+('its catch-all policy.' if control else 'this mailbox.')+' It may restrict verification.', 'policy')

        try:
            code, _ = command(client.connect, ip, 25)
            if code != 220:
                return done('unknown', 'The mail server did not accept the connection.', 'temporary' if 400 <= code < 500 else 'policy', 400 <= code < 500)
            phase = "session"
            code, _ = command(client.ehlo)
            if code != 250:
                code, _ = command(client.helo)
            if code != 250:
                return done('unknown', 'The mail server declined the verification session.', 'temporary' if 400 <= code < 500 else 'policy', 400 <= code < 500)
            if client.has_extn("starttls"):
                # Connection remains pinned to ip; certificate identity is host.
                client._host = host
                command(lambda: client.starttls(context=ssl.create_default_context()))
                code, _ = command(client.ehlo)
                if code != 250:
                    return done('unknown', 'The mail server declined the secure verification session.')
            code, _ = command(client.mail, "")
            if code != 250:
                return done('unknown', 'The server declined a verification-only sender. No mailbox conclusion is possible.', 'temporary' if 400 <= code < 500 else 'sender_policy', 400 <= code < 500)
            phase = "mailbox"
            code, text = command(client.rcpt, address)
            # Generic 550 / policy blocks, full mailboxes and temporary errors
            # are not proof the recipient does not exist.
            if missing_recipient(host, code, text):
                target = 'rejected'
                return done('invalid', 'The mail server explicitly reported that this mailbox does not exist.', 'recipient_missing', control='not_checked')
            if code not in {250, 251}:
                return declined(code, text)
            target = 'accepted'
            code, _ = command(client.rset)
            if code != 250:
                return done('unknown', 'The mailbox was accepted, but the catch-all check could not be completed.')
            code, _ = command(client.mail, "")
            if code != 250:
                return done('unknown', 'The mailbox was accepted, but the catch-all check could not be completed.', 'temporary' if 400 <= code < 500 else 'sender_policy', 400 <= code < 500)
            random_address = "cvstudio-" + secrets.token_hex(16) + "@" + address.rsplit("@", 1)[1]
            code, text = command(client.rcpt, random_address)
            if code in {250, 251}:
                return done('catch_all', 'The server accepts made-up addresses too. A real mailbox can exist on this domain, but this check cannot confirm it.', 'catch_all', control='detected')
            if missing_recipient(host, code, text):
                return done('accepted', 'The server accepted this mailbox and rejected a made-up one. Delivery is still not guaranteed.', 'recipient_supported', control='not_detected')
            return declined(code, text, control=True)
        except ssl.SSLCertVerificationError:
            return done('unknown', "The mail server's secure connection could not be verified. The mailbox remains unconfirmed.", 'tls')
        except TimeoutError:
            if phase == "connection":
                return done('unknown', 'The mail server connection timed out on port 25. Your network or the mail server may block verification. This does not mean the email is invalid.', 'connection', True)
            if phase == "mailbox":
                return done('unknown', 'The mailbox response timed out. The mailbox remains unconfirmed; it has not been marked invalid.', 'timeout', True)
            return done('unknown', "The mail server's verification session timed out before a mailbox answer. The mailbox remains unconfirmed.", 'timeout', True)
        except ConnectionRefusedError:
            return done('unknown', 'The mail server connection was refused. The mailbox remains unconfirmed; it has not been marked invalid.', 'connection', True)
        except (OSError, smtplib.SMTPException, UnicodeError):
            return done('unknown', 'The mail server connection was interrupted or unavailable. The mailbox remains unconfirmed; it has not been marked invalid.', 'connection', True)
        finally:
            # close(), rather than QUIT, cannot wait on an unresponsive server.
            client.close()


class EmailVerifier:
    def __init__(self, dns=None, probe=None):
        self.dns = dns if dns is not None else MailDNS()
        self.probe = probe if probe is not None else SMTPProbe()
        self._slots = threading.BoundedSemaphore(2)
        self._lock = threading.Lock()
        self._domains = set()

    def check(self, payload):
        result = self._check(payload)
        observations = result.pop('_observations', [])
        status = result['status']
        target = {'accepted':'accepted', 'invalid':'rejected', 'catch_all':'accepted'}.get(status, 'unconfirmed')
        if result['mailbox'] == 'not_checked':
            target = 'not_checked'
        if result.get('outcome') == 'conflicting_servers':
            target = 'conflicting'
        elif status == 'unknown' and any(item.get('target') == 'accepted' for item in observations):
            target = 'accepted'
        result['mailbox_evidence'] = target
        result['catch_all'] = {'accepted':'not_detected', 'catch_all':'detected'}.get(status, 'inconclusive' if result['attempts'] and status != 'invalid' else 'not_checked')
        level = {'accepted':'lower_risk', 'invalid':'avoid', 'catch_all':'caution'}.get(status, 'unconfirmed')
        if status == 'accepted' and 'Known disposable domain' in result['flags']:
            level = 'caution'
        labels = {'lower_risk':'Mailbox supported', 'avoid':'Do not use', 'caution':'Use caution', 'unconfirmed':'More evidence needed'}
        result['assessment'] = {'level':level, 'label':labels[level]}
        result['evidence'] = []
        if result['syntax'] == 'ok':
            result['evidence'].append('Address format passed.')
        if result['domain'] in {'mx', 'implicit'}:
            result['evidence'].append('Mail routing records found; records alone do not confirm a mailbox.')
        result['evidence'].append(result['reason'])
        blocked = any(item.get('outcome') in {'policy', 'sender_policy', 'tls', 'mailbox_full'} for item in observations)
        result['retryable'] = status == 'unknown' and not blocked and (result.get('retryable', False) or any(item.get('retryable') for item in observations))
        result['retry_after_seconds'] = 120 if result['retryable'] else 0
        if observations and 'outcome' not in result:
            selected = next((item for item in observations if item.get('status') == status and item.get('reason') == result['reason']), observations[-1])
            result['outcome'] = selected.get('outcome', 'unconfirmed')
        result.setdefault('outcome', 'not_checked')
        return result

    def _check(self, payload):
        if not isinstance(payload, dict) or not isinstance(payload.get("email"), str) or len(payload["email"]) > 320:
            raise VerifierError("Enter one email address of up to 320 characters.")
        mode = payload.get("mode", "full")
        if not isinstance(mode, str) or mode not in {"full", "quick", "deep"}:
            raise VerifierError("Choose mailbox verification or a quick domain check.")
        address, domain, syntax = address_parts(payload["email"])
        result = {"email": payload["email"].strip(), "normalized": address, "status": "unknown", "reason": "",
                  "mode": mode, "checked_at": datetime.now(timezone.utc).isoformat(),
                  "syntax": syntax, "domain": "not_checked", "mailbox": "not_checked", "flags": [], "suggestion": "",
                  "attempts":0, "provider":"Not checked", "_observations":[]}
        local = address.rsplit("@", 1)[0]
        if local.lower().split("+", 1)[0] in _ROLE:
            result["flags"].append("Role address")
        if domain in _DISPOSABLE:
            result["flags"].append("Known disposable domain")
        if domain in _TYPOS:
            result["suggestion"] = local + "@" + _TYPOS[domain]
        if syntax == "invalid":
            result.update(status="invalid", reason="This address has an invalid format. Check its spelling and punctuation.")
            return result
        if syntax == "unsupported":
            result["reason"] = "Quoted mailbox names, international mailbox names and address literals are not supported by this checker. This address has not been marked invalid."
            return result
        if not self._slots.acquire(blocking=False):
            raise VerifierError("The verifier is busy. Wait for the current checks to finish.", 429)
        owned = False
        try:
            with self._lock:
                if domain in self._domains:
                    raise VerifierError("This domain is already being checked. Wait for that check to finish.", 429)
                self._domains.add(domain)
                owned = True
            deadline = time.monotonic() + 25
            state, hosts = self.dns.hosts(domain, deadline)
            result["domain"] = state
            if state in {"no_domain", "no_mail"}:
                result.update(status="invalid", reason="The domain does not exist." if state == "no_domain" else "The domain explicitly declares that it does not receive email.")
                return result
            reachable = []
            by_host = []
            lookup_failure = None
            for host in hosts:
                try:
                    addresses = self.dns.addresses(host, deadline)
                except CheckUnavailable as error:
                    # A failed/restricted MX must not discard another usable
                    # public server. The failing host contributes no addresses.
                    if lookup_failure is None:
                        lookup_failure = error
                    continue
                reachable.extend((host, ip) for ip in addresses)
                by_host.append([(host, ip) for ip in addresses])
            if not reachable:
                if lookup_failure is not None:
                    raise lookup_failure
                result.update(status="invalid" if state == "implicit" else "unknown", domain="no_server",
                              reason="No mail server or fallback server was found." if state == "implicit" else "The advertised mail server has no usable address. Mailbox validity is unknown.")
                return result
            if mode == "quick":
                result.update(status="domain_ok", reason="Address format and mail-server records passed. The individual mailbox was not checked.")
                return result
            # Deep mode compares MX hosts before spending a second connection
            # on an address family. It retains the single 25-second deadline.
            plan = reachable[:2] if mode != 'deep' else [row[index] for index in range(2) for row in by_host if len(row) > index][:4]
            settled = set()
            verdicts = []
            while plan:
                host, ip = plan.pop(0)
                if time.monotonic() >= deadline:
                    break
                if mode == 'deep' and host in settled:
                    continue
                probe_result = self.probe.check(host, ip, address, deadline)
                verdict, reason = probe_result
                result['attempts'] += 1
                observation = dict(getattr(probe_result, 'evidence', {}))
                observation['status'] = verdict
                observation['reason'] = reason
                observation.setdefault('target', {'accepted':'accepted','catch_all':'accepted','invalid':'rejected'}.get(verdict, 'unconfirmed'))
                result['_observations'].append(observation)
                verdicts.append((verdict, reason))
                result['provider'] = mail_provider(host)
                result.update(status=verdict, mailbox=verdict, reason=reason)
                if verdict != 'unknown':
                    settled.add(host)
                elif mode == 'deep' and observation.get('outcome') == 'connection':
                    # A blocked IPv4 route must not spend the remaining budget
                    # repeating IPv4 at another MX before trying known IPv6.
                    alternate = next((item for item in plan if item[0] == host and ipaddress.ip_address(item[1]).version != ipaddress.ip_address(ip).version), None)
                    if alternate is not None:
                        plan.remove(alternate)
                        plan.insert(0, alternate)
                if mode != 'deep' and verdict != "unknown":
                    break
            if verdicts:
                targets = {row['target'] for row in result['_observations']}
                if 'accepted' in targets and 'rejected' in targets:
                    result.update(status='unknown', mailbox='unknown', outcome='conflicting_servers', reason='Mail servers gave conflicting recipient answers. This address needs more evidence; no validity conclusion was made.')
                elif mode == 'deep':
                    chosen = next((item for state in ('catch_all', 'accepted', 'invalid') for item in verdicts if item[0] == state), verdicts[-1])
                    result.update(status=chosen[0], mailbox=chosen[0], reason=chosen[1])
            else:
                result.update(outcome='timeout', retryable=True, reason='The check reached its time limit before a mailbox response. The address remains unconfirmed.')
            return result
        except CheckUnavailable as error:
            transient = str(error) in {"The DNS check timed out. Try this address again later.", "The domain's DNS could not be read. This does not mean the address is invalid."}
            result.update(status="unknown", reason=str(error), outcome='dns_unavailable' if transient else 'check_unavailable', retryable=transient)
            return result
        finally:
            if owned:
                with self._lock:
                    self._domains.discard(domain)
            self._slots.release()

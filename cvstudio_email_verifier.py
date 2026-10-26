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
        return list(dict.fromkeys(addresses))[:2]


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

        try:
            code, _ = command(client.connect, ip, 25)
            if code != 220:
                return "unknown", "The mail server did not accept the connection."
            code, _ = command(client.ehlo)
            if code != 250:
                code, _ = command(client.helo)
            if code != 250:
                return "unknown", "The mail server declined the verification session."
            if client.has_extn("starttls"):
                # Connection remains pinned to ip; certificate identity is host.
                client._host = host
                command(lambda: client.starttls(context=ssl.create_default_context()))
                code, _ = command(client.ehlo)
                if code != 250:
                    return "unknown", "The mail server declined the secure verification session."
            code, _ = command(client.mail, "")
            if code != 250:
                return "unknown", "The server declined a verification-only sender. No mailbox conclusion is possible."
            code, text = command(client.rcpt, address)
            # Generic 550 / policy blocks, full mailboxes and temporary errors
            # are not proof the recipient does not exist.
            if code in {550, 551, 553} and re.search(rb"\b5\.1\.1\b", text):
                return "invalid", "The mail server explicitly reported that this mailbox does not exist."
            if code not in {250, 251}:
                return "unknown", "The server did not confirm this mailbox. It may be protected, blocked or temporarily unavailable."
            code, _ = command(client.rset)
            if code != 250:
                return "unknown", "The mailbox was accepted, but the catch-all check could not be completed."
            code, _ = command(client.mail, "")
            if code != 250:
                return "unknown", "The mailbox was accepted, but the catch-all check could not be completed."
            random_address = "cvstudio-" + secrets.token_hex(16) + "@" + address.rsplit("@", 1)[1]
            code, text = command(client.rcpt, random_address)
            if code in {250, 251}:
                return "catch_all", "The server accepts made-up addresses too. This individual mailbox cannot be confirmed."
            if code in {550, 551, 553} and re.search(rb"\b5\.1\.1\b", text):
                return "accepted", "The server accepted this mailbox and rejected a made-up one. Delivery is still not guaranteed."
            return "unknown", "The mailbox was accepted, but the server did not give a clear catch-all result."
        except (OSError, smtplib.SMTPException, UnicodeError, TimeoutError):
            return "unknown", "Mailbox probing was blocked, interrupted or timed out. Your network may block outgoing SMTP (port 25)."
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
        if not isinstance(payload, dict) or not isinstance(payload.get("email"), str) or len(payload["email"]) > 320:
            raise VerifierError("Enter one email address of up to 320 characters.")
        mode = payload.get("mode", "full")
        if not isinstance(mode, str) or mode not in {"full", "quick"}:
            raise VerifierError("Choose mailbox verification or a quick domain check.")
        address, domain, syntax = address_parts(payload["email"])
        result = {"email": payload["email"].strip(), "normalized": address, "status": "unknown", "reason": "",
                  "mode": mode, "checked_at": datetime.now(timezone.utc).isoformat(),
                  "syntax": syntax, "domain": "not_checked", "mailbox": "not_checked", "flags": [], "suggestion": ""}
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
            for host in hosts:
                addresses = self.dns.addresses(host, deadline)
                reachable.extend((host, ip) for ip in addresses)
            if not reachable:
                result.update(status="invalid" if state == "implicit" else "unknown", domain="no_server",
                              reason="No mail server or fallback server was found." if state == "implicit" else "The advertised mail server has no usable address. Mailbox validity is unknown.")
                return result
            if mode == "quick":
                result.update(status="domain_ok", reason="Address format and mail-server records passed. The individual mailbox was not checked.")
                return result
            for host, ip in reachable[:2]:
                verdict, reason = self.probe.check(host, ip, address, deadline)
                result.update(status=verdict, mailbox=verdict, reason=reason)
                if verdict != "unknown" or time.monotonic() >= deadline:
                    break
            return result
        except CheckUnavailable as error:
            result.update(status="unknown", reason=str(error))
            return result
        finally:
            if owned:
                with self._lock:
                    self._domains.discard(domain)
            self._slots.release()

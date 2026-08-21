from __future__ import annotations

import io
import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .validators import RuleValidationError, validate_rule

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_SOURCE_REDIRECTS = 5
SOURCE_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
OFFICIAL_RULE_SOURCES = {
    "malaysia": {
        "tax_url": "https://www.hasil.gov.my/wp-content/uploads/navigasi-hasil-2026.pdf",
        "contribution_url": "https://www.kwsp.gov.my/en/epf-act-1991-third-schedule",
    },
    "singapore": {
        "tax_url": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates",
        "contribution_url": "https://www.cpf.gov.sg/employer/employer-obligations/how-much-cpf-contributions-to-pay",
    },
}
OFFICIAL_RULE_SOURCE_FALLBACKS = {
    "malaysia": {
        "tax_url": (
            "https://www.hasil.gov.my/wp-content/uploads/sepintas-e-buku-hasil-2025.pdf",
        ),
    },
}


class AiRuleUpdateError(RuntimeError):
    pass


def official_rule_sources() -> dict[str, dict[str, str]]:
    """Return safe official defaults used by the one-click draft workflow."""
    return {country: dict(urls) for country, urls in OFFICIAL_RULE_SOURCES.items()}


def _public_source_url(url: str) -> str:
    url = str(url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise AiRuleUpdateError("Official source URL must be a valid http:// or https:// URL.")
    if parsed.username or parsed.password:
        raise AiRuleUpdateError("Official source URL cannot contain embedded credentials.")
    hostname = parsed.hostname.strip().casefold()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise AiRuleUpdateError("Local or private network URLs are not allowed as official sources.")

    def reject_ip(address: str) -> None:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise AiRuleUpdateError("Local or private network URLs are not allowed as official sources.")

    reject_ip(hostname)
    try:
        for info in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme.lower() == "https" else 80)):
            reject_ip(info[4][0])
    except AiRuleUpdateError:
        raise
    except OSError as exc:
        raise AiRuleUpdateError(f"Unable to resolve official source host {hostname}: {exc}") from exc
    return url


def _response_bytes(response: Any, max_bytes: int = MAX_SOURCE_BYTES) -> bytes:
    content_length = response.headers.get("content-length") if hasattr(response, "headers") else None
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise AiRuleUpdateError("Official source is too large to process safely.")
        except ValueError:
            pass

    if hasattr(response, "iter_content"):
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise AiRuleUpdateError("Official source is too large to process safely.")
            chunks.append(chunk)
        return b"".join(chunks)

    content = bytes(getattr(response, "content", b""))
    if len(content) > max_bytes:
        raise AiRuleUpdateError("Official source is too large to process safely.")
    return content


def fetch_official_source(url: str, max_chars: int = 60000) -> str:
    url = _public_source_url(url)
    current_url = url
    response = None
    try:
        for redirect_count in range(MAX_SOURCE_REDIRECTS + 1):
            current_url = _public_source_url(current_url)
            response = requests.get(
                current_url,
                headers={"User-Agent": "CVStudio-SalaryComparison/1.4", "Accept": "text/html,application/pdf,*/*"},
                timeout=45,
                stream=True,
                allow_redirects=False,
            )
            if response.status_code not in SOURCE_REDIRECT_STATUSES:
                break
            location = str(response.headers.get("location") or "").strip()
            response.close()
            if not location:
                raise AiRuleUpdateError("Official source returned a redirect without a destination.")
            if redirect_count >= MAX_SOURCE_REDIRECTS:
                raise AiRuleUpdateError("Official source redirected too many times.")
            current_url = _public_source_url(urljoin(current_url, location))
        if response is None:  # pragma: no cover - defensive loop invariant
            raise AiRuleUpdateError("Unable to retrieve official source.")
        response.raise_for_status()
        content = _response_bytes(response)
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" in content_type or current_url.lower().split("?", 1)[0].endswith(".pdf"):
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            encoding = getattr(response, "encoding", None) or "utf-8"
            html = content.decode(encoding, errors="replace")
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                tag.decompose()
            text = soup.get_text("\n")
    except AiRuleUpdateError:
        raise
    except requests.RequestException as exc:
        raise AiRuleUpdateError(f"Unable to retrieve official source {url}: {exc}") from exc
    except Exception as exc:
        raise AiRuleUpdateError(f"Unable to read official source {url}: {exc}") from exc
    finally:
        if response is not None:
            response.close()

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise AiRuleUpdateError(f"No readable content found at {url}")
    return text[:max(1000, min(int(max_chars), 200000))]


def _fetch_registered_official_source(
    primary_url: str,
    fallback_urls: tuple[str, ...] = (),
    *,
    source_label: str,
) -> tuple[str, str]:
    """Fetch the first readable registered source and return its actual URL."""
    failures: list[AiRuleUpdateError] = []
    for candidate_url in (primary_url, *fallback_urls):
        try:
            safe_url = _public_source_url(candidate_url)
            return safe_url, fetch_official_source(safe_url)
        except AiRuleUpdateError as exc:
            failures.append(exc)
    last_failure = failures[-1] if failures else AiRuleUpdateError("No source URL is registered.")
    raise AiRuleUpdateError(
        f"Unable to retrieve any registered official {source_label} source. "
        f"Tried {1 + len(fallback_urls)} approved URL(s). Last error: {last_failure}"
    ) from last_failure


def _prompt(country: str, tax_year: int, residency: str, tax_url: str, contribution_url: str,
            tax_text: str, contribution_text: str, *, automatic: bool = False) -> str:
    automatic_instruction = ""
    if automatic:
        automatic_instruction = f"""
- This is an automated next-year draft. Add \"source_year_supported\": true only when the supplied text explicitly supports tax year {tax_year}. Otherwise set it to false and do not infer or roll forward old rates.
"""
    return f"""
Extract salary-comparison rules from the supplied official sources.

Country: {country}
Tax year or assessment year: {tax_year}
Residency profile: {residency}

Return ONLY a valid JSON object with this exact structure:
{{
  "country": "{country}",
  "tax_year": {tax_year},
  "residency": "{residency}",
  "currency": "ISO-4217 code",
  "tax_brackets": [
    {{"lower": 0, "upper": 5000, "rate": 0}},
    {{"lower": 5000, "upper": null, "rate": 0.1}}
  ],
  "contribution_rule": {{
    "scheme": "scheme name",
    "employee_rate": 0,
    "employer_rate": 0,
    "annual_cap": null,
    "include_bonus": true,
    "employee_contribution_tax_deductible": false
  }},
  "source_urls": ["{tax_url}", "{contribution_url}"],
  "notes": ["short assumptions and limitations"],
  "verified": false
}}

Requirements:
- Use decimal fractions for rates: 11% is 0.11.
- Tax brackets must be sorted, contiguous, non-overlapping and begin at zero.
- Use null for the final open-ended upper bound.
- Do not include personal reliefs or rebates in the brackets.
- Do not invent values that are absent or ambiguous.
- When contributions vary by age, citizenship, permanent-resident year or wage band, choose a clearly stated standard full-rate employee profile and explain the assumption in notes.
- Keep all source URLs in the response.
{automatic_instruction}

OFFICIAL TAX SOURCE:
{tax_text}

OFFICIAL CONTRIBUTION SOURCE:
{contribution_text}
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    text = str(text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise AiRuleUpdateError("AI provider did not return a valid JSON object.")
        try:
            value = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise AiRuleUpdateError("AI provider returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise AiRuleUpdateError("AI provider must return one JSON object.")
    return value


def _call_deepseek(api_key: str, model: str, prompt: str) -> tuple[dict[str, Any], dict[str, int]]:
    try:
        response = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "Extract structured tax rules accurately from supplied official text."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=180,
        )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage") or {}
        return _extract_json(content), {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
        }
    except AiRuleUpdateError:
        raise
    except requests.RequestException as exc:
        raise AiRuleUpdateError(f"DeepSeek request failed: {exc}") from exc
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AiRuleUpdateError("DeepSeek returned an unexpected response structure.") from exc


def _call_claude(api_key: str, model: str, prompt: str) -> tuple[dict[str, Any], dict[str, int]]:
    try:
        response = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0,
                "max_tokens": 5000,
                "system": "Extract structured tax rules accurately. Return only JSON.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=180,
        )
        response.raise_for_status()
        body = response.json()
        text = "\n".join(
            block.get("text", "") for block in body.get("content", []) if block.get("type") == "text"
        )
        if not text.strip():
            raise AiRuleUpdateError("Claude returned no text content.")
        usage = body.get("usage") or {}
        return _extract_json(text), {
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
        }
    except AiRuleUpdateError:
        raise
    except requests.RequestException as exc:
        raise AiRuleUpdateError(f"Claude request failed: {exc}") from exc
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AiRuleUpdateError("Claude returned an unexpected response structure.") from exc


def _requested_identity(raw_rule: dict[str, Any], country: str, tax_year: int, residency: str) -> None:
    returned_country = str(raw_rule.get("country") or "").strip()
    returned_residency = str(raw_rule.get("residency") or "").strip()
    try:
        returned_year = int(raw_rule.get("tax_year"))
    except (TypeError, ValueError) as exc:
        raise AiRuleUpdateError("AI response did not contain the requested tax year.") from exc
    if returned_country.casefold() != country.casefold():
        raise AiRuleUpdateError(
            f"AI response country {returned_country!r} does not match requested country {country!r}."
        )
    if returned_year != tax_year:
        raise AiRuleUpdateError(
            f"AI response tax year {returned_year} does not match requested year {tax_year}."
        )
    if returned_residency.casefold() != residency.casefold():
        raise AiRuleUpdateError(
            f"AI response residency {returned_residency!r} does not match requested residency {residency!r}."
        )


def preview_rule_update(
    payload: dict[str, Any],
    *,
    key_resolver: Optional[Callable[[str], str]] = None,
) -> dict[str, Any]:
    """Generate an AI rule proposal for human review.

    When ``key_resolver`` is supplied (the CV Studio host wires it to the
    shared, machine-bound AI secret store), the provider key is resolved on the
    server for the requested provider and any browser-supplied ``api_key`` is
    ignored and never persisted.  When it is absent (standalone mode) the
    one-time key must be supplied in the request payload and is likewise never
    stored.
    """
    if not isinstance(payload, dict):
        raise AiRuleUpdateError("Rule update request must be a JSON object.")
    provider = str(payload.get("provider") or "").strip().lower()
    api_key = str(payload.get("api_key") or "").strip()
    model = str(payload.get("model") or "").strip()
    country = str(payload.get("country") or "").strip()
    residency = str(payload.get("residency") or "Resident").strip()
    tax_url = str(payload.get("tax_url") or "").strip()
    contribution_url = str(payload.get("contribution_url") or "").strip()
    automatic = payload.get("auto_sources") is True
    try:
        tax_year = int(payload.get("tax_year"))
    except (TypeError, ValueError) as exc:
        raise AiRuleUpdateError("Tax year must be a whole number.") from exc

    if provider not in {"deepseek", "claude"}:
        raise AiRuleUpdateError("Provider must be DeepSeek or Claude.")
    if key_resolver is not None:
        # Host-managed mode: never trust or persist a browser-supplied key;
        # resolve the shared provider key on the server instead.
        api_key = str(key_resolver(provider) or "").strip()
        if not api_key:
            raise AiRuleUpdateError(
                f"No securely saved {provider} key was found in CV Studio settings. "
                "Add it under AI provider settings and try again."
            )
    if not api_key:
        raise AiRuleUpdateError("API key is required and is not stored.")
    if len(api_key) > 1000:
        raise AiRuleUpdateError("API key is unexpectedly long.")
    if not model:
        raise AiRuleUpdateError("Enter the exact model ID available in your provider account.")
    if len(model) > 200:
        raise AiRuleUpdateError("Model ID is too long.")
    if not country or len(country) > 120:
        raise AiRuleUpdateError("Country is required.")
    if not residency or len(residency) > 80:
        raise AiRuleUpdateError("Residency profile is required.")
    if not 1900 <= tax_year <= 2200:
        raise AiRuleUpdateError("Tax year is outside the supported range.")

    if automatic:
        sources = OFFICIAL_RULE_SOURCES.get(country.casefold())
        if not sources:
            raise AiRuleUpdateError(
                f"No official one-click source set is registered for {country}. Enter the official URLs manually."
            )
        tax_url = sources["tax_url"]
        contribution_url = sources["contribution_url"]
        fallbacks = OFFICIAL_RULE_SOURCE_FALLBACKS.get(country.casefold(), {})
        tax_url, tax_text = _fetch_registered_official_source(
            tax_url,
            fallbacks.get("tax_url", ()),
            source_label=f"{country} tax",
        )
        contribution_url, contribution_text = _fetch_registered_official_source(
            contribution_url,
            fallbacks.get("contribution_url", ()),
            source_label=f"{country} contribution",
        )
    else:
        tax_url = _public_source_url(tax_url)
        contribution_url = _public_source_url(contribution_url)
        tax_text = fetch_official_source(tax_url)
        contribution_text = fetch_official_source(contribution_url)
    prompt = _prompt(
        country, tax_year, residency, tax_url, contribution_url, tax_text, contribution_text,
        automatic=automatic,
    )
    if provider == "deepseek":
        raw_rule, usage = _call_deepseek(api_key, model, prompt)
    else:
        raw_rule, usage = _call_claude(api_key, model, prompt)

    _requested_identity(raw_rule, country, tax_year, residency)
    if automatic and raw_rule.pop("source_year_supported", None) is not True:
        raise AiRuleUpdateError(
            f"The official pages do not explicitly support {tax_year} yet. No rule was drafted or published."
        )
    # Never trust the provider to mark its own extraction as verified or to choose source URLs.
    raw_rule["country"] = country
    raw_rule["tax_year"] = tax_year
    raw_rule["residency"] = residency
    raw_rule["source_urls"] = [tax_url, contribution_url]
    raw_rule["verified"] = False
    raw_rule["tax_brackets_verified"] = False
    raw_rule["contribution_rule_verified"] = False
    raw_rule["last_updated"] = datetime.now(timezone.utc).isoformat()
    notes = raw_rule.get("notes")
    if not isinstance(notes, list):
        notes = [] if notes in (None, "") else [str(notes)]
    notes.append(f"AI-extracted proposal generated with {provider}/{model}; human review required.")
    raw_rule["notes"] = notes
    try:
        normalized = validate_rule(raw_rule)
    except RuleValidationError as exc:
        raise AiRuleUpdateError(f"AI proposal failed rule validation: {exc}") from exc
    return {"rule": normalized, "usage": usage, "provider": provider, "model": model}

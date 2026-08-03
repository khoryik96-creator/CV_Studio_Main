from __future__ import annotations

import io
import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .validators import RuleValidationError, validate_rule

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MAX_SOURCE_BYTES = 10 * 1024 * 1024


class AiRuleUpdateError(RuntimeError):
    pass


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
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "CVStudio-SalaryComparison/1.4", "Accept": "text/html,application/pdf,*/*"},
            timeout=45,
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()
        final_url = str(getattr(response, "url", url) or url)
        _public_source_url(final_url)
        content = _response_bytes(response)
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" in content_type or url.lower().split("?", 1)[0].endswith(".pdf"):
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

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise AiRuleUpdateError(f"No readable content found at {url}")
    return text[:max(1000, min(int(max_chars), 200000))]


def _prompt(country: str, tax_year: int, residency: str, tax_url: str, contribution_url: str,
            tax_text: str, contribution_text: str) -> str:
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


def preview_rule_update(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AiRuleUpdateError("Rule update request must be a JSON object.")
    provider = str(payload.get("provider") or "").strip().lower()
    api_key = str(payload.get("api_key") or "").strip()
    model = str(payload.get("model") or "").strip()
    country = str(payload.get("country") or "").strip()
    residency = str(payload.get("residency") or "Resident").strip()
    tax_url = str(payload.get("tax_url") or "").strip()
    contribution_url = str(payload.get("contribution_url") or "").strip()
    try:
        tax_year = int(payload.get("tax_year"))
    except (TypeError, ValueError) as exc:
        raise AiRuleUpdateError("Tax year must be a whole number.") from exc

    if provider not in {"deepseek", "claude"}:
        raise AiRuleUpdateError("Provider must be DeepSeek or Claude.")
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

    tax_url = _public_source_url(tax_url)
    contribution_url = _public_source_url(contribution_url)
    tax_text = fetch_official_source(tax_url)
    contribution_text = fetch_official_source(contribution_url)
    prompt = _prompt(country, tax_year, residency, tax_url, contribution_url, tax_text, contribution_text)
    if provider == "deepseek":
        raw_rule, usage = _call_deepseek(api_key, model, prompt)
    else:
        raw_rule, usage = _call_claude(api_key, model, prompt)

    _requested_identity(raw_rule, country, tax_year, residency)
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

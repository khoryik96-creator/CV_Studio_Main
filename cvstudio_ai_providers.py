"""AI provider request/response shape adapters and provider labelling.

Behaviour-preserving extraction of the pure provider-neutral translation
helpers from the legacy web shell: friendly provider labels, transient-outage
hint detection, the OpenAI Responses <-> Anthropic Messages request/response
shape adapters, and Anthropic content-block flattening.

Pure functions of their inputs - no Flask, no globals, no network, no provider
client access. This module never imports ``app``.
"""

import re


def _provider_short_label(provider):
    p = str(provider or "anthropic").strip().lower()
    if p == "deepseek":
        return "DeepSeek"
    if p in ("openai", "gpt"):
        return "GPT/OpenAI"
    return "Claude"


def _provider_down_hint(provider, msg):
    text = str(msg or "")
    low = text.lower()
    if re.search(r"invalid api key|api key required|authentication|unauthorized|forbidden|permission|credit|quota|billing|insufficient|model.*not|unsupported|bad request", low):
        return ""
    if re.search(r"timed?\s*out|timeout|temporar(?:y|ily)|unavailable|overloaded|server error|bad gateway|gateway|service unavailable|connection reset|connection aborted|connection refused|network|upstream|rate limit|too many requests|\b429\b|\b500\b|\b502\b|\b503\b|\b504\b|\b529\b", low):
        return f"{_provider_short_label(provider)} appears down, overloaded, or temporarily unreachable. Try again shortly or switch provider in Settings."
    return ""


def _provider_error_message(provider, msg):
    hint = _provider_down_hint(provider, msg)
    msg = str(msg or "API provider error")
    return (hint + "\n\nDetails: " + msg) if hint else f"API provider error: {msg}"


def _openai_text_from_content(content):
    """Flatten Anthropic-style message content blocks into text for OpenAI Responses."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") in ("text", "input_text", "output_text"):
                    parts.append(str(block.get("text") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content or "")


def _openai_payload_from_anthropic_shape(payload_dict):
    """Translate an Anthropic-Messages-shaped request (model/messages/system/
    max_tokens/tools) into an OpenAI Responses API request.

    Preserve multi-turn role order for repair/continuation calls. v22.0
    concatenated user+assistant+user turns into one string, which could make
    OpenAI continuation repair behave differently from the original Claude path.
    """
    model = payload_dict.get("model") or "gpt-5.5"
    messages = payload_dict.get("messages") or []
    input_items = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "user").strip().lower()
        if role not in ("user", "assistant", "developer", "system"):
            role = "user"
        text = _openai_text_from_content(m.get("content"))
        if text:
            input_items.append({"role": role, "content": text})
    # Responses API accepts a plain string for simple one-shot requests and a
    # message array for conversation-style input. Keep one-shot payloads compact,
    # but preserve roles whenever there is more than one turn.
    if len(input_items) == 1 and input_items[0].get("role") == "user":
        openai_input = input_items[0].get("content", "")
    else:
        openai_input = input_items
    max_tokens = payload_dict.get("max_tokens") or 4096
    out = {
        "model": model,
        "input": openai_input,
        "max_output_tokens": max_tokens,
    }
    system_text = payload_dict.get("system")
    if isinstance(system_text, str) and system_text.strip():
        out["instructions"] = system_text
    elif isinstance(system_text, list):
        # Anthropic also allows a list of content blocks for system.
        sys_joined = "".join(_openai_text_from_content(b) for b in system_text if isinstance(b, dict))
        if sys_joined.strip():
            out["instructions"] = sys_joined
    if payload_dict.get("tools"):
        # Anthropic's web_search_20250305 -> OpenAI Responses API's web_search.
        out["tools"] = [{"type": "web_search"}]
    return out


def _openai_response_to_anthropic_shape(data):
    """Translate an OpenAI Responses API response back into the
    {"content": [...], "usage": {...}} shape every existing caller in this
    file already expects, so no downstream parsing code needs to know or
    care which provider actually answered.

    OpenAI examples expose a convenient output_text field on SDK responses,
    while raw REST responses are usually an output[] list of message blocks.
    Read both shapes so a live API response cannot look empty just because it
    arrived in the convenience form.
    """
    text_out = str(data.get("output_text") or "")
    if not text_out:
        for item in (data.get("output") or []):
            if not isinstance(item, dict):
                continue
            if item.get("type") in ("output_text", "text"):
                text_out += str(item.get("text") or "")
                continue
            if item.get("type") == "message":
                for block in (item.get("content") or []):
                    if isinstance(block, dict) and block.get("type") in ("output_text", "text"):
                        text_out += str(block.get("text") or "")
    usage = dict(data.get("usage") or {})
    return {
        "content": [{"type": "text", "text": text_out}],
        "usage": dict(
            usage,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        ),
    }

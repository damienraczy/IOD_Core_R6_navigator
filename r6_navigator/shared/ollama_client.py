import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent.parent  # project root where params.yml lives

_OLLAMA_MAX_RETRIES = 3
_OLLAMA_RETRY_DELAY = 2  # seconds between attempts


def load_params() -> dict:
    """Charge et retourne la configuration depuis ``params.yml``."""
    params_path = _PROJECT_ROOT / "params.yml"
    with open(params_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _call_ollama(url: str, model: str, system: str, prompt: str, timeout: int) -> str:
    """Appelle l'API Ollama en mode génération non streamée et retourne la réponse brute."""
    payload = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
    ).encode("utf-8")
    endpoint = f"{url.rstrip('/')}/api/generate"

    last_exc: Exception | None = None
    for attempt in range(1, _OLLAMA_MAX_RETRIES + 1):
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["response"]
        except urllib.error.URLError as e:
            last_exc = RuntimeError(f"Ollama unreachable at {url}: {e}")
        except (KeyError, json.JSONDecodeError) as e:
            last_exc = RuntimeError(f"Unexpected Ollama response format: {e}")

        if attempt < _OLLAMA_MAX_RETRIES:
            time.sleep(_OLLAMA_RETRY_DELAY)

    raise last_exc


def _fix_json_strings(text: str) -> str:
    """Échappe les sauts de ligne et tabulations littéraux dans les valeurs JSON."""
    result: list[str] = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
        elif ch == "\\" and in_string:
            result.append(ch)
            escape_next = True
        elif ch == '"':
            in_string = not in_string
            result.append(ch)
        elif in_string and ch == "\n":
            result.append("\\n")
        elif in_string and ch == "\r":
            pass  # discard bare carriage-returns inside strings
        elif in_string and ch == "\t":
            result.append("\\t")
        else:
            result.append(ch)
    return "".join(result)


def _strip_markdown_json(text: str) -> str:
    """Supprime l'enveloppe Markdown ``` optionnelle et corrige les newlines nus."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    return _fix_json_strings(text)


def _cap_bullets(value, max_items: int = 5) -> str:
    """Normalise et tronque une valeur LLM en bloc de puces « - phrase.\n »."""
    if not value:
        return ""
    if isinstance(value, list):
        lines = []
        for item in value:
            item = str(item).strip()
            if not item.startswith("-"):
                item = f"- {item}"
            lines.append(item)
    else:
        lines = [
            line for line in str(value).splitlines() if line.strip().startswith("-")
        ]
    capped = lines[:max_items]
    return "\n".join(capped) + ("\n" if capped else "")


def _to_str(value, fallback: str = "") -> str:
    """Convertit toute valeur LLM en chaîne de caractères simple."""
    if value is None:
        return fallback
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)

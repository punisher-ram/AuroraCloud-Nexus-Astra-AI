from __future__ import annotations

import json
import requests

# Gemini API key for this local desktop build.
# Do not publish this value to a public repository.
GEMINI_API_KEY = "Enter Your key here"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODELS_URL = f"{GEMINI_BASE_URL}/models"


class SerneiaError(RuntimeError):
    pass


def _headers():
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }


def _ensure_key():
    if not GEMINI_API_KEY or not GEMINI_API_KEY.strip():
        raise SerneiaError("Missing Gemini API key.")


def fetch_gemini_models():
    """Fetch all Gemini API models that advertise generateContent support."""
    _ensure_key()
    models = []
    page_token = None
    try:
        while True:
            params = {"pageSize": 1000}
            if page_token:
                params["pageToken"] = page_token
            response = requests.get(
                GEMINI_MODELS_URL,
                headers=_headers(),
                params=params,
                timeout=20,
            )
            if response.status_code == 401:
                raise SerneiaError("Unauthorized (401). The Gemini API key is invalid or revoked.")
            if response.status_code == 403:
                raise SerneiaError("Forbidden (403). This Gemini key/project is not permitted to use the API.")
            if response.status_code == 429:
                raise SerneiaError("Rate limited (429). Please try again later.")
            if response.status_code != 200:
                raise SerneiaError(
                    f"Failed to fetch Gemini models: HTTP {response.status_code} — {response.text[:1000]}"
                )

            payload = response.json()
            for meta in payload.get("models", []):
                if not isinstance(meta, dict):
                    continue
                supported = meta.get("supportedGenerationMethods") or []
                if "generateContent" not in supported:
                    continue
                name = str(meta.get("name", "")).strip()
                if name.startswith("models/"):
                    name = name.split("/", 1)[1]
                if name:
                    models.append(name)

            page_token = payload.get("nextPageToken")
            if not page_token:
                break
    except requests.exceptions.Timeout as exc:
        raise SerneiaError("Gemini model request timed out after 20 seconds.") from exc
    except requests.exceptions.RequestException as exc:
        raise SerneiaError(f"Could not reach generativelanguage.googleapis.com: {exc}") from exc
    except ValueError as exc:
        raise SerneiaError("Gemini returned invalid JSON for the model list.") from exc

    return list(dict.fromkeys(models))


def call_gemini_chat(model_id, messages, system_instruction="", temperature=0.7, max_tokens=2000, timeout=60):
    """Call Gemini's generateContent REST endpoint using the same conversation semantics as the old chat flow."""
    _ensure_key()
    model_id = str(model_id).strip()
    if model_id.startswith("models/"):
        model_id = model_id.split("/", 1)[1]
    if not model_id:
        raise SerneiaError("No Gemini model selected.")

    contents = []
    for message in messages:
        role = str(message.get("role", "user")).strip().lower()
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        if role == "assistant":
            role = "model"
        elif role not in ("user", "model"):
            continue
        contents.append({"role": role, "parts": [{"text": content}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_instruction.strip():
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction.strip()}]
        }

    url = f"{GEMINI_BASE_URL}/models/{model_id}:generateContent"
    try:
        response = requests.post(
            url,
            headers=_headers(),
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.Timeout as exc:
        raise SerneiaError(f"Gemini chat request timed out after {timeout} seconds.") from exc
    except requests.exceptions.RequestException as exc:
        raise SerneiaError(f"Could not reach generativelanguage.googleapis.com: {exc}") from exc

    if response.status_code == 401:
        raise SerneiaError("Unauthorized (401) when calling Gemini chat API. Check the Gemini API key.")
    if response.status_code == 403:
        raise SerneiaError("Forbidden (403). This Gemini model/API access is not permitted for this key/project.")
    if response.status_code == 404:
        raise SerneiaError(f"Gemini model not found (404): {model_id}")
    if response.status_code == 429:
        raise SerneiaError("Rate limited (429). The Gemini account/project limit has been reached.")
    if response.status_code != 200:
        raise SerneiaError(
            f"Gemini API request failed: HTTP {response.status_code} — {response.text[:1000]}"
        )

    try:
        data = response.json()
        candidates = data.get("candidates") or []
        parts = candidates[0]["content"]["parts"]
        text_parts = [str(part.get("text", "")) for part in parts if isinstance(part, dict) and part.get("text")]
        content = "\n".join(text_parts).strip()
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise SerneiaError(
            "Gemini returned an unexpected chat response: " + response.text[:1000]
        ) from exc

    if not content:
        feedback = data.get("promptFeedback") if isinstance(data, dict) else None
        raise SerneiaError(f"Gemini returned an empty response. {feedback or ''}".strip())
    return content


class SerneiaClient:
    """ERP-aware wrapper retaining the existing Aurora AI interface while using Gemini underneath."""

    # Keep the Astra chat dropdown limited to the known chat-capable models requested
    # by the user. Gemini 3.5 Transcribe is intentionally excluded because it is a
    # transcription model rather than a generateContent chat model.
    FALLBACK_MODELS = [
        "gemini-3-flash-preview",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemma-4-31b-it",
    ]
    ALLOWED_MODELS = set(FALLBACK_MODELS)

    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.default_model = "gemini-3.8-flash"

    @staticmethod
    def _sort_models(models):
        unique = list(dict.fromkeys(str(x).strip() for x in models if str(x).strip()))
        return sorted(unique, key=lambda x: (x != "gemini-3.8-flash", x.lower()))

    def list_models(self):
        """Return only the approved chat-capable Gemini models for the Astra selector."""
        try:
            live = fetch_gemini_models()
            live_allowed = [model for model in live if model in self.ALLOWED_MODELS]
            combined = list(dict.fromkeys(live_allowed + self.FALLBACK_MODELS))
            return self._sort_models(combined)
        except SerneiaError:
            return self._sort_models(self.FALLBACK_MODELS)

    def ask(self, question, context, model=None, history=None):
        model_id = (model or self.default_model).strip()
        system = (
            "You are Astra AI, the embedded intelligent business assistant for AURORA CLOUD — NEXUS. "
            "Use only the ERP context supplied below for factual business data. Never invent customers, "
            "invoices, prices, revenue, payments, stock, taxes, or financial results. If the context is "
            "insufficient, say: I don't have enough ERP data to determine that. Clearly distinguish ERP facts "
            "from recommendations or inference. You may act as a software engineer for app questions.\n\n"
            "ERP CONTEXT:\n" + json.dumps(context, ensure_ascii=False, default=str)
        )
        conversation = []
        if history:
            conversation.extend([
                {"role": str(m.get("role")), "content": str(m.get("content"))}
                for m in history[-8:]
                if m.get("role") in ("user", "assistant") and str(m.get("content", "")).strip()
            ])
        conversation.append({"role": "user", "content": question})
        return call_gemini_chat(
            model_id,
            conversation,
            system_instruction=system,
            temperature=0.7,
            max_tokens=2000,
            timeout=60,
        )

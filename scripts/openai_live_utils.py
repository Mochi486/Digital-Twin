import os
import re

from ai_scenario_utils import DEFAULT_OPENAI_MODEL, build_openai_text_format, extract_json_object


OPENAI_PREFERRED_MODELS = [
    "gpt-5.6",
    "gpt-5",
    "gpt-4.1",
    "gpt-4o",
]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"(OPENAI_API_KEY\s*=\s*)([^\s\"']+)", re.IGNORECASE),
    re.compile(r"(Bearer\s+)([A-Za-z0-9._-]+)", re.IGNORECASE),
]


def redact_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 1:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redact_data(value):
    if isinstance(value, dict):
        return {key: redact_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def resolve_openai_model(cli_model: str | None = None) -> str:
    env_model = os.environ.get("OPENAI_MODEL", "").strip()
    if env_model:
        return env_model
    if cli_model and cli_model.strip():
        return cli_model.strip()
    return DEFAULT_OPENAI_MODEL


def get_openai_sdk():
    try:
        import openai
        from openai import OpenAI
    except ImportError:
        return None, {
            "installed": False,
            "version": None,
            "error_type": "import_error",
            "error_message": "The official openai Python SDK is not installed.",
        }
    return OpenAI, {
        "installed": True,
        "version": getattr(openai, "__version__", "unknown"),
        "error_type": None,
        "error_message": None,
    }


def create_openai_client(api_key_override: str | None = None):
    api_key = (api_key_override if api_key_override is not None else os.environ.get("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return None, {
            "installed": None,
            "version": None,
            "error_type": "missing_api_key",
            "error_message": "OPENAI_API_KEY is not set.",
        }
    openai_class, sdk_status = get_openai_sdk()
    if openai_class is None:
        return None, sdk_status
    return openai_class(api_key=api_key), sdk_status


def is_model_access_error(error_type: str | None, status_code: int | None, error_message: str | None) -> bool:
    if error_type in {"model_not_found", "permission_denied"}:
        return True
    if status_code in {403, 404}:
        return True
    lowered = (error_message or "").lower()
    return "model" in lowered and ("not found" in lowered or "not have access" in lowered or "access" in lowered)


def list_accessible_models(client) -> dict:
    try:
        response = client.models.list()
        payload = response.model_dump() if hasattr(response, "model_dump") else response
        model_ids = sorted(item["id"] for item in payload.get("data", []) if isinstance(item, dict) and item.get("id"))
        return {
            "status": "ok",
            "model_ids": model_ids,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "status_code": getattr(exc, "status_code", None),
            "error_message": redact_text(str(exc)),
        }


def choose_fallback_model(accessible_models: list[str]) -> str | None:
    for candidate in OPENAI_PREFERRED_MODELS:
        if candidate in accessible_models:
            return candidate
    for model_id in accessible_models:
        if model_id.startswith("gpt-5") or model_id.startswith("gpt-4.1") or model_id.startswith("gpt-4o"):
            return model_id
    return None


def request_structured_scenario(client, prompt: str, model: str, system_prompt: str) -> dict:
    try:
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            ],
            text={"format": build_openai_text_format()},
        )
    except Exception as exc:  # pragma: no cover
        error_payload = None
        response_obj = getattr(exc, "response", None)
        if response_obj is not None and hasattr(response_obj, "json"):
            try:
                error_payload = response_obj.json()
            except Exception:
                error_payload = None
        return {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "status_code": getattr(exc, "status_code", None),
            "error_message": redact_text(str(exc)),
            "error_payload": redact_data(error_payload) if error_payload is not None else None,
        }

    payload = response.model_dump() if hasattr(response, "model_dump") else response
    candidate = None
    raw_output_text = payload.get("output_text")
    if isinstance(raw_output_text, str) and raw_output_text.strip():
        candidate = extract_json_object(raw_output_text)
    else:
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    candidate = extract_json_object(content["text"])
                    break
            if candidate is not None:
                break

    if candidate is None:
        return {
            "status": "parse_error",
            "model": model,
            "response_id": payload.get("id"),
            "request_timestamp": payload.get("created_at"),
            "usage": payload.get("usage"),
            "raw_response": redact_data(payload),
            "error_type": "structured_output_parse_error",
            "status_code": None,
            "error_message": "Could not extract structured JSON from the OpenAI response.",
        }

    return {
        "status": "ok",
        "model": model,
        "response_id": payload.get("id"),
        "request_timestamp": payload.get("created_at"),
        "usage": payload.get("usage"),
        "raw_response": redact_data(payload),
        "structured_output": candidate,
    }

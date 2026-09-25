"""The model provider for the AI capabilities (plan, explore, review).

Deterministic capabilities never import this module's client. The provider is Anthropic's API
through the optional `ai` extra (`anthropic` SDK). Configure it with ANTHROPIC_API_KEY (or
ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile). TEASERKIT_MODEL picks the model.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .errors import MissingPrerequisite, NoProvider, TeaserkitError

DEFAULT_MODEL = "claude-sonnet-5"
INSTALL_AI = "Install the AI extra: `uv tool install 'teaserkit[ai] @ git+https://github.com/michaeljabbour/teaserkit'` (or `pip install -e '.[ai]'` in a checkout)."
CONFIGURE = "Set ANTHROPIC_API_KEY (or run `ant auth login`), then retry. Deterministic capabilities work without it."


def model() -> str:
    return os.environ.get("TEASERKIT_MODEL") or DEFAULT_MODEL


def configured() -> bool:
    if any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE")):
        return True
    return (Path.home() / ".config" / "anthropic").is_dir()


def client():
    """Return an Anthropic client, or fail naming exactly what is missing."""
    try:
        import anthropic
    except ImportError as e:
        raise MissingPrerequisite("The AI capabilities need the `anthropic` SDK, which is not installed.", INSTALL_AI) from e
    if not configured():
        raise NoProvider("This capability is model-backed and no model provider is configured.", CONFIGURE)
    return anthropic.Anthropic()


def ask_json(system: str, content: list | str, schema: dict, *, max_tokens: int = 16000) -> dict:
    """One structured-output request. Returns the parsed JSON object."""
    import anthropic

    c = client()
    try:
        resp = c.messages.create(
            model=model(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.AuthenticationError as e:
        raise NoProvider(f"The model provider rejected the credentials: {e}", CONFIGURE) from e
    except anthropic.NotFoundError as e:
        raise TeaserkitError(f"Model '{model()}' was not found: {e}", "Set TEASERKIT_MODEL to a model id your account can use.") from e
    except anthropic.RateLimitError as e:
        raise TeaserkitError(f"Rate limited by the model provider: {e}", "Wait and retry.") from e
    except anthropic.APIConnectionError as e:
        raise TeaserkitError(f"Could not reach the model provider: {e}", "Check the network connection and retry.") from e
    except anthropic.APIStatusError as e:
        raise TeaserkitError(f"The model provider returned an error ({e.status_code}): {e}", "Retry; if it persists, try another TEASERKIT_MODEL.") from e
    if resp.stop_reason == "refusal":
        raise TeaserkitError("The model declined this request.", "Rephrase the input or remove content that may be flagged.")
    if resp.stop_reason == "max_tokens":
        raise TeaserkitError("The model's answer was cut off (max_tokens).", "Retry with less input.")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise TeaserkitError(f"The model returned invalid JSON: {e}", "Retry.") from e

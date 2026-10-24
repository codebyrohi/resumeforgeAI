"""Thin wrapper around the Groq API.

Everything provider-specific lives here: prompts, JSON mode, schema validation, retries,
rate-limit backoff and model fallback. The rest of the app only sees `parse_resume` and
`correct_profile`, so switching providers later only touches this file.

Always call these from the background worker, never on the request thread.
"""
import json
import logging
import re
import time
from functools import lru_cache

from pydantic import ValidationError

from app.config import get_settings
from app.schemas import Profile

log = logging.getLogger(__name__)

MAX_INPUT_CHARS = 12_000  # keeps one resume well under the free tier's per-request token cap


class LLMError(Exception):
    pass


class InvalidJSONError(LLMError):
    """Groq's JSON mode rejected the model's output (json_validate_failed); worth a retry."""


PARSE_SYSTEM_PROMPT = """You extract structured data from resume text.
Return ONLY a JSON object with exactly these keys:
{
  "basics": {"full_name": "", "headline": "", "email": "", "phone": "", "location": ""},
  "summary": "",
  "education": [{"institution": "", "degree": "", "field": "", "start": "", "end": "", "grade": "", "details": ""}],
  "experience": [{"company": "", "title": "", "location": "", "start": "", "end": "", "bullets": [""]}],
  "projects": [{"name": "", "description": "", "tech": [""], "url": ""}],
  "skills": [""],
  "links": [{"label": "", "url": ""}]
}
Rules:
- Copy facts exactly as written. Never invent employers, dates, numbers or achievements.
- Use "" or [] when a value is not present in the text.
- Dates stay as written in the resume (e.g. "Jan 2022", "2021", "Present").
- skills is a flat list of short skill names."""

CORRECT_SYSTEM_PROMPT = """You are a proofreader. You receive a JSON object mapping ids to text.
Fix ONLY spelling, grammar and punctuation mistakes.
- Do NOT rewrite, rephrase, shorten or expand.
- Do NOT add achievements, numbers, metrics, tools or claims that are not in the input.
- Keep technical terms, names and acronyms as written.
Return ONLY a JSON object with exactly the same keys, each mapped to its corrected text."""


class GroqLLMClient:
    def __init__(self) -> None:
        from groq import Groq

        s = get_settings()
        if not s.groq_api_key:
            raise LLMError("GROQ_API_KEY is not configured")
        self.client = Groq(api_key=s.groq_api_key, max_retries=0)  # we handle retries ourselves
        self.models = [s.groq_primary_model, s.groq_fallback_model]

    # ---- low level ----

    def _chat_json(self, model: str, system: str, user: str) -> dict:
        """One JSON-mode completion, with exponential backoff on 429 / transient errors."""
        import groq

        # gpt-oss models reason before answering; keep that short so the JSON comes out cleanly.
        extra = {"reasoning_effort": "low"} if model.startswith("openai/gpt-oss") else {}
        delay = 2.0
        for attempt in range(5):
            try:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}],
                    response_format={"type": "json_object"},
                    temperature=0,
                    timeout=60,
                    **extra,
                )
                return json.loads(resp.choices[0].message.content or "{}")
            except (groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError) as e:
                if attempt == 4:
                    raise LLMError(f"Groq unavailable: {e}") from e
                log.warning("Groq %s, retrying in %.0fs", type(e).__name__, delay)
                time.sleep(delay)
                delay *= 2
            except groq.BadRequestError as e:
                if "json_validate_failed" in str(e):
                    raise InvalidJSONError(f"{model} returned invalid JSON") from e
                raise LLMError(f"Groq error: {e}") from e
            except groq.APIError as e:
                raise LLMError(f"Groq error: {e}") from e
        raise LLMError("unreachable")

    # ---- public API ----

    def parse_resume(self, resume_text: str) -> Profile:
        user = "Resume text:\n\n" + resume_text[:MAX_INPUT_CHARS]
        # Primary model: first try + one retry on schema mismatch; then the larger fallback.
        attempts = [self.models[0], self.models[0], self.models[1]]
        last_error: Exception | None = None
        for model in attempts:
            try:
                return Profile.model_validate(self._chat_json(model, PARSE_SYSTEM_PROMPT, user))
            except (ValidationError, json.JSONDecodeError, InvalidJSONError) as e:
                log.warning("Schema mismatch from %s: %s", model, e)
                last_error = e
        raise LLMError(f"Could not get valid JSON from the model: {last_error}")

    def correct_profile(self, profile: Profile) -> Profile:
        texts = collect_free_text(profile)
        if not texts:
            return profile
        try:
            corrected = self._chat_json(self.models[0], CORRECT_SYSTEM_PROMPT, json.dumps(texts))
        except json.JSONDecodeError as e:
            raise LLMError("Invalid JSON from correction model") from e
        safe = {k: v for k, v in corrected.items()
                if k in texts and isinstance(v, str) and is_safe_correction(texts[k], v)}
        return apply_free_text(profile, safe)


# ---- helpers (pure functions, unit-tested) ----

def collect_free_text(profile: Profile) -> dict[str, str]:
    """Flatten every free-text field into {path_id: text} so the model can't touch structure."""
    out: dict[str, str] = {}
    if profile.basics.headline:
        out["headline"] = profile.basics.headline
    if profile.summary:
        out["summary"] = profile.summary
    for i, exp in enumerate(profile.experience):
        for j, bullet in enumerate(exp.bullets):
            if bullet:
                out[f"exp.{i}.{j}"] = bullet
    for i, proj in enumerate(profile.projects):
        if proj.description:
            out[f"proj.{i}"] = proj.description
    for i, edu in enumerate(profile.education):
        if edu.details:
            out[f"edu.{i}"] = edu.details
    return out


def apply_free_text(profile: Profile, texts: dict[str, str]) -> Profile:
    p = profile.model_copy(deep=True)
    for key, value in texts.items():
        parts = key.split(".")
        if key == "headline":
            p.basics.headline = value
        elif key == "summary":
            p.summary = value
        elif parts[0] == "exp":
            p.experience[int(parts[1])].bullets[int(parts[2])] = value
        elif parts[0] == "proj":
            p.projects[int(parts[1])].description = value
        elif parts[0] == "edu":
            p.education[int(parts[1])].details = value
    return p


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def is_safe_correction(original: str, corrected: str) -> bool:
    """Sanity guard: a spelling/grammar fix shouldn't change length much or add numbers."""
    before, after = len(original.split()), len(corrected.split())
    if abs(after - before) > max(2, int(before * 0.15)):
        return False
    return set(_NUMBER.findall(corrected)) <= set(_NUMBER.findall(original))


@lru_cache
def get_llm_client() -> GroqLLMClient:
    return GroqLLMClient()

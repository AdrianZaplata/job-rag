"""Resume extractor — Instructor + tenacity + structured output (Phase 7 D-15).

Mirrors :mod:`job_rag.extraction.extractor` (the job-posting extractor):
- sync function (called from the async upload route via
  ``asyncio.to_thread`` to keep the event loop unblocked — Phase 1 D-05),
- ``@retry`` with exponential backoff via tenacity (3 attempts, 1-10s),
- structured output via Instructor + ``response_model=ResumeExtraction``.

The structured ``response_model`` is the prompt-injection guardrail
(T-07-04): malicious instructions inside the resume cannot alter the typed
output shape. The job-posting extractor wraps user text in a
``<job_posting>`` delimiter; resume text is passed bare here because the
schema is the only contract that matters and the delimiter would add
noise the LLM has to parse (RESEARCH §3 / PATTERNS §1).
"""

import instructor
from tenacity import retry, stop_after_attempt, wait_exponential

from job_rag.config import settings
from job_rag.extraction.resume_prompt import (
    RESUME_PROMPT_VERSION,
    RESUME_SYSTEM_PROMPT,
)
from job_rag.logging import get_logger
from job_rag.models import ResumeExtraction
from job_rag.observability import get_openai_client

log = get_logger(__name__)


@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def extract_resume(text: str) -> tuple[ResumeExtraction, dict]:
    """Extract a structured :class:`ResumeExtraction` from raw resume text.

    Returns a tuple of ``(ResumeExtraction, usage_info)`` where ``usage_info``
    holds ``model``, ``prompt_version``, and OpenAI token counters for the
    upload route's Langfuse ``llm_extract`` span.

    After 3 retries the underlying exception is re-raised. The upload route
    maps:
      - ``pydantic.ValidationError`` → 422 ``extraction_failed`` (D-16, D-35)
      - ``openai.APIError`` family → 503 ``llm_unavailable`` (D-35)
    """
    client = instructor.from_openai(get_openai_client())

    extraction, completion = client.chat.completions.create_with_completion(
        model=settings.openai_model,
        response_model=ResumeExtraction,
        messages=[
            {"role": "system", "content": RESUME_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )

    usage = completion.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0

    usage_info = {
        "model": settings.openai_model,
        "prompt_version": RESUME_PROMPT_VERSION,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    log.info(
        "resume_extraction_complete",
        skills_count=len(extraction.skills),
        **usage_info,
    )
    return extraction, usage_info

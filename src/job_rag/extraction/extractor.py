import re

import instructor
from tenacity import retry, stop_after_attempt, wait_exponential

from job_rag.config import settings
from job_rag.extraction.prompt import PROMPT_VERSION, SYSTEM_PROMPT
from job_rag.logging import get_logger
from job_rag.models import JobPosting
from job_rag.observability import get_openai_client

log = get_logger(__name__)

# Pricing per 1M tokens (USD) for gpt-4o-mini as of 2025-04
_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


def _compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = _PRICING.get(model, {"input": 0.15, "output": 0.60})
    return (prompt_tokens * prices["input"] + completion_tokens * prices["output"]) / 1_000_000


def extract_linkedin_id(url: str) -> str | None:
    match = re.search(r"/jobs/view/(\d+)", url)
    return match.group(1) if match else None


def _sanitize_delimiters(text: str) -> str:
    """Strip delimiter tags from text to prevent prompt injection escape."""
    return text.replace("<job_posting>", "").replace("</job_posting>", "")


@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def extract_posting(raw_text: str) -> tuple[JobPosting, dict]:
    """Extract structured data from a job posting using Instructor.

    Returns a tuple of (JobPosting, usage_info) where usage_info contains
    token counts and cost.
    """
    client = instructor.from_openai(get_openai_client())

    posting, completion = client.chat.completions.create_with_completion(
        model=settings.openai_model,
        response_model=JobPosting,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "<job_posting>\n"
                    f"{_sanitize_delimiters(raw_text)}\n"
                    "</job_posting>"
                ),
            },
        ],
    )

    usage = completion.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    cost = _compute_cost(settings.openai_model, prompt_tokens, completion_tokens)

    usage_info = {
        "model": settings.openai_model,
        "prompt_version": PROMPT_VERSION,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": cost,
    }

    log.info(
        "extraction_complete",
        company=posting.company,
        title=posting.title,
        requirements_count=len(posting.requirements),
        **usage_info,
    )

    return posting, usage_info

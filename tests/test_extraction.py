from unittest.mock import MagicMock, patch

from job_rag.extraction.extractor import extract_linkedin_id, extract_posting
from job_rag.extraction.prompt import PROMPT_VERSION
from job_rag.models import JobPosting, RemotePolicy, SalaryPeriod, Seniority


class TestExtractLinkedInId:
    def test_standard_url(self):
        url = "https://www.linkedin.com/jobs/view/4387647030/"
        assert extract_linkedin_id(url) == "4387647030"

    def test_url_without_trailing_slash(self):
        url = "https://www.linkedin.com/jobs/view/4387647030"
        assert extract_linkedin_id(url) == "4387647030"

    def test_url_with_query_params(self):
        url = "https://www.linkedin.com/jobs/view/4387647030/?trackingId=abc"
        assert extract_linkedin_id(url) == "4387647030"

    def test_non_linkedin_url(self):
        assert extract_linkedin_id("https://example.com/job/123") is None

    def test_empty_string(self):
        assert extract_linkedin_id("") is None


class TestExtractPosting:
    def test_extract_returns_posting_and_usage(self, sample_raw_text: str):
        mock_posting = JobPosting(
            title="Senior AI Engineer",
            company="TestCorp",
            location="Berlin, Germany",
            remote_policy=RemotePolicy.HYBRID,
            salary_min=70000,
            salary_max=90000,
            salary_raw="€70,000-€90,000/year",
            salary_period=SalaryPeriod.YEAR,
            seniority=Seniority.SENIOR,
            employment_type="Full-time",
            requirements=[],
            responsibilities=["Build AI systems"],
            source_url="https://www.linkedin.com/jobs/view/1234567890/",
            raw_text=sample_raw_text,
        )

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 500
        mock_usage.completion_tokens = 200

        mock_completion = MagicMock()
        mock_completion.usage = mock_usage

        with patch("job_rag.extraction.extractor.instructor") as mock_instructor:
            mock_client = MagicMock()
            mock_instructor.from_openai.return_value = mock_client
            mock_client.chat.completions.create_with_completion.return_value = (
                mock_posting,
                mock_completion,
            )

            posting, usage_info = extract_posting(sample_raw_text)

            assert posting.company == "TestCorp"
            assert posting.title == "Senior AI Engineer"
            assert usage_info["prompt_tokens"] == 500
            assert usage_info["completion_tokens"] == 200
            assert usage_info["total_tokens"] == 700
            assert usage_info["cost_usd"] > 0
            assert usage_info["prompt_version"] == PROMPT_VERSION

    def test_prompt_version_is_set(self):
        assert PROMPT_VERSION == "1.1"

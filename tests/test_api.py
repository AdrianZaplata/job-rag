import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from job_rag.api.app import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_ok(self):
        with patch("job_rag.api.routes.get_session") as mock_dep:
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock()

            async def session_gen():
                yield mock_session

            mock_dep.return_value = session_gen()
            app.dependency_overrides[
                __import__("job_rag.api.deps", fromlist=["get_session"]).get_session
            ] = lambda: session_gen()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Override the dependency properly
                from job_rag.api.deps import get_session

                async def override_session():
                    yield mock_session

                app.dependency_overrides[get_session] = override_session
                response = await client.get("/health")

            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
class TestSearchEndpoint:
    async def test_search_no_generate(self):
        from job_rag.api.deps import get_session

        mock_session = AsyncMock()

        async def override_session():
            yield mock_session

        mock_results = [
            {
                "posting": MagicMock(
                    id=uuid.uuid4(),
                    title="AI Engineer",
                    company="TestCorp",
                    location="Berlin",
                    remote_policy="remote",
                    seniority="senior",
                ),
                "distance": 0.2,
                "similarity": 0.8,
            }
        ]

        app.dependency_overrides[get_session] = override_session

        with patch("job_rag.api.routes.search_postings", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_results
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                params = {"q": "RAG experience", "generate": "false"}
                response = await client.get("/search", params=params)

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["company"] == "TestCorp"

    async def test_search_with_generate(self):
        from job_rag.api.deps import get_session

        mock_session = AsyncMock()

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        with patch("job_rag.api.routes.rag_query", new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = {
                "answer": "Based on the postings, TestCorp values RAG experience.",
                "sources": [{"id": "123", "title": "AI Eng", "company": "TestCorp"}],
            }
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/search", params={"q": "RAG experience"})

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data


@pytest.mark.asyncio
class TestMatchEndpoint:
    async def test_match_not_found(self):
        from job_rag.api.deps import get_session

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/match/{uuid.uuid4()}")

        app.dependency_overrides.clear()

        assert response.status_code == 404


@pytest.mark.asyncio
class TestGapsEndpoint:
    async def test_gaps_no_postings(self):
        from job_rag.api.deps import get_session

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/gaps")

        app.dependency_overrides.clear()

        assert response.status_code == 404

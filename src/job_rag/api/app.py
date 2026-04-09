from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from job_rag.api.routes import router
from job_rag.db.engine import async_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await async_engine.dispose()


app = FastAPI(
    title="Job RAG API",
    description="RAG system for AI Engineer job postings — search, matching, and gap analysis",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(router)

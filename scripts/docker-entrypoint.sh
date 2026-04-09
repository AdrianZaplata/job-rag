#!/bin/bash
set -e

echo "Initializing database..."
job-rag init-db

echo "Ingesting postings..."
job-rag ingest

echo "Generating embeddings..."
job-rag embed

echo "Starting API server..."
exec uvicorn job_rag.api.app:app --host 0.0.0.0 --port 8000

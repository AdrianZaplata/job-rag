out = r"C:/Users/adria/Documents/Repo/Career/job-rag/.planning/research/SUMMARY.md"
content = """# Project Research Summary

**Project:** job-rag web app milestone
**Domain:** Personal job-market intelligence SPA + streaming AI chat on existing FastAPI / LangGraph / pgvector backend, Azure free tier
**Researched:** 2026-04-23
**Confidence:** HIGH"""
with open(out, "w", encoding="utf-8") as f:
    f.write(content)
print("done")

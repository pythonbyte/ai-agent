# Tools guide

## http_get

Fetches text from public http(s) URLs. Non-http schemes are rejected.

## workspace_search

Search (`action=search`) or read (`action=read`) files under `workspace_root`.
Path traversal outside the root is blocked.

## memory

Durable key/value store in SQLite (`sqlite_path`). Survives process restarts.

## retrieve

Semantic search over documents ingested into Chroma (`chroma_path`).
Run `ai-agent ingest --docs docs/` before relying on this tool.

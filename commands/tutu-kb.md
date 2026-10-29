---
description: Search or update the Tutu knowledge base (global paper library + this project's research-wiki)
argument-hint: <query> | add <arxiv-id/doi/title> | promote <path>
---

Knowledge-base request: `$ARGUMENTS`

- **Search** (default): run `tutu kb search "<query>" --scope all`. Show the hits (scope, title, path, snippet) and offer to open the most relevant pages.
- **add <id/title>**: delegate to `tutu:research`: fetch metadata (aris:arxiv / aris:semantic-scholar), read the paper, run `tutu kb add-paper ...`, fill in the page, and ingest it into `research-wiki/` if this is a Tutu project.
- **promote <path>**: this copies a project page into the global library. Confirm with the user that it contains no private data or unpublished results, then run `tutu kb promote <path> --approve`.
- **reindex**: `tutu kb reindex`.

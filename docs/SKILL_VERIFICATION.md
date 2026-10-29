# Skill installation and verification report

- **Date:** 2026-10-29
- **Machine:** Ubuntu 24.04, CPU only (no GPU), Python 3.12.3, Claude Code 2.1.312
- **Install command:** `python install.py --extras deepxiv-sdk exa-py wandb`, plus `tutu deps --with-latex --with-drawio`
- **Upstream versions:** superpowers 7.0.1 · ARIS `a3a847b` · Supervisor-Skills `a20d76e` · humanizer 3.1.0

Rerun the checks yourself with `tutu doctor --skills --live`.

## 1. Installation checks (`tutu doctor --skills --live`): all PASS

| Check | Result |
|---|---|
| Skills loaded by Claude Code | 115/115: superpowers 15, aris 87, supervisor-skills 12, humanizer 1 |
| SKILL.md frontmatter (name + description) | all valid |
| Files referenced by the 77 mapped skills (references/, scripts/, shared-references/) | all present |
| ARIS helper resolution through `~/.aris/repo` | 62/62 helper references resolve |
| Tutu venv libraries (numpy, scipy, pandas, matplotlib, seaborn, Pillow, python-pptx, pypdf, requests, pyyaml) + extras (deepxiv-sdk, exa-py, wandb) | all present |
| latexmk, pdflatex, xelatex, bibtex | present (TeX Live 2023) |
| draw.io desktop 32.6.1 (+ xvfb, headless wrapper) | present |
| screen, ssh, rsync | present |
| Live reviewer round-trip (`claude-review` MCP → separate `claude -p`) | OK, threadId returned |
| Optional API keys (Semantic Scholar, Exa, WandB, Gemini) | not set (optional) |

## 2. Helper smoke tests (no LLM)

| Helper | Result |
|---|---|
| `arxiv_fetch.py search` | PASS (returns papers) |
| `openalex_fetch.py search` | PASS |
| `verify_papers.py --arxiv-ids 1706.03762` | PASS (verdict PASS, hallucination_rate 0.0) |
| `research_wiki.py init / ingest_paper / stats` | PASS |
| `reviewer_route.py` in a Tutu project | PASS → `claude-code`, transport `mcp`, fresh_tool `mcp__claude-review__review` |
| `semantic_scholar_fetch.py search` | **HTTP 429 (rate limit)**: the public API without a key is throttled. Set `SEMANTIC_SCHOLAR_API_KEY`; aris:research-lit also falls back to arXiv/OpenAlex |
| `latexmk -pdf` with bibtex / `latexmk -xelatex` | PASS (PDF built, citation resolved) |
| drawio-reconstruction `export_drawio.py` on `examples/data_lake.drawio` | PASS (PNG 1672×958, headless, as root) |
| matplotlib (Agg) figure, python-pptx deck, scipy test, pypdf read | PASS |

## 3. Skills invoked through Claude Code (Sonnet 5.5)

Each test ran through `claude -p`. The Skill tool call was confirmed in the session transcript, and the artifact was checked.

| Repo | Skill | Artifact check | Result |
|---|---|---|---|
| humanizer | `humanizer:humanizer` | `human.txt` rewritten, AI tells removed, meaning kept | PASS |
| Supervisor-Skills | `supervisor-skills:idea-evaluator` | `idea_eval.md` covers Higher/Faster/Stronger/Cheaper/Broader | PASS |
| superpowers | `superpowers:systematic-debugging` | root cause fixed in `stats.py` (ddof and √n); `test_stats.py` prints OK | PASS |
| ARIS | `aris:arxiv` + `aris:research-wiki` | `research-wiki/papers/bhattacharya2018_relating_eyetracking_measures.md` created | PASS |
| ARIS | `aris:paper-compile` | `main.pdf` built, 0 undefined citations | PASS |

## 4. Reviewer (independent, separate process)

**Setup.** A Tutu project with a draft results section containing 4 planted errors:
1. AUC 0.84 reported, while the run recorded 0.71.
2. A fabricated citation.
3. A claim with no evidence label.
4. A trial-level split described as "subject-independent".

**Run.** The `tutu:reviewer` subagent was dispatched with only the artifact paths and the acceptance criteria.

| Criterion | Result |
|---|---|
| Verdict | **FAIL** (correct) |
| Planted errors detected | **4/4**: wrong number vs run_id, fake DOI (Crossref 404), unlabeled claim, subject leakage (verified from the data) |
| Extra valid findings | CI ignores clustering within subjects, single seed, missing `train.py`, confounders, no ethics statement |
| External reviewer process | debug log shows `claude-review` `review_start` → `review_status`; the review file records `backend: claude-code, transport: mcp, threadId …` |
| Models | reviewer subagent `claude-opus-5-5`; research subagent `claude-sonnet-5-5` (debug log) |
| Cost | about $1.10 |

## Known limitations

- Windows was not tested on this machine. CI (GitHub Actions) runs the test suite on windows-latest.
- Cross-model review (Codex) is not installed; the backend is `claude`. To enable it: set `reviewer.backend = "codex"` and run `/aris:setup`.
- In projects without `.aris/reviewer.json` (non-Tutu projects), ARIS defaults to the Codex reviewer. `tutu init` and the SessionStart hook write this file in Tutu projects.

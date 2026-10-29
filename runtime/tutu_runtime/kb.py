"""Searchable knowledge base (SQLite FTS5, stdlib only).

Two tiers, kept separate for project isolation:
  global  : ~/.tutu/knowledge/        public literature shared by every project
            papers/<slug>.md  (ARIS research-wiki paper schema)  + library.bib
  project : <project>/research-wiki/  ideas, experiments, claims, papers (ARIS research-wiki)
            plus <project>/.tutu/notes/

A search never touches a project other than the current one.
Project notes reach the global library only via promote(), which requires
[knowledge] kb_share = true in the project config or an explicit approval.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path

from . import config as config_mod
from . import trace
from .paths import expand, project_dir

INDEX_SUFFIXES = {".md", ".markdown", ".txt", ".bib", ".tex"}


def global_root(cfg: dict | None = None) -> Path:
    root = config_mod.get(cfg or config_mod.load(), "knowledge.root", "~/.tutu/knowledge")
    return expand(root)


def _project_sources(project_root: Path) -> list[Path]:
    return [project_root / "research-wiki", project_dir(project_root) / "notes"]


def _db_path(scope: str, project_root: Path | None, cfg: dict) -> Path:
    if scope == "global":
        return global_root(cfg) / ".index.sqlite"
    assert project_root is not None
    return project_dir(project_root) / "kb.sqlite"


def _connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(path UNINDEXED, title, body, tokenize='unicode61 remove_diacritics 2')")
    con.execute("CREATE TABLE IF NOT EXISTS meta(path TEXT PRIMARY KEY, mtime REAL)")
    return con


def _title(path: Path, text: str) -> str:
    m = re.search(r"^title:\s*\"?(.+?)\"?\s*$", text, re.M) or re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else path.stem


def _iter_files(roots: list[Path]):
    for r in roots:
        if r.is_dir():
            for p in r.rglob("*"):
                if p.is_file() and p.suffix.lower() in INDEX_SUFFIXES and not p.name.startswith("."):
                    yield p


def index(scope: str, project_root: Path | None = None, cfg: dict | None = None) -> int:
    """Incrementally (re)index one scope. Returns number of documents updated."""
    cfg = cfg or config_mod.load(project_root)
    roots = [global_root(cfg)] if scope == "global" else _project_sources(project_root)
    con = _connect(_db_path(scope, project_root, cfg))
    seen, updated = set(), 0
    with con:
        known = dict(con.execute("SELECT path, mtime FROM meta"))
        for p in _iter_files(roots):
            key = str(p)
            seen.add(key)
            mtime = p.stat().st_mtime
            if known.get(key) == mtime:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            con.execute("DELETE FROM docs WHERE path = ?", (key,))
            con.execute("INSERT INTO docs(path, title, body) VALUES (?, ?, ?)", (key, _title(p, text), text))
            con.execute("INSERT OR REPLACE INTO meta(path, mtime) VALUES (?, ?)", (key, mtime))
            updated += 1
        for gone in set(known) - seen:
            con.execute("DELETE FROM docs WHERE path = ?", (gone,))
            con.execute("DELETE FROM meta WHERE path = ?", (gone,))
    con.close()
    return updated


def _fts_query(q: str) -> str:
    # Quote each token so user text (e.g. "AUC-ROC", "MCI:AD") can't break FTS5 syntax.
    toks = re.findall(r"[\w\-]+", q, re.UNICODE)
    return " ".join('"' + t.replace('"', "") + '"' for t in toks) or '""'


def search(query: str, scope: str = "all", project_root: Path | None = None, limit: int = 10) -> list[dict]:
    cfg = config_mod.load(project_root)
    scopes = {"all": ["project", "global"], "project": ["project"], "global": ["global"]}[scope]
    if project_root is None:
        scopes = [s for s in scopes if s == "global"]
    hits = []
    for s in scopes:
        index(s, project_root, cfg)
        con = _connect(_db_path(s, project_root, cfg))
        rows = con.execute(
            "SELECT path, title, snippet(docs, 2, '[', ']', ' … ', 16), bm25(docs) "
            "FROM docs WHERE docs MATCH ? ORDER BY bm25(docs) LIMIT ?",
            (_fts_query(query), limit),
        ).fetchall()
        con.close()
        hits += [{"scope": s, "path": p, "title": t, "snippet": sn, "score": round(-sc, 3)} for p, t, sn, sc in rows]
    return sorted(hits, key=lambda h: -h["score"])[:limit]


def _slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def paper_slug(first_author: str, year: int | str, keyword: str) -> str:
    """ARIS research-wiki convention: <first_author_last_name><year>_<keyword>."""
    last = first_author.strip().split()[-1] if first_author.strip() else "anon"
    return f"{_slugify(last)}{year}_{_slugify(keyword)[:24] or 'paper'}"


PAPER_TEMPLATE = """---
type: paper
node_id: paper:{slug}
title: "{title}"
authors: [{authors}]
year: {year}
venue: "{venue}"
ids: {{doi: "{doi}", arxiv: "{arxiv}", url: "{url}"}}
tags: [{tags}]
added: {added}
added_by_project: "{project}"
---

# {title}

## TL;DR
{tldr}

## Problem / Motivation
TODO

## Method
TODO

## Data & Setup
TODO  <!-- dataset, cohort size, modality (eye-tracking / MRI / OCT / fundus ...), splits -->

## Key Results
TODO  <!-- numbers WITH their source table/figure -->

## Limitations / Threats to validity
TODO

## Relevance to my research
TODO

## Evidence labels
Facts above are [Source: this paper]. Mark anything else as [Inference] or [Hypothesis].
"""


def add_paper(*, title: str, authors: list[str], year: int | str, keyword: str, venue: str = "",
              doi: str = "", arxiv: str = "", url: str = "", tags: list[str] = (), tldr: str = "TODO",
              project_root: Path | None = None, bibtex: str = "") -> Path:
    """Create (or return existing) global paper page. Public literature only."""
    root = global_root(config_mod.load(project_root))
    slug = paper_slug(authors[0] if authors else "", year, keyword)
    page = root / "papers" / f"{slug}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    if not page.exists():
        page.write_text(PAPER_TEMPLATE.format(
            slug=slug, title=title.replace('"', "'"), authors=", ".join(f'"{a}"' for a in authors),
            year=year, venue=venue, doi=doi, arxiv=arxiv, url=url, tags=", ".join(tags),
            added=date.today().isoformat(), project=project_root.name if project_root else "",
            tldr=tldr), encoding="utf-8")
    if bibtex.strip():
        bib = root / "library.bib"
        existing = bib.read_text(encoding="utf-8") if bib.exists() else ""
        key = re.search(r"@\w+\{([^,]+),", bibtex)
        if not key or key.group(1) not in existing:
            with bib.open("a", encoding="utf-8") as f:
                f.write(bibtex.strip() + "\n\n")
    if project_root:
        trace.append(project_root, {"type": "kb_add_paper", "slug": slug, "path": str(page)})
    return page


def promote(project_root: Path, rel_path: str, approved: bool = False) -> Path:
    """Copy a project knowledge page into the global library (isolation gate)."""
    cfg = config_mod.load(project_root)
    if not (approved or config_mod.get(cfg, "knowledge.kb_share", False)):
        raise PermissionError(
            "Project isolation: set [knowledge] kb_share = true in .tutu/project.toml "
            "or pass --approve after the user confirms this page contains no private data.")
    src = (project_root / rel_path).resolve()
    dst = global_root(cfg) / "promoted" / project_root.name / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    trace.append(project_root, {"type": "kb_promote", "src": rel_path, "dst": str(dst), "approved": approved})
    return dst

---
description: Make the current project a Tutu project (.tutu/, ARIS reviewer route, research-wiki)
argument-hint: "[project name]"
---

Initialize Tutu in the current project:

1. Run `tutu init --name "$ARGUMENTS"`, or `tutu init` if no name was given. Show the output.
2. Open `.tutu/project.toml` and walk the user through the settings that matter, asking with AskUserQuestion:
   - `data.protected_paths`: where raw data lives (made read-only for agents);
   - `data.sensitivity` (public / deidentified / phi) and `sensitive_paths`;
   - `ethics.irb_protocol`;
   - `reviewer.backend` (claude | codex);
   - per-project budget overrides.
   Edit the file with their answers. Don't guess paths: look at the repo (e.g. `data/`, `raw/`, `*.dcm`, `*.edf`, `*.asc`, `*.tsv`) and propose them.
3. `tutu init` adds a `## Local Environment` section (`gpu: local`, `python: python3`) to the project CLAUDE.md if there is no GPU section yet. ARIS experiment skills read it. Show the user that section, and change `python:` to their experiment env if it differs, and `gpu:` to `remote`/`vast`/`modal` with server details if they use one.
4. Run `tutu doctor --skills` and report any `MISSING` lines with their fix.
5. Suggest adding `.tutu/kb.sqlite` to .gitignore (already in `.tutu/.gitignore`), and committing `.tutu/project.toml` and `.tutu/plans/` if the user wants a shared trail.

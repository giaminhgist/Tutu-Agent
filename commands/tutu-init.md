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
3. Run `tutu doctor` and report any `!!` lines with their fix.
4. Suggest adding `.tutu/kb.sqlite` to .gitignore (already in `.tutu/.gitignore`), and committing `.tutu/project.toml` and `.tutu/plans/` if the user wants a shared trail.

# Tutu shared protocol

Every Tutu agent follows this file. Agents get it as `${CLAUDE_PLUGIN_ROOT}/config/protocol.md`.

## 1. Where things live (in the user's project)

| Path | Owner | Content |
|---|---|---|
| `.tutu/project.toml` | user | project settings: protected data, sensitivity, budgets, reviewer backend |
| `.tutu/plans/<YYYYMMDD-HHMM>-<slug>.md` | orchestrator | task plan (one per goal) |
| `.tutu/artifacts/<task-id>/` | the agent that did the task | reports, tables, figures, drafts |
| `.tutu/runs/<run_id>/manifest.json` | experiment agent (`tutu provenance`) | code, data, config, seed and env snapshot for one run |
| `.tutu/reviews/<YYYYMMDD-HHMM>-<target>.md` | reviewer | independent verdicts |
| `.tutu/approvals/pending.md` | anyone | actions waiting for a human |
| `.tutu/trace.jsonl` | everyone (`tutu trace`) | append-only audit trail |
| `.tutu/notes/` | anyone | private project notes (indexed by the KB, project scope only) |
| `research-wiki/` | research and methodology agents (aris:research-wiki) | project knowledge: papers, ideas, experiments, claims |
| `~/.tutu/knowledge/papers/` | research agent (`tutu kb add-paper`) | global library of public papers, shared across projects |

If `.tutu/` does not exist, ask the user to run `/tutu:tutu-init` (or `tutu init`) before writing anything.

## 2. Evidence labels (mandatory for scientific content)

Every scientific statement in a report, plan, review or draft carries one label:

- `[Source: <citation or path>]`: a fact taken from a paper (with page, table or section when possible), a dataset or a result file. Numbers need `run_id` or the file path.
- `[Inference]`: your reasoning from sourced facts. State the facts it rests on.
- `[Hypothesis]`: a conjecture that still has to be tested. Say how it could be tested.

Never upgrade a label: a hypothesis does not become a fact because a model said it confidently.
Never invent citations, numbers, datasets or authors. If you cannot verify one, write `[UNVERIFIED]` and flag it.

## 3. Reproducibility

- Before any experiment, run `tutu provenance capture --cmd "<exact command>" --config <cfg> --data <dir> --seed <s> [--name <slug>]`. The command prints a `run_id`.
- After the run, run `tutu provenance finalize <run_id> --status succeeded|failed --result <file> --metrics <json>`.
- A number may appear in a table, figure or paper only if it traces to a `run_id`, or to a published source cited with `[Source: ...]`.
- Use fixed seeds. Report mean ± std or a 95% CI over at least 3 seeds when compute allows; otherwise say "single seed".
- Device is `auto` (cuda > mps > cpu). On CPU, use pilot-sized configs and say so in the report.

## 4. Human-in-the-loop (ask before acting)

Get explicit approval, via the orchestrator or `.tutu/approvals/pending.md`, before:
- modifying anything under `data.protected_paths` (the guard hook denies this outright);
- using data marked `sensitivity = "phi"`, sending any project data off the machine, or uploading to external services;
- GPU jobs above `budget.max_gpu_hours_per_run`, any cloud GPU (vast.ai, Modal), or Slurm submission;
- `git push`, opening or merging PRs, submitting papers, Overleaf push, publishing packages or models;
- deleting results, rewriting git history, or any other irreversible step.

## 5. Quality gates

- "Done" requires evidence from something that ran (test output, metric file, compiled PDF), not a model's assertion.
- Scientific artifacts (lit synthesis, novelty verdict, experiment plan, results to claims, paper sections) pass the **reviewer** agent, a fresh context, before the orchestrator marks them complete.
- A reviewer verdict is one of `PASS`, `PASS_WITH_FIXES`, `FAIL`, with reasons. Two consecutive `FAIL`s on the same artifact mean you stop and escalate to the human.

## 6. Cost awareness

- Respect `[budget]` in config: `max_parallel_subagents`, `max_loop_iterations`, `max_gpu_hours_per_run`, `max_usd_per_session`.
- Before an expensive step, check it: `tutu budget check gpu_hours <est>` (exit code 2 means over the cap, so ask).
- Record actual GPU time with `tutu budget add gpu_hours <h> --note <run_id>`.
- Prefer cheap probes first: a pilot run, a small subset, CPU smoke tests.

## 7. Project isolation

- Work only inside the current project and the global paper library.
- Never read another project's `.tutu/`, `research-wiki/` or data.
- Only public literature goes to `~/.tutu/knowledge`. Private notes, results and ideas stay in the project unless `[knowledge] kb_share = true` or the user approves `tutu kb promote <path> --approve`.

## 8. Knowledge first

Before searching the web, run `tutu kb search "<query>"` (scopes: `project`, `global`, `all`). After reading a paper, store it with `tutu kb add-paper ...` and fill the page. Use aris:research-wiki for project-level ingest and relationships.

## 9. Handoff format (every subagent ends with this)

```
## Handoff
status: done | partial | blocked
artifacts: [paths]
evidence: [run_ids / sources / test commands with their results]
claims: [each claim with its evidence label]
open_questions: [...]
needs_approval: [... or none]
cost: {usd_est, gpu_hours, wall_time}
next: <suggested next task and agent>
```

After each task, append one line to the trace:
`tutu trace task_done --data '{"agent":"<name>","task":"<id>","artifacts":[...],"status":"..."}'`

## 10. Borrowing skills

Each agent preloads about 6 core skills (see `config/skill-map.toml`). Any other installed skill can be invoked with the Skill tool when the task needs it, e.g. writing borrows `aris:paper-compile`. Prefer the skill-map's `borrow` list. Name the skill you used in the handoff.

## 11. Platform notes

- Commands must work in Linux bash and in Git Bash on Windows. Use Python for anything non-trivial, use forward-slash paths, and avoid `screen`, `jq` and GNU-only flags in Tutu's own steps.
- Some ARIS skills (experiment-queue over SSH/screen) are Linux-only. On Windows, use aris:run-experiment locally.
- ARIS helper scripts call `python3`. On Windows without `python3`, set `TUTU_PYTHON` and use `py -3` where needed.

## 12. Scratch files and Python environments

- Temporary scripts and intermediate files go only in `.tutu/artifacts/<task-id>/scratch/`. Delete them before your handoff unless they are a deliverable, and then list them under `artifacts`.
- `.tutu/notes/` is for human-readable notes only.
- The reviewer flags any leftover scratch files.
- **Which Python to use:**
  - `tutu-py` (the Tutu venv: numpy, scipy, pandas, matplotlib, seaborn, Pillow, python-pptx, pypdf, requests, pyyaml) runs ARIS helper scripts (`"$ARIS_REPO"/tools/*.py`) and analysis or figure scripts. When a skill says `python3 <ARIS helper>`, run it with `tutu-py` if `python3` lacks the needed libraries.
  - **Experiment and training code** runs in the project's own environment (the conda env or venv on PATH, or `python:` in the project CLAUDE.md), never in `tutu-py`.
- `tutu provenance capture` records the experiment environment by default, the python on PATH. Pass `--python <path>` to override it.

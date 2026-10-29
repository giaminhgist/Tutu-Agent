# Tutu Agent

**Tutu** is a multi-agent research system that runs on Claude Code and the Claude Agent SDK. You give it a goal. Tutu plans the work, finds evidence, implements, runs experiments, evaluates, keeps an audit trail, and returns reproducible artifacts. It is installed **once per machine (user level)** and works in any project you open with Claude Code, on **Ubuntu and Windows**. A GPU is optional; without one, work runs on the CPU.

Built for AI research in eye tracking, medical imaging, dementia diagnosis, computer vision and representation learning.

> Tutu ships no skills of its own. It **orchestrates** four existing skill libraries: [superpowers](https://github.com/obra/superpowers), [ARIS](https://github.com/wanshuiyin/auto-claude-code-research-in-sleep), [Supervisor-Skills](https://github.com/HKUSTDial/Supervisor-Skills) and [humanizer](https://github.com/blader/humanizer). On top of them it adds agents, guardrails (hooks), provenance, a knowledge base and a headless runner.

---

## 1. Installation (once per machine)

Requirements: [Claude Code](https://code.claude.com/docs), Python ≥ 3.11, and git. On Windows, Claude Code uses Git Bash.

```bash
git clone https://github.com/giaminhgist/Tutu-Agent.git
cd Tutu-Agent
python install.py                # Windows: py -3 install.py
```

`install.py` does the following:
1. Adds this checkout as the `tutu` marketplace.
2. Installs 5 plugins at user scope: `tutu`, `superpowers`, `aris`, `humanizer`, `supervisor-skills`.
3. Creates `~/.tutu/` (config plus the global knowledge library).
4. Points ARIS at its helper scripts.
5. Registers a fresh-context Claude reviewer (`claude-review` MCP).
6. Runs `doctor`.

To update later, run `git pull`. The plugin is read in place from the checkout.

Manual alternative (inside Claude Code):
```
/plugin marketplace add giaminhgist/Tutu-Agent
/plugin install tutu@tutu        # dependencies superpowers, aris, humanizer, supervisor-skills come along
```
Then run `tutu setup` once in Claude Code's Bash, or `python -m tutu_runtime setup` with `PYTHONPATH=runtime`.

**Cross-model reviewer (optional):** `python install.py --reviewer codex`, then install the Codex CLI, log in, and run `/aris:setup` once.

## 2. Usage in any project

```
/tutu:tutu-init                       # create .tutu/, declare raw data (read-only), sensitivity, IRB, budget
/tutu:tutu <research goal>            # orchestrator: plan → delegate → review → report
/tutu:tutu-kb <query>                 # search the knowledge base
/tutu:tutu-status                     # plans, runs, reviews, pending approvals, budget
```
Or run the orchestrator as the main agent: `claude --agent tutu:orchestrator`.

Example goals:
- `/tutu:tutu survey eye-tracking biomarkers for early Alzheimer's detection 2019–2026, comparison table + gaps`
- `/tutu:tutu propose 3 novel ideas for self-supervised scanpath representations for MCI screening and check novelty`
- `/tutu:tutu design and run a CPU pilot: logistic regression vs. GRU on gaze features, subject-level 5-fold CV`
- `/tutu:tutu draft the Methods and Results for MICCAI from runs <ids>, following CLAIM`
- `/tutu:tutu peer review paper.pdf as a TMI reviewer`

### Headless Auto Research Loop (Claude Agent SDK)
```bash
pip install claude-agent-sdk
tutu run --goal "..." --budget-usd 5 --max-iter 3      # or: python -m tutu_runtime run ...
tutu run --goal "..." --dry-run                        # show config, call nothing
```
In headless mode every high-risk action is **denied automatically** and written to `.tutu/approvals/pending.md` for review afterwards.

## 3. Architecture

```
            ┌──────────────── Tutu Orchestrator (plan · dispatch · gates · approvals) ───────────────┐
            │                                                                                       │
 Research ── Methodology ── Coding ── Experiment ── Writing ──────────────► Reviewer (fresh context, independent)
 (lit, KB)   (ideas, design)  (RSE)   (runs, stats)  (paper, figs)            PASS / PASS_WITH_FIXES / FAIL
            │                                                                                       │
            └── hooks: guard (HITL) · provenance nudge · session context ── runtime: provenance · KB · budget · trace ──┘
```

| Agent | Preloaded skills (~6) | Commonly borrowed |
|---|---|---|
| **orchestrator** | superpowers: brainstorming, writing-plans, dispatching-parallel-agents, verification-before-completion · aris: research-pipeline · supervisor: vibe-research-workflow | aris: render-html, research-refine-pipeline |
| **research** | supervisor: deep-research · aris: research-lit, arxiv, semantic-scholar, alphaxiv, research-wiki | openalex, deepxiv, exa-search, wiki-enrich |
| **methodology** | aris: idea-discovery, idea-creator, novelty-check, research-refine, experiment-plan · supervisor: idea-evaluator | ablation-planner, formula-derivation |
| **coding** | aris: research-implement-feature, web-debug-search · superpowers: TDD, systematic-debugging, git-worktrees, verification | receiving-code-review, system-profile |
| **experiment** | aris: experiment-bridge, run-experiment, experiment-queue, monitor-experiment, training-check, analyze-results | paper-figure, ablation-planner, vast-gpu/modal (with approval) |
| **writing** | supervisor: paper-writer, figure-designer, paper-polish · aris: paper-writing, paper-figure · humanizer | grant-proposal, rebuttal, paper-slides, paper-compile, intro-drafter |
| **reviewer** | aris: research-review, result-to-claim, experiment-audit, paper-claim-audit, citation-audit · supervisor: pre-submission-reviewer | kill-argument, citation-crosscheck |

The single source of truth is `config/skill-map.toml`. The test `tests/test_skill_map.py` checks that the agents match the map and that every skill exists.

## 4. Design principles and how they are enforced

| Principle | Mechanism |
|---|---|
| **Evidence-first** | Required `[Source]` / `[Inference]` / `[Hypothesis]` labels (`config/protocol.md`). The reviewer rejects unlabeled claims. Citations go through `aris:citation-audit`. |
| **Reproducibility-by-default** | `tutu provenance capture` writes `.tutu/runs/<run_id>/manifest.json` with git commit + diff, data hashes, a config snapshot, seeds, `pip freeze`, OS and device. A hook nudges when an experiment runs without a manifest. Numbers without a `run_id` cannot go into the paper (`paper-claim-audit`). |
| **Project isolation** | Hooks are no-ops outside `.tutu/`. Agent memory is `memory: project`. The KB searches only the current project plus the public global library. `kb promote` requires `kb_share` or explicit approval. |
| **Human-in-the-loop** | `hooks/guard_hook.py`: **deny** writes to raw data and `rm -rf` outside the project; **ask** before git push, PRs, submissions, cloud GPU, Slurm, sending data off-machine, or reading PHI without approval. |
| **Quality gates** | Every scientific artifact passes the reviewer (fresh context, optional cross-model). `verification-before-completion` applies to code. Two FAILs mean escalation to a human. |
| **Cost-aware** | Caps in `~/.tutu/config.toml` (`max_usd_per_session`, `max_loop_iterations`, `max_parallel_subagents`, `max_gpu_hours_per_run`). `tutu budget check/add`. The SDK runner sets `max_budget_usd` and `max_turns`. |

## 5. Data layout

```
~/.tutu/
  config.toml                 global config (budget, reviewer backend, device)
  knowledge/papers/*.md       global paper library (public), ARIS research-wiki schema
  knowledge/library.bib
<project>/
  .tutu/project.toml          protected_paths, sensitivity, IRB, kb_share, budget overrides
  .tutu/plans/  artifacts/  runs/<run_id>/  reviews/  approvals/  notes/
  .tutu/trace.jsonl           audit trail   ·   .tutu/budget.jsonl
  .aris/reviewer.json         reviewer route used by the ARIS skills
  research-wiki/              project knowledge (ARIS): papers, ideas, experiments, claims
```

## 6. Additional domain features

`config/domain/` holds checklists the agents follow:
- **eye-tracking.md**: calibration, I-VT/I-DT, blink/data-loss handling, BIDS, participant-level splits.
- **medical-imaging.md**: DICOM de-identification, preprocessing, patient- and site-level validation, Dice/HD95, CLAIM.
- **dementia-clinical.md**: diagnostic criteria, confounders (age, education, vision), spectrum bias, STARD.
- **representation-learning.md**: linear probe/kNN/few-shot, contamination, site leakage in embeddings.
- **reporting-standards.md**: TRIPOD+AI, CLAIM, STARD, CONSORT/SPIRIT-AI, DECIDE-AI, PROBAST.

Suggested features you can add later on the same skeleton:
- A **dataset registry** (license/DUA, versions, DVC).
- **Model cards and datasheets** at release time.
- A **grant/IRB tracker**.
- An arXiv **paper-watch** (`/loop` + research agent).
- A Slurm adapter for the experiment agent.

## 7. Runtime CLI

`tutu <cmd>` (on the Bash PATH while the plugin is enabled) or `python -m tutu_runtime <cmd>`:

`setup` · `init` · `doctor` · `status` · `device` · `provenance capture|finalize|list` · `kb search|add-paper|promote|reindex` · `budget add|show|check` · `trace` · `run`

## 8. Cross-platform notes

- All runtime and hook logic is Python stdlib (≥ 3.11) using `pathlib`. Hooks start through `bash hooks/run.sh`, which finds `python3`, `python` or `py`. Set `TUTU_PYTHON` to force a specific interpreter.
- Some ARIS skills call `python3` directly. On Windows, make sure `python3` resolves (App Execution Alias or an alias in Git Bash).
- `aris:experiment-queue` (SSH + screen) is Linux-only. On Windows, the experiment agent uses `aris:run-experiment` locally.
- CI runs the test suite on `ubuntu-latest` and `windows-latest`.

## 9. Development

```bash
python -m pip install pytest && python -m pytest -q tests
claude plugin validate .
```

License: MIT. The skill libraries keep their own licenses.

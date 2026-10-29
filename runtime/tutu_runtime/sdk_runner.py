"""Headless Auto Research Loop on the Claude Agent SDK.

    python -m tutu_runtime run --goal "..." --project . --budget-usd 5 --max-iter 3

Runs the same Tutu orchestrator (/tutu:tutu) with the same plugins, agents and skills
as interactive Claude Code, but unattended:
  * hard caps: max_budget_usd, max_turns, loop iterations (from config, overridable)
  * every tool call goes through guard.evaluate(); "ask" becomes deny + an entry in
    .tutu/approvals/pending.md so a human can review it in the morning
  * all messages are streamed into .tutu/trace.jsonl and costs into budget.jsonl
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from . import budget, guard, trace
from . import config as config_mod
from .paths import plugin_root, project_dir

DEFAULT_MODEL = "claude-opus-5-5"

HEADLESS_RULES = """
HEADLESS MODE (Tutu SDK runner): no human is watching.
- Do not ask questions; record open questions in .tutu/approvals/pending.md and continue with
  the safest reversible option, or stop that branch.
- High-risk actions will be denied automatically and queued for approval; plan around them.
- Stop after {max_iter} research-loop iterations or when the reviewer gate fails twice in a row.
- Finish with a summary: artifacts produced (paths), run_ids, reviewer verdicts, open approvals.
"""


def build_prompt(goal: str, max_iter: int) -> str:
    return f"/tutu:tutu {goal}\n\n{HEADLESS_RULES.format(max_iter=max_iter)}"


def _queue_approval(root: Path, tool: str, tool_input: dict, reason: str) -> None:
    pending = project_dir(root) / "approvals" / "pending.md"
    pending.parent.mkdir(parents=True, exist_ok=True)
    with pending.open("a", encoding="utf-8") as f:
        f.write(f"\n## {trace.now()} — {tool}\n- reason: {reason}\n- input:\n```json\n"
                f"{json.dumps(tool_input, indent=2, ensure_ascii=False)[:4000]}\n```\n")


def make_permission_callback(root: Path):
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    async def can_use_tool(tool_name, tool_input, context):
        decision, reason = guard.evaluate(tool_name, tool_input, root)
        if tool_name == "AskUserQuestion":
            decision, reason = guard.ASK, "interactive question in headless mode"
        if decision == guard.ALLOW:
            return PermissionResultAllow()
        if decision == guard.ASK:
            _queue_approval(root, tool_name, tool_input, reason)
            trace.append(root, {"type": "approval_queued", "tool": tool_name, "reason": reason})
            return PermissionResultDeny(message=f"{reason}. Queued in .tutu/approvals/pending.md; continue without it.")
        trace.append(root, {"type": "denied", "tool": tool_name, "reason": reason})
        return PermissionResultDeny(message=reason)

    return can_use_tool


def build_options(root: Path, *, budget_usd: float, max_turns: int, model: str | None, dev_plugin: bool):
    from claude_agent_sdk import ClaudeAgentOptions

    kwargs = dict(
        cwd=str(root),
        setting_sources=["user", "project", "local"],  # loads globally installed Tutu + skill plugins
        permission_mode="default",
        can_use_tool=make_permission_callback(root),
        max_turns=max_turns,
        max_budget_usd=budget_usd,
    )
    if dev_plugin:  # run straight from a checkout without installing the plugin
        kwargs["plugins"] = [{"type": "local", "path": str(plugin_root())}]
    kwargs["model"] = model or DEFAULT_MODEL  # orchestrator runs on Opus; subagents use their own frontmatter model
    return ClaudeAgentOptions(**kwargs)


async def _run(root: Path, goal: str, opts, max_iter: int, session: str) -> dict:
    from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, ResultMessage, TextBlock

    result: dict = {}
    async with ClaudeSDKClient(options=opts) as client:
        await client.query(build_prompt(goal, max_iter))
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                text = "".join(b.text for b in msg.content if isinstance(b, TextBlock))
                if text.strip():
                    print(text, flush=True)
                    trace.append(root, {"type": "assistant", "session": session, "text": text[:2000]})
            elif isinstance(msg, ResultMessage):
                result = {"subtype": msg.subtype, "is_error": msg.is_error, "turns": msg.num_turns,
                          "cost_usd": msg.total_cost_usd, "session_id": msg.session_id,
                          "denials": len(msg.permission_denials or [])}
    return result


def run(goal: str, project: str = ".", *, budget_usd: float | None = None, max_iter: int | None = None,
        max_turns: int | None = None, model: str | None = None, dev_plugin: bool = False,
        dry_run: bool = False) -> dict:
    root = Path(project).resolve()
    if not project_dir(root).is_dir():
        raise SystemExit(f"{root} is not a Tutu project; run `python -m tutu_runtime init` there first.")
    cfg = config_mod.load(root)
    budget_usd = budget_usd if budget_usd is not None else float(config_mod.get(cfg, "budget.max_usd_per_session", 10))
    max_iter = max_iter or int(config_mod.get(cfg, "budget.max_loop_iterations", 3))
    max_turns = max_turns or int(config_mod.get(cfg, "budget.max_turns", 200))
    session = f"sdk-{trace.now()}"
    plan = {"project": str(root), "goal": goal, "budget_usd": budget_usd, "max_iter": max_iter,
            "max_turns": max_turns, "model": model or DEFAULT_MODEL, "dev_plugin": dev_plugin,
            "prompt": build_prompt(goal, max_iter)}
    if dry_run:
        return {"dry_run": True, **plan}
    opts = build_options(root, budget_usd=budget_usd, max_turns=max_turns, model=model, dev_plugin=dev_plugin)
    trace.append(root, {"type": "sdk_run_started", "session": session, **{k: v for k, v in plan.items() if k != "prompt"}})
    result = asyncio.run(_run(root, goal, opts, max_iter, session))
    if result.get("cost_usd"):
        budget.record(root, "usd", float(result["cost_usd"]), note=f"sdk run: {goal[:80]}", session=session)
    trace.append(root, {"type": "sdk_run_finished", "session": session, **result})
    return result

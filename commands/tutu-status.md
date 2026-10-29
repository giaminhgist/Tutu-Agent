---
description: Show Tutu status for this project (plans, runs, reviews, pending approvals, budget)
---

Run `tutu status` and summarize it for the user:
- latest plans and their open tasks (read the latest `.tutu/plans/*.md` checkboxes);
- recent runs and their status;
- recent review verdicts;
- **pending approvals** (show `.tutu/approvals/pending.md` items if any, and ask whether to approve, edit or reject each);
- budget used vs. caps.
Keep it short.

from tutu_runtime import budget, config


def test_layering(project, home):
    (home / ".tutu").mkdir(exist_ok=True)
    (home / ".tutu" / "config.toml").write_text('[reviewer]\nbackend = "codex"\n[budget]\nmax_loop_iterations = 7\n')
    cfg = config.load(project)
    assert config.get(cfg, "reviewer.backend") == "codex"          # user overrides default
    assert config.get(cfg, "budget.max_loop_iterations") == 7
    assert config.get(cfg, "budget.max_gpu_hours_per_run") == 2.0  # project overrides
    assert config.get(cfg, "compute.device") == "auto"             # repo default


def test_budget_caps(project):
    assert not budget.would_exceed(project, "usd", 0.5)
    budget.record(project, "usd", 0.8)
    assert budget.would_exceed(project, "usd", 0.5)
    assert budget.would_exceed(project, "gpu_hours", 3)
    assert not budget.would_exceed(project, "gpu_hours", 1.5)

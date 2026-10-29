import json
import subprocess

from tutu_runtime import provenance


def test_capture_and_finalize(project):
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"],
                   cwd=project, check=True)
    (project / "cfg.toml").write_text("lr = 0.1\n")
    m = provenance.capture(project, "python train.py --seed 1", name="pilot", configs=["cfg.toml"],
                           data=["data/raw"], seeds=[1])
    run_dir = project / ".tutu" / "runs" / m["run_id"]
    saved = json.loads((run_dir / "manifest.json").read_text())
    assert saved["git"]["available"] and len(saved["git"]["commit"]) == 40
    assert saved["data"][0]["files"] == 1 and len(saved["data"][0]["sha256"]) == 64
    assert saved["configs"][0]["snapshot"] == "configs/cfg.toml"
    assert saved["device"]["device"] in {"cpu", "cuda", "mps"}
    assert saved["seeds"] == [1] and (run_dir / "requirements.lock.txt").exists()

    (project / "metrics.json").write_text('{"auc": 0.8}')
    f = provenance.finalize(project, m["run_id"], status="succeeded", results=["metrics.json"], metrics={"auc": 0.8})
    assert f["status"] == "succeeded" and f["results"][0]["path"] == "metrics.json"
    assert provenance.list_runs(project)[0]["run_id"] == m["run_id"]


def test_data_hash_changes(project):
    a = provenance.path_digest(project / "data/raw", project)["sha256"]
    (project / "data/raw/s01.tsv").write_text("changed")
    assert provenance.path_digest(project / "data/raw", project)["sha256"] != a

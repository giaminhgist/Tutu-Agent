import pytest

from tutu_runtime import guard


def ev(project, tool, **inp):
    return guard.evaluate(tool, inp, project)[0]


def test_noop_outside_project(home, tmp_path):
    assert guard.evaluate("Bash", {"command": "git push"}, tmp_path)[0] == "allow"


@pytest.mark.parametrize("cmd", [
    "rm data/raw/s01.tsv",
    "rm -rf data/raw",
    "mv data/raw/s01.tsv data/processed/",
    "echo x > data/raw/s01.tsv",
    "cat a >> data/raw/new.tsv",
    "sed -i 's/1/2/' data/raw/s01.tsv",
    "cp data/processed/x.tsv data/raw/",
    "python clean.py && rm data/raw/s01.tsv",
    "touch data/raw/x",
])
def test_bash_mutating_protected_denied(project, cmd):
    assert ev(project, "Bash", command=cmd) == "deny"


@pytest.mark.parametrize("cmd", [
    "cat data/raw/s01.tsv",
    "cp data/raw/s01.tsv data/processed/",
    "python preprocess.py --in data/raw --out data/processed",
    "ls -la data/raw",
    "head data/raw/s01.tsv > /tmp/x",
    "python train.py --config cfg.yaml",
])
def test_bash_reading_protected_allowed(project, cmd):
    assert ev(project, "Bash", command=cmd) == "allow"


def test_write_tools(project):
    assert ev(project, "Write", file_path=str(project / "data/raw/new.csv")) == "deny"
    assert ev(project, "Edit", file_path="data/raw/s01.tsv") == "deny"
    assert ev(project, "Write", file_path=str(project / "src/a.py")) == "allow"


@pytest.mark.parametrize("cmd", ["rm -rf /", "rm -rf ~", "rm -rf ../other", "rm -rf *", "rm -rf ."])
def test_broad_rm_denied(project, cmd):
    assert ev(project, "Bash", command=cmd) == "deny"


def test_rm_inside_project_allowed(project):
    assert ev(project, "Bash", command="rm -rf outputs/tmp") == "allow"


@pytest.mark.parametrize("cmd", [
    "git push origin main",
    "gh pr create --fill",
    "vastai create instance 123",
    "modal run train.py",
    "sbatch job.slurm",
    "scp results.csv user@host:/tmp/",
    "twine upload dist/*",
])
def test_high_risk_asks(project, cmd):
    assert ev(project, "Bash", command=cmd) == "ask"


def test_phi_read_asks_until_approved(project):
    f = str(project / "data/phi/patients.csv")
    assert ev(project, "Read", file_path=f) == "ask"
    assert ev(project, "Bash", command="head data/phi/patients.csv") == "ask"
    (project / ".tutu/approvals/phi-access.approved").write_text("approved by PI")
    assert ev(project, "Read", file_path=f) == "allow"


def test_subdirectory_cwd(project):
    sub = project / "src"
    sub.mkdir()
    assert guard.evaluate("Bash", {"command": "rm ../data/raw/s01.tsv"}, sub)[0] == "deny"

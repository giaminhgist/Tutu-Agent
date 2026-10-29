import pytest

from tutu_runtime import kb


def test_add_and_search_global(project):
    page = kb.add_paper(title="Eye movements as biomarkers of Alzheimer's disease", authors=["Ada Lovelace"],
                        year=2024, keyword="eye-tracking AD", tags=["dementia"], tldr="Saccade latency differs.",
                        project_root=project, bibtex="@article{lovelace2024,title={x}}")
    assert page.name == "lovelace2024_eyetrackingad.md"
    hits = kb.search("saccade latency", "global", project)
    assert hits and hits[0]["scope"] == "global"
    # idempotent bib
    kb.add_paper(title="t", authors=["Ada Lovelace"], year=2024, keyword="eye-tracking AD",
                 project_root=project, bibtex="@article{lovelace2024,title={x}}")
    assert page.parent.parent.joinpath("library.bib").read_text().count("lovelace2024") == 1


def test_project_isolation(project, tmp_path):
    (project / "research-wiki" / "ideas").mkdir(parents=True)
    (project / "research-wiki" / "ideas" / "i1.md").write_text("# Idea\npupillometry transformer secret idea")
    other = tmp_path / "work" / "other"
    (other / ".tutu").mkdir(parents=True)
    (other / "research-wiki").mkdir()
    (other / "research-wiki" / "x.md").write_text("pupillometry other project confidential")
    hits = kb.search("pupillometry", "all", project)
    assert [h["scope"] for h in hits] == ["project"]
    assert all("other" not in h["path"].split("/")[-3:] for h in hits)


def test_query_with_special_chars(project):
    assert kb.search('AUC-ROC "MCI:AD" (n=50)', "all", project) == []


def test_promote_requires_permission(project):
    (project / ".tutu" / "notes").mkdir()
    (project / ".tutu" / "notes" / "n.md").write_text("note")
    with pytest.raises(PermissionError):
        kb.promote(project, ".tutu/notes/n.md")
    assert kb.promote(project, ".tutu/notes/n.md", approved=True).exists()

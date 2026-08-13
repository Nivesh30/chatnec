from pathlib import Path

from chatnec.cli import init_project, main


def test_init_project_creates_expected_files(tmp_path: Path):
    target = tmp_path / "my-agent"

    init_project(target)

    assert (target / "app.py").exists()
    assert (target / ".env.example").exists()
    assert (target / "README.md").exists()
    assert (target / ".gitignore").exists()
    assert "create_app" in (target / "app.py").read_text()


def test_init_project_does_not_overwrite_existing_files(tmp_path: Path):
    target = tmp_path / "my-agent"
    target.mkdir()
    (target / "app.py").write_text("# custom content", encoding="utf-8")

    init_project(target)

    assert (target / "app.py").read_text() == "# custom content"


def test_main_init_via_argv(tmp_path: Path):
    target = tmp_path / "scaffolded"

    exit_code = main(["init", str(target)])

    assert exit_code == 0
    assert (target / "app.py").exists()

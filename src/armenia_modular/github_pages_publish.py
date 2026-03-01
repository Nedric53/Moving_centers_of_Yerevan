from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        joined = " ".join(cmd)
        raise RuntimeError(
            f"Command failed: {joined}\n"
            f"cwd: {cwd}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
    return (result.stdout or "").strip()


def _resolve_inside_repo(repo_root: Path, maybe_relative: str | Path) -> Path:
    p = Path(maybe_relative)
    if not p.is_absolute():
        p = repo_root / p
    return p.resolve()


def write_basic_gitignore(repo_root: str | Path) -> Path:
    repo_root = Path(repo_root).resolve()
    gitignore = repo_root / ".gitignore"

    content = """# Python
__pycache__/
*.py[cod]

# Jupyter
.ipynb_checkpoints/
**/.ipynb_checkpoints/

# Local environments
.venv/
venv/
env/

# OS / editor
.DS_Store
.vscode/
"""

    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8")
        if content not in existing:
            with gitignore.open("a", encoding="utf-8") as f:
                if not existing.endswith("\n"):
                    f.write("\n")
                f.write("\n" + content)
    else:
        gitignore.write_text(content, encoding="utf-8")

    return gitignore


def prepare_docs_site(
    repo_root: str | Path,
    site_dir: str | Path = "data/yerevan_interactive",
    docs_dir: str | Path = "docs",
    clean_docs: bool = True,
    add_nojekyll: bool = True,
    make_404_from_index: bool = False,
) -> dict:
    repo_root = Path(repo_root).resolve()
    site_path = _resolve_inside_repo(repo_root, site_dir)
    docs_path = _resolve_inside_repo(repo_root, docs_dir)

    if not site_path.exists():
        raise FileNotFoundError(f"Site folder not found: {site_path}")

    index_in_site = site_path / "index.html"
    if not index_in_site.exists():
        raise FileNotFoundError(
            f"index.html not found in site folder: {index_in_site}"
        )

    if docs_path.exists() and clean_docs:
        shutil.rmtree(docs_path)

    docs_path.mkdir(parents=True, exist_ok=True)

    for item in site_path.iterdir():
        target = docs_path / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    if add_nojekyll:
        (docs_path / ".nojekyll").write_text("", encoding="utf-8")

    if make_404_from_index:
        shutil.copy2(docs_path / "index.html", docs_path / "404.html")

    return {
        "repo_root": str(repo_root),
        "site_source": str(site_path),
        "docs_path": str(docs_path),
        "index_path": str(docs_path / "index.html"),
    }


def ensure_git_repo(
    repo_root: str | Path,
    default_branch: str = "main",
) -> Path:
    repo_root = Path(repo_root).resolve()

    if not (repo_root / ".git").exists():
        _run(["git", "init"], cwd=repo_root)

    try:
        _run(["git", "branch", "-M", default_branch], cwd=repo_root)
    except RuntimeError:
        pass

    return repo_root


def set_remote(
    repo_root: str | Path,
    remote_url: str,
    remote_name: str = "origin",
) -> str:
    repo_root = Path(repo_root).resolve()
    remotes_raw = _run(["git", "remote"], cwd=repo_root)
    remotes = {r.strip() for r in remotes_raw.splitlines() if r.strip()}

    if remote_name in remotes:
        _run(["git", "remote", "set-url", remote_name, remote_url], cwd=repo_root)
    else:
        _run(["git", "remote", "add", remote_name, remote_url], cwd=repo_root)

    return remote_url


def commit_and_push(
    repo_root: str | Path,
    commit_message: str = "Publish site and project",
    branch: str = "main",
    remote_name: str = "origin",
    push: bool = True,
) -> dict:
    repo_root = Path(repo_root).resolve()

    _run(["git", "add", "."], cwd=repo_root)

    status = _run(["git", "status", "--porcelain"], cwd=repo_root)
    commit_created = False

    if status.strip():
        _run(["git", "commit", "-m", commit_message], cwd=repo_root)
        commit_created = True

    _run(["git", "branch", "-M", branch], cwd=repo_root)

    if push:
        _run(["git", "push", "-u", remote_name, branch], cwd=repo_root)

    return {
        "commit_created": commit_created,
        "branch": branch,
        "pushed": push,
    }


def publish_project_to_github_pages(
    repo_root: str | Path = ".",
    site_dir: str | Path = "notebooks/data/yerevan_interactive",
    docs_dir: str | Path = "docs",
    remote_url: Optional[str] = None,
    remote_name: str = "origin",
    branch: str = "main",
    commit_message: str = "Publish site and project",
    write_gitignore_file: bool = True,
    clean_docs: bool = True,
    push: bool = False,
) -> dict:
    repo_root = Path(repo_root).resolve()

    docs_info = prepare_docs_site(
        repo_root=repo_root,
        site_dir=site_dir,
        docs_dir=docs_dir,
        clean_docs=clean_docs,
        add_nojekyll=True,
        make_404_from_index=False,
    )

    gitignore_path = None
    if write_gitignore_file:
        gitignore_path = write_basic_gitignore(repo_root)

    ensure_git_repo(repo_root, default_branch=branch)

    if remote_url:
        set_remote(repo_root, remote_url=remote_url, remote_name=remote_name)

    git_info = commit_and_push(
        repo_root=repo_root,
        commit_message=commit_message,
        branch=branch,
        remote_name=remote_name,
        push=push,
    )

    return {
        **docs_info,
        **git_info,
        "gitignore_path": str(gitignore_path) if gitignore_path else None,
        "pages_note": (
            "In GitHub repo Settings > Pages, choose 'Deploy from a branch', "
            f"branch '{branch}', folder '/docs'."
        ),
    }
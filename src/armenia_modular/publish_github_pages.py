from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Optional


def _run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    if check and p.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  cwd: {cwd}\n"
            f"  rc: {p.returncode}\n"
            f"  stdout:\n{(p.stdout or '').strip()}\n"
            f"  stderr:\n{(p.stderr or '').strip()}\n"
        )
    return p


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def _handle_remove_readonly(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def find_project_root(start: Path) -> Path:
    """
    Finds the project root containing "src" and "notebooks" (or at least "src").
    """
    start = start.resolve()
    candidates = [start] + list(start.parents)
    for c in candidates:
        if (c / "src").exists():
            return c
    return start


def ensure_git_installed() -> None:
    try:
        _run(["git", "--version"], cwd=Path.cwd(), check=True)
    except Exception as e:
        raise RuntimeError("Git is not available. Install Git and restart your terminal/Jupyter.") from e


def ensure_git_repo(repo_root: Path, branch: str = "main") -> None:
    repo_root = repo_root.resolve()
    if not (repo_root / ".git").exists():
        _run(["git", "init"], cwd=repo_root, check=True)
    # Ensure branch name
    _run(["git", "branch", "-M", branch], cwd=repo_root, check=False)


def ensure_git_identity(
    repo_root: Path,
    name: Optional[str] = None,
    email: Optional[str] = None,
    set_global: bool = False,
) -> None:
    """
    Sets git user.name and user.email for this repo (default) or globally.
    If name/email are None, only validates that something is configured.
    """
    repo_root = repo_root.resolve()
    scope = "--global" if set_global else "--local"

    def get_one(key: str) -> str:
        p = _run(["git", "config", scope, "--get", key], cwd=repo_root, check=False)
        return (p.stdout or "").strip()

    existing_name = get_one("user.name")
    existing_email = get_one("user.email")

    if name:
        _run(["git", "config", scope, "user.name", name], cwd=repo_root, check=True)
        existing_name = name

    if email:
        _run(["git", "config", scope, "user.email", email], cwd=repo_root, check=True)
        existing_email = email

    if not existing_name or not existing_email:
        raise RuntimeError(
            "Git identity is not set.\n"
            "Set user.name and user.email (locally for this repo or globally)."
        )


def remove_nested_git_folder(repo_root: Path, nested_git: Path) -> None:
    """
    Removes a nested .git folder that breaks git add/commit.
    Handles Windows read-only and locked-file cases.
    """
    repo_root = repo_root.resolve()
    nested_git = nested_git.resolve()

    if not nested_git.exists():
        return

    # First try shutil with read-only handler
    try:
        if nested_git.is_dir():
            shutil.rmtree(nested_git, onerror=_handle_remove_readonly)
        else:
            nested_git.unlink()
        return
    except Exception:
        pass

    # Windows fallback: attrib + rmdir
    if _is_windows():
        # Remove read-only attributes
        _run(["cmd", "/c", f'attrib -R /S /D "{nested_git}\\*"'], cwd=repo_root, check=False)
        # Force delete directory
        _run(["cmd", "/c", f'rmdir /S /Q "{nested_git}"'], cwd=repo_root, check=False)
        return

    # Non-windows fallback
    try:
        if nested_git.is_dir():
            shutil.rmtree(nested_git, ignore_errors=True)
        else:
            nested_git.unlink(missing_ok=True)  # python 3.8+ supports missing_ok
    except Exception:
        pass


def fix_notebooks_gitlink(repo_root: Path) -> None:
    """
    If notebooks was previously treated as a nested repo/submodule, fix the index.
    """
    repo_root = repo_root.resolve()
    _run(["git", "reset"], cwd=repo_root, check=False)
    _run(["git", "rm", "--cached", "-r", "notebooks"], cwd=repo_root, check=False)


def cleanup_nested_git(repo_root: Path, also_scan: bool = True) -> list[str]:
    """
    Removes notebooks/.git and optionally scans for other nested .git folders.
    Returns list of removed paths.
    """
    repo_root = repo_root.resolve()
    removed: list[str] = []

    # Always handle notebooks/.git first
    nb_git = repo_root / "notebooks" / ".git"
    if nb_git.exists():
        remove_nested_git_folder(repo_root, nb_git)
        removed.append(str(nb_git))

    # Optionally scan for other nested .git directories
    if also_scan:
        for p in repo_root.rglob(".git"):
            if p.resolve() == (repo_root / ".git").resolve():
                continue
            # skip the one we already handled
            if str(p) in removed:
                continue
            remove_nested_git_folder(repo_root, p)
            removed.append(str(p))

    # Fix possible gitlink/index state
    fix_notebooks_gitlink(repo_root)

    return removed


def write_gitignore(repo_root: Path, extra_lines: list[str]) -> Path:
    repo_root = repo_root.resolve()
    gi = repo_root / ".gitignore"
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    add = []
    for line in extra_lines:
        if line.strip() and line not in existing:
            add.append(line)
    if add:
        with gi.open("a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n".join(add) + "\n")
    return gi


def prepare_docs_site(
    repo_root: Path,
    site_dir: str | Path,
    docs_dir: str | Path = "docs",
    clean_docs: bool = True,
    add_nojekyll: bool = True,
) -> dict:
    """
    Copies everything from site_dir into repo_root/docs_dir.
    Ensures docs/index.html exists.
    """
    repo_root = repo_root.resolve()
    site_path = (repo_root / site_dir).resolve() if not Path(site_dir).is_absolute() else Path(site_dir).resolve()
    docs_path = (repo_root / docs_dir).resolve() if not Path(docs_dir).is_absolute() else Path(docs_dir).resolve()

    if not site_path.exists():
        raise FileNotFoundError(f"Site folder not found: {site_path}")

    if not (site_path / "index.html").exists():
        raise FileNotFoundError(f"index.html not found in: {site_path}")

    if docs_path.exists() and clean_docs:
        shutil.rmtree(docs_path, ignore_errors=True)

    docs_path.mkdir(parents=True, exist_ok=True)

    for item in site_path.iterdir():
        dest = docs_path / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    if add_nojekyll:
        (docs_path / ".nojekyll").write_text("", encoding="utf-8")

    if not (docs_path / "index.html").exists():
        raise RuntimeError("Copy finished but docs/index.html is missing. Something is wrong.")

    return {
        "site_source": str(site_path),
        "docs_path": str(docs_path),
        "docs_index": str(docs_path / "index.html"),
    }


def set_remote(repo_root: Path, remote_url: str, remote_name: str = "origin") -> None:
    repo_root = repo_root.resolve()
    remotes = _run(["git", "remote"], cwd=repo_root, check=False).stdout.splitlines()
    remotes = [r.strip() for r in remotes if r.strip()]

    if remote_name in remotes:
        _run(["git", "remote", "set-url", remote_name, remote_url], cwd=repo_root, check=True)
    else:
        _run(["git", "remote", "add", remote_name, remote_url], cwd=repo_root, check=True)


def commit_all(repo_root: Path, message: str) -> bool:
    repo_root = repo_root.resolve()
    _run(["git", "add", "."], cwd=repo_root, check=True)

    status = _run(["git", "status", "--porcelain"], cwd=repo_root, check=True).stdout.strip()
    if not status:
        return False

    _run(["git", "commit", "-m", message], cwd=repo_root, check=True)
    return True


def push(repo_root: Path, branch: str = "main", remote_name: str = "origin") -> None:
    repo_root = repo_root.resolve()
    _run(["git", "push", "-u", remote_name, branch], cwd=repo_root, check=True)


def publish_github_pages(
    repo_root: str | Path = ".",
    site_dir: str | Path = "notebooks/data/yerevan_interactive",
    docs_dir: str | Path = "docs",
    remote_url: Optional[str] = None,
    branch: str = "main",
    commit_message: str = "Publish site",
    git_name: Optional[str] = None,
    git_email: Optional[str] = None,
    cleanup_nested_git_folders: bool = True,
    also_scan_for_nested_git: bool = True,
    add_gitignore_defaults: bool = True,
    push_changes: bool = False,
) -> dict:
    """
    Full publishing flow:
      1) ensure git installed
      2) move to repo root
      3) cleanup nested .git folders that break staging
      4) copy site_dir -> docs_dir
      5) ensure git repo + identity
      6) set remote
      7) commit
      8) optionally push

    After push:
      In GitHub repo Settings > Pages:
        Deploy from a branch
        Branch: main
        Folder: /docs
    """
    ensure_git_installed()

    repo_root = Path(repo_root).resolve()
    # If caller accidentally calls from notebooks, normalize to parent
    if repo_root.name == "notebooks":
        repo_root = repo_root.parent

    repo_root = find_project_root(repo_root)

    removed_nested = []
    if cleanup_nested_git_folders:
        removed_nested = cleanup_nested_git(repo_root, also_scan=also_scan_for_nested_git)

    docs_info = prepare_docs_site(
        repo_root=repo_root,
        site_dir=site_dir,
        docs_dir=docs_dir,
        clean_docs=True,
        add_nojekyll=True,
    )

    if add_gitignore_defaults:
        # Important: keep docs/ tracked, ignore heavy notebooks/data if you want
        write_gitignore(
            repo_root,
            extra_lines=[
                "__pycache__/",
                "*.py[cod]",
                ".ipynb_checkpoints/",
                "**/.ipynb_checkpoints/",
                ".venv/",
                "venv/",
                "env/",
                ".vscode/",
                ".DS_Store",
                # This prevents accidentally committing huge build artifacts.
                # Your site is published from docs/, so notebooks/data is not needed for Pages.
                "notebooks/data/",
                "notebooks/cache/",
            ],
        )

    ensure_git_repo(repo_root, branch=branch)
    ensure_git_identity(repo_root, name=git_name, email=git_email, set_global=False)

    if remote_url:
        set_remote(repo_root, remote_url, remote_name="origin")

    committed = commit_all(repo_root, commit_message)

    if push_changes:
        push(repo_root, branch=branch, remote_name="origin")

    return {
        "repo_root": str(repo_root),
        "removed_nested_git": removed_nested,
        "committed": committed,
        "pushed": push_changes,
        **docs_info,
        "pages_setup": f"GitHub Settings > Pages: Deploy from branch '{branch}' and folder '/{Path(docs_dir).name}'",
    }
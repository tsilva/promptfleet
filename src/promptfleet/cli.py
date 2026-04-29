"""Run one Codex prompt across every git repository under a root path."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


SKIP_DIRS = {
    ".cache",
    ".git",
    ".next",
    ".turbo",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recursively find git repos and run a Codex prompt in each one."
    )
    parser.add_argument("root", help="Directory to scan recursively.")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", help="Prompt text to pass to `codex exec`.")
    prompt_group.add_argument(
        "--prompt-file",
        type=Path,
        help="File containing the prompt to pass to `codex exec`.",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable to run. Defaults to `codex`.",
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Skip repos with unstaged or staged changes.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show matching repos without running Codex.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show Codex stdout/stderr instead of hiding it.",
    )
    return parser.parse_args()


def load_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return args.prompt_file.expanduser().read_text(encoding="utf-8").strip()
    return args.prompt.strip()


def find_git_repos(root: Path) -> list[Path]:
    repos: list[Path] = []

    for current, dirs, _files in os.walk(root):
        current_path = Path(current)
        git_path = current_path / ".git"

        if git_path.exists():
            repos.append(current_path)
            dirs[:] = []
            continue

        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))

    return sorted(repos)


def is_clean(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == ""


def progress_line(index: int, total: int, repo: Path, status: str) -> str:
    width = 28
    filled = int(width * index / total) if total else width
    bar = "#" * filled + "-" * (width - filled)
    return f"[{index:>{len(str(total))}}/{total}] [{bar}] {status}: {repo}"


def tail_output(output: str, max_lines: int = 8) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


def run_codex(
    codex_bin: str, repo: Path, prompt: str, verbose: bool
) -> tuple[int, str]:
    if verbose:
        result = subprocess.run([codex_bin, "exec", prompt], cwd=repo, check=False)
        return result.returncode, ""

    result = subprocess.run(
        [codex_bin, "exec", prompt],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.returncode, result.stdout


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()

    if not root.exists() or not root.is_dir():
        print(f"error: root is not a directory: {root}", file=sys.stderr)
        return 2

    prompt = load_prompt(args)
    if not prompt:
        print("error: prompt is empty", file=sys.stderr)
        return 2

    repos = find_git_repos(root)
    total = len(repos)

    if total == 0:
        print(f"No git repositories found under {root}")
        return 0

    print(f"Found {total} git repositories under {root}")

    ok = 0
    skipped = 0
    failed = 0

    for position, repo in enumerate(repos, start=1):
        print()
        print(progress_line(position, total, repo, "current"), flush=True)

        if args.require_clean and not is_clean(repo):
            skipped += 1
            print(progress_line(position, total, repo, "skipped dirty"), flush=True)
            continue

        if args.dry_run:
            ok += 1
            print(progress_line(position, total, repo, "dry run"), flush=True)
            continue

        code, output = run_codex(args.codex_bin, repo, prompt, args.verbose)

        if code == 0:
            ok += 1
            print(progress_line(position, total, repo, "done"), flush=True)
        else:
            failed += 1
            print(
                progress_line(position, total, repo, f"failed exit {code}"),
                flush=True,
            )
            if output.strip():
                print(tail_output(output), flush=True)

    print()
    print(f"Summary: {ok} ok, {skipped} skipped, {failed} failed")
    return 1 if failed else 0

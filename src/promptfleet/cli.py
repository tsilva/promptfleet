"""Run one Codex prompt across every git repository under a root path."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
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


@dataclass(frozen=True)
class RepoResult:
    repo: Path
    status: str
    code: int
    output: str = ""


def stored_prompt_dirs() -> list[Path]:
    """Return prompt directories for source checkouts and installed packages."""
    package_root = Path(__file__).resolve().parent
    source_root = package_root.parents[1]
    dirs = [source_root / "prompts", package_root / "prompts"]

    unique_dirs: list[Path] = []
    seen: set[Path] = set()
    for prompt_dir in dirs:
        resolved = prompt_dir.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_dirs.append(prompt_dir)

    return unique_dirs


def stored_prompt_files() -> list[Path]:
    files: list[Path] = []
    for prompt_dir in stored_prompt_dirs():
        if not prompt_dir.is_dir():
            continue

        for path in sorted(prompt_dir.rglob("*")):
            relative_parts = path.relative_to(prompt_dir).parts
            has_hidden_part = any(part.startswith(".") for part in relative_parts)
            if path.is_file() and not has_hidden_part:
                files.append(path)

    return sorted(files)


def format_prompt_matches(matches: list[Path]) -> str:
    return ", ".join(str(path) for path in matches)


def resolve_prompt_file(reference: Path) -> Path:
    candidate = reference.expanduser()
    if candidate.exists():
        return candidate

    is_bare_filename = not candidate.is_absolute() and len(candidate.parts) == 1
    if not is_bare_filename:
        raise FileNotFoundError(f"prompt file not found: {reference}")

    stored_prompts = stored_prompt_files()
    exact_matches = [path for path in stored_prompts if path.name == candidate.name]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise ValueError(
            "stored prompt filename is ambiguous: "
            f"{candidate.name} matches {format_prompt_matches(exact_matches)}"
        )

    if candidate.suffix:
        raise FileNotFoundError(f"prompt file not found: {reference}")

    stem_matches = [path for path in stored_prompts if path.stem == candidate.name]
    if len(stem_matches) == 1:
        return stem_matches[0]
    if len(stem_matches) > 1:
        raise ValueError(
            "stored prompt name is ambiguous: "
            f"{candidate.name} matches {format_prompt_matches(stem_matches)}"
        )

    raise FileNotFoundError(f"prompt file not found: {reference}")


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
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of repos to process in parallel. Defaults to 1.",
    )
    return parser.parse_args()


def load_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        prompt_file = resolve_prompt_file(args.prompt_file)
        return prompt_file.read_text(encoding="utf-8").strip()
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
    codex_bin: str, repo: Path, prompt: str, verbose: bool, stream_output: bool
) -> tuple[int, str]:
    if verbose and stream_output:
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


def process_repo(
    repo: Path,
    prompt: str,
    codex_bin: str,
    require_clean: bool,
    dry_run: bool,
    verbose: bool,
    stream_output: bool,
) -> RepoResult:
    if require_clean and not is_clean(repo):
        return RepoResult(repo=repo, status="skipped dirty", code=0)

    if dry_run:
        return RepoResult(repo=repo, status="dry run", code=0)

    code, output = run_codex(
        codex_bin=codex_bin,
        repo=repo,
        prompt=prompt,
        verbose=verbose,
        stream_output=stream_output,
    )
    if code == 0:
        return RepoResult(repo=repo, status="done", code=0, output=output)

    return RepoResult(repo=repo, status=f"failed exit {code}", code=code, output=output)


def print_result(position: int, total: int, result: RepoResult, verbose: bool) -> None:
    print(progress_line(position, total, result.repo, result.status), flush=True)
    if result.output.strip() and (verbose or result.code != 0):
        print(result.output if verbose else tail_output(result.output), flush=True)


def run_repos(
    repos: list[Path],
    prompt: str,
    codex_bin: str,
    require_clean: bool,
    dry_run: bool,
    verbose: bool,
    workers: int,
) -> tuple[int, int, int]:
    ok = 0
    skipped = 0
    failed = 0
    total = len(repos)
    stream_output = workers == 1

    if workers == 1:
        for position, repo in enumerate(repos, start=1):
            print()
            print(progress_line(position, total, repo, "current"), flush=True)

            result = process_repo(
                repo=repo,
                prompt=prompt,
                codex_bin=codex_bin,
                require_clean=require_clean,
                dry_run=dry_run,
                verbose=verbose,
                stream_output=stream_output,
            )

            if result.status.startswith("skipped"):
                skipped += 1
            elif result.code == 0:
                ok += 1
            else:
                failed += 1

            print_result(position, total, result, verbose)

        return ok, skipped, failed

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                process_repo,
                repo,
                prompt,
                codex_bin,
                require_clean,
                dry_run,
                verbose,
                stream_output,
            )
            for repo in repos
        ]

        for position, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            print()

            if result.status.startswith("skipped"):
                skipped += 1
            elif result.code == 0:
                ok += 1
            else:
                failed += 1

            print_result(position, total, result, verbose)

    return ok, skipped, failed


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()

    if args.workers < 1:
        print("error: --workers must be at least 1", file=sys.stderr)
        return 2

    if not root.exists() or not root.is_dir():
        print(f"error: root is not a directory: {root}", file=sys.stderr)
        return 2

    try:
        prompt = load_prompt(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not prompt:
        print("error: prompt is empty", file=sys.stderr)
        return 2

    repos = find_git_repos(root)
    total = len(repos)

    if total == 0:
        print(f"No git repositories found under {root}")
        return 0

    print(f"Found {total} git repositories under {root}")
    if args.workers > 1:
        print(f"Running with {args.workers} workers")

    ok, skipped, failed = run_repos(
        repos=repos,
        prompt=prompt,
        codex_bin=args.codex_bin,
        require_clean=args.require_clean,
        dry_run=args.dry_run,
        verbose=args.verbose,
        workers=args.workers,
    )

    print()
    print(f"Summary: {ok} ok, {skipped} skipped, {failed} failed")
    return 1 if failed else 0

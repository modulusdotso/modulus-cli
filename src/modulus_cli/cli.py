import argparse
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import requests
from rich import print as rich_print

from modulus_cli.config_store import load_api_key, load_workspace_id, save_api_key
from modulus_cli.indexer import RepositoryAnalysisSystem
from modulus_cli.ui import configure_logging, error, info, success


def _normalize_version(v: str) -> tuple[int, ...]:
    parts = []
    for token in v.split("."):
        digits = ""
        for ch in token:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def _get_update_message() -> str | None:
    try:
        installed = version("modulus-cli")
    except PackageNotFoundError:
        return None

    try:
        response = requests.get("https://pypi.org/pypi/modulus-cli/json", timeout=2)
        if response.status_code != 200:
            return None
        latest = response.json().get("info", {}).get("version")
        if not isinstance(latest, str):
            return None
    except Exception:
        return None

    if _normalize_version(latest) > _normalize_version(installed):
        return (
            f"Update available: [bold yellow]{installed}[/bold yellow] -> "
            f"[bold green]{latest}[/bold green]. "
            "Run [bold]python -m pip install -U modulus-cli[/bold]"
        )
    return None


def main() -> None:
    parser = argparse.ArgumentParser(prog="modulus", description="Modulus CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="Login to Modulus with your API key")
    login.add_argument("--api-key", required=True, help="Your Modulus API key")

    repo = sub.add_parser("repo", help="Repository commands")
    repo_sub = repo.add_subparsers(dest="repo_command", required=True)
    index_cmd = repo_sub.add_parser("index", help="Scan and index a local directory")
    index_cmd.add_argument(
        "path",
        type=Path,
        help="Path to the repository or workspace directory",
    )
    sub.add_parser("update", help="Update modulus-cli to the latest version")

    args = parser.parse_args()
    update_message = _get_update_message()
    if update_message:
        rich_print(update_message)

    if args.command == "login":
        save_api_key(args.api_key)
        success("API key saved.")
        info("You can run modulus repo index <path>.")
        return

    if args.command == "update":
        info("Updating modulus cli to the latest version...")
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "modulus-cli"]
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            error("Update failed. Please retry or run the pip command manually.")
            sys.exit(result.returncode)
        success("modulus-cli updated successfully.")
        return

    if args.command == "repo" and args.repo_command == "index":
        configure_logging()
        api_key = load_api_key()
        workspace_id = load_workspace_id()
        if not api_key:
            error("You're not logged in.")
            info("Run modulus login --api-key <api-key> first.")
            sys.exit(1)

        root = args.path.expanduser().resolve()
        if not root.is_dir():
            error(f"Not a directory: {root}")
            sys.exit(1)

        if not workspace_id:
            error("Workspace ID not found.")
            info("Run modulus login --api-key <api-key> first.")
            sys.exit(1)

        info(f"Indexing repository: [bold yellow]{root}[/bold yellow]")
        resp = RepositoryAnalysisSystem(api_key).analyze_repository(
            workspace_id, str(root)
        )
        if resp.get("status") == "error":
            error("Indexing failed.")
            sys.exit(1)
        rich_print(
            f"Indexing started successfully, id: [bold bright_cyan]{resp.get('job_id')}[/bold bright_cyan]"
        )
        return

    parser.error("Unknown command")

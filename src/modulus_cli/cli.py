import argparse
import sys
from pathlib import Path

from rich import print as rich_print

from modulus_cli.config_store import load_api_key, load_workspace_id, save_api_key
from modulus_cli.indexer import RepositoryAnalysisSystem
from modulus_cli.ui import configure_logging, error, info, success


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

    args = parser.parse_args()

    if args.command == "login":
        save_api_key(args.api_key)
        success("API key saved.")
        info("You can run modulus repo index <path>.")
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

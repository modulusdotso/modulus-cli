import argparse
import hashlib
import logging
import sys
from pathlib import Path
from plistlib import load

from modulus_cli.config_store import load_api_key, load_workspace_id, save_api_key
from modulus_cli.indexer import RepositoryAnalysisSystem


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
        print("API key saved. You can run `modulus repo index <path>`.")
        return

    if args.command == "repo" and args.repo_command == "index":
        api_key = load_api_key()
        workspace_id = load_workspace_id()
        if not api_key:
            print(
                "You're not logged in. Run `modulus login --api-key <api-key>` first.",
                file=sys.stderr,
            )
            sys.exit(1)

        root = args.path.expanduser().resolve()
        if not root.is_dir():
            print(f"Not a directory: {root}", file=sys.stderr)
            sys.exit(1)

        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        if not workspace_id:
            print(
                "Workspace ID not found. Run `modulus login --api-key <api-key>` first.",
                file=sys.stderr,
            )
            sys.exit(1)

        ok = RepositoryAnalysisSystem(api_key).analyze_repository(
            workspace_id, str(root)
        )
        if not ok:
            print("Indexing failed.", file=sys.stderr)
            sys.exit(1)
        print("Indexing completed successfully.")
        return

    parser.error("Unknown command")

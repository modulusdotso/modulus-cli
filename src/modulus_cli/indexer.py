import json
import logging
import traceback
import urllib.error
import urllib.request
from typing import Any, Dict

import dotenv

from modulus_cli.constants import MODULUS_INDEX_URL
from modulus_cli.function_extractor import FunctionExtractor
from modulus_cli.static_inventory import StaticInventoryCollector

dotenv.load_dotenv()
logger = logging.getLogger(__name__)


def run_inventory_indexing(repo_data: Dict[str, Any], api_key: str) -> bool:
    """POST collected repo payload to the Modulus index API."""
    body = json.dumps(repo_data).encode("utf-8")
    request = urllib.request.Request(
        MODULUS_INDEX_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            code = getattr(response, "status", response.getcode())
            if 200 <= code < 300:
                return True
            logger.error("Index API returned status %s", code)
            return False
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.error("Index API HTTP error %s: %s", exc.code, detail[:2000])
        return False
    except urllib.error.URLError as exc:
        logger.error("Index API request failed: %s", exc.reason)
        return False


def run_llm_indexing_from_repo_data(repo_data: Dict[str, Any], api_key: str) -> bool:
    return run_inventory_indexing(repo_data, api_key)


class RepositoryAnalysisSystem:
    """
    Main system for analyzing local workspaces and storing structured summaries.

    Orchestrates:
    Static inventory (traverse, structure, extract)
    """

    def __init__(self, api_key: str):
        logger.info("Initializing RepositoryAnalysisSystem")
        self._api_key = api_key
        self.function_extractor = FunctionExtractor()
        self.static_inventory = StaticInventoryCollector(self.function_extractor)

        logger.info("RepositoryAnalysisSystem initialized successfully")

    def analyze_repository(self, workspace_id: str, workspace_path: str) -> bool:
        try:
            repo_data = self.static_inventory.collect_repo_data(
                workspace_id, workspace_path
            )
            return run_llm_indexing_from_repo_data(repo_data, self._api_key)
        except Exception as e:
            logger.error(f"Error analyzing workspace {workspace_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return False

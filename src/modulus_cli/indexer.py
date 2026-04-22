import json
import logging
import traceback
from typing import Any, Dict

from modulus_cli.api_client import index_repo
from modulus_cli.function_extractor import FunctionExtractor
from modulus_cli.static_inventory import StaticInventoryCollector

logger = logging.getLogger(__name__)


def run_llm_indexing_from_repo_data(repo_data: Dict[str, Any], api_key: str) -> Dict:
    response = index_repo(repo_data, api_key)
    resp_json = json.loads(response.text)
    return resp_json


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

    def analyze_repository(self, workspace_id: str, workspace_path: str) -> Dict:
        try:
            repo_data = self.static_inventory.collect_repo_data(
                workspace_id, workspace_path
            )

            resp = run_llm_indexing_from_repo_data(repo_data, self._api_key)
            return {"job_id": resp["job_id"], "status": resp["decision"]}
        except Exception as e:
            logger.error(f"Error analyzing workspace {workspace_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return {"job_id": None, "status": "error"}

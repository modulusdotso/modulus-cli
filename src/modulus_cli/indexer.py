import logging
import traceback
from typing import Any, Dict

import dotenv

from src.modulus_cli.function_extractor import FunctionExtractor
from src.modulus_cli.static_inventory import StaticInventoryCollector

dotenv.load_dotenv()
logger = logging.getLogger(__name__)


def run_llm_indexing_from_repo_data(repo_data: Dict[str, Any]) -> bool:
    return run_inventory_indexing(repo_data)


class RepositoryAnalysisSystem:
    """
    Main system for analyzing local workspaces and storing structured summaries.

    Orchestrates:
    Static inventory (traverse, structure, extract)
    """

    def __init__(self, claude_api_key: str):
        logger.info("Initializing RepositoryAnalysisSystem")
        self.function_extractor = FunctionExtractor()
        self.static_inventory = StaticInventoryCollector(self.function_extractor)

        logger.info("RepositoryAnalysisSystem initialized successfully")

    def analyze_repository(self, workspace_id: str, workspace_path: str) -> bool:
        try:
            repo_data = self.static_inventory.collect_repo_data(
                workspace_id, workspace_path
            )
            return run_llm_indexing_from_repo_data(repo_data)
        except Exception as e:
            logger.error(f"Error analyzing workspace {workspace_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return False

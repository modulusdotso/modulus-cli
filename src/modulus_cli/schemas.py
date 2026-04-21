"""Dataclasses for static repo analysis and indexing."""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class FunctionInfo:
    """
    Represents a function extracted from code.

    Attributes:
        name: Function name (e.g., "process_data", "User.get_profile")
        docstring: Function docstring/documentation
        start_line: Starting line number
        end_line: Ending line number
        file_path: Path to the file containing this function
        content: Function content (body)
    """

    name: str
    docstring: str
    start_line: int
    end_line: int
    file_path: str
    content: str


@dataclass
class FileAnalysis:
    """
    Represents analysis data for a single file.

    Attributes:
        file_path: Path to the file
        language: Programming language detected
        functions: List of FunctionInfo objects
        imports: List of import statements
        dependencies: List of external dependencies detected
        content: Full file content (for analysis, not storage)
    """

    file_path: str
    language: str
    functions: List[FunctionInfo]
    imports: List[str]
    dependencies: List[str]
    content: str


@dataclass
class RepoStructure:
    """Repository directory structure with file and directory counts."""

    tree: Dict[str, Any]
    file_count: int
    directory_count: int

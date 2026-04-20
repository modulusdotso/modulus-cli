"""Static inventory: filesystem walk, repo tree, per-file extraction (steps 1–3, no LLM)."""

import ast
import json
import logging
import os
import re
from fnmatch import fnmatch
from typing import Any, Dict, List, Optional, Tuple

from src.modulus_cli.function_extractor import FunctionExtractor
from src.modulus_cli.schemas import FileAnalysis, RepoStructure

logger = logging.getLogger(__name__)


class StaticInventoryCollector:
    """Traverse files, build structure tree, extract functions/imports/deps per file."""

    def __init__(self, function_extractor: FunctionExtractor):
        self.function_extractor = function_extractor

    def _load_gitignore_patterns(self, workspace_path: str) -> List[str]:
        gitignore_path = os.path.join(workspace_path, ".gitignore")
        if not os.path.exists(gitignore_path):
            return []
        try:
            with open(gitignore_path, "r", encoding="utf-8") as handle:
                lines = [line.strip() for line in handle.readlines()]
        except Exception as e:
            logger.warning(f"Failed to read .gitignore: {str(e)}")
            return []
        return [line for line in lines if line and not line.startswith("#")]

    def _is_ignored_path(self, relative_path: str, patterns: List[str]) -> bool:
        if not patterns:
            return False
        rel = relative_path.replace(os.sep, "/")
        for pattern in patterns:
            if not pattern or pattern.startswith("!"):
                continue
            pat = pattern[1:] if pattern.startswith("/") else pattern
            if pat.endswith("/"):
                prefix = pat.rstrip("/")
                if rel.startswith(prefix):
                    return True
            if fnmatch(rel, pat):
                return True
        return False

    def _collect_local_files(self, workspace_path: str) -> List[Tuple[str, str]]:
        skip_dirs = [
            "node_modules",
            ".venv",
            "venv",
            ".git",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            ".idea",
            ".vscode",
            ".eggs",
            ".tox",
            ".cache",
            ".coverage",
            ".github",
            ".gitlab",
            ".DS_Store",
            ".env",
            ".next",
            "dist",
            "build",
            "out",
            "target",
            "coverage",
            "logs",
            "log",
            "tmp",
            "temp",
        ]
        skip_files = [".DS_Store", "Thumbs.db", "desktop.ini"]
        patterns = self._load_gitignore_patterns(workspace_path)

        collected: List[Tuple[str, str]] = []
        for root, dirs, files in os.walk(workspace_path, followlinks=False):
            dirs_to_remove = []
            for dir_name in dirs:
                full_dir = os.path.join(root, dir_name)
                rel_dir = os.path.relpath(full_dir, workspace_path).replace(os.sep, "/")
                if os.path.islink(full_dir):
                    dirs_to_remove.append(dir_name)
                    continue
                if dir_name in skip_dirs or self._is_ignored_path(
                    f"{rel_dir}/", patterns
                ):
                    dirs_to_remove.append(dir_name)
                    continue
            for dir_name in dirs_to_remove:
                dirs.remove(dir_name)

            for file_name in files:
                if file_name in skip_files:
                    continue
                full_file = os.path.join(root, file_name)
                if os.path.islink(full_file):
                    continue
                rel_file = os.path.relpath(full_file, workspace_path).replace(
                    os.sep, "/"
                )
                if self._is_ignored_path(rel_file, patterns):
                    continue
                collected.append((full_file, rel_file))
        return collected

    def _build_repo_structure(self, file_paths: List[str]) -> RepoStructure:
        """Build a tree structure representing the workspace directory layout."""
        logger.info("Building workspace structure tree...")

        tree = {}
        file_count = 0
        directory_count = 0

        for file_path in file_paths:
            path_parts = file_path.split("/")

            current_level = tree
            for i, part in enumerate(path_parts):
                is_file = i == len(path_parts) - 1

                if is_file:
                    file_ext = part.split(".")[-1].lower() if "." in part else ""
                    language = self._detect_language_from_extension(file_ext, "")

                    current_level[part] = {
                        "type": "file",
                        "path": file_path,
                        "language": language,
                    }
                    file_count += 1
                else:
                    if part not in current_level:
                        current_level[part] = {"type": "directory", "children": {}}
                        directory_count += 1
                    current_level = current_level[part]["children"]

        logger.info(
            f"Workspace structure built: {file_count} files, {directory_count} directories"
        )

        return RepoStructure(
            tree=tree, file_count=file_count, directory_count=directory_count
        )

    def _detect_language_from_extension(self, ext: str, content: str = "") -> str:
        """Detect programming language from file extension and optionally content."""
        ext_lower = ext.lower()

        if ext_lower == "js" and content:
            if "import type" in content or "interface " in content:
                return "typescript"
            return "javascript"

        language_map = {
            "py": "python",
            "js": "javascript",
            "jsx": "javascript",
            "ts": "typescript",
            "tsx": "typescript",
            "mjs": "typescript",
            "java": "java",
            "go": "go",
            "swift": "swift",
            "rs": "rust",
            "rb": "ruby",
            "php": "php",
            "cpp": "cpp",
            "c": "c",
            "h": "c",
            "cs": "csharp",
        }
        return language_map.get(ext_lower, "unknown")

    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import statements from code based on language."""
        imports = []

        try:
            if language == "python":
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(f"import {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        names = ", ".join([alias.name for alias in node.names])
                        imports.append(f"from {module} import {names}")

            elif language in ["javascript", "typescript"]:
                import_pattern = r"import\s+(?:(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)(?:\s*,\s*(?:\{[^}]*\}|\*\s+as\s+\w+|\w+))*\s+from\s+)?['\"]([^'\"]+)['\"]"
                matches = re.findall(import_pattern, content)
                imports.extend([f"import from '{m}'" for m in matches])

                require_pattern = r"require\(['\"]([^'\"]+)['\"]\)"
                require_matches = re.findall(require_pattern, content)
                imports.extend([f"require('{m}')" for m in require_matches])

            elif language == "java":
                import_pattern = r"import\s+([\w.]+)\s*;"
                matches = re.findall(import_pattern, content)
                imports.extend([f"import {m}" for m in matches])

            elif language == "go":
                import_pattern = r'import\s+(?:\(([^)]+)\)|"([^"]+)")'
                matches = re.findall(import_pattern, content)
                for match in matches:
                    if isinstance(match, tuple):
                        imports.extend(
                            [f"import {m.strip()}" for m in match if m.strip()]
                        )
                    else:
                        imports.append(f"import {match}")

        except Exception as e:
            logger.warning(f"Error extracting imports for {language}: {str(e)}")

        return list(set(imports))

    def _extract_dependencies(self, content: str, file_path: str) -> List[str]:
        """Extract external dependencies from package files."""
        dependencies = []

        try:
            if file_path.endswith("package.json"):
                data = json.loads(content)
                deps = data.get("dependencies", {})
                dev_deps = data.get("devDependencies", {})
                all_deps = {**deps, **dev_deps}
                dependencies.extend(
                    [f"{name}@{version}" for name, version in all_deps.items()]
                )

            elif file_path.endswith("requirements.txt"):
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        dep = re.split(r"[>=<!=]", line)[0].strip()
                        if dep:
                            dependencies.append(dep)

            elif file_path.endswith("pom.xml"):
                dependency_pattern = (
                    r"<dependency>.*?<artifactId>([^<]+)</artifactId>.*?</dependency>"
                )
                matches = re.findall(dependency_pattern, content, re.DOTALL)
                dependencies.extend(matches)

            elif file_path.endswith("go.mod"):
                for line in content.split("\n"):
                    if line.strip().startswith("require"):
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            dependencies.append(parts[1])

            elif file_path.endswith("Cargo.toml"):
                dependency_pattern = r'(\w+)\s*=\s*["\']([^"\']+)["\']'
                matches = re.findall(dependency_pattern, content)
                dependencies.extend([f"{name}@{version}" for name, version in matches])

        except Exception as e:
            logger.warning(f"Error extracting dependencies from {file_path}: {str(e)}")

        return dependencies

    def _fetch_readme(self, workspace_path: str) -> Optional[str]:
        """Fetch README file from workspace root if it exists."""
        readme_names = ["README.md", "README.txt", "README.rst", "README", "readme.md"]
        for readme_name in readme_names:
            readme_path = os.path.join(workspace_path, readme_name)
            if not os.path.exists(readme_path):
                continue
            try:
                with open(readme_path, "r", encoding="utf-8") as handle:
                    content = handle.read()
                logger.info(f"Found README: {readme_name}")
                return content
            except Exception:
                continue

        logger.info("No README file found")
        return None

    def _analyze_file(
        self, absolute_path: str, relative_path: str
    ) -> Optional[FileAnalysis]:
        """Analyze a single file to extract functions, imports, and dependencies."""
        file_path = relative_path

        file_ext = "." + file_path.split(".")[-1].lower() if "." in file_path else ""
        skip_extensions = {
            ".md",
            ".txt",
            ".json",
            ".yaml",
            ".yml",
            ".lock",
            ".log",
            ".png",
            ".jpg",
            ".jpeg",
            ".svg",
            ".gif",
            ".ico",
            ".webp",
            ".mp4",
            ".webm",
            ".mov",
            ".avi",
            ".mp3",
            ".wav",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".pdf",
            ".zip",
            ".tar",
            ".gz",
        }
        if file_ext in skip_extensions and not any(
            file_path.endswith(f)
            for f in [
                "package.json",
                "requirements.txt",
                "pom.xml",
                "go.mod",
                "Cargo.toml",
            ]
        ):
            return None

        try:
            if os.path.getsize(absolute_path) > 2 * 1024 * 1024:
                logger.debug(f"Skipping large file: {file_path}")
                return None

            try:
                with open(absolute_path, "rb") as handle:
                    raw = handle.read()
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                logger.debug(f"Skipping binary file: {file_path}")
                return None

            language = self.function_extractor.detect_language(content, file_path)

            functions = self.function_extractor.extract_functions(content, file_path)
            for func in functions:
                func.file_path = file_path

            imports = self._extract_imports(content, language)

            dependencies = self._extract_dependencies(content, file_path)

            return FileAnalysis(
                file_path=file_path,
                language=language,
                functions=functions,
                imports=imports,
                dependencies=dependencies,
                content=content,
            )

        except Exception as e:
            logger.warning(f"Error analyzing file {file_path}: {str(e)}")
            return None

    def collect_repo_data(
        self, workspace_id: str, workspace_path: str
    ) -> Dict[str, Any]:
        """Collect all workspace data for LLM analysis (steps 1–3)."""
        logger.info("=" * 80)
        logger.info(f"Collecting data for workspace: {workspace_id}")
        logger.info("=" * 80)

        logger.info("Collecting files from local workspace...")
        file_pairs = self._collect_local_files(workspace_path)
        relative_paths = [rel for _, rel in file_pairs]
        logger.info(f"Found {len(relative_paths)} files")

        repo_structure = self._build_repo_structure(relative_paths)

        logger.info("Analyzing files...")
        file_analyses = []
        for i, (absolute_path, relative_path) in enumerate(file_pairs):
            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i + 1}/{len(file_pairs)} files processed")

            analysis = self._analyze_file(absolute_path, relative_path)
            if analysis:
                file_analyses.append(analysis)

        logger.info(
            f"Analyzed {len(file_analyses)} of {len(file_pairs)} files (successful)"
        )

        readme_content = self._fetch_readme(workspace_path)

        repo_data = {
            "workspace_id": workspace_id,
            "workspace_path": workspace_path,
            "structure": repo_structure.tree,
            "structure_stats": {
                "file_count": repo_structure.file_count,
                "directory_count": repo_structure.directory_count,
            },
            "files": [
                {
                    "relative_path": fa.file_path,
                    "language": fa.language,
                    "functions": [
                        {
                            "name": f.name,
                            "docstring": f.docstring,
                            "start_line": f.start_line,
                            "end_line": f.end_line,
                        }
                        for f in fa.functions
                    ],
                    "imports": fa.imports,
                    "dependencies": fa.dependencies,
                }
                for fa in file_analyses
            ],
            "readme": readme_content,
        }

        logger.info("Workspace data collection complete")
        return repo_data

import ast
import logging
import re
from typing import List

import esprima
import javalang
from tree_sitter import Language as TSLanguage
from tree_sitter import Node as TSNode
from tree_sitter import Parser as TSParser
from tree_sitter import Tree as TSTree
from tree_sitter_typescript import language_tsx, language_typescript

from modulus_cli.schemas import FunctionInfo

logger = logging.getLogger(__name__)

_TREE_SITTER_TS_AVAILABLE = False
_TS_LANGUAGE = TSLanguage(language_typescript())
_TSX_LANGUAGE = TSLanguage(language_tsx())
_TREE_SITTER_TS_AVAILABLE = True


class FunctionExtractor:
    """
    Handles extraction of functions from different programming languages.

    This class provides language-specific parsers to extract:
    - Function definitions
    - Function docstrings
    - Function locations (line numbers)

    Supports: Python, JavaScript, TypeScript, Java, Go, Swift, Rust
    """

    def __init__(self):
        self.language_parsers = {
            "python": self._parse_python,
            "javascript": self._parse_javascript,
            "typescript": self._parse_typescript,
            "java": self._parse_java,
            "go": self._parse_go,
            "swift": self._parse_swift,
            "rust": self._parse_rust,
        }

    def detect_language(self, content: str, filename: str) -> str:
        """Detect programming language from file content and name."""
        ext = filename.split(".")[-1] if "." in filename else ""
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

    def extract_functions(self, content: str, filename: str) -> List[FunctionInfo]:
        """Extract functions from file content based on language."""
        language = self.detect_language(content, filename)

        if language not in self.language_parsers:
            return []

        try:
            if language == "typescript":
                functions = self._parse_typescript(content, filename)
            elif language == "javascript":
                functions = self._parse_javascript(content, filename)
            else:
                functions = self.language_parsers[language](content)
            return functions
        except Exception as e:
            logger.warning(f"Error extracting functions from {filename}: {str(e)}")
            return []

    def _parse_python(self, content: str) -> List[FunctionInfo]:
        """Extract functions from Python code using AST."""
        functions = []
        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            method_name = f"{node.name}.{item.name}"
                            start_line = item.lineno
                            end_line = item.end_lineno
                            docstring = ast.get_docstring(item) or ""

                            functions.append(
                                FunctionInfo(
                                    name=method_name,
                                    docstring=docstring,
                                    start_line=start_line,
                                    end_line=end_line,
                                    file_path="",
                                )
                            )

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    is_in_class = False
                    for parent in ast.walk(tree):
                        if isinstance(parent, ast.ClassDef):
                            if node in parent.body:
                                is_in_class = True
                                break

                    if not is_in_class:
                        start_line = node.lineno
                        end_line = node.end_lineno
                        docstring = ast.get_docstring(node) or ""

                        functions.append(
                            FunctionInfo(
                                name=node.name,
                                docstring=docstring,
                                start_line=start_line,
                                end_line=end_line,
                                file_path="",
                            )
                        )
        except Exception as e:
            logger.warning(f"Error parsing Python: {str(e)}")

        return functions

    def _parse_javascript(self, content: str, filename: str = "") -> List[FunctionInfo]:
        """Extract functions from JavaScript code using esprima."""
        functions = []
        try:
            if content.startswith("#!"):
                lines = content.split("\n")
                if lines[0].startswith("#!"):
                    content = "\n".join(lines[1:])

            opts = {"loc": True, "range": True, "tolerant": True, "jsx": True}
            use_module = "import " in content or "export " in content
            try:
                tree = (
                    esprima.parseModule(content, opts)
                    if use_module
                    else esprima.parseScript(content, opts)
                )
            except Exception:
                tree = esprima.parseScript(content, opts)

            def process_node(node, parent_name=""):
                if node.type == "FunctionDeclaration":
                    name = node.id.name if node.id else f"anonymous_{len(functions)}"
                    if parent_name:
                        name = f"{parent_name}.{name}"

                    start_line = node.loc.start.line
                    end_line = node.loc.end.line

                    docstring = ""
                    if hasattr(node, "leadingComments") and node.leadingComments:
                        for comment in node.leadingComments:
                            if (
                                comment.type == "Block"
                                and comment.value.strip().startswith("*")
                            ):
                                docstring = comment.value.strip()
                                lines_ds = docstring.split("\n")
                                cleaned_lines = []
                                for line in lines_ds:
                                    line = line.strip()
                                    if line.startswith("*"):
                                        line = line[1:].strip()
                                    cleaned_lines.append(line)
                                docstring = "\n".join(cleaned_lines).strip()

                    functions.append(
                        FunctionInfo(
                            name=name,
                            docstring=docstring,
                            start_line=start_line,
                            end_line=end_line,
                            file_path="",
                        )
                    )

                if hasattr(node, "body"):
                    body = node.body
                    if body is not None:
                        if isinstance(body, list):
                            for child in body:
                                process_node(child, parent_name)
                        elif hasattr(body, "body") and body.body is not None:
                            for child in body.body:
                                process_node(child, parent_name)

            process_node(tree)
        except Exception as e:
            msg = str(e)
            loc = f" in {filename}" if filename else ""
            if any(
                x in msg.lower()
                for x in (
                    "unexpected token",
                    "unexpected identifier",
                    "reserved word",
                    "rest parameter",
                )
            ):
                logger.debug(f"JavaScript parser limit{loc}: {msg}")
            else:
                logger.warning(f"Error parsing JavaScript{loc}: {msg}")

        return functions

    def _parse_typescript(self, content: str, filename: str = "") -> List[FunctionInfo]:
        """Extract functions from TypeScript/TSX using tree-sitter."""
        if not _TREE_SITTER_TS_AVAILABLE:
            logger.debug(
                "tree-sitter-typescript not available, skipping TypeScript function extraction"
            )
            return []
        functions: List[FunctionInfo] = []
        try:
            use_tsx = filename.lower().endswith(".tsx") if filename else False
            language = _TSX_LANGUAGE if use_tsx else _TS_LANGUAGE
            parser = TSParser(language)
            tree: TSTree = parser.parse(bytes(content, "utf-8"))
            root = tree.root_node
            if root is None:
                return []
            bytes_content = bytes(content, "utf-8")

            def node_text(node: TSNode) -> str:
                return bytes_content[node.start_byte : node.end_byte].decode(
                    "utf-8", errors="replace"
                )

            def extract_docstring_for_node(node: TSNode) -> str:
                start_byte = node.start_byte
                if start_byte <= 0:
                    return ""
                before = bytes_content[:start_byte].decode("utf-8", errors="replace")
                lines_before = before.split("\n")
                if not lines_before:
                    return ""
                last_line = lines_before[-1].strip()
                if last_line.startswith("/**") or last_line.startswith("/*"):
                    return last_line
                if last_line.startswith("//"):
                    return last_line
                return ""

            def walk(node: TSNode, parent_name: str = "") -> None:
                if node.type == "function_declaration":
                    name_node = node.child_by_field_name("name")
                    name = (
                        node_text(name_node)
                        if name_node
                        else f"anonymous_{len(functions)}"
                    )
                    if parent_name:
                        name = f"{parent_name}.{name}"
                    functions.append(
                        FunctionInfo(
                            name=name,
                            docstring=extract_docstring_for_node(node),
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            file_path="",
                        )
                    )
                elif node.type == "method_definition":
                    name_node = node.child_by_field_name("name")
                    name = (
                        node_text(name_node)
                        if name_node
                        else f"anonymous_{len(functions)}"
                    )
                    if parent_name:
                        name = f"{parent_name}.{name}"
                    functions.append(
                        FunctionInfo(
                            name=name,
                            docstring=extract_docstring_for_node(node),
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            file_path="",
                        )
                    )
                class_name = ""
                if node.type == "class_declaration":
                    name_node = node.child_by_field_name("name")
                    class_name = node_text(name_node) if name_node else ""
                for i in range(node.child_count):
                    child = node.child(i)
                    if child is None:
                        continue
                    next_parent = (
                        class_name if node.type == "class_declaration" else parent_name
                    )
                    walk(child, next_parent)

            walk(root)
        except Exception as e:
            logger.warning(
                f"Error parsing TypeScript from {filename or '(unknown)'}: {str(e)}"
            )
        return functions

    def _parse_java(self, content: str) -> List[FunctionInfo]:
        """Extract functions from Java code using javalang."""
        functions = []
        try:
            tree = javalang.parse.parse(content)
            for _, node in tree.filter(javalang.tree.MethodDeclaration):
                start_line = node.position.line
                end_line = node.position.line + len(node.body.split("\n"))
                docstring = node.documentation if hasattr(node, "documentation") else ""

                functions.append(
                    FunctionInfo(
                        name=node.name,
                        docstring=docstring,
                        start_line=start_line,
                        end_line=end_line,
                        file_path="",
                    )
                )
        except Exception as e:
            logger.warning(f"Error parsing Java: {str(e)}")

        return functions

    def _parse_go(self, content: str) -> List[FunctionInfo]:
        """Extract functions from Go code using regex."""
        functions = []
        try:
            func_pattern = r"func\s+(?P<receiver>\([^)]+\))?\s*(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*(?P<returns>[^{]*)\s*{(?P<body>.*?)}"

            for match in re.finditer(func_pattern, content, re.DOTALL):
                receiver = match.group("receiver") or ""
                name = match.group("name")

                start_line = content[: match.start()].count("\n") + 1
                end_line = content[: match.end()].count("\n") + 1

                if receiver:
                    recv_match = re.search(r"\([^)]*(\w+)[^)]*\)", receiver)
                    if recv_match:
                        recv_type = recv_match.group(1)
                        name = f"{recv_type}.{name}"

                functions.append(
                    FunctionInfo(
                        name=name,
                        docstring="",
                        start_line=start_line,
                        end_line=end_line,
                        file_path="",
                    )
                )
        except Exception as e:
            logger.warning(f"Error parsing Go: {str(e)}")

        return functions

    def _parse_swift(self, content: str) -> List[FunctionInfo]:
        """Extract functions from Swift code using regex."""
        functions = []
        try:
            func_pattern = r"func\s+(\w+)\s*\([^)]*\)\s*(?:->\s*[^{]+)?\s*\{"
            matches = list(re.finditer(func_pattern, content, re.MULTILINE))

            for match in matches:
                func_name = match.group(1)
                start_pos = match.start()
                start_line = content[:start_pos].count("\n") + 1

                brace_count = 0
                end_pos = start_pos
                for i, char in enumerate(content[start_pos:], start_pos):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end_pos = i + 1
                            break

                end_line = content[:end_pos].count("\n") + 1

                functions.append(
                    FunctionInfo(
                        name=func_name,
                        docstring="",
                        start_line=start_line,
                        end_line=end_line,
                        file_path="",
                    )
                )
        except Exception as e:
            logger.warning(f"Error parsing Swift: {str(e)}")

        return functions

    def _parse_rust(self, content: str) -> List[FunctionInfo]:
        """Extract functions from Rust code using regex."""
        functions = []
        try:
            func_pattern = r"fn\s+(\w+)\s*\([^)]*\)\s*(?:->\s*[^{]+)?\s*\{"
            matches = list(re.finditer(func_pattern, content, re.MULTILINE))

            for match in matches:
                func_name = match.group(1)
                start_pos = match.start()
                start_line = content[:start_pos].count("\n") + 1

                brace_count = 0
                end_pos = start_pos
                for i, char in enumerate(content[start_pos:], start_pos):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end_pos = i + 1
                            break

                end_line = content[:end_pos].count("\n") + 1

                functions.append(
                    FunctionInfo(
                        name=func_name,
                        docstring="",
                        start_line=start_line,
                        end_line=end_line,
                        file_path="",
                    )
                )
        except Exception as e:
            logger.warning(f"Error parsing Rust: {str(e)}")
        return functions

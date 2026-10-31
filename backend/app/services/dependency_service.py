"""Deterministic, source-backed extraction of local repository file dependencies."""
import ast
import posixpath
import re
from pathlib import PurePosixPath
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import quote

from app.models.repository import (
    DependencyCycle, DependencyEdge, DependencyNode, RepositoryDependenciesResponse,
    RepositoryFile, RepositoryResponse, UnresolvedDependency,
)
from app.services.github_service import GitHubService
from app.services.repository_snapshot_service import RepositorySnapshotService
from app.services.vector_store import VectorStoreService

SUPPORTED = {"Python", "JavaScript", "React JSX", "TypeScript", "React TSX", "Java"}
JS_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts")
JS_IMPORT = re.compile(r"(?:\b(?:import|export)\s+(?:[^\n;]*?\s+from\s+)?|\b(?:require|import)\s*\()\s*['\"]([^'\"]+)['\"]")
JAVA_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([\w.$*]+)\s*;", re.MULTILINE)


class DependencyAnalysisService:
    """Build directed edges only when an import resolves to an ingested source file."""

    @classmethod
    async def analyze_repository(cls, repo_url: str, refresh: bool = False, max_files: int = 250):
        owner, repository = GitHubService.parse_repo_url(repo_url)
        snapshot = None if refresh else RepositorySnapshotService.get(owner, repository)
        if snapshot is None and not refresh:
            files = VectorStoreService.get_repository_files(owner, repository)
            if files:
                snapshot = RepositoryResponse(
                    owner=owner, repository=repository, description=None,
                    default_branch=VectorStoreService.get_repository_default_branch(owner, repository),
                    stars=0, total_source_files_found=len(files), files_returned=len(files),
                    files_truncated=False, truncation_reason=None, files=files,
                )
                RepositorySnapshotService.save(snapshot)
        if snapshot is None:
            snapshot = await GitHubService.ingest_repository(repo_url)
            RepositorySnapshotService.save(snapshot)
        return cls.analyze_files(snapshot, max_files=max_files)

    @classmethod
    def analyze_files(cls, snapshot: RepositoryResponse, max_files: int = 250) -> RepositoryDependenciesResponse:
        supported = sorted((file for file in snapshot.files if file.language in SUPPORTED), key=lambda f: f.path)
        files = supported[:max_files]
        paths = {file.path for file in files}
        java_packages = {
            match.group(1)
            for file in files if file.language == "Java"
            for match in [re.search(r"^\s*package\s+([\w.]+)\s*;", file.content, re.MULTILINE)]
            if match
        }
        edges: Dict[Tuple[str, str, int, str], DependencyEdge] = {}
        unresolved: Dict[Tuple[str, str, int], UnresolvedDependency] = {}

        for file in files:
            imports = cls._imports(file)
            for imported, line, relative in imports:
                target = cls._resolve(file, imported, paths)
                if target:
                    key = (file.path, target, line, imported)
                    edges[key] = DependencyEdge(
                        id=f"{file.path}:{line}:{target}", source=file.path, target=target,
                        imported_name=imported, source_path=file.path, source_line=line,
                        source_url=cls._url(snapshot, file.path, line),
                    )
                elif relative or (
                    file.language == "Java"
                    and any(imported.startswith(package + ".") or imported == package for package in java_packages)
                ):
                    key = (file.path, imported, line)
                    unresolved[key] = UnresolvedDependency(
                        source_path=file.path, language=file.language, imported_name=imported,
                        source_line=line, reason="Local import did not match a source file in the repository snapshot.",
                        source_url=cls._url(snapshot, file.path, line),
                    )

        ordered_edges = sorted(edges.values(), key=lambda edge: (edge.source, edge.source_line, edge.target))
        adjacency: Dict[str, Set[str]] = {path: set() for path in paths}
        incoming: Dict[str, int] = {path: 0 for path in paths}
        outgoing: Dict[str, int] = {path: 0 for path in paths}
        for edge in ordered_edges:
            adjacency[edge.source].add(edge.target)
            outgoing[edge.source] += 1
            incoming[edge.target] += 1
        cycles = cls._cycles(adjacency)
        cycle_ids: Dict[str, List[str]] = {path: [] for path in paths}
        for cycle in cycles:
            for path in cycle.paths:
                cycle_ids[path].append(cycle.id)
        nodes = [DependencyNode(
            id=file.path, path=file.path, language=file.language,
            incoming_count=incoming[file.path], outgoing_count=outgoing[file.path],
            isolated=incoming[file.path] == 0 and outgoing[file.path] == 0,
            cycle_ids=cycle_ids[file.path], source_url=cls._url(snapshot, file.path),
        ) for file in files]
        return RepositoryDependenciesResponse(
            owner=snapshot.owner, repository=snapshot.repository, default_branch=snapshot.default_branch,
            nodes=nodes, edges=ordered_edges,
            unresolved_imports=sorted(unresolved.values(), key=lambda item: (item.source_path, item.source_line)),
            cycles=cycles, isolated_files=[node.path for node in nodes if node.isolated],
            files_analyzed=len(files), total_source_files=len(supported),
            files_truncated=snapshot.files_truncated or len(supported) > len(files),
            graph_limit=max_files, languages=sorted({file.language for file in files}),
        )

    @staticmethod
    def _url(snapshot: RepositoryResponse, path: str, line: Optional[int] = None) -> str:
        url = f"https://github.com/{snapshot.owner}/{snapshot.repository}/blob/{quote(snapshot.default_branch, safe='/')}/{quote(path, safe='/')}"
        return f"{url}#L{line}" if line else url

    @classmethod
    def _imports(cls, file: RepositoryFile) -> List[Tuple[str, int, bool]]:
        result: List[Tuple[str, int, bool]] = []
        if file.language == "Python":
            try:
                tree = ast.parse(file.content)
            except SyntaxError:
                return result
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    result.extend((alias.name, node.lineno, False) for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    module = "." * node.level + (node.module or "")
                    if node.level:
                        result.append((module, node.lineno, True))
                        if not node.module:
                            result.extend((module + alias.name, node.lineno, True) for alias in node.names)
                        else:
                            result.extend((module + "." + alias.name, node.lineno, True) for alias in node.names)
                    elif module:
                        result.append((module, node.lineno, False))
                        result.extend((module + "." + alias.name, node.lineno, False) for alias in node.names)
            return list(dict.fromkeys(result))
        if file.language in {"JavaScript", "React JSX", "TypeScript", "React TSX"}:
            for line_no, line in enumerate(file.content.splitlines(), 1):
                result.extend((match.group(1), line_no, match.group(1).startswith(".")) for match in JS_IMPORT.finditer(line))
            return list(dict.fromkeys(result))
        if file.language == "Java":
            for match in JAVA_IMPORT.finditer(file.content):
                imported = match.group(1)
                result.append((imported, file.content.count("\n", 0, match.start()) + 1, False))
            return result
        return result

    @classmethod
    def _resolve(cls, file: RepositoryFile, imported: str, paths: Set[str]) -> Optional[str]:
        candidates: List[str] = []
        path = file.path
        if file.language in {"JavaScript", "React JSX", "TypeScript", "React TSX"}:
            if not imported.startswith("."):
                return None
            base = posixpath.normpath(posixpath.join(posixpath.dirname(path), imported))
            candidates.append(base)
            candidates.extend(base + ext for ext in JS_EXTENSIONS)
            candidates.extend(posixpath.join(base, "index" + ext) for ext in JS_EXTENSIONS)
        elif file.language == "Python":
            if imported.startswith("."):
                level = len(imported) - len(imported.lstrip("."))
                module = imported[level:]
                package_dir = posixpath.dirname(path)
                if PurePosixPath(path).name == "__init__.py":
                    package_dir = posixpath.dirname(path)
                for _ in range(max(level - 1, 0)):
                    package_dir = posixpath.dirname(package_dir)
                base = posixpath.join(package_dir, module.replace(".", "/")) if module else package_dir
            else:
                base = imported.replace(".", "/")
            candidates.extend((base + ".py", posixpath.join(base, "__init__.py")))
        elif file.language == "Java":
            if imported.endswith(".*"):
                return None
            candidates.append(imported.replace(".", "/") + ".java")
        for candidate in candidates:
            if candidate in paths:
                return candidate
            # Python and Java source roots commonly add a prefix such as src/ or backend/.
            suffix_matches = sorted(item for item in paths if item.endswith("/" + candidate))
            if file.language in {"Java", "Python"} and len(suffix_matches) == 1:
                return suffix_matches[0]
        return None

    @staticmethod
    def _cycles(graph: Dict[str, Set[str]]) -> List[DependencyCycle]:
        """Tarjan SCC traversal; cycles are strongly connected groups, emitted once."""
        index = 0
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        stack: List[str] = []
        on_stack: Set[str] = set()
        groups: List[List[str]] = []

        def visit(node: str) -> None:
            nonlocal index
            indices[node] = lowlinks[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)
            for target in graph.get(node, set()):
                if target not in indices:
                    visit(target)
                    lowlinks[node] = min(lowlinks[node], lowlinks[target])
                elif target in on_stack:
                    lowlinks[node] = min(lowlinks[node], indices[target])
            if lowlinks[node] == indices[node]:
                group = []
                while True:
                    member = stack.pop()
                    on_stack.remove(member)
                    group.append(member)
                    if member == node:
                        break
                if len(group) > 1 or node in graph.get(node, set()):
                    groups.append(sorted(group))

        for node in sorted(graph):
            if node not in indices:
                visit(node)
        groups.sort(key=lambda group: group[0])
        return [DependencyCycle(id=f"cycle-{number}", paths=group) for number, group in enumerate(groups, 1)]

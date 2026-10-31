"""Deterministic repository architecture extraction from ingested source files."""
import ast
import posixpath
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import quote

from app.models.repository import (
    ArchitectureComponent,
    ArchitectureRelationship,
    RepositoryArchitectureResponse,
    RepositoryFile,
    RepositoryResponse,
)
from app.services.github_service import GitHubService
from app.services.repository_snapshot_service import RepositorySnapshotService
from app.services.vector_store import VectorStoreService


ARCHITECTURE_LANGUAGES = {
    "Python", "JavaScript", "React JSX", "TypeScript", "React TSX",
    "Java", "C#", "C++", "C/C++ Header", "C++ Header",
}
EXTENSIONS = {
    "Python": (".py",),
    "JavaScript": (".js", ".jsx", ".mjs", ".cjs"),
    "React JSX": (".jsx", ".js"),
    "TypeScript": (".ts", ".mts", ".cts"),
    "React TSX": (".tsx", ".ts"),
    "Java": (".java",),
    "C#": (".cs",),
    "C++": (".cpp", ".cc", ".cxx", ".hpp", ".h", ".hh", ".hxx"),
    "C/C++ Header": (".h", ".hpp"),
    "C++ Header": (".hpp", ".h"),
}
IMPORT_DATABASES = {
    "sqlite3": "SQLite",
    "sqlalchemy": "SQLAlchemy",
    "psycopg": "PostgreSQL",
    "psycopg2": "PostgreSQL",
    "asyncpg": "PostgreSQL",
    "pg": "PostgreSQL",
    "mysql": "MySQL",
    "mysql2": "MySQL",
    "pymongo": "MongoDB",
    "mongoose": "MongoDB",
    "redis": "Redis",
    "prisma": "Prisma",
    "typeorm": "TypeORM",
    "sequelize": "Sequelize",
    "org.hibernate": "Hibernate",
    "org.springframework.data": "Spring Data",
    "microsoft.entityframeworkcore": "Entity Framework Core",
    "microsoft.data.sqlclient": "SQL Server client",
    "npgsql": "PostgreSQL",
}
INTEGRATION_IMPORTS = {
    "httpx": "HTTP client (HTTPX)",
    "requests": "HTTP client (Requests)",
    "axios": "HTTP client (Axios)",
    "groq": "Groq API client",
    "openai": "OpenAI API client",
    "boto3": "AWS SDK (Boto3)",
    "google.cloud": "Google Cloud client",
    "kafka": "Kafka client",
}
ENTRYPOINT_NAMES = {
    "main.py", "app.py", "server.py", "index.py", "manage.py", "wsgi.py", "asgi.py",
    "main.js", "main.jsx", "main.ts", "main.tsx", "index.js", "index.jsx",
    "index.ts", "index.tsx", "server.js", "server.ts",
}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace", "route", "api_route"}


@dataclass(frozen=True)
class ImportFact:
    module: str
    line: int
    style: str


class ArchitectureService:
    """Analyze cached repository source; fetch only when no local snapshot/index exists."""

    @classmethod
    async def analyze_repository(cls, repo_url: str, refresh: bool = False) -> RepositoryArchitectureResponse:
        owner, repository = GitHubService.parse_repo_url(repo_url)
        snapshot = None if refresh else RepositorySnapshotService.get(owner, repository)
        if snapshot is None and not refresh:
            indexed_files = VectorStoreService.get_repository_files(owner, repository)
            if indexed_files:
                snapshot = RepositoryResponse(
                    owner=owner,
                    repository=repository,
                    description=None,
                    default_branch=VectorStoreService.get_repository_default_branch(owner, repository),
                    stars=0,
                    total_source_files_found=len(indexed_files),
                    files_returned=len(indexed_files),
                    files_truncated=False,
                    truncation_reason=None,
                    files=indexed_files,
                )
                RepositorySnapshotService.save(snapshot)
        if snapshot is None:
            snapshot = await GitHubService.ingest_repository(repo_url)
            RepositorySnapshotService.save(snapshot)
        return cls.analyze_files(snapshot)

    @classmethod
    def analyze_files(cls, snapshot: RepositoryResponse) -> RepositoryArchitectureResponse:
        components: Dict[str, ArchitectureComponent] = {}
        relationships: Dict[str, ArchitectureRelationship] = {}
        files = snapshot.files
        root_id = f"repo:{snapshot.owner.lower()}/{snapshot.repository.lower()}"
        components[root_id] = ArchitectureComponent(
            id=root_id,
            label=f"{snapshot.owner}/{snapshot.repository}",
            component_type="repository",
            evidence_type="detected",
            description="Repository root from the GitHub repository identity.",
            details=[snapshot.default_branch and f"Default branch: {snapshot.default_branch}"],
        )

        paths = {file.path for file in files}
        directory_paths: Set[str] = set()
        for file in files:
            parent = PurePosixPath(file.path).parent
            while str(parent) not in ("", "."):
                directory_paths.add(str(parent))
                parent = parent.parent
        for directory in sorted(directory_paths, key=lambda value: (value.count("/"), value)):
            directory_id = f"dir:{directory}"
            parent_path = str(PurePosixPath(directory).parent)
            parent_id = f"dir:{parent_path}" if parent_path not in ("", ".") else root_id
            components[directory_id] = ArchitectureComponent(
                id=directory_id,
                label=PurePosixPath(directory).name,
                component_type="directory",
                evidence_type="detected",
                description="Directory present in the ingested repository file paths.",
                path=directory,
            )
            cls._edge(relationships, parent_id, directory_id, "contains", "detected")

        modules_by_path: Dict[str, str] = {}
        file_facts: Dict[str, Tuple[List[ImportFact], List[ArchitectureComponent], bool]] = {}
        for file in sorted(files, key=lambda item: item.path):
            module_id = f"file:{file.path}"
            modules_by_path[file.path] = module_id
            imports, declarations, has_main_guard = cls._extract_facts(file)
            file_facts[file.path] = (imports, declarations, has_main_guard)
            filename = PurePosixPath(file.path).name.lower()
            is_entry = has_main_guard or filename in ENTRYPOINT_NAMES
            stem = PurePosixPath(file.path).stem.lower()
            path_parts = {part.lower() for part in PurePosixPath(file.path).parts[:-1]}
            conventional_role = None
            if stem.endswith(("_service", "service")) or "services" in path_parts:
                conventional_role = "service"
            elif stem.endswith(("_controller", "controller")) or "controllers" in path_parts:
                conventional_role = "controller"
            component_type = "entry_point" if is_entry else conventional_role or "module"
            evidence = (
                "detected" if has_main_guard else
                "inferred" if is_entry or conventional_role else
                "detected"
            )
            description = (
                "Python module contains an `if __name__ == '__main__'` entry guard."
                if has_main_guard else
                "Candidate application entry point inferred from its conventional filename."
                if is_entry else
                f"{conventional_role.title()} role inferred from the source path naming."
                if conventional_role else
                f"Source module parsed as {file.language}."
                if file.language in ARCHITECTURE_LANGUAGES else
                f"Repository source file; architecture parsing is unsupported for {file.language}."
            )
            components[module_id] = ArchitectureComponent(
                id=module_id,
                label=PurePosixPath(file.path).name,
                component_type=component_type,
                evidence_type=evidence,
                description=description,
                path=file.path,
                language=file.language,
                start_line=1,
                end_line=max(1, len(file.content.splitlines())),
                source_url=cls._source_url(snapshot, file.path, 1, max(1, len(file.content.splitlines()))),
            )
            parent = str(PurePosixPath(file.path).parent)
            parent_id = f"dir:{parent}" if parent not in ("", ".") else root_id
            cls._edge(relationships, parent_id, module_id, "contains", "detected")
            if is_entry and not has_main_guard:
                cls._edge(relationships, root_id, module_id, "entry-point filename convention", "inferred")

            for declaration in declarations:
                components[declaration.id] = declaration.model_copy(update={
                    "source_url": cls._source_url(
                        snapshot, file.path, declaration.start_line or 1, declaration.end_line or declaration.start_line or 1
                    )
                })
                cls._edge(
                    relationships, module_id, declaration.id, "declares", "detected",
                    file.path, declaration.start_line,
                )

        path_lookup = cls._build_path_lookup(paths)
        for file in files:
            source_id = modules_by_path[file.path]
            imports, _, _ = file_facts[file.path]
            for imported in imports:
                resolved_path = cls._resolve_import(file, imported, path_lookup)
                if resolved_path and resolved_path in modules_by_path:
                    cls._edge(
                        relationships, source_id, modules_by_path[resolved_path], "imports", "detected",
                        file.path, imported.line,
                    )
                integration = cls._integration_name(imported.module)
                if integration:
                    integration_id = f"integration:{integration.lower().replace(' ', '-') }"
                    if integration_id not in components:
                        database = integration in {
                            "SQLite", "SQLAlchemy", "PostgreSQL", "MySQL", "MongoDB", "Redis",
                            "Prisma", "TypeORM", "Sequelize", "Hibernate", "Spring Data",
                            "Entity Framework Core", "SQL Server client",
                        }
                        components[integration_id] = ArchitectureComponent(
                            id=integration_id,
                            label=integration,
                            component_type="database" if database else "integration",
                            evidence_type="detected",
                            description=f"External integration referenced by the `{imported.module}` import.",
                            details=[f"Imported in {file.path}:{imported.line}"],
                        )
                    cls._edge(
                        relationships, source_id, integration_id,
                        "database integration" if components[integration_id].component_type == "database" else "external integration",
                        "detected", file.path, imported.line,
                    )

        detected = list(components.values())
        supported = sorted({file.language for file in files if file.language in ARCHITECTURE_LANGUAGES})
        unsupported = sorted(file.path for file in files if file.language not in ARCHITECTURE_LANGUAGES)
        return RepositoryArchitectureResponse(
            owner=snapshot.owner,
            repository=snapshot.repository,
            default_branch=snapshot.default_branch,
            components=detected,
            relationships=list(relationships.values()),
            files_analyzed=len(files),
            directories_detected=len(directory_paths),
            entry_points_detected=sum(
                component.component_type == "entry_point" and component.evidence_type == "detected"
                for component in detected
            ),
            entry_point_candidates=sum(component.component_type == "entry_point" for component in detected),
            routes_detected=sum(component.component_type == "route" for component in detected),
            files_truncated=snapshot.files_truncated,
            truncation_reason=snapshot.truncation_reason,
            supported_languages=supported,
            unsupported_files=unsupported,
        )

    @classmethod
    def _extract_facts(cls, file: RepositoryFile) -> Tuple[List[ImportFact], List[ArchitectureComponent], bool]:
        imports: List[ImportFact] = []
        declarations: List[ArchitectureComponent] = []
        main_guard = False
        if file.language == "Python":
            try:
                tree = ast.parse(file.content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports.extend(ImportFact(alias.name, node.lineno, "python") for alias in node.names)
                    elif isinstance(node, ast.ImportFrom):
                        module = ("." * node.level) + (node.module or "")
                        imports.append(ImportFact(module, node.lineno, "python"))
                    elif isinstance(node, ast.If) and cls._is_main_guard(node.test):
                        main_guard = True
                    elif isinstance(node, ast.ClassDef):
                        role = cls._class_role(node.name)
                        if role:
                            declarations.append(cls._declaration(file, node.name, role, node.lineno, getattr(node, "end_lineno", node.lineno)))
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for decorator in node.decorator_list:
                            route = cls._python_route(decorator)
                            if route:
                                label, line = route
                                declarations.append(cls._declaration(file, label, "route", line, line))
            except SyntaxError:
                pass

        ext = PurePosixPath(file.path).suffix.lower()
        if ext in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}:
            normalized_imports = []
            for match in re.finditer(r"\bimport\s+(?:[^;]*?\s+from\s+)?['\"]([^'\"]+)['\"]|\b(?:require|import)\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", file.content):
                normalized_imports.append(ImportFact(match.group(1) or match.group(2), file.content.count("\n", 0, match.start()) + 1, "js"))
            imports = normalized_imports
            for match in re.finditer(r"\b(?:app|router)\.(get|post|put|patch|delete|route)\s*\(\s*['\"]([^'\"]+)['\"]", file.content, re.I):
                line = file.content.count("\n", 0, match.start()) + 1
                declarations.append(cls._declaration(file, f"{match.group(1).upper()} {match.group(2)}", "route", line, line))
            for match in re.finditer(r"\bclass\s+([A-Za-z_$][\w$]*)", file.content):
                name = match.group(1)
                role = cls._class_role(name)
                if role:
                    line = file.content.count("\n", 0, match.start()) + 1
                    declarations.append(cls._declaration(file, name, role, line, line))

        elif file.language == "Java":
            imports.extend(ImportFact(match.group(1), file.content.count("\n", 0, match.start()) + 1, "java")
                           for match in re.finditer(r"^\s*import\s+(?:static\s+)?([\w.*]+)\s*;", file.content, re.M))
            cls._regex_declarations(file, declarations, r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)", "class")
            cls._java_routes(file, declarations)
        elif file.language == "C#":
            imports.extend(ImportFact(match.group(1), file.content.count("\n", 0, match.start()) + 1, "csharp")
                           for match in re.finditer(r"^\s*using\s+([\w.]+)\s*;", file.content, re.M))
            cls._regex_declarations(file, declarations, r"\b(?:class|interface|record)\s+([A-Za-z_][\w]*)", "class")
            cls._attribute_routes(file, declarations)
        elif file.language in {"C++", "C/C++ Header", "C++ Header"}:
            imports.extend(ImportFact(match.group(1), file.content.count("\n", 0, match.start()) + 1, "cpp")
                           for match in re.finditer(r"^\s*#\s*include\s*[\"<]([^\">]+)[\">]", file.content, re.M))
            cls._regex_declarations(file, declarations, r"\b(?:class|struct)\s+([A-Za-z_][\w]*)", "class")
        return imports, declarations, main_guard

    @classmethod
    def _declaration(cls, file: RepositoryFile, label: str, role: str, start: int, end: int) -> ArchitectureComponent:
        description = {
            "route": "HTTP route declaration detected in source code.",
            "controller": "Controller class declaration detected in source code.",
            "service": "Service class declaration detected in source code.",
        }[role]
        return ArchitectureComponent(
            id=f"{role}:{file.path}:{start}:{label}",
            label=label,
            component_type=role,
            evidence_type="detected",
            description=description,
            path=file.path,
            language=file.language,
            start_line=start,
            end_line=end,
        )

    @staticmethod
    def _class_role(name: str) -> Optional[str]:
        if name.lower().endswith("controller"):
            return "controller"
        if name.lower().endswith(("service", "serviceimpl")):
            return "service"
        return None

    @staticmethod
    def _is_main_guard(node: ast.expr) -> bool:
        return isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "__name__" and any(
            isinstance(value, ast.Constant) and value.value == "__main__" for value in node.comparators
        )

    @classmethod
    def _python_route(cls, decorator: ast.expr) -> Optional[Tuple[str, int]]:
        if not isinstance(decorator, ast.Call):
            return None
        target = decorator.func
        method = target.attr.lower() if isinstance(target, ast.Attribute) else ""
        if method not in HTTP_METHODS:
            return None
        route_path = decorator.args[0].value if decorator.args and isinstance(decorator.args[0], ast.Constant) else "*"
        return f"{method.upper()} {route_path}", decorator.lineno

    @classmethod
    def _regex_declarations(cls, file: RepositoryFile, output: List[ArchitectureComponent], pattern: str, _kind: str) -> None:
        for match in re.finditer(pattern, file.content):
            name = match.group(1)
            role = cls._class_role(name)
            if role:
                line = file.content.count("\n", 0, match.start()) + 1
                output.append(cls._declaration(file, name, role, line, line))

    @classmethod
    def _java_routes(cls, file: RepositoryFile, output: List[ArchitectureComponent]) -> None:
        for match in re.finditer(r"@(Get|Post|Put|Patch|Delete|Request)Mapping(?:\s*\(\s*['\"]([^'\"]*)['\"])?", file.content):
            line = file.content.count("\n", 0, match.start()) + 1
            output.append(cls._declaration(file, f"{match.group(1).upper()} {match.group(2) or '*'}", "route", line, line))

    @classmethod
    def _attribute_routes(cls, file: RepositoryFile, output: List[ArchitectureComponent]) -> None:
        pattern = r"""\[(Http(Get|Post|Put|Patch|Delete)|Route)(?:\(\s*['\"]?([^\]\)]*)['\"]?\s*\))?\]"""
        for match in re.finditer(pattern, file.content, re.I):
            line = file.content.count("\n", 0, match.start()) + 1
            output.append(cls._declaration(file, f"{match.group(1)} {match.group(3) or '*'}".strip(), "route", line, line))

    @classmethod
    def _build_path_lookup(cls, paths: Set[str]) -> Set[str]:
        return paths

    @classmethod
    def _resolve_import(cls, source: RepositoryFile, imported: ImportFact, paths: Set[str]) -> Optional[str]:
        module = imported.module.strip()
        candidates: List[str] = []
        if imported.style == "js":
            if not module.startswith("."):
                return None
            base = posixpath.normpath(posixpath.join(posixpath.dirname(source.path), module))
            candidates.extend([base, *(base + suffix for suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"))])
            candidates.extend(posixpath.join(base, "index" + suffix) for suffix in (".js", ".jsx", ".ts", ".tsx"))
        elif imported.style == "cpp":
            base = posixpath.normpath(posixpath.join(posixpath.dirname(source.path), module))
            candidates.extend([base, posixpath.normpath(module), "/" + module])
        else:
            if imported.style == "python" and module.startswith("."):
                level = len(module) - len(module.lstrip("."))
                suffix = module[level:].replace(".", "/")
                parent = posixpath.dirname(source.path)
                for _ in range(max(0, level - 1)):
                    parent = posixpath.dirname(parent)
                base = posixpath.normpath(posixpath.join(parent, suffix))
            else:
                base = module.replace(".", "/")
            candidates.extend([base + ".py", posixpath.join(base, "__init__.py"), base + ".java", base + ".cs"])
            candidates.extend(path for path in paths if (
                path.endswith("/" + base + ".py")
                or path.endswith("/" + base + "/__init__.py")
                or path.endswith("/" + base + ".java")
                or path.endswith("/" + base + ".cs")
            ))
            if imported.style == "java":
                candidates.extend(path for path in paths if path.endswith("/" + module.replace(".", "/") + ".java"))
        for candidate in candidates:
            clean = candidate.lstrip("/")
            if clean in paths:
                return clean
        return None

    @classmethod
    def _integration_name(cls, module: str) -> Optional[str]:
        normalized = module.lower().lstrip(".")
        for package, display_name in {**IMPORT_DATABASES, **INTEGRATION_IMPORTS}.items():
            if normalized == package or normalized.startswith(package + "."):
                return display_name
        return None

    @classmethod
    def _edge(cls, relationships: Dict[str, ArchitectureRelationship], source: str, target: str,
              label: str, evidence_type: str, source_path: Optional[str] = None,
              source_line: Optional[int] = None) -> None:
        key = f"{source}|{target}|{label}|{source_path or ''}|{source_line or ''}"
        relationships.setdefault(key, ArchitectureRelationship(
            id=key, source=source, target=target, label=label, evidence_type=evidence_type,
            source_path=source_path, source_line=source_line,
        ))

    @staticmethod
    def _source_url(snapshot: RepositoryResponse, path: str, start: int, end: int) -> str:
        return (
            f"https://github.com/{quote(snapshot.owner)}/{quote(snapshot.repository)}/blob/"
            f"{quote(snapshot.default_branch, safe='/')}/{quote(path, safe='/')}#L{start}-L{end}"
        )

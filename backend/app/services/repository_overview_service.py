"""Build and persist deterministic, source-backed repository overview context."""
from collections import Counter
from contextlib import closing
import ast
import configparser
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import tomllib
from typing import List, Optional

from app.core.config import settings
from app.models.repository import (
    RepositoryContextChunk,
    RepositoryFile,
    RepositoryOverview,
    RepositoryOverviewEvidence,
    RepositoryResponse,
)
from app.services.architecture_service import ArchitectureService


README_RE = re.compile(r"(?:^|/)readme(?:\.(?:md|rst|txt))?$", re.IGNORECASE)
MANIFEST_NAMES = {
    "pyproject.toml", "setup.cfg", "setup.py", "requirements.txt", "pipfile",
    "package.json", "composer.json", "cargo.toml", "go.mod", "pom.xml",
    "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    "tsconfig.json", "vite.config.js", "vite.config.ts", "webpack.config.js",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "makefile",
    "cmakelists.txt", "environment.yml", "environment.yaml",
}
FRAMEWORK_NAMES = {
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask",
    "starlette": "Starlette", "streamlit": "Streamlit", "react": "React",
    "react-dom": "React", "vite": "Vite", "next": "Next.js",
    "next.js": "Next.js", "express": "Express", "vue": "Vue",
    "angular": "Angular", "spring-boot": "Spring Boot", "spring": "Spring",
    "langchain": "LangChain", "chromadb": "ChromaDB", "sentence-transformers": "Sentence Transformers",
    "pydantic": "Pydantic", "sqlalchemy": "SQLAlchemy", "prisma": "Prisma",
    "tensorflow": "TensorFlow", "torch": "PyTorch", "pytorch": "PyTorch",
}
NON_CODE_LANGUAGES = {"Markdown", "reStructuredText", "TOML", "Text", "XML", "Gradle", "Configuration", "Properties"}


class RepositoryOverviewService:
    """Persist one content-fingerprinted overview per GitHub repository."""

    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        path = Path(settings.CHROMA_PERSIST_DIRECTORY) / "repository_overviews.sqlite3"
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(path), timeout=20)
        connection.execute(
            """CREATE TABLE IF NOT EXISTS repository_overviews (
                owner TEXT NOT NULL, repository TEXT NOT NULL,
                fingerprint TEXT NOT NULL, overview_json TEXT NOT NULL,
                PRIMARY KEY(owner, repository)
            )"""
        )
        return connection

    @staticmethod
    def fingerprint(snapshot: RepositoryResponse) -> str:
        digest = hashlib.sha256()
        for file in sorted(snapshot.files, key=lambda item: item.path):
            digest.update(file.path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(file.content.encode("utf-8"))
            digest.update(b"\0")
        return digest.hexdigest()

    @classmethod
    def get_or_build(cls, snapshot: RepositoryResponse) -> RepositoryOverview:
        fingerprint = cls.fingerprint(snapshot)
        with closing(cls._connect()) as connection:
            row = connection.execute(
                "SELECT fingerprint, overview_json FROM repository_overviews WHERE owner=? AND repository=?",
                (snapshot.owner.lower(), snapshot.repository.lower()),
            ).fetchone()
        if row and row[0] == fingerprint:
            return RepositoryOverview.model_validate_json(row[1])

        overview = cls.build(snapshot, fingerprint)
        with closing(cls._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO repository_overviews(owner, repository, fingerprint, overview_json)
                   VALUES (?, ?, ?, ?) ON CONFLICT(owner, repository) DO UPDATE SET
                   fingerprint=excluded.fingerprint, overview_json=excluded.overview_json""",
                (snapshot.owner.lower(), snapshot.repository.lower(), fingerprint, overview.model_dump_json()),
            )
        return overview

    @classmethod
    def build(cls, snapshot: RepositoryResponse, fingerprint: Optional[str] = None) -> RepositoryOverview:
        files = sorted(snapshot.files, key=lambda item: item.path.lower())
        readmes = [file for file in files if README_RE.search(file.path)]
        manifests = [file for file in files if PurePosixPath(file.path).name.lower() in MANIFEST_NAMES
                     or PurePosixPath(file.path).name.lower().startswith("requirements-")]
        languages = Counter(file.language for file in files if file.language not in NON_CODE_LANGUAGES)
        dependencies: set[str] = set()
        project_name = None
        project_description = None

        for file in manifests:
            name = PurePosixPath(file.path).name.lower()
            try:
                if name == "package.json":
                    data = json.loads(file.content)
                    project_name = project_name or data.get("name")
                    project_description = project_description or data.get("description")
                    for group in ("dependencies", "devDependencies", "optionalDependencies"):
                        dependencies.update(data.get(group, {}).keys())
                elif name == "pyproject.toml":
                    data = tomllib.loads(file.content)
                    project = data.get("project", {})
                    project_name = project_name or project.get("name")
                    project_description = project_description or project.get("description")
                    dependencies.update(cls._dependency_name(value) for value in project.get("dependencies", []))
                    for group in project.get("optional-dependencies", {}).values():
                        dependencies.update(cls._dependency_name(value) for value in group)
                    poetry = data.get("tool", {}).get("poetry", {})
                    project_name = project_name or poetry.get("name")
                    project_description = project_description or poetry.get("description")
                    dependencies.update(poetry.get("dependencies", {}).keys())
                elif name.startswith("requirements") or name == "pipfile":
                    dependencies.update(
                        cls._dependency_name(line.strip()) for line in file.content.splitlines()
                        if line.strip() and not line.lstrip().startswith(("#", "-", "["))
                    )
                elif name == "setup.cfg":
                    config = configparser.ConfigParser()
                    config.read_string(file.content)
                    metadata = config["metadata"] if config.has_section("metadata") else {}
                    options = config["options"] if config.has_section("options") else {}
                    project_name = project_name or metadata.get("name")
                    project_description = project_description or metadata.get("description")
                    dependencies.update(cls._dependency_name(line) for line in options.get("install_requires", "").splitlines() if line.strip())
                elif name == "setup.py":
                    tree = ast.parse(file.content)
                    for node in ast.walk(tree):
                        if not isinstance(node, ast.Call) or getattr(node.func, "id", getattr(node.func, "attr", "")) != "setup":
                            continue
                        values = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
                        if isinstance(values.get("name"), ast.Constant):
                            project_name = project_name or values["name"].value
                        if isinstance(values.get("description"), ast.Constant):
                            project_description = project_description or values["description"].value
                        requirements = values.get("install_requires")
                        if isinstance(requirements, (ast.List, ast.Tuple)):
                            dependencies.update(
                                cls._dependency_name(item.value) for item in requirements.elts
                                if isinstance(item, ast.Constant) and isinstance(item.value, str)
                            )
                else:
                    dependencies.update(match.group(1) for match in re.finditer(
                        r"(?im)^\s*(?:import\s+)?([A-Za-z][A-Za-z0-9_.-]+)\s*(?:[<>=~!]|$)", file.content
                    ))
            except (ValueError, TypeError, AttributeError, tomllib.TOMLDecodeError):
                # Invalid or unsupported manifests remain available as direct excerpts.
                continue

        dependency_names = sorted({item.lower().replace("_", "-") for item in dependencies if item})
        frameworks = sorted({label for item in dependency_names for key, label in FRAMEWORK_NAMES.items()
                             if item == key or item.startswith(f"{key}-")})
        if not project_description and readmes:
            project_description = cls._readme_intro(readmes[0].content)
        headings = []
        for readme in readmes:
            headings.extend(re.findall(r"(?m)^\s{0,3}#{1,4}\s+(.+?)\s*#*\s*$", readme.content))
        entry_points, modules, module_files = cls._architecture_facts(snapshot)

        evidence: List[RepositoryOverviewEvidence] = []
        for file in readmes[:2]:
            evidence.append(cls._evidence(file, "readme", 10000))
        for file in manifests[:8]:
            evidence.append(cls._evidence(file, "manifest", 6500))
        for language in sorted(languages):
            exemplar = next((file for file in files if file.language == language), None)
            if exemplar:
                evidence.append(cls._evidence(exemplar, "language", 700))
        for path in entry_points[:8]:
            file = next((item for item in files if item.path == path), None)
            if file:
                evidence.append(cls._evidence(file, "entry_point", 1800))
        for module, path in module_files[:8]:
            file = next((item for item in files if item.path == path), None)
            if file:
                evidence.append(cls._evidence(file, "module", 900))

        return RepositoryOverview(
            owner=snapshot.owner,
            repository=snapshot.repository,
            fingerprint=fingerprint or cls.fingerprint(snapshot),
            description=snapshot.description,
            readme_paths=[file.path for file in readmes],
            project_name=project_name or snapshot.repository,
            project_description=project_description,
            languages=dict(sorted(languages.items())),
            frameworks=frameworks,
            dependencies=dependency_names[:60],
            feature_headings=list(dict.fromkeys(headings))[:24],
            entry_points=entry_points,
            important_modules=modules,
            manifest_paths=[file.path for file in manifests],
            evidence=evidence,
        )

    @classmethod
    def context_for_intent(cls, overview: RepositoryOverview, intent: str) -> List[RepositoryContextChunk]:
        if intent == "technology":
            categories = {"manifest", "language", "readme"}
        elif intent == "architecture":
            categories = {"readme", "entry_point", "module"}
        else:
            categories = {"readme", "manifest", "language", "entry_point", "module"}
        selected = [item for item in overview.evidence if item.category in categories]
        if intent == "technology":
            order = {"manifest": 0, "language": 1, "readme": 2}
            selected.sort(key=lambda item: (order.get(item.category, 9), item.path))
        return [RepositoryContextChunk(
            chunk_id=item.evidence_id,
            path=item.path,
            language=item.language,
            start_line=item.start_line,
            end_line=item.end_line,
            content=item.content,
            context_type="overview",
        ) for item in selected]

    @classmethod
    def architecture_context(cls, snapshot: RepositoryResponse) -> List[RepositoryContextChunk]:
        architecture = ArchitectureService.analyze_files(snapshot)
        files = {file.path: file for file in snapshot.files}
        component_by_id = {component.id: component for component in architecture.components}
        contexts: List[RepositoryContextChunk] = []

        for relationship in architecture.relationships:
            if not relationship.source_path or not relationship.source_line:
                continue
            file = files.get(relationship.source_path)
            if not file:
                continue
            line = relationship.source_line
            excerpt = RepositoryOverviewService._line_excerpt(file, line, line)
            source = component_by_id.get(relationship.source)
            target = component_by_id.get(relationship.target)
            evidence_type = relationship.evidence_type
            fact = (
                f"{evidence_type.title()} architecture relationship: "
                f"{source.label if source else relationship.source} {relationship.label} "
                f"{target.label if target else relationship.target}."
            )
            contexts.append(RepositoryContextChunk(
                chunk_id=f"arch_{relationship.id}", path=file.path, language=file.language,
                start_line=line, end_line=line, content=f"{fact}\nSource excerpt:\n{excerpt}",
                context_type="architecture",
            ))

        for component in architecture.components:
            if component.component_type not in {"entry_point", "service", "controller", "route", "database", "integration"}:
                continue
            if not component.path or component.path not in files:
                continue
            file = files[component.path]
            start = component.start_line or 1
            end = min(component.end_line or start, start + 20)
            excerpt = cls._line_excerpt(file, start, end)
            details = "; ".join(component.details)
            fact = (
                f"{component.evidence_type.title()} architecture component: {component.label}; "
                f"role={component.component_type}; {component.description} {details}"
            )
            contexts.append(RepositoryContextChunk(
                chunk_id=f"arch_{component.id}", path=file.path, language=file.language,
                start_line=start, end_line=end, content=f"{fact}\nSource excerpt:\n{excerpt}",
                context_type="architecture",
            ))
        return contexts[:24]

    @staticmethod
    def _line_excerpt(file: RepositoryFile, start_line: int, end_line: int) -> str:
        lines = file.content.splitlines()
        start = max(0, start_line - 1)
        return "\n".join(lines[start:max(start + 1, end_line)])[:5000]

    @staticmethod
    def _evidence(file: RepositoryFile, category: str, max_chars: int) -> RepositoryOverviewEvidence:
        lines = file.content.splitlines()
        selected = []
        length = 0
        for line in lines:
            addition = len(line) + (1 if selected else 0)
            if length + addition > max_chars:
                break
            selected.append(line)
            length += addition
        content = "\n".join(selected)
        identity = hashlib.sha1(f"{category}:{file.path}".encode()).hexdigest()[:16]
        return RepositoryOverviewEvidence(
            evidence_id=f"overview_{identity}", category=category, path=file.path,
            language=file.language, start_line=1, end_line=max(1, len(selected)), content=content,
        )

    @staticmethod
    def _dependency_name(value: str) -> str:
        return re.split(r"[<>=~!;\[]", value, maxsplit=1)[0].strip().strip('"\'')

    @staticmethod
    def _readme_intro(content: str) -> Optional[str]:
        paragraphs = []
        for line in content.splitlines():
            value = line.strip()
            if not value:
                if paragraphs:
                    break
                continue
            if value.startswith("#") or value.startswith("[") or value.startswith("!"):
                continue
            paragraphs.append(value)
            if len(" ".join(paragraphs)) > 500:
                break
        return " ".join(paragraphs)[:600] or None

    @classmethod
    def _architecture_facts(cls, snapshot: RepositoryResponse):
        architecture = ArchitectureService.analyze_files(snapshot)
        entries = sorted({component.path for component in architecture.components
                          if component.component_type == "entry_point" and component.path})
        counts: Counter[str] = Counter()
        representatives = {}
        component_paths = {}
        importance = Counter()
        for component in architecture.components:
            if component.path:
                component_paths[component.id] = component.path
                if component.component_type in {"entry_point", "service", "controller", "route"}:
                    importance[component.path] += 5 if component.component_type == "entry_point" else 3
        for relationship in architecture.relationships:
            source_path = component_paths.get(relationship.source)
            target_path = component_paths.get(relationship.target)
            if source_path:
                importance[source_path] += 1
            if target_path:
                importance[target_path] += 1
        for file in snapshot.files:
            parts = PurePosixPath(file.path).parts
            if len(parts) > 1:
                module = parts[0]
                counts[module] += 1
                representatives.setdefault(module, file.path)
        important_paths = sorted(importance, key=lambda path: (-importance[path], path))
        modules = list(dict.fromkeys(important_paths + sorted(counts, key=lambda path: (-counts[path], path))))[:12]
        module_files = []
        for path in modules:
            if path in representatives:
                module_files.append((path, representatives[path]))
            else:
                module_files.append((PurePosixPath(path).stem, path))
        return entries, modules, module_files

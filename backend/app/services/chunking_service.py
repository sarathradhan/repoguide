"""Service for splitting repository source code files into semantic chunks."""
import logging
import hashlib
import re
from typing import Dict, List, Optional
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from app.core.config import settings
from app.models.repository import CodeChunk, RepositoryFile

logger = logging.getLogger("repoguide.chunking")

# Mapping of file language string to LangChain Language enum
LANGCHAIN_LANGUAGE_MAP: Dict[str, Language] = {
    "Python": Language.PYTHON,
    "Java": Language.JAVA,
    "JavaScript": Language.JS,
    "React JSX": Language.JS,
    "TypeScript": Language.TS,
    "React TSX": Language.TS,
    "C++": Language.CPP,
    "C/C++ Header": Language.CPP,
    "C++ Header": Language.CPP,
    "C#": Language.CSHARP,
    "HTML": Language.HTML,
}


class ChunkingService:
    """Handles splitting source code into syntax-aware chunks with line range preservation."""

    @classmethod
    def get_splitter_for_language(
        cls,
        language: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> RecursiveCharacterTextSplitter:
        """Create a language-aware text splitter or generic recursive splitter."""
        c_size = settings.CHUNK_SIZE if chunk_size is None else chunk_size
        c_overlap = settings.CHUNK_OVERLAP if chunk_overlap is None else chunk_overlap
        if c_size <= 0 or c_overlap < 0 or c_overlap >= c_size:
            raise ValueError("Chunk size must be positive and overlap must be between 0 and chunk size.")

        lang_enum = LANGCHAIN_LANGUAGE_MAP.get(language)
        if lang_enum:
            try:
                return RecursiveCharacterTextSplitter.from_language(
                    language=lang_enum,
                    chunk_size=c_size,
                    chunk_overlap=c_overlap,
                )
            except Exception as e:
                logger.warning(
                    "Failed to create language-specific splitter for %s: %s; using fallback.",
                    language,
                    e,
                )

        # Fallback recursive splitter with code-oriented separators
        separators = ["\n\n", "\n", ";", " ", ""]
        return RecursiveCharacterTextSplitter(
            separators=separators,
            chunk_size=c_size,
            chunk_overlap=c_overlap,
        )

    @classmethod
    def chunk_file(
        cls,
        owner: str,
        repository: str,
        file: RepositoryFile,
    ) -> List[CodeChunk]:
        """
        Split a single source code file into CodeChunks with accurate line ranges.

        Args:
            owner: Repository owner
            repository: Repository name
            file: RepositoryFile model containing path, language, content

        Returns:
            List of CodeChunk instances
        """
        content = file.content
        if not content or not content.strip():
            return []

        splitter = cls.get_splitter_for_language(file.language)
        raw_chunks = splitter.split_text(content)

        chunks: List[CodeChunk] = []
        previous_start_idx = -1

        for idx, chunk_text in enumerate(raw_chunks):
            # Clean chunk text
            stripped_chunk = chunk_text.strip()
            if not stripped_chunk:
                continue

            # Splitter chunks preserve source text apart from surrounding whitespace.
            # Search from just after the previous start: chunks may overlap, while
            # repeated identical blocks must still advance to their next occurrence.
            pos = content.find(stripped_chunk, previous_start_idx + 1)
            if pos < 0:
                logger.warning("Could not map chunk offset exactly for %s", file.path)
                continue

            # Calculate 1-based start and end line numbers
            start_line = content[:pos].count("\n") + 1
            end_line = content[: pos + len(stripped_chunk)].count("\n") + (
                1 if pos + len(stripped_chunk) == 0 or content[pos + len(stripped_chunk) - 1 : pos + len(stripped_chunk)] != "\n" else 0
            )

            previous_start_idx = pos

            # Construct safe deterministic chunk ID
            # Format: {owner}_{repo}_{path_alphanum}_{chunk_index}
            safe_path = re.sub(r"[^a-zA-Z0-9_.-]", "_", file.path)[:80]
            path_hash = hashlib.sha256(file.path.encode("utf-8")).hexdigest()[:12]
            chunk_id = f"{owner}_{repository}_{safe_path}_{path_hash}_chunk_{idx}"

            chunks.append(
                CodeChunk(
                    chunk_id=chunk_id,
                    owner=owner,
                    repository=repository,
                    path=file.path,
                    language=file.language,
                    content=stripped_chunk,
                    chunk_index=idx,
                    start_line=start_line,
                    end_line=end_line,
                )
            )

        return chunks

    @classmethod
    def chunk_repository_files(
        cls,
        owner: str,
        repository: str,
        files: List[RepositoryFile],
    ) -> List[CodeChunk]:
        """
        Chunk all files in a repository and return aggregate list of chunks.

        Args:
            owner: Repository owner
            repository: Repository name
            files: List of RepositoryFile models

        Returns:
            Flat list of CodeChunk instances
        """
        all_chunks: List[CodeChunk] = []

        for file in files:
            file_chunks = cls.chunk_file(owner, repository, file)
            all_chunks.extend(file_chunks)

        logger.info(
            "Chunked %d files for %s/%s into %d code chunks",
            len(files),
            owner,
            repository,
            len(all_chunks),
        )
        return all_chunks


"""Deterministic intent routing for repository Q&A retrieval."""
import re


class QuestionIntentService:
    BROAD_PATTERNS = (
        r"\bwhat\s+(?:is|does)\s+(?:this|the)\s+(?:project|repo|repository)\b",
        r"\bmain\s+features?\b", r"\bproject\s+overview\b", r"\b(repo|repository)\s+overview\b",
        r"\bpurpose\s+of\s+(?:this|the)\s+(?:project|repo|repository)\b",
        r"\bdescribe\s+(?:this|the)\s+(?:project|repo|repository)\b",
        r"\bsummar(?:y|ize)\s+(?:this|the)\s+(?:project|repo|repository)\b",
    )
    TECHNOLOGY_PATTERNS = (
        r"\btechnolog(?:y|ies)\b", r"\btech\s+stack\b", r"\bstack\b",
        r"\blanguages?\b", r"\bframeworks?\b", r"\bdependencies\b",
        r"\blibraries\b", r"\bpackages\b", r"\bwhat\s+does\s+it\s+use\b",
    )
    ARCHITECTURE_PATTERNS = (
        r"\barchitect(?:ure|ural)\b", r"\bhow\s+is\s+(?:the\s+)?(?:project|codebase|repository)\s+organ[ie]zed\b",
        r"\bapplication\s+structure\b", r"\bentry\s+points?\b", r"\bmajor\s+modules\b",
    )
    FILE_PATTERN = re.compile(
        r"(?:^|[\s`'\"])[\w./-]+\.(?:py|pyi|js|jsx|ts|tsx|java|cs|cpp|h|hpp|json|ya?ml|toml|md|rst|txt|xml|cfg|ini)(?:$|[\s`'\"#:])",
        re.IGNORECASE,
    )

    @classmethod
    def detect(cls, question: str) -> str:
        text = question.strip().lower()
        if any(re.search(pattern, text) for pattern in cls.BROAD_PATTERNS):
            return "broad"
        if any(re.search(pattern, text) for pattern in cls.TECHNOLOGY_PATTERNS):
            return "technology"
        if any(re.search(pattern, text) for pattern in cls.ARCHITECTURE_PATTERNS):
            return "architecture"
        if cls.FILE_PATTERN.search(question) or re.search(r"\b(?:in|inside|from)\s+(?:the\s+)?file\b", text):
            return "file_specific"
        return "implementation"

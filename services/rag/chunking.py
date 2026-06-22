from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


DEFAULT_SOURCE_PATTERNS = ["README.md", "HANDOFF.md", "docs/*.md"]
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
MIN_CHUNK_CHARS = 120


@dataclass(frozen=True)
class Chunk:
    id: str
    source_path: str
    title: str
    ordinal: int
    text: str


def discover_markdown_files(root: Path, patterns: Sequence[str] | None = None) -> List[Path]:
    selected: List[Path] = []
    seen = set()
    for pattern in patterns or DEFAULT_SOURCE_PATTERNS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file() or path.suffix.lower() != ".md":
                continue
            relative = path.relative_to(root).as_posix()
            if relative in seen:
                continue
            if _is_unsafe_source(relative):
                continue
            selected.append(path)
            seen.add(relative)
    return selected


def load_markdown_chunks(
    root: Path,
    paths: Iterable[Path],
    max_chars: int = 1200,
    overlap_chars: int = 160,
) -> List[Chunk]:
    chunks: List[Chunk] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        chunks.extend(split_markdown(relative, text, max_chars=max_chars, overlap_chars=overlap_chars))
    return chunks


def split_markdown(
    source_path: str,
    text: str,
    max_chars: int = 1200,
    overlap_chars: int = 160,
) -> List[Chunk]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    sections = _split_sections(normalized)
    chunks: List[Chunk] = []
    ordinal = 0
    for title, section_text in sections:
        section_text = section_text.strip()
        if not section_text:
            continue
        start = 0
        while start < len(section_text):
            end = min(len(section_text), start + max_chars)
            if end < len(section_text):
                boundary = max(
                    section_text.rfind("\n\n", start, end),
                    section_text.rfind("\n", start, end),
                    section_text.rfind("。", start, end),
                )
                if boundary > start + max_chars // 2:
                    end = boundary + 1
            chunk_text = section_text[start:end].strip()
            if chunk_text and _is_meaningful_chunk(chunk_text):
                chunks.append(
                    Chunk(
                        id=f"{source_path}#{ordinal}",
                        source_path=source_path,
                        title=title or source_path,
                        ordinal=ordinal,
                        text=chunk_text,
                    )
                )
                ordinal += 1
            if end >= len(section_text):
                break
            start = max(0, end - overlap_chars)
    return chunks


def _is_meaningful_chunk(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if len(compact) >= MIN_CHUNK_CHARS:
        return True
    return text.count("\n") >= 4 and ("|" in text or "```" in text)


def _split_sections(text: str) -> List[tuple[str, str]]:
    sections: List[tuple[str, List[str]]] = []
    current_title = ""
    current_lines: List[str] = []
    for line in text.split("\n"):
        heading = HEADING_RE.match(line)
        if heading and current_lines:
            sections.append((current_title, current_lines))
            current_lines = []
        if heading:
            current_title = heading.group(2).strip()
        current_lines.append(line)
    if current_lines:
        sections.append((current_title, current_lines))
    return [(title, "\n".join(lines)) for title, lines in sections]


def _is_unsafe_source(relative_path: str) -> bool:
    parts = set(relative_path.split("/"))
    return (
        relative_path.startswith(".")
        or ".git" in parts
        or "__pycache__" in parts
        or relative_path.startswith("benchmarks/results/")
        or ".env" in parts
    )

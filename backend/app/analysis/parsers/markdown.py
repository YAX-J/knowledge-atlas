"""Line-preserving structural Markdown parser; no rendering or model calls."""

import hashlib
import re
import uuid
from dataclasses import dataclass


ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?)|[ \t]*)$")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
LIST = re.compile(r"^ {0,3}(?:[-+*]|\d{1,9}[.)])[ \t]+")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
THEMATIC = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")


@dataclass(frozen=True)
class MarkdownChunk:
    id: uuid.UUID
    position: int
    kind: str
    heading_path: list[str]
    start_line: int
    end_line: int
    content: str
    content_sha256: str


def parse_markdown(content: str, *, source_id: uuid.UUID) -> list[MarkdownChunk]:
    # Keep line endings so content is an exact slice of the stored source.
    lines = content.splitlines(keepends=True)
    chunks: list[MarkdownChunk] = []
    headings: list[tuple[int, str]] = []

    def line_at(index: int) -> str:
        line = lines[index].rstrip("\r\n")
        return line.removeprefix("\ufeff") if index == 0 else line

    def heading_at(index: int) -> tuple[int, str, int] | None:
        line = line_at(index)
        match = ATX.match(line)
        if match:
            title = re.sub(r"[ \t]+#+[ \t]*$", "", match[2] or "").strip()
            return len(match[1]), title, 1
        if (
            line.strip()
            and not LIST.match(line)
            and not FENCE.match(line)
            and not THEMATIC.match(line)
            and not line.startswith(("    ", "\t", ">"))
            and index + 1 < len(lines)
        ):
            underline = SETEXT.match(line_at(index + 1))
            if underline:
                return (1 if underline[1][0] == "=" else 2), line.strip(), 2
        return None

    def emit(start: int, end: int, kind: str) -> None:
        text = "".join(lines[start:end])
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        chunks.append(MarkdownChunk(
            id=uuid.uuid5(source_id, f"{start + 1}:{end}:{kind}:{digest}"),
            position=len(chunks),
            kind=kind,
            heading_path=[title for _, title in headings],
            start_line=start + 1,
            end_line=end,
            content=text,
            content_sha256=digest,
        ))

    index = 0
    while index < len(lines):
        line = line_at(index)
        if not line.strip():
            index += 1
            continue
        start = index
        fence = FENCE.match(line)
        if fence:
            marker = fence[1]
            closing = re.compile(
                r"^ {0,3}" + re.escape(marker[0])
                + r"{" + str(len(marker)) + r",}[ \t]*$"
            )
            index += 1
            while index < len(lines):
                closed = closing.match(line_at(index))
                index += 1
                if closed:
                    break
            emit(start, index, "code")
            continue
        heading = heading_at(index)
        if heading:
            level, title, length = heading
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, title))
            index += length
            emit(start, index, "heading")
            continue
        if THEMATIC.match(line):
            index += 1
            emit(start, index, "paragraph")
            continue
        is_list = bool(LIST.match(line))
        index += 1
        while index < len(lines):
            next_line = line_at(index)
            if not next_line.strip():
                # Preserve blank lines inside loose/nested lists.
                lookahead = index + 1
                while lookahead < len(lines) and not line_at(lookahead).strip():
                    lookahead += 1
                if is_list and lookahead < len(lines):
                    following = line_at(lookahead)
                    if LIST.match(following) or following.startswith(("  ", "\t")):
                        index = lookahead
                        continue
                break
            if is_list and next_line.startswith(("    ", "\t")):
                index += 1
                continue
            if heading_at(index) or FENCE.match(next_line) or THEMATIC.match(next_line):
                break
            if not is_list and LIST.match(next_line):
                break
            index += 1
        emit(start, index, "list" if is_list else "paragraph")
    return chunks

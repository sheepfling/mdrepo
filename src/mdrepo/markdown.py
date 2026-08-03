"""Markdown parsing with source-aware link destination extraction."""

from __future__ import annotations

import re
from bisect import bisect_right
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypeGuard, cast

from markdown_it import MarkdownIt
from markdown_it.rules_inline.state_inline import StateInline
from markdown_it.token import Token

from mdrepo.models import (
    Document,
    LinkKind,
    LinkOccurrence,
    LinkSourceKind,
    TextSpan,
)

_AUTOLINK_SCHEME: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]{1,31}:")

@dataclass(frozen=True, slots=True)
class _ScannedDestination:
    raw_target: str
    normalized_target: str
    kind: LinkKind
    source_kind: LinkSourceKind
    angle_wrapped: bool

class _SourceMap:
    """Map absolute character offsets to one-based source locations."""

    def __init__(self, text: str) -> None:
        starts = [0]
        for index, character in enumerate(text):
            if character == "\n":
                starts.append(index + 1)
        self.text = text
        self.line_starts = tuple(starts)

    def line_range(self, start_line: int, end_line: int) -> tuple[int, int]:
        """Return a half-open absolute range for zero-based Markdown token lines."""

        safe_start = max(0, min(start_line, len(self.line_starts) - 1))
        start = self.line_starts[safe_start]
        if end_line < len(self.line_starts):
            end = self.line_starts[max(end_line, safe_start)]
        else:
            end = len(self.text)
        return start, end

    def position(self, offset: int) -> tuple[int, int]:
        """Convert an absolute offset to one-based line and column."""

        safe_offset = max(0, min(offset, len(self.text)))
        line_index = max(0, bisect_right(self.line_starts, safe_offset) - 1)
        column = safe_offset - self.line_starts[line_index] + 1
        return line_index + 1, column

    def span(self, start: int, end: int) -> TextSpan:
        line, column = self.position(start)
        return TextSpan(start=start, end=end, line=line, column=column)

class MarkdownParser:
    """CommonMark parser that records direct and reference link destinations."""

    def __init__(self) -> None:
        parser = MarkdownIt(
            "commonmark",
            options_update={
                "html": True,
                "linkify": False,
                "store_labels": True,
                "typographer": False,
            },
        )
        with suppress(KeyError):
            parser.enable("table")
        self._parser = parser

    def parse(self, *, path: Path, root: Path, text: str) -> Document:
        """Parse one UTF-8-decoded Markdown document."""

        resolved_path = path.resolve()
        relative_path = resolved_path.relative_to(root)
        environment: dict[str, Any] = {}
        tokens = tuple(self._parser.parse(text, environment))
        source_map = _SourceMap(text)

        links: list[LinkOccurrence] = []
        for token in tokens:
            if token.type != "inline" or token.children is None:
                continue
            links.extend(
                self._extract_inline_links(
                    token=token,
                    source_map=source_map,
                )
            )

        definitions = self._extract_reference_definitions(
            environment=environment,
            source_map=source_map,
        )
        return Document(
            path=resolved_path,
            relative_path=relative_path,
            text=text,
            links=tuple(links),
            reference_definitions=definitions,
        )

    def _extract_inline_links(
            self,
            *,
            token: Token,
            source_map: _SourceMap,
    ) -> tuple[LinkOccurrence, ...]:
        line_map = token.map or [0, 1]
        start_line = int(line_map[0])
        end_line = int(line_map[1])
        region_start, region_end = source_map.line_range(start_line, end_line)
        scanned = _scan_inline_destinations(token.content, self._parser)
        scanned_index = 0
        search_offset = region_start
        occurrences: list[LinkOccurrence] = []

        for child in token.children or []:
            semantic = _semantic_link(child)
            if semantic is None:
                continue
            target, kind, source_kind, reference_label = semantic
            if source_kind is LinkSourceKind.REFERENCE_USE:
                line, column = source_map.position(region_start)
                occurrences.append(
                    LinkOccurrence(
                        target=target,
                        raw_target=target,
                        kind=kind,
                        source_kind=source_kind,
                        line=line,
                        column=column,
                        span=None,
                        reference_label=reference_label,
                    )
                )
                continue

            matched: _ScannedDestination | None = None
            while scanned_index < len(scanned):
                candidate = scanned[scanned_index]
                scanned_index += 1
                if candidate.kind is kind and candidate.normalized_target == target:
                    matched = candidate
                    break

            if matched is None:
                line, column = source_map.position(region_start)
                occurrences.append(
                    LinkOccurrence(
                        target=target,
                        raw_target=target,
                        kind=kind,
                        source_kind=source_kind,
                        line=line,
                        column=column,
                        span=None,
                        reference_label=None,
                    )
                )
                continue

            span = _locate_raw_destination(
                source_map=source_map,
                raw_target=matched.raw_target,
                start=search_offset,
                region_start=region_start,
                region_end=region_end,
                angle_wrapped=matched.angle_wrapped,
            )
            if span is not None:
                search_offset = span.end
                line = span.line
                column = span.column
            else:
                line, column = source_map.position(region_start)
            occurrences.append(
                LinkOccurrence(
                    target=target,
                    raw_target=matched.raw_target,
                    kind=kind,
                    source_kind=matched.source_kind,
                    line=line,
                    column=column,
                    span=span,
                    reference_label=None,
                )
            )
        return tuple(occurrences)

    def _extract_reference_definitions(
            self,
            *,
            environment: dict[str, Any],
            source_map: _SourceMap,
    ) -> tuple[LinkOccurrence, ...]:
        references = environment.get("references", {})
        if not isinstance(references, dict):
            return ()

        occurrences: list[LinkOccurrence] = []
        typed_references = cast(dict[str, Any], references)
        for label, raw_data in typed_references.items():
            if not isinstance(raw_data, dict):
                continue
            data = cast(dict[str, Any], raw_data)
            target = data.get("href")
            line_map = data.get("map")
            if not isinstance(target, str) or not _is_line_map(line_map):
                continue

            start_line, end_line = int(line_map[0]), int(line_map[1])
            region_start, region_end = source_map.line_range(start_line, end_line)
            span, raw_target = _locate_reference_destination(
                parser=self._parser,
                source_map=source_map,
                target=target,
                region_start=region_start,
                region_end=region_end,
            )
            if span is None:
                line, column = source_map.position(region_start)
                raw_target = target
            else:
                line = span.line
                column = span.column

            occurrences.append(
                LinkOccurrence(
                    target=target,
                    raw_target=raw_target,
                    kind=LinkKind.REFERENCE_DEFINITION,
                    source_kind=LinkSourceKind.REFERENCE_DEFINITION,
                    line=line,
                    column=column,
                    span=span,
                    reference_label=str(label),
                )
            )
        return tuple(
            sorted(
                occurrences,
                key=lambda occurrence: (occurrence.line, occurrence.column or 0),
            )
        )

def _semantic_link(
        token: Token,
) -> tuple[str, LinkKind, LinkSourceKind, str | None] | None:
    if token.type == "link_open":
        target = token.attrGet("href")
        if not isinstance(target, str):
            return None
        label = token.meta.get("label")
        if isinstance(label, str):
            return target, LinkKind.LINK, LinkSourceKind.REFERENCE_USE, label
        source_kind = (
            LinkSourceKind.AUTOLINK if token.markup == "autolink" else LinkSourceKind.DIRECT
        )
        return target, LinkKind.LINK, source_kind, None

    if token.type == "image":
        target = token.attrGet("src")
        if not isinstance(target, str):
            return None
        label = token.meta.get("label")
        if isinstance(label, str):
            return target, LinkKind.IMAGE, LinkSourceKind.REFERENCE_USE, label
        return target, LinkKind.IMAGE, LinkSourceKind.DIRECT, None
    return None

def _scan_inline_destinations(
        source: str,
        parser: MarkdownIt,
) -> tuple[_ScannedDestination, ...]:
    candidates: list[_ScannedDestination] = []
    position = 0
    while position < len(source):
        character = source[position]
        if character == "\\":
            position += 2
            continue
        if character == "`":
            position = _skip_code_span(source, position)
            continue

        if source.startswith("![", position):
            parsed = _parse_direct_destination(
                source=source,
                parser=parser,
                bracket_position=position + 1,
                kind=LinkKind.IMAGE,
            )
            if parsed is not None:
                candidate, end = parsed
                candidates.append(candidate)
                position = end
                continue
        elif character == "[":
            parsed = _parse_direct_destination(
                source=source,
                parser=parser,
                bracket_position=position,
                kind=LinkKind.LINK,
            )
            if parsed is not None:
                candidate, end = parsed
                candidates.append(candidate)
                position = end
                continue
        elif character == "<":
            close = source.find(">", position + 1)
            if close >= 0 and "\n" not in source[position + 1: close]:
                raw_target = source[position + 1: close]
                if _AUTOLINK_SCHEME.match(raw_target):
                    candidates.append(
                        _ScannedDestination(
                            raw_target=raw_target,
                            normalized_target=parser.normalizeLink(raw_target),
                            kind=LinkKind.LINK,
                            source_kind=LinkSourceKind.AUTOLINK,
                            angle_wrapped=True,
                        )
                    )
                    position = close + 1
                    continue
        position += 1
    return tuple(candidates)

def _parse_direct_destination(
        *,
        source: str,
        parser: MarkdownIt,
        bracket_position: int,
        kind: LinkKind,
) -> tuple[_ScannedDestination, int] | None:
    state = StateInline(source, parser, {}, [])
    disable_nested = kind is LinkKind.LINK
    label_end = parser.helpers.parseLinkLabel(state, bracket_position, disable_nested)
    if label_end < 0:
        return None

    position = label_end + 1
    if position >= len(source) or source[position] != "(":
        return None
    position += 1
    while position < len(source) and (source[position].isspace() or source[position] == "\n"):
        position += 1
    if position >= len(source):
        return None

    destination_start = position
    result = parser.helpers.parseLinkDestination(source, position, len(source))
    if result.ok:
        normalized = parser.normalizeLink(result.str)
        position = result.pos
        if source[destination_start] == "<":
            raw_start = destination_start + 1
            raw_end = max(raw_start, result.pos - 1)
            angle_wrapped = True
        else:
            raw_start = destination_start
            raw_end = result.pos
            angle_wrapped = False
        raw_target = source[raw_start:raw_end]
    elif source[position] == ")":
        normalized = ""
        raw_target = ""
        raw_start = position
        raw_end = position
        angle_wrapped = False
    else:
        return None

    before_title = position
    while position < len(source) and (source[position].isspace() or source[position] == "\n"):
        position += 1
    title = parser.helpers.parseLinkTitle(source, position, len(source))
    if position < len(source) and before_title != position and title.ok:
        position = title.pos
        while position < len(source) and (source[position].isspace() or source[position] == "\n"):
            position += 1
    if position >= len(source) or source[position] != ")":
        return None

    _ = raw_start, raw_end
    return (
        _ScannedDestination(
            raw_target=raw_target,
            normalized_target=normalized,
            kind=kind,
            source_kind=LinkSourceKind.DIRECT,
            angle_wrapped=angle_wrapped,
        ),
        position + 1,
    )

def _skip_code_span(source: str, start: int) -> int:
    run_length = 1
    while start + run_length < len(source) and source[start + run_length] == "`":
        run_length += 1
    marker = "`" * run_length
    close = source.find(marker, start + run_length)
    return close + run_length if close >= 0 else start + run_length

def _locate_raw_destination(
        *,
        source_map: _SourceMap,
        raw_target: str,
        start: int,
        region_start: int,
        region_end: int,
        angle_wrapped: bool,
) -> TextSpan | None:
    if not raw_target:
        return None

    safe_start = max(start, region_start)
    candidates: list[int] = []
    position = source_map.text.find(raw_target, safe_start, region_end)
    while position >= 0:
        candidates.append(position)
        position = source_map.text.find(raw_target, position + 1, region_end)
    if not candidates:
        return None

    contextual = [
        position
        for position in candidates
        if _has_destination_context(
            text=source_map.text,
            position=position,
            raw_target=raw_target,
            angle_wrapped=angle_wrapped,
        )
    ]
    chosen: int | None
    if contextual:
        chosen = contextual[0]
    elif len(candidates) == 1:
        chosen = candidates[0]
    else:
        chosen = None
    if chosen is None:
        return None
    return source_map.span(chosen, chosen + len(raw_target))

def _has_destination_context(
        *,
        text: str,
        position: int,
        raw_target: str,
        angle_wrapped: bool,
) -> bool:
    if angle_wrapped:
        before = text[position - 1] if position > 0 else ""
        after_index = position + len(raw_target)
        after = text[after_index] if after_index < len(text) else ""
        return before == "<" and after == ">"

    cursor = position - 1
    while cursor >= 0 and text[cursor].isspace():
        cursor -= 1
    return cursor >= 0 and text[cursor] == "("

def _locate_reference_destination(
        *,
        parser: MarkdownIt,
        source_map: _SourceMap,
        target: str,
        region_start: int,
        region_end: int,
) -> tuple[TextSpan | None, str]:
    region = source_map.text[region_start:region_end]
    delimiter = region.find("]:")
    if delimiter < 0:
        return None, target

    position = delimiter + 2
    while position < len(region) and (region[position].isspace() or region[position] == "\n"):
        position += 1
    result = parser.helpers.parseLinkDestination(region, position, len(region))
    if not result.ok:
        return None, target

    if region[position] == "<":
        raw_start = position + 1
        raw_end = max(raw_start, result.pos - 1)
    else:
        raw_start = position
        raw_end = result.pos
    raw_target = region[raw_start:raw_end]
    if parser.normalizeLink(result.str) != target:
        return None, raw_target
    absolute_start = region_start + raw_start
    return source_map.span(absolute_start, region_start + raw_end), raw_target

def _is_line_map(value: object) -> TypeGuard[list[int]]:
    if not isinstance(value, list):
        return False
    typed_value = cast(list[object], value)
    return len(typed_value) == 2 and all(isinstance(item, int) for item in typed_value)

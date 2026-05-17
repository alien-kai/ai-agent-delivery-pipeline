"""Minimal YAML reader shared by sibling scripts in this directory.

Implements the limited YAML subset that this repo's task specs and Codex
review outputs actually use: top-level mappings, lists of scalars, lists of
mappings, and block scalars (`|`, `>`, `|-`, `>-`, `|+`, `>+`). No flow
style, anchors, tags, or merge keys. Folded style `>` is treated as `|`
(unfolded); we do not need fidelity for round-trip writes.
"""

from __future__ import annotations

import re
from typing import Any

_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:(.*)$")
_BLOCK_STYLES = {"|", ">", "|-", ">-", "|+", ">+"}


def parse_yaml(text: str) -> Any:
    lines = text.split("\n")
    if lines and lines[0].startswith("﻿"):
        lines[0] = lines[0][1:]
    pos = [0]
    result = _read_map(lines, pos, 0)
    # The top-level document must be fully consumed. `_read_map` returns
    # when it encounters a list marker (`- `) at its own indent so the
    # caller can resume; at top level there is no caller, so a trailing
    # `- ...` block — or any other unconsumed nonblank line — is schema
    # drift that would otherwise hide content from the gate.
    while pos[0] < len(lines):
        ln = lines[pos[0]]
        if _blank_or_comment(ln):
            pos[0] += 1
            continue
        raise ValueError(
            f"unexpected trailing content at line {pos[0] + 1}: {ln.strip()!r}"
        )
    return result


def _read_map(lines, pos, base_indent):
    out: dict[str, Any] = {}
    while pos[0] < len(lines):
        i = pos[0]
        line = lines[i]
        if _blank_or_comment(line):
            pos[0] = i + 1
            continue
        cur = _indent(line)
        if cur < base_indent:
            return out
        if cur > base_indent:
            # Anything indented deeper than our base should already have
            # been consumed by a nested reader. Reaching it here means
            # the input is malformed — fail closed instead of skipping.
            raise ValueError(
                f"unexpected indentation at line {i + 1}: {line.strip()!r}"
            )
        stripped = line[base_indent:]
        if stripped.startswith("- ") or stripped == "-":
            return out
        m = _KEY_RE.match(stripped)
        if not m:
            # Non-blank, non-comment line at the expected indent that is
            # neither a mapping entry nor a list start — malformed.
            raise ValueError(
                f"unrecognized YAML syntax at line {i + 1}: {line.strip()!r}"
            )
        key = m.group(1)
        rest = _strip_inline_comment(m.group(2)).strip()
        pos[0] = i + 1
        if key in out:
            # Duplicate keys in a mapping are schema drift. Reject loudly
            # so downstream `try / except` paths can fail closed instead
            # of inheriting the parser's last-value-wins semantics.
            raise ValueError(f"duplicate key {key!r} in mapping")
        if rest == "":
            out[key] = _read_nested(lines, pos, base_indent + 1)
        elif rest in _BLOCK_STYLES:
            out[key] = _read_block_scalar(lines, pos, base_indent + 1, rest)
        else:
            out[key] = _scalar(rest)
            _consume_scalar_continuation(lines, pos, base_indent)
    return out


def _consume_scalar_continuation(lines, pos, base_indent):
    """Advance past plain-scalar continuation lines after a scalar value.

    YAML lets a plain (unquoted) scalar span multiple physical lines as
    long as each continuation line is indented deeper than the container.
    We don't preserve the wrapped text — only advance ``pos`` past it so
    the surrounding reader's next iteration starts at the expected indent.

    Important: a deeper-indented line that *looks structured* (a list
    item ``- ...`` or a mapping entry ``key: value``) is rejected as
    schema drift. Allowing it would let a malformed spec smuggle hidden
    findings or mapping entries past the gate after an inline scalar
    value such as ``findings: []``.
    """
    while pos[0] < len(lines):
        ln = lines[pos[0]]
        if _blank_or_comment(ln):
            pos[0] += 1
            continue
        ind = _indent(ln)
        if ind <= base_indent:
            break
        stripped = ln[ind:]
        if stripped.startswith("- ") or stripped == "-":
            raise ValueError(
                f"unexpected list item at line {pos[0] + 1}: {ln.strip()!r}"
            )
        if _KEY_RE.match(stripped):
            raise ValueError(
                f"unexpected mapping entry at line {pos[0] + 1}: {ln.strip()!r}"
            )
        pos[0] += 1


def _read_nested(lines, pos, min_indent):
    j = pos[0]
    while j < len(lines) and _blank_or_comment(lines[j]):
        j += 1
    if j == len(lines):
        return None
    ind = _indent(lines[j])
    if ind < min_indent:
        return None
    stripped = lines[j][ind:]
    if stripped.startswith("- ") or stripped == "-":
        return _read_list(lines, pos, ind)
    return _read_map(lines, pos, ind)


def _read_list(lines, pos, indent):
    out: list[Any] = []
    while pos[0] < len(lines):
        i = pos[0]
        line = lines[i]
        if _blank_or_comment(line):
            pos[0] = i + 1
            continue
        cur = _indent(line)
        if cur < indent:
            return out
        if cur > indent:
            # Same rule as _read_map: a deeper line that wasn't already
            # consumed by a nested reader is malformed.
            raise ValueError(
                f"unexpected indentation in list at line {i + 1}: "
                f"{line.strip()!r}"
            )
        stripped = line[indent:]
        if not (stripped.startswith("- ") or stripped == "-"):
            return out
        if stripped == "-":
            pos[0] = i + 1
            out.append(_read_nested(lines, pos, indent + 2))
            continue
        rest = _strip_inline_comment(stripped[2:]).rstrip()
        km = _KEY_RE.match(rest) if not rest.startswith(("'", '"')) else None
        if km:
            key = km.group(1)
            kvrest = _strip_inline_comment(km.group(2)).strip()
            pos[0] = i + 1
            item: dict[str, Any] = {}
            if kvrest == "":
                item[key] = _read_nested(lines, pos, indent + 4)
            elif kvrest in _BLOCK_STYLES:
                item[key] = _read_block_scalar(lines, pos, indent + 4, kvrest)
            else:
                item[key] = _scalar(kvrest)
            extra = _read_map(lines, pos, indent + 2)
            for k, v in extra.items():
                if k in item:
                    # Inline `- key: value` collides with a later `key:`
                    # under the same list item — reject for the same
                    # fail-closed reason as in `_read_map`.
                    raise ValueError(f"duplicate key {k!r} in mapping")
                item[k] = v
            out.append(item)
        else:
            out.append(_scalar(rest))
            pos[0] = i + 1
            _consume_scalar_continuation(lines, pos, indent)
    return out


def _read_block_scalar(lines, pos, min_indent, style):
    body: list[str] = []
    block_indent = None
    while pos[0] < len(lines):
        i = pos[0]
        line = lines[i]
        if line.strip() == "":
            body.append("")
            pos[0] = i + 1
            continue
        ind = _indent(line)
        if block_indent is None:
            if ind < min_indent:
                break
            block_indent = ind
        if ind < block_indent:
            break
        body.append(line[block_indent:])
        pos[0] = i + 1
    if "+" not in style:
        while body and body[-1] == "":
            body.pop()
    text = "\n".join(body)
    if "-" not in style and text:
        text += "\n"
    return text


def _indent(line: str) -> int:
    n = 0
    for c in line:
        if c == " " or c == "\t":
            n += 1
        else:
            break
    return n


def _blank_or_comment(line: str) -> bool:
    s = line.strip()
    return s == "" or s.startswith("#")


def _strip_inline_comment(s: str) -> str:
    in_s = False
    in_d = False
    for i, c in enumerate(s):
        if c == "'" and not in_d:
            in_s = not in_s
        elif c == '"' and not in_s:
            in_d = not in_d
        elif c == "#" and not in_s and not in_d:
            if i == 0 or s[i - 1] in (" ", "\t"):
                return s[:i].rstrip()
    return s


def _scalar(s: str):
    s = s.strip()
    if s == "":
        return None
    # Flow-style empty containers. We don't support general flow style, but
    # `[]` and `{}` are commonly used even in otherwise block-style YAML and
    # must round-trip as real empty containers (not the string "[]").
    if s == "[]":
        return []
    if s == "{}":
        return {}
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    if s == "true":
        return True
    if s == "false":
        return False
    if s in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s

"""Parse Chrome 'Copy as cURL (cmd)' into raw HTTP request headers."""

from __future__ import annotations

import re
import shlex


def is_curl_input(text: str) -> bool:
    """Return True if pasted text looks like a cURL command."""
    first = text.strip().splitlines()[0].strip().lower()
    return first.startswith("curl ")


def _normalize_windows_curl(text: str) -> str:
    """Convert Chrome 'Copy as cURL (cmd)' escaping to normal quotes."""
    # Line continuations: caret at end of line
    text = re.sub(r"\^\s*\r?\n\s*", " ", text)
    text = text.replace("^&", "&")
    text = text.replace('^"', '"')
    text = text.replace("^^", "^")
    # Trailing caret before whitespace (leftover line-join marker)
    text = re.sub(r"\^\s+", " ", text)
    return text


def _extract_quoted_args(text: str, flag: str) -> list[str]:
    """Extract all values for -H / -b flags, including Windows ^\" quoting."""
    values: list[str] = []
    pattern = re.compile(
        rf"(?:{flag})\s+(?:\^(?P<qc1>\"|')|(?P<qc2>\"|'))(?P<val>.*?)(?:\^(?P=qc1)|(?P=qc2))",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        values.append(match.group("val"))

    if values:
        return values

    # Fallback: standard quoting
    pattern2 = re.compile(rf"(?:{flag})\s+(?P<q>['\"])(?P<val>.*?)(?P=q)", re.IGNORECASE | re.DOTALL)
    return [m.group("val") for m in pattern2.finditer(text)]


def headers_from_curl(curl_text: str) -> str:
    """Convert Chrome 'Copy as cURL' output to raw request headers text."""
    normalized = _normalize_windows_curl(curl_text.strip())
    lines = normalized.splitlines()
    joined = " ".join(line.strip() for line in lines if line.strip())

    headers: list[str] = []

    for header in _extract_quoted_args(joined, r"-H|--header"):
        headers.append(header)

    for cookie in _extract_quoted_args(joined, r"-b|--cookie"):
        headers.append(f"cookie: {cookie}")

    if not headers:
        try:
            tokens = shlex.split(joined, posix=False)
        except ValueError as exc:
            raise ValueError("Could not parse cURL command.") from exc

        i = 0
        while i < len(tokens):
            token = tokens[i].lower()
            if token in ("-h", "--header") and i + 1 < len(tokens):
                headers.append(tokens[i + 1])
                i += 2
                continue
            if token in ("-b", "--cookie") and i + 1 < len(tokens):
                headers.append(f"cookie: {tokens[i + 1]}")
                i += 2
                continue
            i += 1

    if not headers:
        raise ValueError("No headers found in cURL text. Use 'Copy as cURL (cmd)' in Chrome.")

    return "\n".join(headers)

"""Strict UTF-8 and mojibake checks shared by ingestion and acceptance tests."""
from __future__ import annotations

import re


MOJIBAKE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("replacement_character", re.compile("\ufffd")),
    ("gbk_replacement", re.compile("锟斤拷|烫烫烫|屯屯屯")),
    ("chinese_utf8_as_gbk", re.compile("绠楁硶|鏁版嵁|鍖归厤|璇勬祴|閿欒|鐨勫|瀹炴柦|浼樺寲")),
    ("utf8_as_latin1", re.compile(r"(?:Ã[\x80-\u00bf]|Â[\x80-\u00bf]|â[\x80-\u00bf]|ã[\x80-\u00bf]|æ[\x80-\u00bf])")),
)


def mojibake_matches(text: str, limit: int = 20) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for name, pattern in MOJIBAKE_PATTERNS:
        for match in pattern.finditer(text):
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 50)
            matches.append({"pattern": name, "offset": match.start(), "sample": text[start:end]})
            if len(matches) >= limit:
                return matches
    return matches

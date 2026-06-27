"""Text KeyValues (VDF) reader/writer — for Steam's ``config.vdf``.

Unlike ``shortcuts.vdf`` (binary, see :mod:`deckport.vdf`), ``config.vdf`` is the
text KeyValues format::

    "InstallConfigStore"
    {
        "Software"
        {
            "Valve" { ... }
        }
    }

We parse it to nested dicts and write it back tab-indented. Steam normalizes
this file on exit, so we aim for *valid, structure-preserving* output rather than
byte-identical — but we still back the file up before writing. Pure stdlib.
"""
from __future__ import annotations

__all__ = ["loads", "dumps", "load_file", "save_file"]


def _tokenize(text: str):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":  # // comment to EOL
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c in "{}":
            yield c
            i += 1
            continue
        if c == '"':
            i += 1
            buf = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    nxt = text[i + 1]
                    buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
                    i += 2
                else:
                    buf.append(text[i])
                    i += 1
            i += 1  # closing quote
            yield ('"', "".join(buf))
            continue
        # bare (unquoted) token — rare in config.vdf, supported for robustness
        j = i
        while j < n and text[j] not in ' \t\r\n{}"':
            j += 1
        yield ('"', text[i:j])
        i = j


def _parse_map(tokens, depth=0) -> dict:
    out: dict = {}
    for tok in tokens:
        if tok == "}":
            return out
        if tok == "{":
            raise ValueError("unexpected '{' (expected a key)")
        key = tok[1]
        nxt = next(tokens)
        if nxt == "{":
            out[key] = _parse_map(tokens, depth + 1)
        elif isinstance(nxt, tuple):
            out[key] = nxt[1]
        else:
            raise ValueError(f"unexpected token after key {key!r}: {nxt!r}")
    if depth != 0:
        raise ValueError("unexpected end of input inside a block")
    return out


def loads(text: str) -> dict:
    """Parse text KeyValues into nested dicts (last value wins on duplicate keys)."""
    return _parse_map(_tokenize(text))


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def dumps(d: dict, indent: int = 0) -> str:
    """Serialize nested dicts to tab-indented Steam-style text KeyValues."""
    pad = "\t" * indent
    lines = []
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f'{pad}"{_esc(str(k))}"')
            lines.append(f"{pad}{{")
            lines.append(dumps(v, indent + 1))
            lines.append(f"{pad}}}")
        else:
            lines.append(f'{pad}"{_esc(str(k))}"\t\t"{_esc(str(v))}"')
    return "\n".join(line for line in lines if line != "")


def load_file(path: str) -> dict:
    import os

    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8", errors="replace") as f:
        return loads(f.read())


def save_file(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(data) + "\n")

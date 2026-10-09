"""Strict JSON + a documented TOON subset: nested objects and scalar tabular arrays.
Unsupported list-object forms fail closed rather than inventing nutrition.
"""

import json
import re
from typing import Any


class FormatError(ValueError):
    pass


def scalar(value):
    v = value.strip()
    if not v:
        raise FormatError("空值必须显式使用 null")
    if v.startswith('"'):
        try:
            return json.loads(v)
        except ValueError as e:
            raise FormatError("非法引号/转义") from e
    if v in ("null", "true", "false") or re.fullmatch(
        r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?", v
    ):
        return json.loads(v)
    if any(x in v for x in ('"', "[", "{", "}")):
        raise FormatError("不支持的 TOON 标量")
    return v


def split_row(line, delimiter):
    parts, buf, quoted, escaped = [], "", False, False
    for ch in line:
        if ch == delimiter and not quoted:
            parts.append(buf.strip())
            buf = ""
            continue
        buf += ch
        if escaped:
            escaped = False
        elif ch == "\\" and quoted:
            escaped = True
        elif ch == '"':
            quoted = not quoted
    if quoted:
        raise FormatError("TOON 引号未闭合")
    return parts + [buf.strip()]


def toon(text: str):
    lines = [x.rstrip() for x in text.splitlines() if x.strip()]

    def block(pos, indent):
        out: dict[str, Any] = {}
        while pos < len(lines):
            line = lines[pos]
            depth = len(line) - len(line.lstrip(" "))
            if depth < indent:
                break
            if depth != indent:
                raise FormatError("TOON 缩进错误")
            s = line.strip()
            tab = re.fullmatch(r"([^\[{:]*?)\[(\d+)([,|\t]?)\]\{(.+)\}:\s*", s)
            if tab:
                key, count, delimiter, fields = tab.groups()
                delim = delimiter or ","
                names = [str(scalar(x)) for x in split_row(fields, delim)]
                if len(names) != len(set(names)):
                    raise FormatError("TOON 重复字段")
                rows = []
                pos += 1
                for _ in range(int(count)):
                    if pos >= len(lines) or not lines[pos].startswith(" " * (indent + 2)):
                        raise FormatError("TOON 行数/缩进与声明不符")
                    values = [scalar(x) for x in split_row(lines[pos].strip(), delim)]
                    if len(values) != len(names):
                        raise FormatError("TOON 列数与声明不符")
                    rows.append(dict(zip(names, values, strict=True)))
                    pos += 1
                if not key:
                    if out or pos != len(lines):
                        raise FormatError("非法根数组")
                    return rows, pos
                if key in out:
                    raise FormatError("TOON 重复键")
                out[key] = rows
                continue
            if ":" not in s or s.startswith("-"):
                raise FormatError("不支持的 TOON 结构；需要显式适配")
            key, value = s.split(":", 1)
            key = str(scalar(key))
            if key in out:
                raise FormatError("TOON 重复键")
            pos += 1
            if value.strip():
                out[key] = scalar(value)
            elif pos < len(lines) and lines[pos].startswith(" " * (indent + 2)):
                out[key], pos = block(pos, indent + 2)
            else:
                out[key] = {}
        return out, pos

    result, consumed = block(0, 0)
    if consumed != len(lines):
        raise FormatError("TOON 未完整消费")
    return result


def decode(text: str):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[-1].strip() != "```":
            raise FormatError("代码块被截断")
        text = "\n".join(lines[1:-1])
    if "## Original Response" in text:
        text = text.split("## Original Response", 1)[1].strip()
    try:
        return json.loads(text)
    except ValueError:
        return toon(text)


def unwrap(result):
    if getattr(result, "isError", False):
        raise FormatError("MCP 工具返回失败（已隐去原始内容）")
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    texts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
    if not texts:
        raise FormatError("MCP 返回空数据")
    return decode("\n".join(texts))


def api_data(result):
    """Official API envelope may carry TOON in its JSON data string."""
    value = unwrap(result)
    if isinstance(value, dict) and ("success" in value or "code" in value):
        if value.get("success") is False or value.get("code", 200) not in (0, 200, "200", "0"):
            raise FormatError("官方业务接口失败；已隐去原始错误内容")
        value = value.get("data")
    if isinstance(value, str):
        value = decode(value)
    if value is None:
        raise FormatError("官方接口返回空 data")
    return value

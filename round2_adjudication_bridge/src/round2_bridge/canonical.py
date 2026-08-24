"""Canonical JSON for commitments.

Sorted keys, compact separators, UTF-8, reject NaN/Infinity.
This is NOT RFC 8785. If the locked project uses JCS, replace this
module and pin the implementation before creating a commitment.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


class CanonicalError(ValueError):
    pass


def _reject_nonfinite(obj: Any) -> Any:
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            raise CanonicalError("NaN/Infinity are not admissible in committed JSON")
        return obj
    if isinstance(obj, dict):
        return {k: _reject_nonfinite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_reject_nonfinite(v) for v in obj]
    return obj


def dumps(obj: Any) -> bytes:
    clean = _reject_nonfinite(obj)
    text = json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_obj(obj: Any) -> str:
    return sha256_bytes(dumps(obj))


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return sha256_bytes(f.read())

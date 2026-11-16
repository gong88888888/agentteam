"""HMAC signing helpers for evidence and verdict ledgers."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha256_hex(obj: Any) -> str:
    if isinstance(obj, bytes):
        data = obj
    elif isinstance(obj, str):
        data = obj.encode("utf-8")
    else:
        data = canonical(obj)
    return hashlib.sha256(data).hexdigest()


def sign_object(obj: dict[str, Any], key: bytes, *, field: str = "signature") -> dict[str, Any]:
    payload = dict(obj)
    payload.pop(field, None)
    payload.pop("record_hash", None)
    signature = hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()
    out = dict(obj)
    out[field] = f"hmac-sha256:{signature}"
    return out


def verify_object(obj: dict[str, Any], key: bytes, *, field: str = "signature") -> bool:
    sig = obj.get(field, "")
    if not isinstance(sig, str) or not sig.startswith("hmac-sha256:"):
        return False
    expected = sign_object(obj, key, field=field)[field]
    return hmac.compare_digest(sig, expected)


def record_hash(record: dict[str, Any]) -> str:
    payload = dict(record)
    payload.pop("record_hash", None)
    return sha256_hex(payload)

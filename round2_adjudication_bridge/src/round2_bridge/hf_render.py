from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"^[0-9a-f]{64}$")
RESOLVE = re.compile(r"/resolve/[0-9a-f]{7,40}/")
SECRETISH = re.compile(r"(hf_|sk-|AKIA|token|secret)", re.I)


def render(req: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    digest = req.get("frozen_spec_digest", "")
    if not HEX64.match(str(digest)):
        errors.append("frozen_spec_digest must be 64 hex")
    url = req.get("spec_url", "")
    if not RESOLVE.search(str(url)):
        errors.append("spec_url must pin /resolve/<commit>/")
    if not HEX64.match(str(req.get("runner_digest", ""))):
        errors.append("runner_digest must be 64 hex")
    flavor = req.get("hardware_flavor")
    timeout = req.get("timeout_seconds")
    if not flavor or not timeout:
        errors.append("hardware_flavor and timeout_seconds required")
    price = float(req.get("hourly_price_usd", 0) or 0)
    hours = float(req.get("timeout_hours", 0) or 0)
    cap = float(req.get("max_cost_usd", 0) or 0)
    est = price * hours
    if cap <= 0 or est > cap:
        errors.append(f"cost-cap violation: estimated {est} > max {cap}")
    secrets = req.get("secret_names", [])
    if not isinstance(secrets, list) or not secrets:
        errors.append("secret_names required; never secret values")
    blob = json.dumps(req)
    if SECRETISH.search(blob) and any(
        k in req for k in ("token", "secret_value", "hf_token", "api_key")
    ):
        errors.append("secret-value leakage")
    if errors:
        return {"ok": False, "errors": errors}
    argv = [
        "hf",
        "jobs",
        "run",
        "--flavor",
        str(flavor),
        "--timeout",
        str(timeout),
        "uv",
        "run",
        "--frozen",
        str(url),
    ]
    return {
        "ok": True,
        "argv": argv,
        "shell_preview": " ".join(argv),
        "estimated_cost_usd": est,
        "note": "dry-run only; this renderer cannot submit",
    }


def load_and_render(path: Path) -> dict[str, Any]:
    return render(json.loads(path.read_text()))

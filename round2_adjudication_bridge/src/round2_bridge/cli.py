from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from round2_bridge.canonical import CanonicalError, dumps, sha256_bytes
from round2_bridge.hf_render import load_and_render
from round2_bridge.models import EXIT, Status
from round2_bridge.validator import validate


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="round2-bridge")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate")
    v.add_argument("bundle")
    v.add_argument("--repo")
    v.add_argument("--output")

    c = sub.add_parser("commit-json")
    c.add_argument("payload")

    h = sub.add_parser("render-hf-job")
    h.add_argument("request")
    h.add_argument("--output")

    args = p.parse_args(argv)
    try:
        if args.cmd == "validate":
            repo = Path(args.repo) if args.repo else None
            report = validate(Path(args.bundle), repo)
            payload = {
                "status": report.status.value,
                "bindings": report.bindings,
                "findings": [f.__dict__ for f in report.findings],
                "ledger": report.ledger,
            }
            text = json.dumps(payload, indent=2)
            if args.output:
                Path(args.output).write_text(text + "\n")
            else:
                print(text)
            return EXIT[report.status]
        if args.cmd == "commit-json":
            obj = json.loads(Path(args.payload).read_text())
            raw = dumps(obj)
            print(json.dumps({"sha256": sha256_bytes(raw), "nbytes": len(raw)}))
            return 0
        if args.cmd == "render-hf-job":
            out = load_and_render(Path(args.request))
            text = json.dumps(out, indent=2)
            if args.output:
                Path(args.output).write_text(text + "\n")
            else:
                print(text)
            return 0 if out.get("ok") else 4
    except CanonicalError as e:
        print(f"CLI: {e}", file=sys.stderr)
        return EXIT[Status.CLI_ERROR]
    except Exception as e:  # noqa: BLE001 — fail closed
        print(f"CLI: {e}", file=sys.stderr)
        return EXIT[Status.CLI_ERROR]
    return EXIT[Status.CLI_ERROR]

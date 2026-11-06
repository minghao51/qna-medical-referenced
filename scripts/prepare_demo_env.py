#!/usr/bin/env python3
"""Create the demo deployment env file with generated secrets.

Run from the repository root:

    uv run python scripts/prepare_demo_env.py --origin https://lab.example.com

Writes `.env.demo` (mode 600) from `.env.demo.example` and fills the session
secret, operator API key and its bcrypt-hashed API key record. It never prints
the generated secrets and refuses to overwrite an existing file without
``--force``. Tunnel and provider credentials remain for the operator to fill in.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / ".env.demo.example"

_KEYS = (
    "DEMO_ORIGIN",
    "APP__API__SESSION_SIGNING_SECRET",
    "OPERATOR_API_KEY",
    "APP__API__API_KEYS_JSON",
)


def _replace_values(template: str, updates: dict[str, str]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for line in template.splitlines():
        stripped = line.lstrip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in updates:
                lines.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        lines.append(line)
    missing = set(updates) - seen
    if missing:
        raise SystemExit(f"Template is missing required keys: {sorted(missing)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origin",
        required=True,
        help="Cloudflare Access hostname, e.g. https://lab.example.com (no trailing slash)",
    )
    parser.add_argument(
        "--target",
        default=".env.demo",
        help="Output path (default: .env.demo in the current directory)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing target")
    args = parser.parse_args()

    origin = args.origin.strip().rstrip("/")
    if not origin.startswith("https://") or len(origin) <= len("https://"):
        parser.error("--origin must be a full https URL")

    target = Path(args.target)
    if target.exists() and not args.force:
        raise SystemExit(f"{target} already exists; pass --force to overwrite")
    if not TEMPLATE.exists():
        raise SystemExit(f"Missing template: {TEMPLATE}")

    # Import lazily so --help and validation do not construct application settings.
    sys.path.insert(0, str(REPO_ROOT))
    from src.app.security import generate_api_key_record

    operator_key = secrets.token_hex(32)
    session_secret = secrets.token_hex(32)
    record = generate_api_key_record(
        "ingress",
        operator_key,
        owner="gateway",
        role="operator",
    )

    content = _replace_values(
        TEMPLATE.read_text(encoding="utf-8"),
        {
            "DEMO_ORIGIN": origin,
            "APP__API__SESSION_SIGNING_SECRET": session_secret,
            "OPERATOR_API_KEY": operator_key,
            "APP__API__API_KEYS_JSON": json.dumps([record], separators=(",", ":")),
        },
    )
    target.write_text(content, encoding="utf-8")
    target.chmod(0o600)
    print(f"Wrote {target} (mode 600).")
    print("Fill CLOUDFLARE_TUNNEL_TOKEN and provider keys; do not commit this file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

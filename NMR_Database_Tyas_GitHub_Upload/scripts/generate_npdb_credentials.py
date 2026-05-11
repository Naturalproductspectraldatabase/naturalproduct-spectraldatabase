#!/usr/bin/env python3
"""Generate NPDB approved-user credentials for Streamlit secrets.

The generated TOML uses password_hash values so plaintext passwords do not
need to live in the deployed secrets file. Keep any CSV/plain report private.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import secrets
import string
import sys
from pathlib import Path


HASH_SCHEME = "pbkdf2_sha256"
ITERATIONS = 390_000
SUFFIX_ALPHABET = string.ascii_letters + string.digits


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_urlsafe(18)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS,
    )
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{HASH_SCHEME}${ITERATIONS}${salt}${encoded}"


def random_suffix(length: int) -> str:
    return "".join(secrets.choice(SUFFIX_ALPHABET) for _ in range(length))


def toml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def user_block(username: str, password_hash_value: str, role: str) -> str:
    return "\n".join(
        [
            "[[NPDB_APPROVED_USERS]]",
            f"username = {toml_quote(username)}",
            f"password_hash = {toml_quote(password_hash_value)}",
            f"role = {toml_quote(role)}",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate NPDB approved-user TOML blocks.")
    parser.add_argument("--viewer-count", type=int, default=0, help="Number of viewer accounts to generate.")
    parser.add_argument("--viewer-prefix", default="npdb_user", help="Viewer username prefix.")
    parser.add_argument("--viewer-password-prefix", default="Onnamide", help="Viewer password prefix.")
    parser.add_argument("--suffix-length", type=int, default=5, help="Random suffix length for viewer passwords.")
    parser.add_argument("--owner-username", default="npdb_tyas", help="Owner username.")
    parser.add_argument("--owner-password", default="", help="Owner password. Omit to skip owner block.")
    parser.add_argument(
        "--plain-report",
        type=Path,
        default=None,
        help="Optional private CSV path containing plaintext credentials for distribution.",
    )
    args = parser.parse_args()

    if args.viewer_count < 0:
        parser.error("--viewer-count must be zero or greater.")
    if args.suffix_length < 4:
        parser.error("--suffix-length should be at least 4 characters.")

    rows: list[dict[str, str]] = []
    blocks: list[str] = []

    if args.owner_password:
        owner_hash = password_hash(args.owner_password)
        blocks.append(user_block(args.owner_username, owner_hash, "owner_editor"))
        rows.append(
            {
                "username": args.owner_username,
                "password": args.owner_password,
                "role": "owner_editor",
            }
        )

    for index in range(1, args.viewer_count + 1):
        username = f"{args.viewer_prefix}{index}"
        password = f"{args.viewer_password_prefix}{random_suffix(args.suffix_length)}"
        blocks.append(user_block(username, password_hash(password), "viewer"))
        rows.append({"username": username, "password": password, "role": "viewer"})

    sys.stdout.write("\n".join(blocks))

    if args.plain_report:
        args.plain_report.parent.mkdir(parents=True, exist_ok=True)
        with args.plain_report.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["username", "password", "role"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nPlain credential report written to: {args.plain_report}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fix MySQL user auth plugin for local dev (caching_sha2_password)."""
from __future__ import annotations

import sys

import pymysql

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

HOSTS = ("localhost", "127.0.0.1", "%")
ROOT_USER = os.getenv("MYSQL_ROOT_USER", "root")
ROOT_PASSWORD = os.getenv("MYSQL_ROOT_PASSWORD", "")


def _db_credentials_from_env() -> tuple[str, str, str]:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise SystemExit("Set DATABASE_URL in .env before running this script")
    parsed = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
    if not parsed.username or not parsed.password:
        raise SystemExit("DATABASE_URL must include user and password")
    database = (parsed.path or "/cw").lstrip("/") or "cw"
    return parsed.username, unquote(parsed.password), database


def main() -> int:
    user, password, database = _db_credentials_from_env()
    conn = pymysql.connect(
        host="127.0.0.1",
        user=ROOT_USER,
        password=ROOT_PASSWORD,
        database="mysql",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user, host, plugin FROM mysql.user WHERE user = %s",
                (user,),
            )
            rows = cur.fetchall()
            print("Before:", rows)

            for host in HOSTS:
                cur.execute(
                    "CREATE USER IF NOT EXISTS %s@%s IDENTIFIED WITH caching_sha2_password BY %s",
                    (user, host, password),
                )
                try:
                    cur.execute(
                        "ALTER USER %s@%s IDENTIFIED WITH caching_sha2_password BY %s",
                        (user, host, password),
                    )
                    print(f"Altered {user}@{host}")
                except pymysql.err.OperationalError as exc:
                    if exc.args[0] != 1396:
                        raise
                    print(f"Created {user}@{host}")

            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
            for host in HOSTS:
                cur.execute(
                    f"GRANT ALL PRIVILEGES ON `{database}`.* TO %s@%s",
                    (user, host),
                )

            cur.execute("FLUSH PRIVILEGES")
            conn.commit()

            cur.execute(
                "SELECT user, host, plugin FROM mysql.user WHERE user = %s",
                (user,),
            )
            print("After:", cur.fetchall())
    finally:
        conn.close()

    test = pymysql.connect(
        host="127.0.0.1",
        user=user,
        password=password,
        database=database,
    )
    test.close()
    print("Connection test OK for", user, "->", database)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("Error:", exc, file=sys.stderr)
        raise SystemExit(1) from exc

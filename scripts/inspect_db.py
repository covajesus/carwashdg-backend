from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
url = os.getenv("DATABASE_URL", "").replace("mysql+pymysql://", "mysql://", 1)
parsed = urlparse(url)
password = unquote(parsed.password or "")
host = parsed.hostname or "127.0.0.1"
port = parsed.port or 3306
user = parsed.username
database = (parsed.path or "/cw").lstrip("/")

print("=== Connection from .env ===")
print(f"host={host}:{port} user={user} database={database}")
print()

conn = pymysql.connect(
    host=host,
    port=port,
    user=user,
    password=password,
    database=database,
)
cur = conn.cursor()

cur.execute("SELECT DATABASE()")
print("SELECT DATABASE():", cur.fetchone()[0])

cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
print(f"SHOW TABLES -> {len(tables)} table(s)")
for name in tables:
    print(f"  - {name}")

cur.execute(
    """
    SELECT COUNT(*) FROM information_schema.tables
    WHERE table_schema = %s AND table_name = 'users'
    """,
    (database,),
)
exists = cur.fetchone()[0]
print(f"\ninformation_schema: cw.users exists = {bool(exists)}")

if exists:
    cur.execute("SELECT COUNT(*) FROM users")
    print("rows in users:", cur.fetchone()[0])
    cur.execute("DESCRIBE users")
    print("\nDESCRIBE users:")
    for row in cur.fetchall():
        print(" ", row)

conn.close()

print("\n=== All databases on this server (same host/user) ===")
conn2 = pymysql.connect(host=host, port=port, user=user, password=password)
cur2 = conn2.cursor()
cur2.execute("SHOW DATABASES")
for (db_name,) in cur2.fetchall():
    if db_name in ("information_schema", "performance_schema", "mysql", "sys"):
        continue
    cur2.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = %s AND table_name = 'users'
        """,
        (db_name,),
    )
    if cur2.fetchone()[0]:
        cur2.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s",
            (db_name,),
        )
        n_tables = cur2.fetchone()[0]
        print(f"  {db_name}: has users ({n_tables} tables total)")
conn2.close()

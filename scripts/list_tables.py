from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
url = os.getenv("DATABASE_URL", "").replace("mysql+pymysql://", "mysql://", 1)
parsed = urlparse(url)
password = unquote(parsed.password or "")
conn = pymysql.connect(
    host=parsed.hostname or "127.0.0.1",
    port=parsed.port or 3306,
    user=parsed.username,
    password=password,
    database=(parsed.path or "/cw").lstrip("/"),
)
cur = conn.cursor()
cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
print(f"Database: {(parsed.path or '/cw').lstrip('/')}")
print(f"Host: {parsed.hostname}:{parsed.port or 3306}")
print(f"User: {parsed.username}")
print(f"Tables ({len(tables)}):")
for name in sorted(tables):
    print(f"  - {name}")
cur.execute("SHOW TABLES LIKE %s", ("%user%",))
print("Like user:", cur.fetchall())
conn.close()

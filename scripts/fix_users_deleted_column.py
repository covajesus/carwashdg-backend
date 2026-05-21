"""Rename users.deletedd_date -> deleted_date (local schema typo)."""
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
url = os.getenv("DATABASE_URL", "").replace("mysql+pymysql://", "mysql://", 1)
parsed = urlparse(url)
password = unquote(parsed.password or "")
database = (parsed.path or "/carwashdg").lstrip("/")

conn = pymysql.connect(
    host=parsed.hostname or "127.0.0.1",
    port=parsed.port or 3306,
    user=parsed.username,
    password=password,
    database=database,
)
cur = conn.cursor()
cur.execute(
    """
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = %s AND table_name = 'users' AND column_name = 'deletedd_date'
    """,
    (database,),
)
if not cur.fetchone()[0]:
    print("Column deletedd_date not found; nothing to do.")
else:
    cur.execute(
        "ALTER TABLE users CHANGE COLUMN deletedd_date deleted_date DATETIME NULL",
    )
    conn.commit()
    print("Renamed users.deletedd_date -> deleted_date in", database)
conn.close()

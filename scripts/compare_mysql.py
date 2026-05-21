import pymysql

SYSTEM_DBS = {"information_schema", "performance_schema", "mysql", "sys"}


def scan(label: str, **kwargs) -> None:
    print(f"=== {label} ===")
    try:
        conn = pymysql.connect(**kwargs)
    except Exception as exc:
        print(f"  Connection failed: {exc}\n")
        return
    cur = conn.cursor()
    cur.execute("SHOW DATABASES")
    for (db_name,) in cur.fetchall():
        if db_name in SYSTEM_DBS:
            continue
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s",
            (db_name,),
        )
        table_count = cur.fetchone()[0]
        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = %s AND table_name = 'users'
            """,
            (db_name,),
        )
        has_users = bool(cur.fetchone()[0])
        if table_count or has_users:
            extra = " <- has users" if has_users else ""
            print(f"  {db_name}: {table_count} tables{extra}")
    conn.close()
    print()


scan("root @ 127.0.0.1", host="127.0.0.1", user="root", password="", database="mysql")
scan(
    "cw @ 127.0.0.1 (from .env)",
    host="127.0.0.1",
    user="cw",
    password="TuPasswordSegura123!",
    database="mysql",
)

for db in ("cw", "carwashdg"):
    try:
        conn = pymysql.connect(
            host="127.0.0.1",
            user="root",
            password="",
            database=db,
        )
        cur = conn.cursor()
        cur.execute("SHOW TABLES")
        tables = [r[0] for r in cur.fetchall()]
        print(f"=== root -> database `{db}` ===")
        print(f"  {len(tables)} tables")
        print(f"  users present: {'users' in tables}")
        if tables:
            print("  sample:", ", ".join(sorted(tables)[:8]), "...")
        conn.close()
        print()
    except Exception as exc:
        print(f"=== root -> `{db}` === FAILED: {exc}\n")

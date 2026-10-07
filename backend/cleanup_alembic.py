import sqlite3

conn = sqlite3.connect("mediavault.db")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '_alembic_tmp%'")
tables = cursor.fetchall()
for t in tables:
    print(f"Dropping {t[0]}")
    cursor.execute(f"DROP TABLE IF EXISTS {t[0]}")
conn.commit()
conn.close()
print("Done")

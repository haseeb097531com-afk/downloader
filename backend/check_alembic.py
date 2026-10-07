import sqlite3

conn = sqlite3.connect("mediavault.db")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '_alembic_tmp%'")
tables = cursor.fetchall()
print("Temp tables:", tables)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
print("Users table exists:", cursor.fetchone())
conn.close()

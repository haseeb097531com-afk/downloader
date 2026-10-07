import sqlite3

conn = sqlite3.connect("mediavault.db")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(users)")
cols = cursor.fetchall()
print("Columns:", [c[1] for c in cols])

cursor.execute("SELECT id, username, role, parent_id FROM users")
rows = cursor.fetchall()
print("Users:")
for row in rows:
    print(f"  id={row[0]}, username={row[1]}, role={row[2]}, parent_id={row[3]}")

cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users'")
indexes = cursor.fetchall()
print("Indexes:", [i[0] for i in indexes])

conn.close()

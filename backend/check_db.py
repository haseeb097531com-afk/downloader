import sqlite3

conn = sqlite3.connect("mediavault.db")
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(users)")
cols = cursor.fetchall()
print("Columns:", [c[1] for c in cols])
cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users'")
indexes = cursor.fetchall()
print("Indexes:", [i[0] for i in indexes])
conn.close()

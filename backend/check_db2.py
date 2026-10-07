import sqlite3

conn = sqlite3.connect("mediavault.db")
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(users)")
cols = cursor.fetchall()
print("Columns:", [c[1] for c in cols])
print("Column details:")
for c in cols:
    print(f"  {c[1]}: type={c[2]}, notnull={c[3]}, dflt_value={c[4]}, pk={c[5]}")
conn.close()

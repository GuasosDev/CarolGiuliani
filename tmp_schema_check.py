import sqlite3
conn = sqlite3.connect('/home/diego/proyectos/GD-CarolGiuliani/db.sqlite3')
cur = conn.cursor()
cur.execute('PRAGMA table_info("communications_emailqueue")')
for row in cur.fetchall():
    print(row)
conn.close()

import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("DELETE FROM conferencias")

conn.commit()
conn.close()

print("Banco limpo! Pode começar novos registros.")
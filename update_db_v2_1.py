import sqlite3
conn = sqlite3.connect('support_system.db')
try:
    conn.execute("ALTER TABLE tickets ADD COLUMN channel_name TEXT")
    print("✅ 数据库已新增 channel_name 字段。")
except sqlite3.OperationalError:
    print("✅ 字段已存在。")
conn.commit()
conn.close()
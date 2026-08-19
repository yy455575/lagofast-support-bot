import sqlite3
conn = sqlite3.connect('support_system.db')
cursor = conn.cursor()
# 创建指令队列表：用于 WebUI 给 Bot 下发发送消息的任务
cursor.execute('''
    CREATE TABLE IF NOT EXISTS cmd_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT NOT NULL,
        message_content TEXT NOT NULL,
        status TEXT DEFAULT 'pending' -- pending: 待发送, sent: 已发送
    )
''')
conn.commit()
conn.close()
print("✅ 数据库指令表升级完成。")
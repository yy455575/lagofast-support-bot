import sqlite3

def setup_database():
    # 1. 连接到数据库（如果目录下没有 support_system.db，会自动创建这个文件）
    conn = sqlite3.connect('support_system.db')
    cursor = conn.cursor()

    # 2. 创建 FAQ 知识库表 (faq_library)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faq_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_keywords TEXT NOT NULL,
            answer_content TEXT NOT NULL
        )
    ''')

    # 3. 创建 工单表 (tickets)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            discord_message_id TEXT NOT NULL,
            original_content TEXT NOT NULL,
            status TEXT DEFAULT 'pending',  -- 状态默认设为 pending (待处理)
            ai_response TEXT,               -- 记录 AI 给出的回复内容
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 提交更改并关闭连接
    conn.commit()
    conn.close()
    print("✅ 数据库 support_system.db 及其数据表已成功初始化！")

if __name__ == '__main__':
    setup_database()
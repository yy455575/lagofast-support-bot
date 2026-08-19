import sqlite3

def upgrade_database():
    conn = sqlite3.connect('support_system.db')
    cursor = conn.cursor()

    print("开始执行 Phase 2 数据库升级...")

    # 1. 升级 tickets 表：增加问题分类字段，为数据看板做准备
    try:
        cursor.execute("ALTER TABLE tickets ADD COLUMN category TEXT DEFAULT '未分类'")
        print("✅ tickets 表已新增 category 字段。")
    except sqlite3.OperationalError:
        print("⚠️ tickets 表 category 字段已存在，跳过。")

    # 2. 修改 faq_library 表：将 note_info 更名为 trigger_rule（SQLite不支持直接改名，这里我们新建表并迁移数据）
    try:
        cursor.execute('''
            CREATE TABLE faq_library_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                question_keywords TEXT,
                trigger_rule TEXT,      -- 原 note_info 更改为 触发规则
                answer_content TEXT
            )
        ''')
        cursor.execute('INSERT INTO faq_library_new (id, category, question_keywords, trigger_rule, answer_content) SELECT id, category, question_keywords, note_info, answer_content FROM faq_library')
        cursor.execute('DROP TABLE faq_library')
        cursor.execute('ALTER TABLE faq_library_new RENAME TO faq_library')
        print("✅ faq_library 表已重构，内部须知已更新为 '触发规则'。")
    except Exception as e:
        print(f"⚠️ faq_library 重构遇到问题或已重构: {e}")

    # 3. 新建 macros 表：用于自动话术模块（人工快捷指令）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS macros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT UNIQUE NOT NULL, -- 例如: /ping
            reply_content TEXT NOT NULL   -- 对应的话术
        )
    ''')
    print("✅ 自动话术 macros 表创建完毕。")

    # 4. 新建 ai_learning 表：用于收集 AI 不懂的问题
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_learning (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_question TEXT NOT NULL,
            reason TEXT DEFAULT 'AI 未知/无匹配 FAQ',
            status TEXT DEFAULT 'unlearned', -- unlearned (待学习), learned (已加入知识库)
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ AI 学习池 ai_learning 表创建完毕。")

    conn.commit()
    conn.close()
    print("🚀 Phase 2 数据库升级全部完成！")

if __name__ == '__main__':
    upgrade_database()
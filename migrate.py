"""
LagoFast 客服系统 - 统一数据库迁移脚本
运行方式: python migrate.py
作用: 一键完成所有历史数据库升级 + 修复数据一致性
"""
import sqlite3

DB_PATH = 'support_system.db'
COMMUNITY_CATEGORY = '社区引流'

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def migrate():
    print("🚀 开始执行统一数据库迁移...")
    conn = get_connection()
    cursor = conn.cursor()

    # ========== Step 1: 确保基础表存在 ==========
    print("📋 Step 1: 检查基础表结构...")
    
    # faq_library 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faq_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            question_keywords TEXT,
            trigger_rule TEXT,
            answer_content TEXT
        )
    ''')
    
    # tickets 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            discord_message_id TEXT NOT NULL,
            original_content TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            ai_response TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # cmd_queue 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cmd_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            message_content TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    print("  ✅ 基础表检查完成")

    # ========== Step 2: 确保 tickets 表有所有必要字段 ==========
    print("📋 Step 2: 检查 tickets 表字段...")
    
    ticket_columns = [
        ("category", "TEXT DEFAULT '未分类'"),
        ("discord_channel_id", "TEXT"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("last_notified_at", "TIMESTAMP"),
        ("reply_status", "TEXT DEFAULT 'unreplied'"),
        ("channel_name", "TEXT"),
    ]
    for col_name, col_type in ticket_columns:
        try:
            cursor.execute(f"ALTER TABLE tickets ADD COLUMN {col_name} {col_type}")
            print(f"  ✅ 新增字段: tickets.{col_name}")
        except sqlite3.OperationalError:
            pass  # 字段已存在
    print("  ✅ tickets 表字段检查完成")

    # ========== Step 3: 确保 faq_library 表有 trigger_rule 字段 ==========
    print("📋 Step 3: 检查 faq_library 表结构...")
    
    # 检查是否有旧的 note_info 字段需要迁移
    cursor.execute("PRAGMA table_info(faq_library)")
    faq_columns = {row[1] for row in cursor.fetchall()}
    
    if 'note_info' in faq_columns and 'trigger_rule' not in faq_columns:
        print("  🔄 检测到旧版 faq_library 结构，正在迁移...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faq_library_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                question_keywords TEXT,
                trigger_rule TEXT,
                answer_content TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO faq_library_new (id, category, question_keywords, trigger_rule, answer_content)
            SELECT id, category, question_keywords, note_info, answer_content FROM faq_library
        ''')
        cursor.execute('DROP TABLE faq_library')
        cursor.execute('ALTER TABLE faq_library_new RENAME TO faq_library')
        print("  ✅ faq_library 迁移完成 (note_info → trigger_rule)")
    
    if 'category' not in faq_columns:
        try:
            cursor.execute("ALTER TABLE faq_library ADD COLUMN category TEXT")
            print("  ✅ faq_library 新增 category 字段")
        except sqlite3.OperationalError:
            pass
    print("  ✅ faq_library 表检查完成")

    # ========== Step 4: 创建可选功能表 ==========
    print("📋 Step 4: 检查可选功能表...")
    
    # macros 快捷话术表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS macros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT UNIQUE NOT NULL,
            reply_content TEXT NOT NULL
        )
    ''')
    
    # ai_learning 学习池表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_learning (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_question TEXT NOT NULL,
            reason TEXT DEFAULT 'AI 未知/无匹配 FAQ',
            status TEXT DEFAULT 'unlearned',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("  ✅ 可选功能表检查完成")

    # ========== Step 5: 修复历史数据一致性 ==========
    print("📋 Step 5: 修复历史数据一致性...")
    
    # 修复社区引流分类不匹配：'Community_Lead' → '社区引流'
    cursor.execute("UPDATE tickets SET category = ? WHERE category = 'Community_Lead'", (COMMUNITY_CATEGORY,))
    if cursor.rowcount > 0:
        print(f"  ✅ 已修复 {cursor.rowcount} 条社区引流记录的分类标签")
    
    # 修复空 original_content
    cursor.execute("UPDATE tickets SET original_content = '[System]: 历史归档数据' WHERE original_content IS NULL")
    if cursor.rowcount > 0:
        print(f"  ✅ 已修复 {cursor.rowcount} 条空内容记录")
    
    # 重置状态不一致的工单
    cursor.execute("UPDATE tickets SET status = 'pending' WHERE reply_status = 'unreplied' AND status NOT IN ('resolved', 'chat_alert')")
    cursor.execute("UPDATE tickets SET status = 'in_progress' WHERE reply_status = 'replied' AND status NOT IN ('resolved', 'chat_alert')")
    print("  ✅ 历史数据修复完成")

    # ========== 完成 ==========
    conn.commit()
    conn.close()
    print("\n" + "=" * 50)
    print("🎉 统一数据库迁移全部完成！")
    print("   现在可以安全启动 bot.py 和 webui.py")
    print("=" * 50)

if __name__ == '__main__':
    migrate()
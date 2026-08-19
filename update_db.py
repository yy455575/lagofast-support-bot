import sqlite3

def update_faq_table():
    # 连接当前目录下的数据库
    conn = sqlite3.connect('support_system.db')
    cursor = conn.cursor()
    
    # 暴力删除旧的、字段不全的表
    cursor.execute('DROP TABLE IF EXISTS faq_library')
    
    # 按照最新的 CSV 格式重新建表（包含 category 字段）
    cursor.execute('''
        CREATE TABLE faq_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,          -- 问题类型
            question_keywords TEXT, -- 问题表现
            note_info TEXT,         -- 内部须知
            answer_content TEXT     -- 回复话术
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ FAQ 表结构已彻底重置！现在包含了 category 字段。")

if __name__ == '__main__':
    update_faq_table()
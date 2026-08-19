import sqlite3
from datetime import datetime, timezone

DB_PATH = 'support_system.db'

def run_migration():
    print("🚀 开始执行 V5.0 数据大清洗...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 重置所有未结单的工单状态（按照新的规则）
    # 如果最后一次更新是 'unreplied'，进入 pending (待处理)
    cursor.execute("UPDATE tickets SET status = 'pending' WHERE reply_status = 'unreplied' AND status != 'resolved'")
    # 如果最后一次更新是 'replied'，进入 in_progress (跟进中)
    cursor.execute("UPDATE tickets SET status = 'in_progress' WHERE reply_status = 'replied' AND status != 'resolved'")

    # 2. 清理可能存在的历史空数据
    cursor.execute("UPDATE tickets SET original_content = '[System]: 历史归档数据' WHERE original_content IS NULL")

    conn.commit()
    conn.close()
    print("✅ 历史数据梳理完成！请准备运行新的 bot.py")

if __name__ == "__main__":
    run_migration()
import sqlite3
import csv

def import_csv_to_db(csv_filename):
    conn = sqlite3.connect('support_system.db')
    cursor = conn.cursor()
    
    success_count = 0
    current_category = "未分类" 
    
    try:
        # 注意这里的 encoding='gbk'
        with open(csv_filename, mode='r', encoding='gbk') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                category = row.get('问题类型', '').strip()
                if category:
                    current_category = category
                else:
                    category = current_category
                
                keywords = row.get('问题表现', '').strip()
                note = row.get('关键信息', '').strip()
                answer = row.get('回复话术', '').strip()
                
                if not keywords and not answer:
                    continue
                
                cursor.execute('''
                    INSERT INTO faq_library (category, question_keywords, note_info, answer_content)
                    VALUES (?, ?, ?, ?)
                ''', (category, keywords, note, answer))
                
                success_count += 1
                
        conn.commit()
        print(f"✅ 成功读取并导入了 {success_count} 条 FAQ 数据！")
        
    except FileNotFoundError:
        print(f"❌ 找不到文件：{csv_filename}，请确认文件是否在 C:\\Users\\yh\\DCworkflow 目录下。")
    except Exception as e:
        print(f"❌ 导入失败: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    import_csv_to_db('LagoFast - 用户FAQ.csv')
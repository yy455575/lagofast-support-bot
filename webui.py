import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import re

DB_PATH = 'support_system.db'
COMMUNITY_CATEGORY = '社区引流'  # 与 bot.py 保持一致

st.set_page_config(page_title="Discord 客服中枢 V5.5", page_icon="🎮", layout="wide")

def get_connection():
    """获取启用 WAL 模式的数据库连接"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

# ================= 自定义富文本渲染 =================
def format_chat_log(text):
    if not isinstance(text, str): return ""
    
    # 1. 匹配所有形式的用户发言
    text = re.sub(r'(?:👤\s*)?\[User\]:?', r"<span style='color: #FF8C00; font-weight: bold;'>👤 [User]:</span>", text, flags=re.IGNORECASE)
    # 2. 匹配所有形式的管理员发言
    text = re.sub(r'(?:👨‍💻\s*)?\[Staff\]:?', r"<span style='color: #1E90FF; font-weight: bold;'>👨‍💻 [Staff]:</span>", text, flags=re.IGNORECASE)
    # 3. 匹配所有形式的 Bot 发言
    text = re.sub(r'(?:🤖\s*)?\[LagoFast - Bot\]:?', r"<span style='color: #2E8B57; font-weight: bold;'>🤖 [LagoFast - Bot]:</span>", text, flags=re.IGNORECASE)
    # 4. 匹配 System Panel
    text = re.sub(r'(?:⚙️\s*)?\[System Panel\]:?', r"<span style='color: #9E9E9E; font-weight: bold;'>⚙️ [System]:</span>", text, flags=re.IGNORECASE)
    # 5. 匹配 System 警告
    text = re.sub(r'(?:⚠️\s*)?\[System\]:?', r"<span style='color: #9E9E9E; font-weight: bold;'>⚠️ [System]:</span>", text, flags=re.IGNORECASE)
    
    return f"""
    <div style='
        background-color: #FFFFFF; 
        color: #333333; 
        border: 1px solid #EAEAEA; 
        padding: 16px; 
        border-radius: 8px; 
        line-height: 1.6; 
        font-family: sans-serif;
        white-space: pre-wrap;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    '>{text}</div>
    """

# ================= 侧边栏导航 =================
st.sidebar.title("🎮 客服中枢 V5.5")
st.sidebar.caption("安全加固版 · 数据一致性修复")
page = st.sidebar.radio("模块导航", ["🎫 工单系统 (Tickets)", "💬 社区监控 (Chats)", "📚 知识库管理", "📊 专业数据看板"])

# ================= 板块一：🎫 工单系统 =================
if page == "🎫 工单系统 (Tickets)":
    st.title("🎫 独立工单处理中心")
    st.caption("此处仅展示通过正式 Ticket 频道创建的工单，不受社区风控数据干扰。")
    
    tab_new, tab_progress, tab_resolved = st.tabs(["🔴 待处理 (用户发言)", "🟡 跟进中 (管理员/Bot已回复)", "🟢 已结单 (3天自动删除)"])
    conn = get_connection()
    
    query = """
        SELECT *, COALESCE(discord_channel_id, 'ARCHIVE_' || id) as group_id, MAX(updated_at) as last_act 
        FROM tickets 
        WHERE status IN ('pending', 'in_progress', 'resolved') AND category != ?
        GROUP BY group_id 
        ORDER BY last_act DESC
    """
    try:
        df_tickets = pd.read_sql(query, conn, params=(COMMUNITY_CATEGORY,))
        if not df_tickets.empty:
            df_tickets['display_time'] = pd.to_datetime(df_tickets['updated_at']).dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            df_tickets = pd.DataFrame(columns=['id', 'status', 'channel_name', 'discord_channel_id', 'original_content', 'display_time', 'reply_status', 'category'])
    except Exception as e:
        st.error(f"查询工单数据失败: {e}")
        df_tickets = pd.DataFrame()

    def render_table(df, tab_name, show_actions=False):
        if df.empty: 
            st.info("🎉 当前分类下暂无记录。")
            return
        
        for _, row in df.iterrows():
            channel_display = row['channel_name'] if pd.notna(row['channel_name']) else "未知"
            has_channel_id = pd.notna(row['discord_channel_id']) and str(row['discord_channel_id']).isdigit()
            
            if row['status'] == 'resolved':
                status_tag = "⚪ 已结单"
            elif row.get('reply_status') == 'unreplied':
                status_tag = "🔴 待回复"
            else:
                status_tag = "🟢 已回复"
                
            expander_title = f"频道: #{channel_display} | 标签: {row.get('category', '未分类')} | 状态: {status_tag} | 时间: {row.get('display_time', '未知')}"
            
            with st.expander(expander_title):
                st.markdown(format_chat_log(row['original_content']), unsafe_allow_html=True)
                
                if show_actions:
                    st.divider()
                    reply_text = st.text_area("✍️ 管理员回复", key=f"re_{tab_name}_{row['id']}", placeholder="输入并下发后，工单将自动移入【跟进中】列表...")
                    c1, c2, c3 = st.columns(3)
                    
                    with c1:
                        if st.button("🚀 仅下发回复", key=f"s_{tab_name}_{row['id']}", type="secondary", use_container_width=True):
                            if has_channel_id and reply_text:
                                conn.execute("INSERT INTO cmd_queue (channel_id, message_content) VALUES (?, ?)", (row['discord_channel_id'], f"👨‍💻 **Staff:** {reply_text}"))
                                conn.execute("UPDATE tickets SET status='in_progress', reply_status='replied', updated_at=CURRENT_TIMESTAMP WHERE id=?", (row['id'],))
                                conn.commit(); st.rerun()
                            else: st.warning("ID无效或内容为空")
                            
                    with c2:
                        if st.button("✅ 手动结单", key=f"cl_{tab_name}_{row['id']}", type="primary", use_container_width=True):
                            if has_channel_id and reply_text:
                                conn.execute("INSERT INTO cmd_queue (channel_id, message_content) VALUES (?, ?)", (row['discord_channel_id'], f"👨‍💻 **Staff:** {reply_text}"))
                            conn.execute("UPDATE tickets SET status='resolved', reply_status='replied', updated_at=CURRENT_TIMESTAMP WHERE id=?", (row['id'],))
                            conn.commit(); st.success("已结单，将存入已结单列表"); st.rerun()
                                
                    with c3:
                        if st.button("🗑️ 远程销毁频道", key=f"del_{tab_name}_{row['id']}", type="primary", use_container_width=True):
                            if has_channel_id:
                                conn.execute("INSERT INTO cmd_queue (channel_id, message_content) VALUES (?, ?)", (row['discord_channel_id'], "$Delete"))
                                conn.execute("UPDATE tickets SET status='resolved', updated_at=CURRENT_TIMESTAMP WHERE id=?", (row['id'],))
                                conn.commit(); st.rerun()

    with tab_new: render_table(df_tickets[df_tickets['status'] == 'pending'], "new", True)
    with tab_progress: render_table(df_tickets[df_tickets['status'] == 'in_progress'], "prog", True)
    with tab_resolved: render_table(df_tickets[df_tickets['status'] == 'resolved'], "res")
    conn.close()

# ================= 板块二：💬 社区监控中心 =================
elif page == "💬 社区监控 (Chats)":
    st.title("💬 社区风控预警中心")
    st.caption("这里独立记录所有在公共频道的潜在提问。数据与正式工单池完全隔离。")
    conn = get_connection()
    
    # 【修复】使用统一的社区分类标签
    df_chats = pd.read_sql("SELECT * FROM tickets WHERE category = ? ORDER BY updated_at DESC", conn, params=(COMMUNITY_CATEGORY,))
    
    if not df_chats.empty:
        df_chats['display_time'] = pd.to_datetime(df_chats['updated_at']).dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')
        
        # 顶部：信息量波动图
        df_trend = df_chats.set_index('display_time').resample('1h').size().reset_index(name='消息量')
        fig = px.line(df_trend, x='display_time', y='消息量', title="近期待处理社区提问波动曲线 (小时级)", markers=True)
        st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        tab_chat_alert, tab_chat_res = st.tabs(["🔴 待处理异常", "🟢 已归档预警"])
        
        with tab_chat_alert:
            df_alerts = df_chats[df_chats['status'] == 'chat_alert']
            if df_alerts.empty: st.info("暂无待处理项。")
            for _, row in df_alerts.iterrows():
                with st.expander(f"频道: #{row['channel_name']} | 状态: 🔴 待审阅 | 时间: {row['display_time'].strftime('%Y-%m-%d %H:%M:%S')}"):
                    st.markdown(format_chat_log(row['original_content']), unsafe_allow_html=True)
                    if st.button("✔️ 已审阅并归档", key=f"chat_{row['id']}"):
                        conn.execute("UPDATE tickets SET status='resolved' WHERE id=?", (row['id'],))
                        conn.commit(); st.rerun()
                        
        with tab_chat_res:
            df_res = df_chats[df_chats['status'] == 'resolved']
            if df_res.empty: st.info("暂无已归档项。")
            for _, row in df_res.iterrows():
                with st.expander(f"频道: #{row['channel_name']} | 状态: 🟢 已归档 | 时间: {row['display_time'].strftime('%Y-%m-%d %H:%M:%S')}"):
                    st.markdown(format_chat_log(row['original_content']), unsafe_allow_html=True)
    else:
        st.success("🎉 目前社区风平浪静，暂未发现提问风暴。")
    conn.close()

# ================= 板块三：知识库管理 =================
elif page == "📚 知识库管理":
    st.title("📚 知识库管理")
    tab_faq, tab_add = st.tabs(["📖 FAQ 管理", "➕ 新增 FAQ"])
    conn = get_connection()

    with tab_faq:
        try:
            df_faq = pd.read_sql("SELECT rowid as id, category as '分类', question_keywords as '关键词', trigger_rule as '触发规则', answer_content as '标准话术' FROM faq_library", conn)
            st.dataframe(df_faq[['分类', '关键词', '触发规则', '标准话术']], use_container_width=True)
            
            st.divider()
            if not df_faq.empty:
                faq_options = {row['id']: f"[{row['分类']}] {row['关键词'][:30]}..." for _, row in df_faq.iterrows()}
                selected_faq_id = st.selectbox("👇 选择修改：", options=list(faq_options.keys()), format_func=lambda x: faq_options[x])
                
                if selected_faq_id:
                    selected_row = df_faq[df_faq['id'] == selected_faq_id].iloc[0]
                    with st.form(f"edit_faq"):
                        e_cat = st.text_input("问题分类", value=selected_row['分类'])
                        e_key = st.text_input("触发关键词", value=selected_row['关键词'])
                        e_ans = st.text_area("AI 标准回复话术", value=selected_row['标准话术'], height=150)
                        
                        col_save, col_del = st.columns(2)
                        with col_save:
                            if st.form_submit_button("💾 保存修改", type="primary"):
                                conn.execute("UPDATE faq_library SET category=?, question_keywords=?, answer_content=? WHERE rowid=?", (e_cat, e_key, e_ans, selected_faq_id))
                                conn.commit(); st.rerun()
                        with col_del:
                            if st.form_submit_button("🗑️ 永久删除"):
                                conn.execute("DELETE FROM faq_library WHERE rowid=?", (selected_faq_id,))
                                conn.commit(); st.rerun()
        except Exception as e:
            st.error(f"读取数据失败: {e}")

    with tab_add:
        with st.form("manual_faq"):
            f_cat = st.text_input("问题分类")
            f_key = st.text_input("触发关键词")
            f_ans = st.text_area("AI 标准回复话术", height=200)
            if st.form_submit_button("🚀 录入并生效"):
                if f_key and f_ans:
                    conn.execute("INSERT INTO faq_library (category, question_keywords, answer_content) VALUES (?, ?, ?)", (f_cat, f_key, f_ans))
                    conn.commit(); st.rerun()
                else:
                    st.warning("关键词和回复话术不能为空")
    conn.close()

# ================= 板块四：数据看板 =================
elif page == "📊 专业数据看板":
    st.title("📊 核心工单数据看板")
    st.caption("此处统计数据已完全剥离社区（Chats）的引流信息，仅体现正式工单效能。")
    conn = get_connection()
    try:
        total_fb = pd.read_sql("SELECT COUNT(*) as c FROM tickets WHERE category != ?", conn, params=(COMMUNITY_CATEGORY,)).iloc[0]['c']
        chitchat_fb = pd.read_sql("SELECT COUNT(*) as c FROM tickets WHERE category='Chitchat' AND category != ?", conn, params=(COMMUNITY_CATEGORY,)).iloc[0]['c']
        ai_resolved = pd.read_sql("SELECT COUNT(*) as c FROM tickets WHERE status='resolved' AND category='FAQ_Resolved'", conn).iloc[0]['c']
        human_tickets = pd.read_sql("SELECT COUNT(*) as c FROM tickets WHERE status IN ('pending', 'in_progress') AND category != ?", conn, params=(COMMUNITY_CATEGORY,)).iloc[0]['c']
        community_alerts = pd.read_sql("SELECT COUNT(*) as c FROM tickets WHERE category = ?", conn, params=(COMMUNITY_CATEGORY,)).iloc[0]['c']
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("累计正式工单", total_fb)
        c2.metric("🤖 AI 自动解决", ai_resolved)
        c3.metric("👨‍💻 人工待处理", human_tickets)
        c4.metric("🍵 闲聊过滤", chitchat_fb)
        c5.metric("📢 社区预警", community_alerts)

        df_pie = pd.read_sql("SELECT category, COUNT(*) as count FROM tickets WHERE category != ? GROUP BY category", conn, params=(COMMUNITY_CATEGORY,))
        if not df_pie.empty:
            fig = px.pie(df_pie, values='count', names='category', title="核心工单业务标签分布", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
            
        # 新增：趋势图
        st.divider()
        st.subheader("📈 工单趋势")
        try:
            df_trend = pd.read_sql("""
                SELECT date(updated_at) as date, COUNT(*) as count 
                FROM tickets 
                WHERE category != ? 
                GROUP BY date(updated_at) 
                ORDER BY date(updated_at) DESC 
                LIMIT 30
            """, conn, params=(COMMUNITY_CATEGORY,))
            if not df_trend.empty:
                fig_trend = px.bar(df_trend, x='date', y='count', title="近 30 天工单量趋势", labels={'date': '日期', 'count': '工单数'})
                st.plotly_chart(fig_trend, use_container_width=True)
        except Exception as e:
            st.info(f"趋势图生成失败: {e}")
    except Exception as e:
        st.error(f"数据看板加载失败: {e}")
    conn.close()
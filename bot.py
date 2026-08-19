import discord
import sqlite3
import asyncio
import logging
import os
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta, timezone
from openai import AsyncOpenAI
from dotenv import load_dotenv

# ================= 加载环境变量 =================
load_dotenv()

# ================= 核心配置区 =================
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')

if not BOT_TOKEN or not DEEPSEEK_API_KEY:
    raise ValueError("❌ 缺少必要的环境变量！请检查 .env 文件是否包含 BOT_TOKEN 和 DEEPSEEK_API_KEY")

# 频道分类 ID 配置 (需替换为真实纯数字 ID)
TICKET_CATEGORIES = [1315994632185712671, 1318149535159156736, 1491315604672479276, 1286636114605510666, 1491315968692060272, 1491315997863313510] # 6个工单分类目录 ID
CHAT_CHANNEL_IDS = [1283782240903630869, 1283781888078516254, 933542219577712644, 1012022716238401676, 1440283130794872944, 1283782168044114071, 1394192746356539543, 1286635317947793439]
ADMIN_USER_ID = 1521069963849240596             # 遇到麻烦时需要被 @ 的管理员 ID (lagofastjustine)
SUPPORT_TICKET_CHANNEL_ID = 1095422143031951422  # 「📩」support-ticket 频道 ID（用于社区引导用户开 ticket）

STAFF_ROLES = ['Admin', 'Staff', 'Developer', 'Customer Support', 'Marketing Staff']
DB_PATH = 'support_system.db'
CLEANUP_THRESHOLD_DAYS = 3                     # 触发自动清理的无活跃天数
COMMUNITY_CATEGORY = '社区引流'                # 社区监控的统一分类标签
# ==========================================

# ================= 日志配置 =================
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DiscordBotLogger')
logger.setLevel(logging.INFO)
file_handler = RotatingFileHandler('bot_runtime.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

ai_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
intents = discord.Intents.all()
client = discord.Client(intents=intents)

# ================= 数据库工具函数 =================
def get_db_connection():
    """获取启用 WAL 模式的数据库连接"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS cmd_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT NOT NULL, 
        message_content TEXT NOT NULL, status TEXT DEFAULT 'pending')
    ''')
    columns = [
        ("discord_channel_id", "TEXT"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("last_notified_at", "TIMESTAMP"), 
        ("reply_status", "TEXT DEFAULT 'unreplied'") 
    ]
    for col_name, col_type in columns:
        try: cursor.execute(f"ALTER TABLE tickets ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError: pass
    conn.commit()
    conn.close()

# ================= 消息内容提取 =================
def extract_content(message):
    full_content = message.content or ""
    if message.embeds:
        for embed in message.embeds:
            parts = []
            if embed.title: parts.append(f"标题: {embed.title}")
            if embed.description: parts.append(f"描述: {embed.description}")
            for field in embed.fields: parts.append(f"{field.name}: {field.value}")
            full_content += "\n" + "\n".join(parts)
    return full_content.strip()

# ================= 工单存储 =================
def save_ticket(user_id, message_id, append_text, status=None, ai_response=None, category=None, channel_name=None, discord_channel_id=None, reply_status=None, update_notify_time=False):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("SELECT id, original_content FROM tickets WHERE discord_channel_id = ? AND status != 'resolved' LIMIT 1", (str(discord_channel_id),))
        existing_ticket = cursor.fetchone()
        
        if existing_ticket:
            if append_text is None:
                # 仅更新元数据，不追加内容
                sql = "UPDATE tickets SET updated_at = ?"
                params = [now]
                if status: sql += ", status = ?"; params.append(status)
                if ai_response: sql += ", ai_response = ?"; params.append(ai_response)
                if category: sql += ", category = ?"; params.append(category)
                if reply_status: sql += ", reply_status = ?"; params.append(reply_status)
                if update_notify_time: sql += ", last_notified_at = ?"; params.append(now)
                sql += " WHERE id = ?"
                params.append(existing_ticket[0])
                cursor.execute(sql, params)
            else:
                new_content = f"{existing_ticket[1]}\n---\n[{now}] {append_text}"
                sql = "UPDATE tickets SET original_content = ?, updated_at = ?"
                params = [new_content, now]
                
                if status: sql += ", status = ?"; params.append(status)
                if ai_response: sql += ", ai_response = ?"; params.append(ai_response)
                if category: sql += ", category = ?"; params.append(category)
                if reply_status: sql += ", reply_status = ?"; params.append(reply_status)
                if update_notify_time: sql += ", last_notified_at = ?"; params.append(now)
                
                sql += " WHERE id = ?"
                params.append(existing_ticket[0])
                cursor.execute(sql, params)
        else:
            notified_at = now if update_notify_time else None
            initial_content = f"[{now}] {append_text}"
            cursor.execute('''INSERT INTO tickets (user_id, discord_message_id, original_content, status, ai_response, category, channel_name, discord_channel_id, updated_at, reply_status, last_notified_at)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                           (str(user_id), str(message_id), initial_content, status or 'pending', ai_response, category or '未分类', channel_name, str(discord_channel_id), now, reply_status or 'unreplied', notified_at))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ 数据库写入失败 (save_ticket): {e}", exc_info=True)

# ================= FAQ 知识库（带缓存 + 智能检索） =================
_FAQ_CACHE = {"data": None, "list": None, "updated": 0}
FAQ_CACHE_TTL = 300  # 5 分钟缓存

def _refresh_faq_cache():
    """刷新 FAQ 缓存"""
    global _FAQ_CACHE
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT category, question_keywords, trigger_rule, answer_content FROM faq_library')
        faqs = cursor.fetchall()
        conn.close()
        if not faqs:
            _FAQ_CACHE["data"] = "本地知识库目前为空。"
            _FAQ_CACHE["list"] = []
        else:
            context = "【内部 FAQ 知识库】\n"
            faq_list = []
            for cat, keys, rule, ans in faqs:
                context += f"- 分类: {cat} | 关键词: {keys}\n"
                if rule: context += f"  触发规则: {rule}\n"
                if ans: context += f"  标准话术: {ans}\n"
                faq_list.append({"category": cat, "keywords": keys, "rule": rule, "answer": ans})
            _FAQ_CACHE["data"] = context
            _FAQ_CACHE["list"] = faq_list
        _FAQ_CACHE["updated"] = datetime.now(timezone.utc).timestamp()
    except Exception as e:
        logger.error(f"⚠️ FAQ 知识库读取异常: {e}")
        _FAQ_CACHE["data"] = "知识库读取异常。"
        _FAQ_CACHE["list"] = []

def get_faq_context():
    """获取完整 FAQ 上下文（用于分类阶段）"""
    now = datetime.now(timezone.utc).timestamp()
    if _FAQ_CACHE["data"] is None or (now - _FAQ_CACHE["updated"]) >= FAQ_CACHE_TTL:
        _refresh_faq_cache()
    return _FAQ_CACHE["data"]

def get_relevant_faqs(category_hint=None, query=""):
    """智能 FAQ 检索：根据分类和关键词返回最相关的 FAQ 条目"""
    now = datetime.now(timezone.utc).timestamp()
    if _FAQ_CACHE["list"] is None or (now - _FAQ_CACHE["updated"]) >= FAQ_CACHE_TTL:
        _refresh_faq_cache()
    
    faq_list = _FAQ_CACHE["list"]
    if not faq_list:
        return "此领域暂无 FAQ 覆盖。"
    
    # 如果有分类提示，优先筛选相关分类
    if category_hint and category_hint not in ("Other", "API_Error"):
        category_map = {
            "Refund": ["退款", "Refund", "退款政策", "购买"],
            "Cancel": ["取消", "Cancel", "订阅", "自动续费"],
            "Login_Error": ["登录", "Login", "账号", "注册", "密码"],
            "Crash": ["崩溃", "闪退", "Crash", "黑屏", "白屏"],
            "Lag": ["延迟", "卡顿", "掉线", "Lag", "Ping", "网络"],
            "Payment": ["支付", "付款", "Payment", "购买", "订阅"],
            "Connection": ["连接", "Connection", "服务器", "节点"],
            "Account": ["账号", "Account", "密码", "邮箱"],
            "Download": ["下载", "安装", "Download", "Install"],
            "Subscription": ["订阅", "套餐", "Subscription", "会员", "VIP"],
        }
        target_cats = category_map.get(category_hint, [category_hint])
        scored = []
        for faq in faq_list:
            score = 0
            faq_cat = (faq["category"] or "").lower()
            faq_keys = (faq["keywords"] or "").lower()
            for tc in target_cats:
                if tc.lower() in faq_cat or tc.lower() in faq_keys:
                    score += 10
            if query:
                for word in query.lower().split():
                    if word in faq_keys or word in (faq["answer"] or "").lower():
                        score += 3
            scored.append((score, faq))
        scored.sort(key=lambda x: x[0], reverse=True)
        top_faqs = [f for s, f in scored[:5] if s > 0]
        if not top_faqs:
            top_faqs = faq_list[:3]
    else:
        top_faqs = faq_list[:5]
    
    result = "【相关 FAQ 知识】\n"
    for faq in top_faqs:
        result += f"- 分类: {faq['category']} | 关键词: {faq['keywords']}\n"
        if faq["answer"]: result += f"  标准话术: {faq['answer']}\n"
    return result

# ================= 智能容错兜底回复机制 =================
async def safe_reply(message, text):
    """尝试引用回复，如果原消息被删，则回退为普通频道消息"""
    try:
        await message.reply(text)
    except discord.errors.HTTPException as e:
        if getattr(e, 'code', None) == 50035 or "Unknown message" in str(e):
            logger.warning(f"⚠️ 原消息已被删除，触发兜底发送机制 (@{message.author})")
            try:
                await message.channel.send(f"<@{message.author.id}> {text}")
            except Exception as inner_e:
                logger.error(f"❌ 兜底发送彻底失败 (频道可能已被销毁): {inner_e}")
        else:
            logger.error(f"❌ 回复发送出现未知异常: {e}")
    except Exception as e:
        logger.error(f"❌ safe_reply 出现异常: {e}")

# ================= 两阶段 AI Pipeline =================

# --- 第一跳：轻量级意图分类 ---
async def ai_classify(user_message, system_type="ticket"):
    """第一阶段：仅做意图分类，返回 JSON {intent, category, language, urgency}"""
    faq_context = get_faq_context()
    
    if system_type == "ticket":
        classify_prompt = f"""你是一个消息意图分类器。分析用户消息，返回严格的 JSON 格式。

可用意图: FAQ(命中知识库), CHITCHAT(闲聊), NEED_HUMAN(需要人工), TOXIC(违规)

可用分类标签(仅用于 NEED_HUMAN): Refund, Cancel, Login_Error, Crash, Lag, Payment, Connection, Account, Download, Subscription, Other

可用语言: en, zh, ja, ko, es, pt, fr, de, ru, other

可用紧急度: low, medium, high

规则：
- 如果用户诉求可以通过 FAQ 解决 → intent=FAQ
- 纯闲聊/打招呼 → intent=CHITCHAT
- 需要退款/账号操作/技术问题无法远程解决 → intent=NEED_HUMAN
- 违规/辱骂/垃圾信息 → intent=TOXIC
- category 穿透现象看本质（抱怨延迟但求退款 → Refund）
- 必须使用与玩家消息相同的语言

{faq_context}

只输出 JSON，不要任何其他文字。格式：
{{"intent":"FAQ","category":"Lag","language":"en","urgency":"medium"}}"""
    else:
        classify_prompt = f"""你是社区消息分类器。返回严格的 JSON 格式。

可用意图: CHITCHAT(纯闲聊), PARTIAL_ANSWER(可给部分解答), NEED_HUMAN(需开ticket)

可用语言: en, zh, ja, ko, es, pt, fr, de, ru, other

规则：
- 纯闲聊/打招呼 → CHITCHAT
- 简单技术问题你很有把握可以回答 → PARTIAL_ANSWER
- 复杂问题/账号退款/Bug反馈 → NEED_HUMAN

{faq_context}

只输出 JSON，不要任何其他文字。格式：
{{"intent":"CHITCHAT","category":"General","language":"en"}}"""

    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "system", "content": classify_prompt}, {"role": "user", "content": user_message}],
            temperature=0.1, max_tokens=500
        )
        raw = response.choices[0].message.content.strip()
        # 提取 JSON（兼容 markdown 代码块包裹）
        import json, re
        json_match = re.search(r'\{[^}]+\}', raw)
        if json_match:
            result = json.loads(json_match.group())
            return result
        # 回退：尝试从原始输出解析标签
        if "[FAQ]" in raw: return {"intent": "FAQ", "category": "General", "language": "en", "urgency": "low"}
        if "[NEED_HUMAN]" in raw: return {"intent": "NEED_HUMAN", "category": "Other", "language": "en", "urgency": "medium"}
        if "[CHITCHAT]" in raw: return {"intent": "CHITCHAT", "category": "General", "language": "en", "urgency": "low"}
        if "[TOXIC]" in raw: return {"intent": "TOXIC", "category": "Toxic", "language": "en", "urgency": "high"}
        return {"intent": "NEED_HUMAN", "category": "Other", "language": "en", "urgency": "medium"}
    except Exception as e:
        logger.error(f"❌ AI 分类失败: {e}")
        return {"intent": "NEED_HUMAN", "category": "API_Error", "language": "en", "urgency": "high"}

# --- 第二跳：精准回复生成 ---
async def ai_reply(context, classification, system_type="ticket"):
    """第二阶段：根据分类结果，注入最相关的 FAQ 生成高质量回复"""
    intent = classification.get("intent", "NEED_HUMAN")
    category = classification.get("category", "Other")
    language = classification.get("language", "en")
    
    if system_type == "ticket":
        # 工单场景：根据意图注入不同的 FAQ 量和 prompt
        if intent == "FAQ":
            relevant_faqs = get_relevant_faqs(category, context)
            reply_prompt = f"""你是 LagoFast 游戏加速器的专业客服。根据 FAQ 知识回答玩家问题。

规则：
1. 严格按照 FAQ 话术回答，不要编造信息
2. 使用与玩家相同的语言回复（检测到的语言: {language}）
3. 语气专业、友好、简洁
4. 如果 FAQ 信息不足以完全回答，在末尾加上"如果还有问题，请告诉我们，会有专人协助你。"

{relevant_faqs}"""
            temp = 0.2
        elif intent == "CHITCHAT":
            reply_prompt = f"""你是 LagoFast 游戏加速器的友好客服。
玩家在工单里闲聊，请用友好轻松的方式回应，但保持专业。
使用与玩家相同的语言回复（检测到的语言: {language}）。
简短回复即可，1-2句话。"""
            temp = 0.6
        elif intent == "TOXIC":
            return "[TOXIC]"  # 不生成回复
        else:  # NEED_HUMAN
            reply_prompt = f"""你是 LagoFast 游戏加速器的客服。
玩家的问题需要人工处理，请生成一句简短的引导语，告知已通知管理员。
使用与玩家相同的语言回复（检测到的语言: {language}）。
只输出引导语，1-2句话，不要输出其他内容。"""
            temp = 0.3
    else:
        # 社区场景
        if intent == "PARTIAL_ANSWER":
            relevant_faqs = get_relevant_faqs(category, context)
            reply_prompt = f"""你是 LagoFast 社区的智能助手「小L」，一个热爱游戏的加速器专家。

【你的性格】友好、幽默、偶尔使用游戏梗，像一个懂技术的游戏好友。
【语言】使用与玩家相同的语言回复（检测到的语言: {language}）

你可以直接给一个简短有用的回答，然后在末尾建议"如果还有问题可以开 ticket 获取专属支持"。

{relevant_faqs}"""
            temp = 0.5
        elif intent == "CHITCHAT":
            reply_prompt = f"""你是 LagoFast 社区的智能助手「小L」，一个热爱游戏的加速器专家。

【你的性格】
- 友好、幽默、偶尔使用游戏梗
- 真心关心玩家的游戏体验，不像一个客服机器人
- 可以聊聊游戏，分享有趣的游戏体验

【语言】使用与玩家相同的语言回复（检测到的语言: {language}）
简短互动，1-2句话即可。"""
            temp = 0.7
        else:  # NEED_HUMAN
            return "[NEED_HUMAN]"
    
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "system", "content": reply_prompt}, {"role": "user", "content": context}],
            temperature=temp, max_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"❌ AI 回复生成失败: {e}")
        return None

# --- 统一入口：两阶段 Pipeline ---
async def smart_ai_pipeline(user_message, system_type="ticket"):
    """两阶段 AI Pipeline：先分类 → 再精准回复"""
    # 第一跳：分类
    classification = await ai_classify(user_message, system_type)
    intent = classification.get("intent", "NEED_HUMAN")
    category = classification.get("category", "Other")
    
    logger.info(f"🧠 AI分类结果: intent={intent}, category={category}, lang={classification.get('language')}, urgency={classification.get('urgency')}")
    
    # 第二跳：生成回复
    reply = await ai_reply(user_message, classification, system_type)
    
    return intent, category, reply

# ================= WebUI 指令队列轮询 =================
async def check_webui_replies():
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, channel_id, message_content FROM cmd_queue WHERE status='pending'")
            cmds = cursor.fetchall()
            for cmd_id, channel_id, text in cmds:
                if str(channel_id).isdigit():
                    channel = client.get_channel(int(channel_id))
                    if channel:
                        if text == "$Delete":
                            try:
                                await channel.delete(reason="WebUI Admin Request")
                                logger.info(f"🗑️ 已通过 WebUI 远程删除频道: {channel_id}")
                            except discord.Forbidden:
                                logger.error(f"⚠️ 机器人权限不足，无法删除频道 {channel_id}")
                        else:
                            await channel.send(f"{text}")
                            logger.info(f"📤 成功下发 WebUI 远程指令到频道: {channel_id}")
                cursor.execute("UPDATE cmd_queue SET status='sent' WHERE id=?", (cmd_id,))
            conn.commit()
            conn.close()
        except Exception as e: 
            logger.error(f"⚠️ WebUI 队列检查异常: {e}")
        await asyncio.sleep(3)

# ================= 自动清理过期频道 =================
async def auto_cleanup_task():
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            threshold_time = (datetime.now(timezone.utc) - timedelta(days=CLEANUP_THRESHOLD_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                SELECT discord_channel_id, channel_name FROM tickets 
                WHERE updated_at < ? AND status = 'resolved' AND discord_channel_id IS NOT NULL
            """, (threshold_time,))
            
            expired_tickets = cursor.fetchall()
            for ch_id, ch_name in expired_tickets:
                if str(ch_id).isdigit():
                    channel = client.get_channel(int(ch_id))
                    if channel:
                        try:
                            await channel.delete(reason="3 days auto cleanup")
                            logger.warning(f"🧹 自动清理：已删除 {CLEANUP_THRESHOLD_DAYS} 天前的结单频道 #{ch_name}")
                        except discord.Forbidden:
                            logger.error(f"⚠️ 权限不足无法删除频道 #{ch_name}")
                cursor.execute("DELETE FROM tickets WHERE discord_channel_id=?", (ch_id,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"⚠️ 自动清理任务异常: {e}", exc_info=True)
        await asyncio.sleep(3600)

# ================= Bot 事件处理 =================
@client.event
async def on_ready():
    init_db()
    logger.info(f'✅ 机器人 V6.0 (智能两阶段Pipeline + DeepSeek V4 Flash) 已启动！')
    client.loop.create_task(check_webui_replies())
    client.loop.create_task(auto_cleanup_task())

@client.event
async def on_message(message):
    # 【修复】完全跳过自身消息，防止自回复循环
    if message.author == client.user: return
    if not message.guild: return

    content = extract_content(message)
    if not content: return
    channel_name = message.channel.name
    channel_id = message.channel.id
    cat_id = getattr(message.channel, 'category_id', None)

    # 安全检查：DM/未缓存用户可能是 User 对象而非 Member（无 roles 属性）
    if isinstance(message.author, discord.Member):
        is_staff = any(role in STAFF_ROLES for role in [r.name for r in message.author.roles])
    else:
        is_staff = False
    is_bot = message.author.bot

    # $delete 手动删除指令
    if content.strip().lower() == '$delete' and is_staff and cat_id in TICKET_CATEGORIES:
        try:
            await message.channel.delete(reason="Admin Manual Delete")
            save_ticket(message.author.id, message.id, append_text="👨‍💻 [Staff]: 执行了销毁指令", status='resolved', reply_status='replied', discord_channel_id=channel_id)
        except discord.Forbidden:
            await safe_reply(message, "⚠️ 我没有 Manage Channels 权限，无法删除此频道！")
        return

    # ================= 工单频道处理 =================
    if cat_id in TICKET_CATEGORIES:
        # Staff/Bot 发言：仅记录到工单，不触发 AI
        if is_staff or is_bot:
            append_str = f"🤖 [LagoFast - Bot]: {content}" if is_bot else f"👨‍💻 [Staff]: {content}"
            save_ticket(message.author.id, message.id, append_text=append_str, 
                        status='in_progress', reply_status='replied', discord_channel_id=channel_id, channel_name=channel_name)
            return  # 【修复】Staff/Bot 消息处理后直接返回，不再触发 AI

        # 普通用户发言：记录 + AI 回复
        if not is_staff and not is_bot:
            save_ticket(message.author.id, message.id, append_text=f"👤 [User]: {content}", 
                        status='pending', reply_status='unreplied', discord_channel_id=channel_id, channel_name=channel_name)

        # 获取频道历史上下文
        history_msgs = []
        async for past_msg in message.channel.history(limit=5):
            ext_text = extract_content(past_msg)
            if ext_text:
                sender = "System Panel" if past_msg.author.bot else past_msg.author.name
                history_msgs.insert(0, f"[{sender}]: {ext_text}")
                
        full_context_for_ai = "【上下文】\n" + "\n".join(history_msgs)

        async with message.channel.typing():
            intent, category, reply = await smart_ai_pipeline(full_context_for_ai, system_type="ticket")
            
        if intent == "FAQ" and reply:
            await safe_reply(message, reply)
            save_ticket(message.author.id, message.id, append_text=f"🤖 [LagoFast - Bot]: {reply}", 
                        status='in_progress', ai_response=reply, category="FAQ_Resolved", channel_name=channel_name, discord_channel_id=channel_id, reply_status='replied')
        
        elif intent == "NEED_HUMAN":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT last_notified_at FROM tickets WHERE discord_channel_id = ? AND status != 'resolved'", (str(channel_id),))
            row = cursor.fetchone()
            can_notify = True
            if row and row[0]:
                last_time = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - last_time < timedelta(hours=24):
                    can_notify = False
            conn.close()
            
            if can_notify:
                notify_msg = reply or f"🤖 I have notified admin <@{ADMIN_USER_ID}> to assist you."
                await safe_reply(message, notify_msg)
                save_ticket(message.author.id, message.id, append_text=f"🤖 [LagoFast - Bot]: 通知了管理员", 
                            status='pending', category=category, channel_name=channel_name, discord_channel_id=channel_id, update_notify_time=True)
            else:
                logger.info(f"⏳ 频道 #{channel_name} 在 24 小时内已通知过管理员，本次静默记录。")
                save_ticket(message.author.id, message.id, append_text=f"👤 [User]: {content}", 
                            status='pending', category=category, channel_name=channel_name, discord_channel_id=channel_id)
            
        elif intent == "CHITCHAT" and reply:
            await safe_reply(message, reply)
            save_ticket(message.author.id, message.id, append_text=f"🤖 [LagoFast - Bot]: {reply}", 
                        status='in_progress', category="Chitchat", channel_name=channel_name, discord_channel_id=channel_id, reply_status='replied')

        elif intent == "TOXIC":
            logger.warning(f"⚠️ 检测到违规内容 - 频道: #{channel_name}, 用户: {message.author}")
            save_ticket(message.author.id, message.id, append_text=f"⚠️ [System]: 检测到违规内容", 
                        status='in_progress', category="Toxic", channel_name=channel_name, discord_channel_id=channel_id)

    # ================= 社区频道处理（智能 AI 觉醒） =================
    elif channel_id in CHAT_CHANNEL_IDS:
        if not is_staff and not is_bot:
            async with message.channel.typing():
                intent, category, reply = await smart_ai_pipeline(content, system_type="chat")

            if intent == "PARTIAL_ANSWER" and reply:
                # AI 可以在社区里直接给部分解答
                await safe_reply(message, reply)
                combined_name = f"{channel_name}-{message.author.display_name}"
                chat_ticket_id = f"CHAT_{channel_id}_{message.id}"
                save_ticket(user_id=message.author.id, message_id=message.id, 
                            append_text=f"👤 [User]: {content}\n🤖 [小L]: {reply}", 
                            status='chat_alert', category=COMMUNITY_CATEGORY, 
                            channel_name=combined_name, discord_channel_id=chat_ticket_id, 
                            reply_status='replied')

            elif intent == "NEED_HUMAN":
                await safe_reply(message, f"Please click <#{SUPPORT_TICKET_CHANNEL_ID}> to open a ticket, we can help you!")
                combined_name = f"{channel_name}-{message.author.display_name}"
                chat_ticket_id = f"CHAT_{channel_id}_{message.id}"
                save_ticket(user_id=message.author.id, message_id=message.id, 
                            append_text=f"👤 [User]: {content}", 
                            status='chat_alert', category=COMMUNITY_CATEGORY, 
                            channel_name=combined_name, discord_channel_id=chat_ticket_id, 
                            reply_status='unreplied')

            elif intent == "CHITCHAT" and reply:
                await safe_reply(message, reply)

client.run(BOT_TOKEN)
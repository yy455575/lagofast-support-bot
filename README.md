# LagoFast Discord 客服系统

一个基于 Discord 的智能客服机器人系统，支持工单管理、AI 智能回复、社区监控和 WebUI 管理后台。

## 功能特性

- 🤖 **两阶段 AI Pipeline**：先意图分类 → 再精准回复，使用 DeepSeek V4 Flash 大模型
- 📋 **工单系统**：自动记录用户消息、AI 回复、管理员介入
- 📚 **FAQ 知识库**：支持智能检索与缓存，回答常见问题
- 🌐 **多语言支持**：自动检测用户语言并使用对应语言回复
- 🏘️ **社区智能监控**：在社区频道自动识别并回答用户问题
- 🗑️ **工单自动清理**：3 天无活跃的已结工单自动删除
- 🖥️ **WebUI 管理后台**：基于 Streamlit 的远程管理界面

## 快速开始

### 环境要求

- Python 3.9+
- Discord Bot Token
- DeepSeek API Key

### 安装

```bash
# 克隆项目
git clone <你的仓库地址>
cd DCworkflow

# 安装依赖
pip install -r requirements.txt
```

### 配置

复制 `.env.example` 为 `.env` 并填写配置：

```env
# Discord Bot Token
BOT_TOKEN=你的_Discord_Bot_Token

# DeepSeek API Key
DEEPSEEK_API_KEY=你的_DeepSeek_API_Key
```

### 运行

```bash
# 启动 Discord Bot
python bot.py

# 启动 WebUI 管理后台
streamlit run webui.py
```

## 项目结构

| 文件 | 说明 |
|------|------|
| `bot.py` | Discord 机器人主程序（两阶段 AI Pipeline） |
| `webui.py` | Streamlit WebUI 管理后台 |
| `init_db.py` | 数据库初始化脚本 |
| `import_faq.py` | FAQ CSV 导入脚本 |
| `update_db.py` | 数据库更新脚本（含 v2、v2.1 版本） |
| `fix_db.py` | 数据库修复脚本 |
| `cmd_queue.py` | WebUI 指令队列处理 |
| `migrate.py` | 数据库迁移脚本 |

## 核心配置

在 `bot.py` 中配置：

- `TICKET_CATEGORIES`：工单分类目录 ID 列表
- `CHAT_CHANNEL_IDS`：社区监控频道 ID 列表
- `ADMIN_USER_ID`：需要通知的管理员用户 ID
- `STAFF_ROLES`：客服/管理员角色名列表

## 技术栈

- [discord.py](https://github.com/Rapptz/discord.py) - Discord API 封装
- [DeepSeek API](https://platform.deepseek.com/) - AI 大模型（deepseek-v4-flash）
- [Streamlit](https://streamlit.io/) - WebUI 框架
- SQLite - 数据存储

## 协作开发

1. 所有敏感配置放在 `.env` 文件中（已被 `.gitignore` 排除，不会提交到 GitHub）
2. 数据库文件 `*.db` 不会被提交，请在服务器上运行 `init_db.py` 初始化
3. 使用分支开发 + Pull Request 合并代码
4. FAQ 数据使用 `import_faq.py` 从 CSV 导入

## 许可证

私有项目，仅供内部使用。
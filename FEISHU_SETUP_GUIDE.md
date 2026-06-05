# 🚀 飞书版「第二大脑」知识库 — 完整搭建指南

> 基于 Andrej Karpathy 的知识管理理念，将 Obsidian + Codex 方案完整迁移到飞书生态。
> **核心优势：云端实时同步、多端无缝协作、飞书原生工具链。**

---

## 📋 目录

1. [架构概览](#1-架构概览)
2. [Phase 1：飞书应用配置](#2-phase-1飞书应用配置)
3. [Phase 2：知识库搭建](#3-phase-2知识库搭建)
4. [Phase 3：多维表格搭建](#4-phase-3多维表格搭建)
5. [Phase 4：个人主页仪表盘](#5-phase-4个人主页仪表盘)
6. [Phase 5：代码部署](#6-phase-5代码部署)
7. [Phase 6：定时任务配置](#7-phase-6定时任务配置)
8. [Phase 7：飞书 Bot 配置](#8-phase-7飞书-bot-配置)
9. [日常使用指南](#9-日常使用指南)

---

## 1. 架构概览

```
你的 Mac（Claude Code AI 引擎）
    │
    ├── GitHub Actions（云端定时任务）
    │   ├── 每天 7:00 → 抓取热点 + 发布简报
    │   ├── 每天 12:00 → 午间更新
    │   ├── 每天 19:00 → 晚间汇总
    │   └── 每周日 21:00 → 周报复盘
    │
    ├── macOS launchd（本地实时任务）
    │   ├── 每小时 → 天气同步
    │   └── 每 6 小时 → GitHub 统计
    │
    └── Webhook Server（Bot 交互）
        ├── "番茄" → 开始专注记录
        ├── "打卡" → 每日习惯打卡
        └── "灵感" → 快速捕获想法
            │
            ▼
    ╔══════════════════════════════════╗
    ║       飞书云端（实时同步）       ║
    ║                                  ║
    ║  📚 第二大脑（知识库）           ║
    ║  📊 个人操作系统（多维表格）      ║
    ║  📄 个人主页（仪表盘文档）       ║
    ║  🤖 第二大脑 Bot（消息交互）     ║
    ║  📅 飞书日历                     ║
    ╚══════════════════════════════════╝
            │
    ┌───────┼────────┬────────┐
    ▼       ▼        ▼        ▼
  桌面端  手机端   Web端   平板端
```

---

## 2. Phase 1：飞书应用配置

### 2.1 创建飞书自建应用

1. 打开 [飞书开放平台](https://open.feishu.cn/app)
2. 点击「创建企业自建应用」
3. 填写：
   - **应用名称**：`第二大脑`
   - **应用描述**：`AI 驱动的个人知识库管理系统`
4. 创建后进入应用详情页

### 2.2 获取凭证

在应用页面「凭证与基础信息」中记录：

```
FEISHU_APP_ID     = cli_xxxxxxxxxxxx
FEISHU_APP_SECRET = xxxxxxxxxxxxxxxxxxxx
```

### 2.3 配置权限

在「权限管理」中添加以下权限：

| 权限 | 用途 |
|------|------|
| `wiki:wiki` | 读写知识库 |
| `docx:document` | 创建/编辑文档 |
| `bitable:app` | 读写多维表格 |
| `im:message` | 发送机器人消息 |
| `im:message:send_as_bot` | 以 Bot 身份发送消息 |
| `calendar:calendar` | 读写日历 |

> ⚠️ 每次添加权限后需要「发布新版本」并让管理员审批。

### 2.4 发布应用

1. 点击「创建版本」
2. 填写版本号 `1.0.0` 和更新说明
3. 提交发布
4. **让飞书管理员审批通过**（如果是个人版飞书，自动通过）

---

## 3. Phase 2：知识库搭建

### 3.1 创建知识库

1. 打开飞书 → 左侧栏「知识库」
2. 点击「创建知识库」
3. 名称：`第二大脑`
4. 描述：AI 驱动的自生长知识库
5. 创建后记录 **知识库空间 ID**（从 URL 中获取：`https://xxx.feishu.cn/wiki/space/{SPACE_ID}`）

```
FEISHU_SPACE_ID = xxxxxxxxxxxx
```

### 3.2 搭建节点树

创建以下节点结构（复制粘贴到知识库中创建页面）：

```
第二大脑（知识库根节点）
│
├── 📥 1-INBOX（收件箱）
│   ├── 说明：自动抓取的待分类素材存放于此
│   └── 每日由 AI 自动归档重要资讯
│
├── 🧠 2-知识图谱
│   ├── 🤖 AI & 大模型
│   │   └── 基础模型、Agent、训练推理、多模态
│   ├── 💻 半导体 & 硬件
│   │   └── GPU、芯片制程、光刻、服务器
│   ├── 🦾 机器人 & 自动驾驶
│   │   └── 人形机器人、Tesla FSD、无人机
│   ├── 💰 商业 & 创投
│   │   └── 融资、IPO、收购、市值分析
│   ├── 🎨 产品 & 设计
│   │   └── App 更新、UX 设计、交互创新
│   ├── 🔬 科研前沿
│   │   └── 论文精读、学术突破、前沿探索
│   └── 🌱 个人成长
│       └── 效率方法、学习笔记、思维模型
│
├── 📰 3-每日简报
│   ├── 2026-W23（按周自动归档）
│   │   ├── 2026-06-05 日报
│   │   └── 2026-06-04 日报
│   └── ...
│
├── 📊 4-每周复盘
│   ├── 2026-W23 周报
│   └── ...
│
├── 🎯 5-输出成果
│   ├── 深度分析
│   ├── 演讲 / PPT
│   └── 视频脚本
│
└── ⚙️ 6-元知识
    ├── 分类体系说明
    ├── 标签词典
    └── AI 处理规则
```

---

## 4. Phase 3：多维表格搭建

### 4.1 创建工作区

1. 飞书 → 新建 → 多维表格
2. 名称：`个人操作系统`
3. 记录 **Bitable App Token**（URL 中 `/base/{TOKEN}` 部分）

```
FEISHU_BITABLE_TOKEN = xxxxxxxxxxxx
```

### 4.2 创建数据表

在「个人操作系统」中创建以下 7 张表：

#### 表 1：📋 任务管理

| 字段名 | 类型 | 配置 |
|--------|------|------|
| 任务名称 | 文本 | - |
| 状态 | 单选 | 待办 / 进行中 / 已完成 / 已归档 |
| 优先级 | 单选 | P0 / P1 / P2 / P3 |
| 所属项目 | 关联 → 项目日志表 | - |
| 截止日期 | 日期 | - |
| 预估番茄 | 数字 | - |
| 实际耗时(分) | 数字 | - |
| 标签 | 多选 | - |

**视图配置：**
- 📋 看板视图：按「状态」分组
- 📅 日历视图：按「截止日期」
- 🔥 优先级视图：筛选 P0+P1

#### 表 2：📈 项目日志

| 字段名 | 类型 | 配置 |
|--------|------|------|
| 项目名称 | 文本 | - |
| 状态 | 单选 | 规划中 / 进行中 / 暂停 / 已完成 |
| 开始日期 | 日期 | - |
| 目标完成日 | 日期 | - |
| 进度% | 进度条 | - |
| 今日更新 | 多行文本 | - |
| 知识库链接 | URL | - |

**视图配置：**
- 📊 甘特图：开始日期 → 目标完成日
- 📋 看板视图：按「状态」

#### 表 3：🍅 番茄专注记录

| 字段名 | 类型 | 配置 |
|--------|------|------|
| 日期 | 日期 | - |
| 开始时间 | 文本 | - |
| 时长(分) | 数字 | 默认 25 |
| 关联任务 | 关联 → 任务管理 | - |
| 中断次数 | 数字 | 默认 0 |
| 完成状态 | 单选 | 进行中 / 完成 / 中断 |

**视图配置：**
- 📊 日历热力图：按日期聚合，颜色按完成数

#### 表 4：✅ 每日打卡

| 字段名 | 类型 | 配置 |
|--------|------|------|
| 日期 | 日期 | - |
| 自律打卡 | 多选 | 早起 / 冥想 / 阅读 / 运动 / 不熬夜 / 写作 / 学习 |
| 健身记录 | 多行文本 | - |
| 背单词数 | 数字 | - |
| 心情评分 | 数字 | 1-5 星 |
| 日记内容 | 多行文本 | - |
| 今日总结 | 多行文本 | AI 自动生成 |

**视图配置：**
- 📅 日历视图：显示打卡完成情况
- 📊 表单视图：方便手机快速打卡

#### 表 5：📊 知识统计

| 字段名 | 类型 | 配置 |
|--------|------|------|
| 日期 | 日期 | - |
| 新增页面数 | 数字 | - |
| 阅读文章数 | 数字 | - |
| 输出字数 | 数字 | - |
| GitHub 仓库统计 | 多行文本 | JSON 格式 |
| 技能学习进度 | 百分比 | - |

#### 表 6：⏳ 倒计时

| 字段名 | 类型 | 配置 |
|--------|------|------|
| 事件名称 | 文本 | - |
| 目标日期 | 日期 | - |
| 剩余天数 | 公式 | `DATETIME_DIFF([目标日期], TODAY(), "days")` |
| 类型 | 单选 | 考试 / 项目截止 / 旅行 / 其他 |

#### 表 7：🌤️ 天气记录

| 字段名 | 类型 | 配置 |
|--------|------|------|
| 日期 | 日期 | - |
| 城市 | 文本 | - |
| 天气 | 文本 | - |
| 温度范围 | 文本 | - |
| 备注 | 文本 | - |

### 4.3 记录各表的 Table ID

每张表创建后，点击表名旁的「...」→「更多」→ 复制表 ID：

```
FEISHU_TASK_TABLE_ID      = tblxxxxxxxxxxxx  (表1)
FEISHU_PROJECT_TABLE_ID   = tblxxxxxxxxxxxx  (表2)
FEISHU_POMODORO_TABLE_ID  = tblxxxxxxxxxxxx  (表3)
FEISHU_DAILY_TABLE_ID     = tblxxxxxxxxxxxx  (表4)
FEISHU_STATS_TABLE_ID     = tblxxxxxxxxxxxx  (表5)
FEISHU_COUNTDOWN_TABLE_ID = tblxxxxxxxxxxxx  (表6)
FEISHU_WEATHER_TABLE_ID   = tblxxxxxxxxxxxx  (表7)
```

---

## 5. Phase 4：个人主页仪表盘

### 5.1 创建个人主页文档

1. 飞书 → 新建 → 文档
2. 标题：`🏠 个人主页`
3. 固定在左侧栏（右键 → 固定）

### 5.2 嵌入多维表格视图

在文档中使用「嵌入」功能：

```
🏠 个人主页
═══════════════════════════════════════

📅 今日概览 - {今天的日期}
────────────────────────────────────
[嵌入：任务管理 - 看板视图 - 筛选今日到期]
[嵌入：每日打卡 - 今日记录]

🍅 番茄专注
────────────────────────────────────
[嵌入：番茄专注记录 - 日历热力图]

📈 项目进展
────────────────────────────────────
[嵌入：项目日志 - 甘特图视图]

⏳ 倒计时
────────────────────────────────────
[嵌入：倒计时表 - 列表视图]

🌤️ 天气
────────────────────────────────────
[嵌入：天气记录 - 今日天气]

🔗 快捷入口
────────────────────────────────────
📚 [第二大脑知识库](飞书链接)
📰 [今日简报](飞书链接)
📊 [个人操作系统](飞书链接)
```

> 💡 飞书文档的嵌入块是**实时更新**的 — 当多维表格数据变化时，嵌入视图自动刷新。

---

## 6. Phase 5：代码部署

### 6.1 克隆/更新仓库

```bash
cd /Users/apple/tech-news-daily
```

所有脚本已就位：
- `feishu_sync.py` — 飞书 API 客户端
- `feishu_pipeline.py` — AI 管线（抓取→分类→发布）
- `feishu_webhook_server.py` — Bot Webhook 服务
- `weather_sync.py` — 天气同步
- `github_stats_sync.py` — GitHub 统计同步

### 6.2 配置 GitHub Secrets

在 GitHub 仓库设置 → Secrets and variables → Actions → 添加：

| Secret 名称 | 值 |
|-------------|-----|
| `FEISHU_APP_ID` | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | 飞书应用 App Secret |
| `FEISHU_SPACE_ID` | 知识库空间 ID |
| `FEISHU_BITABLE_TOKEN` | 多维表格 Token |
| `FEISHU_STATS_TABLE_ID` | 知识统计表 ID |
| `FEISHU_WEBHOOK_URL` | Bot Webhook URL（可选） |

### 6.3 更新 requirements.txt

```bash
cd /Users/apple/tech-news-daily
```

编辑 `requirements.txt`：
```
feedparser>=6.0.0
requests>=2.28.0
python-dotenv>=1.0.0
```

### 6.4 推送代码

```bash
git add -A
git commit -m "feat: 飞书知识库完整管线 - AI Pipeline + Webhook + 实时同步"
git push
```

---

## 7. Phase 6：定时任务配置

### 7.1 GitHub Actions（自动运行）

推送后即生效，定时规则：

| 任务 | 时间 | Workflow 文件 |
|------|------|--------------|
| 每日简报 x3 | 7:30 / 12:00 / 19:00 CST | `feishu-daily.yml` |
| 每周复盘 | 周日 21:00 CST | `feishu-weekly.yml` |
| 每日新闻邮件 | 6:10 CST | `daily-news.yml`（已有） |

### 7.2 macOS launchd（本地任务）

> ⚠️ 先编辑 plist 文件，填入正确的环境变量值！

编辑这些文件填入你的飞书凭证：
- `~/Library/LaunchAgents/com.user.feishu-weather.plist`
- `~/Library/LaunchAgents/com.user.feishu-github-stats.plist`
- `~/Library/LaunchAgents/com.user.feishu-webhook.plist`

加载服务：

```bash
# 天气同步（每小时）
launchctl load ~/Library/LaunchAgents/com.user.feishu-weather.plist

# GitHub 统计（每 6 小时）
launchctl load ~/Library/LaunchAgents/com.user.feishu-github-stats.plist

# Webhook 服务（常驻）
launchctl load ~/Library/LaunchAgents/com.user.feishu-webhook.plist
```

管理命令：

```bash
# 查看服务状态
launchctl list | grep feishu

# 卸载
launchctl unload ~/Library/LaunchAgents/com.user.feishu-weather.plist

# 查看日志
tail -f /tmp/feishu-weather.log
tail -f /tmp/feishu-webhook.log
```

---

## 8. Phase 7：飞书 Bot 配置

### 8.1 创建 Bot 并获取 Webhook URL

1. 在飞书群聊中 → 设置 → 群机器人 → 添加机器人
2. 选择「自定义机器人」
3. 名称：`第二大脑 Bot`
4. 复制 **Webhook URL**：

```
FEISHU_WEBHOOK_URL = https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxx
```

### 8.2 配置交互能力（可选，需要公网 IP）

如果需要通过 @Bot 交互控制番茄钟和打卡：

1. 使用 ngrok 暴露本地 Webhook 服务：
```bash
brew install ngrok
ngrok http 8888
```

2. 在飞书开放平台 → 应用详情 → 事件订阅：
   - 请求网址：`https://xxxx.ngrok.io/webhook`
   - 订阅事件：`im.message.receive_v1`

3. 配置环境变量后启动服务：
```bash
python3 /Users/apple/tech-news-daily/feishu_webhook_server.py --port 8888
```

### 8.3 Bot 命令清单

| 命令 | 功能 |
|------|------|
| `番茄 [任务名]` | 开始 25 分钟番茄专注 |
| `结束番茄` | 完成当前番茄 |
| `打卡 [习惯]` | 每日习惯打卡 |
| `灵感 [内容]` | 快速捕获想法到 INBOX |
| `统计` | 查看今日概览 |
| `帮助` | 显示命令列表 |

---

## 9. 日常使用指南

### 9.1 每日工作流

```
早上 6:10  📧 QQ邮箱收到新闻邮件
早上 7:30  📰 飞书知识库发布第一次简报
          🏠 打开飞书「个人主页」查看今日概览
上午      🍅 开始番茄专注 → Bot 交互或手动记录
中午 12:00 📰 午间更新简报
下午      📝 学习/工作中捕获灵感 → @Bot「灵感 xxx」
晚上 19:00 📰 晚间简报总结
睡前      ✅ 每日打卡 → 手机飞书表单视图快速填写
          飞书实时同步，所有数据云端保存
```

### 9.2 每周复盘

```
周日 21:00  📊 飞书知识库自动生成周报
周一        📖 打开周报，回顾本周 TOP 5 进展
            🎯 更新下周目标和项目计划
```

### 9.3 知识库自生长循环

```
1. AI 自动抓取 → 📥 INBOX
2. AI 自动分类 → 🧠 知识图谱各节点
3. AI 自动总结 → 📰 每日简报
4. AI 自动复盘 → 📊 每周周报
5. 手动深度加工 → 🎯 输出成果
6. 反馈到 AI 规则 → ⚙️ 元知识更新
       ↓
   循环迭代 ↑
```

### 9.4 实时性保证

| 数据类型 | 更新方式 | 延迟 |
|----------|----------|------|
| 知识库内容 | GitHub Actions 定时 | 最长 5 小时 |
| 多维表格数据 | API 实时写入 + 飞书同步 | 秒级 |
| 天气信息 | launchd 每小时 | 最长 1 小时 |
| GitHub 统计 | launchd 每 6 小时 | 最长 6 小时 |
| 嵌入视图 | 飞书原生实时刷新 | 秒级 |
| 跨设备同步 | 飞书云端自动 | 秒级 |

---

## 🔧 故障排查

### 问题 1：GitHub Actions 失败

1. 检查 Secrets 是否全部配置
2. 检查飞书应用是否已发布并通过审批
3. 在 Actions 页面查看错误日志

### 问题 2：launchd 服务未运行

```bash
# 查看错误日志
cat /tmp/feishu-weather.err

# 手动测试
python3 /Users/apple/tech-news-daily/weather_sync.py --city Shanghai
```

### 问题 3：飞书 API 调用失败

- 确认 token 未过期（自动刷新）
- 确认应用权限已审批
- 确认 API 调用频率未超限

---

## 📁 项目文件清单

```
tech-news-daily/
├── send_news.py                  # 原有：邮件新闻
├── feishu_sync.py                # 🆕 飞书 API 客户端
├── feishu_pipeline.py            # 🆕 AI 管线主脚本
├── feishu_webhook_server.py      # 🆕 Bot Webhook 服务
├── weather_sync.py               # 🆕 天气同步
├── github_stats_sync.py          # 🆕 GitHub 统计同步
├── FEISHU_SETUP_GUIDE.md         # 🆕 本搭建指南
├── requirements.txt              # 依赖列表
├── README.md                     # 原有说明
└── .github/workflows/
    ├── daily-news.yml            # 原有：邮件定时
    ├── feishu-daily.yml          # 🆕 每日简报定时
    └── feishu-weekly.yml         # 🆕 每周复盘定时

~/Library/LaunchAgents/
├── com.user.feishu-weather.plist     # 🆕 天气同步定时
├── com.user.feishu-github-stats.plist# 🆕 GitHub 统计定时
└── com.user.feishu-webhook.plist     # 🆕 Webhook 服务
```

---

> 🎉 **完成！** 你已经拥有一个基于飞书的、实时更新的自生长知识库系统。
> 它会在云端 7x24 运行，自动抓取、分类、复盘，而你只需要专注于深度思考和创作。

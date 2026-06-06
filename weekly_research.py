#!/usr/bin/env python3
"""
飞书知识库 - 每周深度研究脚本
================================
每三/五/日自动运行，从网络中搜索与知识库主题相关的内容，
生成深度研究摘要并更新飞书知识库对应节点。

运行模式：
    python weekly_research.py              # 自动按当天星期选择主题
    python weekly_research.py ai-ml        # 手动指定主题
    python weekly_research.py --list       # 列出所有主题

主题与知识库节点映射：
    ai-ml      → AI & 机器学习
    coding     → 编程技术
    tech-biz   → 科技商业
    product    → 产品设计
    opensource → 开源动态
    tools      → 效率工具
    photo      → 摄影摄像技巧
"""

import os
import sys
import json
import re
import ssl
import subprocess
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from collections import OrderedDict

import feedparser
import urllib.request

from feishu_sync import FeishuClient

# ── 常量 ──────────────────────────────────────────────
CST = timezone(timedelta(hours=8))
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# ── 加载 .env ─────────────────────────────────────────
_env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_file):
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip()

FEISHU_SPACE_ID = os.environ.get("FEISHU_SPACE_ID", "")

# ── 主题定义 ──────────────────────────────────────────
TOPICS = {
    "ai-ml": {
        "name": "AI & 机器学习",
        "icon": "🤖",
        "node_token": "LPSdwYixHivkLKkfmkpc9b8anpl",
        "doc_id": "Pls2dYI9fo9QrkxjibDc9qrun8b",
        "keywords": [
            "AI", "GPT", "OpenAI", "大模型", "LLM", "Claude", "Gemini",
            "DeepSeek", "Agent", "transformer", "neural network", "深度学习",
            "机器学习", "RLHF", "RAG", "fine-tuning", "AGI", "Anthropic",
            "Llama", "Mistral", "diffusion", "多模态", "推理", "alignment",
            "NLP", "computer vision", "token", "embedding", "向量数据库",
            "langchain", "crewai", "autogen", "文心一言", "通义千问", "ChatGPT",
            "vLLM", "ollama", "sglang", "prompt engineering", "提示工程",
        ],
        "rss_extra": [
            "https://blog.research.google/feeds/posts/default",
            "https://openai.com/blog/rss.xml",
            "https://huggingface.co/blog/feed.xml",
        ],
    },
    "coding": {
        "name": "编程技术",
        "icon": "💻",
        "node_token": "BWs8wavMkitEtUkAjq2cEgLwnRg",
        "doc_id": "KFqPd8YNzofVdlxbdgJcOcDnnMf",
        "keywords": [
            "Python", "Rust", "Go", "TypeScript", "JavaScript", "Rust",
            "代码", "编程", "框架", "架构", "API", "GitHub", "开源",
            "编译器", "WebAssembly", "Kubernetes", "Docker", "数据库",
            "PostgreSQL", "SQLite", "Redis", "GraphQL", "REST", "微服务",
            "React", "Vue", "Next.js", "后端", "前端", "全栈", "DevOps",
            "CI/CD", "测试", "性能优化", "并发", "async", "CSS", "HTML",
        ],
        "rss_extra": [
            "https://github.blog/feed/",
            "https://blog.rust-lang.org/feed.xml",
        ],
    },
    "tech-biz": {
        "name": "科技商业",
        "icon": "💼",
        "node_token": "K7C8wGuOOiw1qAkHufdcwNASnYe",
        "doc_id": "BhJMdjE7No6DZGxWthNcV1Jfn7d",
        "keywords": [
            "融资", "IPO", "上市", "收购", "市值", "股价", "投资",
            "创业", "startup", "创始人", "独角兽", "VC", "PE",
            "季度财报", "营收", "利润", "裁员", "扩张", "市场份额",
            "Apple", "Google", "Microsoft", "Meta", "Amazon", "Nvidia",
            "Tesla", "ByteDance", "字节", "腾讯", "阿里", "百度",
            "芯片", "半导体", "SaaS", "云服务", "监管", "反垄断",
        ],
        "rss_extra": [],
    },
    "product": {
        "name": "产品设计",
        "icon": "🎨",
        "node_token": "Aou5wxOt3iPscZk4Z0nc74kTngb",
        "doc_id": "UekrdwKWboWsnRxFIdrcFq41nKg",
        "keywords": [
            "产品", "设计", "UX", "UI", "用户体验", "交互设计",
            "App", "发布", "更新", "feature", "产品经理", "原型",
            "Figma", "Sketch", "用户研究", "A/B测试", "增长",
            "onboarding", "留存", "转化率", "设计系统", "Design Token",
            "accessibility", "响应式", "暗黑模式", "动效", "微交互",
        ],
        "rss_extra": [],
    },
    "opensource": {
        "name": "开源动态",
        "icon": "🌟",
        "node_token": "BLkswzBhYi0UqYkrukpcrLY8nyg",
        "doc_id": "CM5JdzWpoodHJvxfrXHc4gWYnfg",
        "keywords": [
            "开源", "GitHub", "Linux", "基金会", "License",
            "Apache", "MIT", "GPL", "CNCF", "Linux Foundation",
            "Star", "Fork", "PR", "maintainer", "贡献者",
            "Webpack", "Vite", "Node.js", "Deno", "Bun",
            "TensorFlow", "PyTorch", "Kubernetes", "Docker",
            "RISC-V", "Blender", "Godot", "Homebrew",
        ],
        "rss_extra": [
            "https://opensource.googleblog.com/feeds/posts/default",
        ],
    },
    "tools": {
        "name": "效率工具",
        "icon": "🛠️",
        "node_token": "FAiGwREC1iRCTWk9unNcWvaEnrd",
        "doc_id": "DyhndZflWozdcix6HzgcZ3MQn3f",
        "keywords": [
            "工具", "效率", "自动化", "Notion", "Obsidian", "插件",
            "VSCode", "terminal", "CLI", "Alfred", "Raycast",
            "shortcut", "工作流", "模板", "GTD", "番茄钟",
            "Markdown", "笔记", "知识管理", "PKM", "second brain",
            "API", "webhook", "zapier", "ifttt", "make",
            "日历", "待办", "项目管理", "Linear", "Notion",
        ],
        "rss_extra": [],
    },
    "photo": {
        "name": "摄影摄像技巧",
        "icon": "📷",
        "node_token": None,  # 独立文档，不在 wiki 中
        "doc_id": "PsBmduLtWoGyr5xnYStc0fInnMb",
        "keywords": [
            "摄影", "相机", "镜头", "后期", "Lightroom", "Photoshop",
            "视频", "拍摄", "构图", "曝光", "光圈", "快门", "ISO",
            "Sony", "Canon", "Nikon", "Fujifilm", "iPhone摄影",
            "电影感", "调色", "DaVinci", "Premiere", "稳定器",
            "无人机", "航拍", "Vlog", "cinematography", "filmmaking",
            "photography", "camera", "lens", "tutorial",
        ],
        "rss_extra": [
            "https://petapixel.com/feed/",
            "https://www.dpreview.com/feed",
        ],
    },
}

# ── 基础 RSS 源（与 feishu_pipeline.py 共享）───────
RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "Wired": "https://www.wired.com/feed/rss",
    "Hacker News": "https://hnrss.org/frontpage?count=20",
    "The Register": "https://www.theregister.com/headlines.atom",
    "36氪": "https://36kr.com/feed",
    "IT之家": "https://www.ithome.com/rss/",
    "机器之心": "https://www.jiqizhixin.com/rss",
    "雷锋网": "https://www.leiphone.com/feed",
    "少数派": "https://sspai.com/feed",
}

# ── 研究状态追踪 ─────────────────────────────────────
STATE_FILE = os.path.join(os.path.dirname(__file__), "research_state.json")


def load_state() -> Dict:
    """加载研究状态，追踪已处理的内容"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_research": {}, "seen_urls": [], "research_count": 0}


def save_state(state: Dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ── RSS 抓取 ──────────────────────────────────────────

def fetch_feed(url: str, source_name: str) -> List[Dict]:
    """抓取单个 RSS 源"""
    entries = []
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        data = urllib.request.urlopen(req, timeout=15, context=_SSL_CONTEXT).read()
        feed = feedparser.parse(data)

        for entry in feed.entries[:20]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "") or entry.get("description", "")
            summary = re.sub(r"<[^>]+>", "", summary)[:500]

            if not title or not link:
                continue

            pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
            entry_date = None
            if pub_date:
                try:
                    entry_date = datetime(*pub_date[:6], tzinfo=CST)
                except Exception:
                    pass

            entries.append({
                "source": source_name,
                "title": title,
                "link": link,
                "summary": summary,
                "date": entry_date,
            })
    except Exception as e:
        print(f"    ⚠️  {source_name}: {e}")

    return entries


def fetch_all_for_topic(topic_key: str) -> List[Dict]:
    """为特定主题抓取所有 RSS 源并过滤"""
    topic = TOPICS[topic_key]
    keywords = topic.get("keywords", [])
    all_entries = []

    # 基础 RSS
    for source, url in RSS_FEEDS.items():
        print(f"    📡 {source} ...", end=" ", flush=True)
        entries = fetch_feed(url, source)
        print(f"{len(entries)} 条")
        all_entries.extend(entries)

    # 主题专属 RSS
    for url in topic.get("rss_extra", []):
        source = url.split("/")[2]
        print(f"    📡 {source} ...", end=" ", flush=True)
        entries = fetch_feed(url, source)
        print(f"{len(entries)} 条")
        all_entries.extend(entries)

    # 按关键词过滤
    keyword_lower = {k.lower() for k in keywords}
    matched = []
    for entry in all_entries:
        text = f"{entry['title']} {entry.get('summary', '')}".lower()
        score = sum(1 for kw in keyword_lower if kw.lower() in text)
        if score > 0:
            entry["keyword_score"] = score
            matched.append(entry)

    # 按关键词匹配度排序
    matched.sort(key=lambda e: e.get("keyword_score", 0), reverse=True)

    # 去重
    seen = OrderedDict()
    for entry in matched:
        key = re.sub(r"[^\w\s]", "", entry["title"].lower())[:80]
        if key not in seen or entry["keyword_score"] > seen[key].get("keyword_score", 0):
            seen[key] = entry

    return list(seen.values())


# ── 新鲜度检查 ────────────────────────────────────────

def filter_fresh(entries: List[Dict], state: Dict, days: int = 7) -> List[Dict]:
    """过滤出新鲜内容（最近N天 + 未处理过）"""
    cutoff = datetime.now(CST) - timedelta(days=days)
    seen_urls = set(state.get("seen_urls", []))

    fresh = []
    for entry in entries:
        url = entry.get("link", "")
        if url in seen_urls:
            continue
        date = entry.get("date")
        if date and date < cutoff:
            continue
        fresh.append(entry)

    return fresh


# ── AI 研究 ───────────────────────────────────────────

def build_research_prompt(topic: Dict, entries: List[Dict]) -> str:
    """构建研究 prompt"""
    today = datetime.now(CST).strftime("%Y年%m月%d日")

    articles_text = ""
    for i, e in enumerate(entries[:30]):
        articles_text += f"{i+1}. **[{e['source']}] {e['title']}**\n"
        articles_text += f"   链接: {e['link']}\n"
        if e.get('summary'):
            articles_text += f"   摘要: {e['summary'][:300]}\n"
        articles_text += "\n"

    return f"""你是知识管理研究助手。请基于以下最新资讯，为「{topic['name']}」主题生成一份深度研究简报。

## 当前日期
{today}

## 主题信息
- 名称: {topic['name']}
- 核心关键词: {', '.join(topic.get('keywords', [])[:20])}

## 最新相关资讯
{articles_text}

## 输出格式
请用以下 Markdown 结构输出（直接输出，不要代码块包裹）：

---
## 🔥 本周必关注 ({topic['name']})

（挑选 3 条最重要的内容，每条 2-3 句话解释为什么重要，附上链接）

## 📊 趋势观察

（1-2 个正在浮现的行业趋势，每个趋势用 3-5 句分析，结合具体案例）

## 🛠️ 值得尝试 / 值得读

（2-3 个具体的工具、项目、文章推荐，说明谁应该关注、怎么用）

## 💭 一句话总结

（用一句话概括本周这个领域最重要的事）
---

请确保每条推荐都附带了原文链接。中文输出。"""


def research_with_claude(topic_key: str, entries: List[Dict]) -> Optional[str]:
    """
    使用 Claude Code CLI 进行深度研究。
    将 RSS 内容作为上下文，Claude 进行分析和综合。
    """
    topic = TOPICS[topic_key]
    if not entries:
        print("    ⚠️  没有新鲜内容可供研究")
        return None

    prompt = build_research_prompt(topic, entries)
    print(f"    📤 发送 {len(entries[:30])} 条资讯给 AI 分析...")

    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ, "HOME": os.environ.get("HOME", "/Users/apple")},
        )

        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout.strip()
            # 清理可能的代码块标记
            output = re.sub(r'^```(?:markdown)?\s*\n?', '', output)
            output = re.sub(r'\n?```\s*$', '', output)
            return output
        else:
            print(f"    ⚠️  Claude CLI 返回异常 (code={result.returncode})")
            if result.stderr:
                print(f"    stderr: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print(f"    ⚠️  Claude CLI 超时")
        return None
    except FileNotFoundError:
        print(f"    ⚠️  Claude CLI 不可用")
        return None


# ── 飞书发布 ──────────────────────────────────────────

# 所有研究更新统一发布到这个 doc（每周回顾页面），不污染各主题的知识页
RESEARCH_LOG_DOC_ID = "GvxOd4mTIozWJuxxsrpc7HyxnZd"


def publish_research(client: FeishuClient, topic_key: str, research_content: str):
    """将研究报告追加到「每周回顾」页面，按日期和主题组织"""
    topic = TOPICS[topic_key]
    today = datetime.now(CST)
    date_str = today.strftime("%Y-%m-%d")
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    day_str = weekdays[today.weekday()]

    # 构建研究更新块（带主题标签和日期）
    block = (
        f"## {topic['icon']} {topic['name']} — {date_str}（{day_str}）\n\n"
        f"{research_content.strip()}"
    )

    try:
        client.append_doc_content(RESEARCH_LOG_DOC_ID, block, position="top")
        print(f"    ✅ 研究已发布到「每周回顾」: {topic['name']}")
        return True
    except Exception as e:
        print(f"    ❌ 发布失败: {e}")
        return False


# ── 主题选择 ──────────────────────────────────────────

def get_topics_for_today() -> List[str]:
    """根据星期几选择要研究的主题"""
    weekday = datetime.now(CST).weekday()  # 0=Mon, 2=Wed, 4=Fri, 6=Sun

    # 周三(2): AI, 编程, 开源
    # 周五(4): 科技商业, 产品, 效率工具
    # 周日(6): AI, 摄影, 开源
    schedule = {
        2: ["ai-ml", "coding", "opensource"],       # Wednesday
        4: ["tech-biz", "product", "tools"],          # Friday
        6: ["ai-ml", "photo", "opensource"],          # Sunday
    }

    return schedule.get(weekday, ["ai-ml"])  # fallback: just AI


# ── 主流程 ────────────────────────────────────────────

def research_topic(topic_key: str, state: Dict) -> Optional[str]:
    """对单个主题进行完整研究流程，返回研究内容"""
    topic = TOPICS.get(topic_key)
    if not topic:
        print(f"❌ 未知主题: {topic_key}")
        return None

    print(f"\n{'='*60}")
    print(f"{topic['icon']} 研究主题: {topic['name']}")
    print(f"{'='*60}")

    # 1. 抓取 RSS
    print("  📡 抓取 RSS 源...")
    entries = fetch_all_for_topic(topic_key)
    print(f"    关键词匹配: {len(entries)} 条")

    # 2. 过滤新鲜内容
    fresh = filter_fresh(entries, state, days=7)
    print(f"    新鲜未处理: {len(fresh)} 条")

    if len(fresh) < 3:
        print(f"    ⚠️  新鲜内容不足（< 3条），跳过 AI 分析")
        return None

    # 3. AI 分析
    print("  🤖 AI 深度分析...")
    research = research_with_claude(topic_key, fresh)
    if not research:
        return None

    print(f"    ✅ 研究完成 ({len(research)} 字符)")

    # 4. 发布到飞书
    print("  📤 发布到飞书...")
    client = FeishuClient()
    success = publish_research(client, topic_key, research)

    # 5. 更新状态
    if success:
        state["last_research"][topic_key] = datetime.now(CST).isoformat()
        state["research_count"] = state.get("research_count", 0) + 1
        seen = state.get("seen_urls", [])
        for entry in fresh[:50]:
            seen.append(entry["link"])
        state["seen_urls"] = seen[-500:]  # 保留最近 500 条

    return research


def main():
    state = load_state()

    # 解析参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            print("可用主题:")
            for k, v in TOPICS.items():
                print(f"  {k:12s} → {v['icon']} {v['name']}")
            return
        elif sys.argv[1] in TOPICS:
            topics = [sys.argv[1]]
        else:
            print(f"未知参数: {sys.argv[1]}")
            print(f"可用: {', '.join(TOPICS.keys())} 或 --list")
            sys.exit(1)
    else:
        topics = get_topics_for_today()

    today = datetime.now(CST)
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    print(f"\n{'='*60}")
    print(f"🧠 飞书知识库 - 每周深度研究")
    print(f"   日期: {today.strftime('%Y-%m-%d')} ({weekdays[today.weekday()]})")
    print(f"   主题: {', '.join(topics)}")
    print(f"   历史研究次数: {state.get('research_count', 0)}")
    print(f"{'='*60}")

    results = {}
    for topic_key in topics:
        try:
            content = research_topic(topic_key, state)
            results[topic_key] = "✅" if content else "⏭️ 跳过"
        except Exception as e:
            print(f"  ❌ {topic_key} 研究异常: {e}")
            results[topic_key] = f"❌ {e}"

    # 保存状态
    save_state(state)

    # 输出总结
    print(f"\n{'='*60}")
    print(f"📋 研究总结:")
    for k, v in results.items():
        name = TOPICS[k]['name']
        print(f"  {v}  {name}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

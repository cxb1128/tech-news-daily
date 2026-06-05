#!/usr/bin/env python3
"""
飞书知识库 AI Pipeline
=======================
每日运行的核心管线，串联以下流程：

1. 信息抓取：RSS 源 → 原始条目列表
2. AI 处理：Claude Code 做分类、摘要、打分、标签
3. 飞书发布：
   - 每日简报 → 飞书知识库「每日简报」节点
   - 分类内容 → 知识库「知识图谱」各分类节点
   - 统计信息 → 多维表格「知识统计」表
4. 飞书通知：通过 Bot Webhook 推送简报摘要

运行模式：
    python feishu_pipeline.py daily       # 每日简报
    python feishu_pipeline.py weekly      # 每周复盘
    python feishu_pipeline.py classify    # 仅分类（不发布简报）
    python feishu_pipeline.py sync-stats  # 仅同步统计数据
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import feedparser
import ssl
from feishu_sync import FeishuClient

# ── SSL 兼容处理 ─────────────────────────────────────
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# ── 加载 .env ─────────────────────────────────────────
_env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                if _k.strip() not in os.environ:
                    os.environ[_k.strip()] = _v.strip()

# ── 配置 ──────────────────────────────────────────────
CST = timezone(timedelta(hours=8))

# Feishu 配置 — 从环境变量读取
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_SPACE_ID = os.environ.get("FEISHU_SPACE_ID", "")  # 知识库空间 ID
FEISHU_BITABLE_TOKEN = os.environ.get("FEISHU_BITABLE_TOKEN", "")  # 多维表格 token
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")
FEISHU_DAILY_TABLE_ID = os.environ.get("FEISHU_DAILY_TABLE_ID", "")  # 每日打卡表
FEISHU_STATS_TABLE_ID = os.environ.get("FEISHU_STATS_TABLE_ID", "")  # 知识统计表

# 知识库节点结构（与实际 wiki 节点对应）
# 从 wiki_nodes.json 加载，如果有的话
_wiki_nodes_path = os.path.join(os.path.dirname(__file__), "wiki_nodes.json")
WIKI_NODES = {}
if os.path.exists(_wiki_nodes_path):
    with open(_wiki_nodes_path) as f:
        WIKI_NODES = json.load(f)

KNOWLEDGE_TREE = {
    "📥 收件箱": {
        "node_token": WIKI_NODES.get("📥 收件箱", ""),
        "parent": None,
        "description": "待分类的原始素材",
    },
    "📋 每日简报": {
        "node_token": WIKI_NODES.get("📋 每日简报", ""),
        "parent": None,
    },
    "📊 每周回顾": {
        "node_token": WIKI_NODES.get("📊 每周回顾", ""),
        "parent": None,
    },
    "🗂️ 分类归档": {
        "node_token": WIKI_NODES.get("🗂️ 分类归档", ""),
        "parent": None,
        "children": {
            "ai-ml": {"title": "AI & 机器学习", "node_token": WIKI_NODES.get("AI & 机器学习", ""),
                      "keywords": ["AI", "GPT", "OpenAI", "大模型", "LLM", "Claude", "Gemini", "DeepSeek", "Agent"]},
            "coding": {"title": "编程技术", "node_token": WIKI_NODES.get("编程技术", ""),
                       "keywords": ["代码", "编程", "开源", "GitHub", "Python", "Rust", "框架", "架构"]},
            "tech-biz": {"title": "科技商业", "node_token": WIKI_NODES.get("科技商业", ""),
                         "keywords": ["融资", "IPO", "上市", "收购", "市值", "股价", "投资", "商业"]},
            "product": {"title": "产品设计", "node_token": WIKI_NODES.get("产品设计", ""),
                        "keywords": ["App", "发布", "更新", "设计", "UX", "产品"]},
            "opensource": {"title": "开源动态", "node_token": WIKI_NODES.get("开源动态", ""),
                           "keywords": ["开源", "GitHub", "Linux", "基金会", "License"]},
            "tools": {"title": "效率工具", "node_token": WIKI_NODES.get("效率工具", ""),
                      "keywords": ["工具", "效率", "自动化", "Notion", "Obsidian", "插件"]},
        },
    },
}

# 与 send_news.py 共享的 RSS 源
RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "Wired": "https://www.wired.com/feed/rss",
    "Hacker News": "https://hnrss.org/frontpage?count=15",
    "The Register": "https://www.theregister.com/headlines.atom",
    "CNET": "https://www.cnet.com/rss/news/",
    "36氪": "https://36kr.com/feed",
    "IT之家": "https://www.ithome.com/rss/",
    "品玩": "https://www.pingwest.com/feed/",
    "机器之心": "https://www.jiqizhixin.com/rss",
    "雷锋网": "https://www.leiphone.com/feed",
    "少数派": "https://sspai.com/feed",
}


# ── 信息抓取 ────────────────────────────────────────

def fetch_all_feeds() -> List[Dict]:
    """拉取所有 RSS 源的最新内容"""
    all_entries = []

    for source, url in RSS_FEEDS.items():
        try:
            print(f"  📡 {source} ...", end=" ", flush=True)
            import urllib.request
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            data = urllib.request.urlopen(req, timeout=15, context=_SSL_CONTEXT).read()
            feed = feedparser.parse(data)
            count = len(feed.entries)
            print(f"{count} 条")

            for entry in feed.entries[:15]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", "") or entry.get("description", "")
                # 清理 HTML 标签
                import re
                summary = re.sub(r"<[^>]+>", "", summary)[:300]

                if not title or not link:
                    continue

                pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
                entry_date = None
                if pub_date:
                    try:
                        entry_date = datetime(*pub_date[:6]).date()
                    except Exception:
                        pass

                all_entries.append({
                    "source": source,
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "date": entry_date,
                })
        except Exception as e:
            print(f"⚠️  失败: {e}")

    return all_entries


def deduplicate(entries: List[Dict]) -> List[Dict]:
    """按标题去重"""
    import re
    from collections import OrderedDict

    seen = OrderedDict()
    for entry in entries:
        key = re.sub(r"[^\w\s]", "", entry["title"].lower())
        key = re.sub(r"\s+", " ", key)[:80]
        if key not in seen:
            seen[key] = entry
    return list(seen.values())


# ── AI 处理（调用 Claude Code） ──────────────────────

def classify_with_claude(entries: List[Dict]) -> List[Dict]:
    """
    使用 Claude Code CLI 对条目进行分类和摘要。

    由于 Claude Code CLI 是非交互式工具，这里通过创建临时
    prompt 文件 + `claude --print` 模式来调用。
    """
    if not entries:
        return entries

    # 构建 prompt
    entries_text = ""
    for i, e in enumerate(entries[:50]):  # 单次处理最多 50 条
        entries_text += f"{i+1}. [{e['source']}] {e['title']}\n   URL: {e['link']}\n   摘要: {e.get('summary', 'N/A')[:200]}\n\n"

    categories = "\n".join(
        f"- **{v['title']}** (key={k}): {', '.join(v.get('keywords', ['通用']))}"
        for k, v in KNOWLEDGE_TREE.get("🗂️ 分类归档", {}).get("children", {}).items()
    )

    prompt = f"""你是知识管理专家。请分析以下科技新闻，给出分类和重要性评估。

## 可用分类
{categories}
- **其他** (key=other): 不属于以上分类

## 待分类内容
{entries_text}

## 输出格式
对每一条目输出 JSON（不要 markdown 代码块标记，输出纯 JSON 数组）：
[
  {{
    "index": 1,
    "category_key": "ai-models",
    "importance": 8,
    "summary_cn": "一句话中文摘要",
    "tags": ["标签1", "标签2"],
    "why_important": "为什么这条重要（中文，20字以内）"
  }}
]

importance 评分 1-10:
- 9-10: 重大突破/发布/收购
- 7-8: 重要行业动态
- 5-6: 值得关注
- 1-4: 一般资讯

请只输出 JSON 数组，不要任何额外文字。"""

    try:
        # 写入临时 prompt 文件
        prompt_file = "/tmp/feishu_pipeline_prompt.txt"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        # 调用 claude CLI (--print flag + prompt as positional arg)
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "HOME": os.environ.get("HOME", "/Users/apple")},
        )

        if result.returncode != 0:
            print(f"⚠️  Claude CLI 错误: {result.stderr[:200]}")
            return entries

        # 解析 JSON 结果
        output = result.stdout.strip()
        # Claude 可能输出中带有 markdown 代码块标记
        if "```json" in output:
            output = output.split("```json")[1].split("```")[0]
        elif "```" in output:
            output = output.split("```")[1].split("```")[0]

        classifications = json.loads(output)

        # 将分类结果合并回条目
        class_map = {c["index"]: c for c in classifications}
        for i, entry in enumerate(entries):
            idx = i + 1
            if idx in class_map:
                c = class_map[idx]
                entry["category_key"] = c.get("category_key", "other")
                entry["importance"] = c.get("importance", 5)
                entry["ai_summary"] = c.get("summary_cn", "")
                entry["tags"] = c.get("tags", [])
                entry["why_important"] = c.get("why_important", "")
            else:
                entry["category_key"] = "other"
                entry["importance"] = 3
                entry["ai_summary"] = entry["title"]
                entry["tags"] = []
                entry["why_important"] = ""

    except subprocess.TimeoutExpired:
        print("⚠️  Claude CLI 超时")
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON 解析失败: {e}")
    except Exception as e:
        print(f"⚠️  AI 分类失败: {e}")

    return entries


# ── 飞书发布 ────────────────────────────────────────

def generate_daily_brief(classified_entries: List[Dict]) -> str:
    """生成每日简报的 Markdown 内容"""
    today = datetime.now(CST)
    date_str = today.strftime("%Y年%m月%d日")
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    day_str = f"{date_str}（{weekdays[today.weekday()]}）"

    # 按重要性排序
    sorted_entries = sorted(
        classified_entries,
        key=lambda e: e.get("importance", 0),
        reverse=True,
    )

    # 按分类分组
    by_category = {}
    for entry in sorted_entries[:30]:
        cat = entry.get("category_key", "other")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(entry)

    # 反向映射
    key_to_name = {}
    cat_node = KNOWLEDGE_TREE.get("🗂️ 分类归档", {})
    for k, v in cat_node.get("children", {}).items():
        key_to_name[k] = v["title"]

    # 构建简报
    lines = [
        f"# 📰 每日科技简报",
        f"",
        f"**日期：{day_str}**",
        f"",
        f"> 📊 本日共收录 {len(classified_entries)} 条资讯，" +
        f"精选 {len(sorted_entries[:30])} 条，覆盖 {len(by_category)} 个领域。",
        f"",
        f"---",
        f"",
        f"## 🔥 今日必读 TOP 10",
        f"",
    ]

    for i, entry in enumerate(sorted_entries[:10]):
        importance_star = "⭐" * min(entry.get("importance", 5), 5)
        lines.append(
            f"{i+1}. {importance_star} **[{entry['source']}]** "
            f"[{entry['title']}]({entry['link']})"
        )
        if entry.get("ai_summary"):
            lines.append(f"   > {entry['ai_summary']}")
        if entry.get("why_important"):
            lines.append(f"   > 💡 {entry['why_important']}")
        lines.append("")

    lines.extend(["---", "", "## 📂 分类速览", ""])

    for cat_key, cat_entries in by_category.items():
        name = key_to_name.get(cat_key, "其他")
        lines.append(f"### {name}（{len(cat_entries)} 条）")
        lines.append("")
        for entry in cat_entries[:5]:
            tags_str = " ".join(f"`{t}`" for t in entry.get("tags", [])[:3])
            lines.append(
                f"- [{entry['title']}]({entry['link']}) "
                f"— {entry['source']} {tags_str}"
            )
        lines.append("")

    lines.extend([
        "---",
        "",
        "> 🤖 本简报由 AI 自动生成于 " +
        datetime.now(CST).strftime("%Y-%m-%d %H:%M CST"),
        "> 知识库：[第二大脑](https://www.feishu.cn/)",
    ])

    return "\n".join(lines)


def publish_to_feishu(
    client: FeishuClient,
    classified_entries: List[Dict],
    brief_content: str,
    mode: str = "daily",
) -> Dict[str, str]:
    """将处理结果发布到飞书"""
    result = {}

    if not FEISHU_SPACE_ID:
        print("⚠️  未设置 FEISHU_SPACE_ID，跳过飞书发布")
        return result

    today = datetime.now(CST)

    # 1. 发布每日简报到知识库「📋 每日简报」节点下
    if mode in ("daily", "weekly"):
        week_label = today.strftime("%Y-W%W")
        date_label = today.strftime("%Y-%m-%d")

        if mode == "daily":
            title = f"{date_label} 日报"
        else:
            title = f"{week_label} 周报"

        # 使用已有的「📋 每日简报」或「📊 每周回顾」节点作为父节点
        parent_key = "📋 每日简报" if mode == "daily" else "📊 每周回顾"
        parent_token = WIKI_NODES.get(parent_key, "")

        try:
            node_token = client.create_knowledge_page(
                space_id=FEISHU_SPACE_ID,
                title=title,
                content=brief_content,
                parent_node_token=parent_token,
            )
            result["brief_node_token"] = node_token
            print(f"  ✅ 简报已发布: {title}")
        except Exception as e:
            print(f"  ⚠️  简报发布失败: {e}")

    # 2. 将高重要性条目写入 INBOX
    important_entries = [
        e for e in classified_entries if e.get("importance", 0) >= 7
    ]
    if important_entries:
        inbox_content = f"# 📥 待分类重要资讯\n\n"
        inbox_content += f"抓取时间：{today.strftime('%Y-%m-%d %H:%M')}\n\n---\n\n"
        for entry in important_entries[:10]:
            inbox_content += (
                f"## [{entry['source']}] {entry['title']}\n\n"
                f"- **链接**：{entry['link']}\n"
                f"- **重要性**：{'⭐' * entry.get('importance', 5)}\n"
                f"- **AI 摘要**：{entry.get('ai_summary', 'N/A')}\n"
                f"- **建议归类**：{entry.get('category_key', 'other')}\n"
                f"- **标签**：{', '.join(entry.get('tags', []))}\n\n"
                f"---\n\n"
            )
        try:
            inbox_parent = WIKI_NODES.get("📥 收件箱", "")
            client.create_knowledge_page(
                space_id=FEISHU_SPACE_ID,
                title=f"📥 {today.strftime('%m%d')} 重要资讯",
                content=inbox_content,
                parent_node_token=inbox_parent,
            )
            result["inbox_created"] = "ok"
            print(f"  ✅ INBOX 已更新: {len(important_entries)} 条重要资讯")
        except Exception as e:
            print(f"  ⚠️  INBOX 更新失败: {e}")

    # 3. 更新知识统计多维表格
    if FEISHU_BITABLE_TOKEN and FEISHU_STATS_TABLE_ID:
        try:
            client.add_bitable_record(
                FEISHU_BITABLE_TOKEN,
                FEISHU_STATS_TABLE_ID,
                {
                    "日期": int(today.timestamp() * 1000),
                    "文章阅读数": len(classified_entries),
                    "任务完成数": 1 if result.get("brief_node_token") else 0,
                },
            )
            result["stats_updated"] = "ok"
            print(f"  ✅ 统计数据已更新")
        except Exception as e:
            print(f"  ⚠️  统计更新失败: {e}")

    # 4. 发送飞书 Bot 通知
    if FEISHU_WEBHOOK_URL:
        top5 = sorted(
            classified_entries,
            key=lambda e: e.get("importance", 0),
            reverse=True,
        )[:5]

        card_lines = [
            f"📊 共收录 **{len(classified_entries)}** 条资讯",
            "",
            "**🔥 今日 TOP 5：**",
        ]
        for i, entry in enumerate(top5):
            card_lines.append(
                f"{i+1}. [{entry['title'][:60]}]({entry['link']})"
            )

        card = FeishuClient.build_text_card(
            title=f"📰 每日科技简报 - {today.strftime('%m/%d')}",
            content="\n".join(card_lines),
            color="blue",
        )
        FeishuClient.send_webhook_message(FEISHU_WEBHOOK_URL, card)
        result["notification_sent"] = "ok"
        print(f"  ✅ Bot 通知已发送")

    return result


# ── 命令行入口 ──────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python feishu_pipeline.py [daily|weekly|classify|sync-stats]")
        sys.exit(1)

    mode = sys.argv[1]
    print(f"\n🚀 飞书知识库 Pipeline - 模式: {mode}")
    print(f"   时间: {datetime.now(CST).strftime('%Y-%m-%d %H:%M CST')}\n")

    # 1. 抓取
    print("📡 拉取 RSS 源...")
    entries = fetch_all_feeds()
    print(f"   总计: {len(entries)} 条原始条目")

    # 2. 去重
    entries = deduplicate(entries)
    print(f"   去重后: {len(entries)} 条")

    # 3. AI 分类（daily/weekly 模式）
    if mode in ("daily", "weekly", "classify"):
        print("\n🤖 AI 分类与摘要...")
        entries = classify_with_claude(entries)

        # 统计分类结果
        from collections import Counter
        cat_counts = Counter(e.get("category_key", "other") for e in entries)
        for cat, count in cat_counts.most_common():
            print(f"   {cat}: {count} 条")

    # 4. 生成简报并发布
    if mode in ("daily", "weekly"):
        print(f"\n📝 生成{mode}简报...")
        brief = generate_daily_brief(entries)

        print("📤 发布到飞书...")
        client = FeishuClient()
        result = publish_to_feishu(client, entries, brief, mode=mode)

        print(f"\n✅ {mode} 模式完成")
        print(f"   结果: {json.dumps(result, ensure_ascii=False)}")

    elif mode == "classify":
        # 仅输出分类结果（用于调试或自定义处理）
        print(f"\n✅ 分类完成，共 {len(entries)} 条")

    elif mode == "sync-stats":
        print("📊 同步统计数据到多维表格...")
        client = FeishuClient()
        if FEISHU_BITABLE_TOKEN and FEISHU_DAILY_TABLE_ID:
            today = datetime.now(CST)
            client.add_bitable_record(
                FEISHU_BITABLE_TOKEN,
                FEISHU_DAILY_TABLE_ID,
                {
                    "日期": int(today.timestamp() * 1000),
                    "今日笔记": f"自动同步于 {today.strftime('%Y-%m-%d %H:%M')}",
                },
            )
            print("   ✅ 同步完成")

    else:
        print(f"❌ 未知模式: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()

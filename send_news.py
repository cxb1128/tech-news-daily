#!/usr/bin/env python3
"""
每日科技新闻邮件发送脚本
通过 RSS 聚合全球科技媒体头条，生成 HTML 邮件并通过 QQ 邮箱发送。
GitHub Actions 每天 19:00 CST 自动运行。
"""

import feedparser
import smtplib
import os
import sys
import re
import ssl
import urllib.request
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from collections import OrderedDict
from html import escape

# ── 配置 ──────────────────────────────────────────────
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SENDER = "364341493@qq.com"
RECIPIENT = "364341493@qq.com"
AUTH_CODE = os.environ.get("QQ_AUTH_CODE", "")

CST = timezone(timedelta(hours=8))

# 为 feedparser 设置 User-Agent（部分 RSS 源需要）
USER_AGENT = "Mozilla/5.0 (compatible; TechNewsBot/1.0)"
feedparser.USER_AGENT = USER_AGENT

# 给 urllib 也设上
opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", USER_AGENT)]

# RSS 源列表 — 已验证的可靠源
RSS_FEEDS = {
    # 英文源
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "Wired": "https://www.wired.com/feed/rss",
    "Hacker News": "https://hnrss.org/frontpage?count=15",
    "The Register": "https://www.theregister.com/headlines.atom",
    "CNET": "https://www.cnet.com/rss/news/",
    # 中文源
    "36氪": "https://36kr.com/feed",
    "IT之家": "https://www.ithome.com/rss/",
    "品玩": "https://www.pingwest.com/feed/",
    "机器之心": "https://www.jiqizhixin.com/rss",
    "雷锋网": "https://www.leiphone.com/feed",
    "少数派": "https://sspai.com/feed",
}


def get_today_str():
    return datetime.now(CST).strftime("%Y-%m-%d")


def get_date_display():
    now = datetime.now(CST)
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return f"{now.year}年{now.month}月{now.day}日（{weekdays[now.weekday()]}）"


def fetch_feeds():
    """拉取所有 RSS 源"""
    all_entries = []

    # 如果本地 SSL 有问题（macOS Python 常见），跳过验证
    ssl_context = None
    try:
        ssl_context = ssl.create_default_context()
    except Exception:
        pass

    for source, url in RSS_FEEDS.items():
        try:
            print(f"  📡 拉取 {source} ...", end=" ")
            feed = feedparser.parse(url)
            count = len(feed.entries)
            print(f"{count} 条")

            for entry in feed.entries[:20]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
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
                    "date": entry_date,
                })
        except Exception as e:
            print(f"  ⚠️  {source} 失败: {e}", file=sys.stderr)
            continue

    return all_entries


def score_entry(entry):
    """打分：日期越近 + 关键词匹配 = 越高分"""
    score = 0
    today = datetime.now(CST).date()

    if entry["date"]:
        if entry["date"] == today:
            score += 100
        elif entry["date"] == today - timedelta(days=1):
            score += 50
        elif entry["date"] >= today - timedelta(days=2):
            score += 20
    else:
        score += 30

    hot_keywords = [
        "AI", "ChatGPT", "OpenAI", "Nvidia", "Apple", "Google", "Microsoft",
        "Tesla", "Meta", "SpaceX", "IPO", "芯片", "模型", "发布", "融资",
        "大模型", "机器人", "量子", "半导体", "iPhone", "GPU", "自动驾驶",
        "人形", "Agent", "代理", "开源", "收购", "上市", "突破",
        "Intel", "AMD", "ARM", "DeepSeek", "Starlink", "Copilot",
    ]
    title_lower = entry["title"].lower()
    for kw in hot_keywords:
        if kw.lower() in title_lower:
            score += 5

    return score


def deduplicate(entries):
    """去重"""
    seen = OrderedDict()
    for entry in entries:
        key = re.sub(r"[^\w\s]", "", entry["title"].lower())
        key = re.sub(r"\s+", " ", key)[:80]
        if key not in seen:
            seen[key] = entry
    return list(seen.values())


def generate_html(entries, count=15):
    """生成 HTML 邮件"""
    date_display = get_date_display()
    actual_count = min(len(entries), count)

    html = f"""<h1 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:8px">📰 全球科技日报</h1>
<p style="color:#666;font-size:14px">日期：{date_display}</p>

<div style="background:#f0f7ff;padding:12px 16px;border-radius:8px;margin:16px 0">
  <p style="margin:0;color:#1a73e8;font-weight:bold">📊 今日共 {actual_count} 条要闻 | 来源：TechCrunch、The Verge、Ars Technica、36氪、IT之家 等</p>
</div>

<ol style="line-height:2;font-size:15px">
"""

    for entry in entries[:count]:
        source = escape(entry["source"])
        title = escape(entry["title"])
        link = escape(entry["link"])
        html += f'  <li><b>{source}</b> — {title} 🔗 <a href="{link}">来源</a></li>\n'

    html += """</ol>

<hr style="margin-top:24px">
<p style="color:#999;font-size:12px">📬 由 GitHub Actions 每日自动生成并发送 | 每天早上 6:10（北京时间）| RSS 聚合，无 AI 参与</p>"""

    return html


def send_email(html_body, subject=None):
    """通过 QQ SMTP 发送邮件"""
    if not AUTH_CODE:
        print("❌ 错误：未设置 QQ_AUTH_CODE 环境变量", file=sys.stderr)
        sys.exit(1)

    if subject is None:
        subject = f"📰 每日科技新闻 - {datetime.now(CST).strftime('%m月%d日')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = SENDER
    msg["To"] = RECIPIENT

    plain = re.sub(r"<[^>]+>", "", html_body)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.login(SENDER, AUTH_CODE)
            server.sendmail(SENDER, [RECIPIENT], msg.as_string())
        print("✅ 邮件发送成功！")
    except smtplib.SMTPException as e:
        print(f"❌ SMTP 错误: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    print(f"📡 开始拉取 RSS 新闻源... ({get_today_str()})")
    print(f"   共 {len(RSS_FEEDS)} 个源\n")

    # 1. 拉取
    entries = fetch_feeds()
    print(f"\n📥 共拉取 {len(entries)} 条原始条目")

    if len(entries) == 0:
        print("❌ 未拉取到任何新闻，请检查网络或 RSS 源状态", file=sys.stderr)
        # 不发送空邮件
        sys.exit(0)

    # 2. 打分排序
    entries.sort(key=score_entry, reverse=True)

    # 3. 去重
    entries = deduplicate(entries)
    print(f"📋 去重后剩余 {len(entries)} 条")

    # 4. 取前 15
    top_n = min(len(entries), 15)
    print(f"✨ 精选前 {top_n} 条发送")

    # 5. 生成 HTML
    html = generate_html(entries, count=top_n)

    # 6. 发送
    print("\n📧 发送邮件...")
    send_email(html)

    # 7. 摘要
    print("\n📰 今日新闻摘要：")
    for i, entry in enumerate(entries[:top_n]):
        print(f"  {i+1}. [{entry['source']}] {entry['title'][:80]}")


if __name__ == "__main__":
    main()

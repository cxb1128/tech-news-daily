#!/usr/bin/env python3
"""
每日科技新闻邮件发送脚本
通过 RSS 聚合全球科技媒体头条，MyMemory 翻译英文标题为中文。
GitHub Actions 每天早上 6:10 CST 自动运行。
80% 国际内容 + 20% 国内内容。
"""

import feedparser
import smtplib
import os
import sys
import re
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

USER_AGENT = "Mozilla/5.0 (compatible; TechNewsBot/1.0)"
feedparser.USER_AGENT = USER_AGENT

opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", USER_AGENT)]

# ── RSS 源 ────────────────────────────────────────────
# 国际源 — 英文科技媒体，通过 MyMemory 翻译为中文
INTERNATIONAL_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "Wired": "https://www.wired.com/feed/rss",
    "The Register": "https://www.theregister.com/headlines.atom",
    "Hacker News": "https://hnrss.org/frontpage?count=15",
    "CNET": "https://www.cnet.com/rss/news/",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    "BBC Tech": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "Reuters Tech": "https://www.reuters.com/arc/outboundfeeds/v3/all/?outputType=xml&section=technology",
}

# 国内源 — 补充本土视角，无需翻译
DOMESTIC_FEEDS = {
    "36氪": "https://36kr.com/feed",
    "IT之家": "https://www.ithome.com/rss/",
    "少数派": "https://sspai.com/feed",
    "量子位": "https://www.qbitai.com/feed",
}


def get_all_feeds():
    feeds = {}
    feeds.update(INTERNATIONAL_FEEDS)
    feeds.update(DOMESTIC_FEEDS)
    return feeds


def get_today_str():
    return datetime.now(CST).strftime("%Y-%m-%d")


def get_date_display():
    now = datetime.now(CST)
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return f"{now.year}年{now.month}月{now.day}日（{weekdays[now.weekday()]}）"


def fetch_feeds():
    """拉取所有 RSS 源"""
    all_entries = []

    for source, url in get_all_feeds().items():
        try:
            print(f"  📡 拉取 {source} ...", end=" ")
            feed = feedparser.parse(url)
            count = len(feed.entries)
            print(f"{count} 条")

            for entry in feed.entries[:15]:
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

                is_international = source in INTERNATIONAL_FEEDS

                all_entries.append({
                    "source": source,
                    "title": title,
                    "link": link,
                    "date": entry_date,
                    "international": is_international,
                })
        except Exception as e:
            print(f"  ⚠️  {source} 失败: {e}", file=sys.stderr)
            continue

    return all_entries


def translate_entries(entries):
    """用 MyMemory 翻译英文标题为中文（免费，无 API key）"""
    from deep_translator import MyMemoryTranslator

    # 找出需要翻译的国际条目（标题不含足够中文）
    to_translate = []
    for i, entry in enumerate(entries):
        if entry["international"]:
            chinese_chars = len(re.findall(r'[一-鿿]', entry["title"]))
            if chinese_chars < 3:
                to_translate.append(i)

    if not to_translate:
        print("  🌐 无需翻译")
        return entries

    print(f"  🌐 MyMemory 翻译 {len(to_translate)} 条英文标题...")
    translator = MyMemoryTranslator(source="en", target="zh-CN")

    for idx in to_translate:
        try:
            zh = translator.translate(entries[idx]["title"])
            if zh and zh != entries[idx]["title"]:
                # 保存原题，用中文替换
                entries[idx]["title_en"] = entries[idx]["title"]
                entries[idx]["title"] = zh
        except Exception as e:
            print(f"    ⚠️ 翻译失败: {entries[idx]['title'][:40]}... ({e})", file=sys.stderr)

    translated = len(to_translate) - sum(1 for i in to_translate if entries[i].get("title_en") is None)
    print(f"    ✅ 成功翻译 {translated}/{len(to_translate)} 条")
    return entries


def score_entry(entry):
    """打分：日期 + 关键词 + 国际源加权"""
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

    # 国际源加权确保 80%
    if entry["international"]:
        score += 20

    hot_keywords = [
        "AI", "ChatGPT", "OpenAI", "Nvidia", "Apple", "Google", "Microsoft",
        "Tesla", "Meta", "SpaceX", "芯片", "模型", "发布", "融资",
        "大模型", "机器人", "量子", "半导体", "iPhone", "GPU",
        "人形", "Agent", "开源", "收购", "上市", "突破",
        "Intel", "AMD", "ARM", "DeepSeek", "Starlink",
        "字节", "腾讯", "阿里", "华为", "小米", "比亚迪",
        "卫星", "核聚变", "基因", "电池", "关税", "制裁",
    ]
    text = (entry["title"] + " " + entry.get("title_en", "")).lower()
    for kw in hot_keywords:
        if kw.lower() in text:
            score += 5

    return score


def deduplicate(entries):
    """去重"""
    seen = OrderedDict()
    for entry in entries:
        key = re.sub(r"[^\w\s]", "", entry["title"])
        key = re.sub(r"\s+", "", key)[:60]
        if key not in seen:
            seen[key] = entry
    return list(seen.values())


def select_balanced(entries, count=15, intl_ratio=0.8):
    """按 80/20 比例选择"""
    intl = [e for e in entries if e["international"]]
    dom = [e for e in entries if not e["international"]]

    need_intl = int(count * intl_ratio)   # 12
    need_dom = count - need_intl            # 3

    # 不够时互相补充
    actual_intl = min(need_intl, len(intl))
    actual_dom = min(need_dom, len(dom))

    if actual_intl < need_intl:
        actual_dom = min(count - actual_intl, len(dom))
    if actual_dom < need_dom:
        actual_intl = min(count - actual_dom, len(intl))

    return intl[:actual_intl] + dom[:actual_dom]


def generate_html(entries):
    """生成 HTML 邮件"""
    date_display = get_date_display()
    total = len(entries)
    intl_count = sum(1 for e in entries if e["international"])

    html = f"""<h1 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:8px">📰 全球科技日报</h1>
<p style="color:#666;font-size:14px">日期：{date_display}</p>

<div style="background:#f0f7ff;padding:12px 16px;border-radius:8px;margin:16px 0">
  <p style="margin:0;color:#1a73e8;font-weight:bold">
    🌍 国际 {intl_count} 条（{intl_count * 100 // total}%）| 🇨🇳 国内 {total - intl_count} 条 |
    来源：TechCrunch、The Verge、Ars Technica、BBC、MIT TR、36氪、IT之家 等
  </p>
</div>

<ol style="line-height:2;font-size:15px">
"""

    for entry in entries:
        source = escape(entry["source"])
        title = escape(entry["title"])
        link = escape(entry["link"])
        badge = "🌍" if entry["international"] else "🇨🇳"

        title_en = entry.get("title_en", "")
        if title_en:
            html += f'  <li>{badge} <b>[{source}]</b> {title} <br><small style="color:#888">原文：{escape(title_en)}</small> <a href="{link}">🔗</a></li>\n'
        else:
            html += f'  <li>{badge} <b>[{source}]</b> {title} <a href="{link}">🔗</a></li>\n'

    html += """</ol>

<hr style="margin-top:24px">
<p style="color:#999;font-size:12px">📬 由 GitHub Actions 每日自动生成并发送 | 每天早上 6:10 | MyMemory 翻译 | 国际占比 ≥80%</p>"""

    return html


def send_email(html_body, subject=None):
    """通过 QQ SMTP 发送邮件"""
    if not AUTH_CODE:
        print("❌ 错误：未设置 QQ_AUTH_CODE", file=sys.stderr)
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
    print(f"   国际源 {len(INTERNATIONAL_FEEDS)} 个 + 国内源 {len(DOMESTIC_FEEDS)} 个\n")

    # 1. 拉取
    entries = fetch_feeds()
    intl_total = sum(1 for e in entries if e["international"])
    print(f"\n📥 共拉取 {len(entries)} 条（🌍 国际 {intl_total} / 🇨🇳 国内 {len(entries) - intl_total}）")

    if len(entries) == 0:
        print("❌ 未拉取到任何新闻", file=sys.stderr)
        sys.exit(0)

    # 2. 翻译
    print()
    entries = translate_entries(entries)

    # 3. 打分排序
    entries.sort(key=score_entry, reverse=True)

    # 4. 去重
    entries = deduplicate(entries)
    print(f"📋 去重后剩余 {len(entries)} 条")

    # 5. 按比例选 15 条
    selected = select_balanced(entries, count=15, intl_ratio=0.8)
    intl_sel = sum(1 for e in selected if e["international"])
    print(f"✨ 精选 {len(selected)} 条（🌍 {intl_sel} + 🇨🇳 {len(selected) - intl_sel}）")

    # 6. HTML + 发送
    html = generate_html(selected)
    print("\n📧 发送邮件...")
    send_email(html)

    # 7. 摘要
    print("\n📰 今日新闻摘要：")
    for i, entry in enumerate(selected):
        badge = "🌍" if entry["international"] else "🇨🇳"
        title_en = entry.get("title_en", "")
        if title_en:
            print(f"  {i+1}. {badge} [{entry['source']}] {entry['title'][:50]} ← {title_en[:50]}")
        else:
            print(f"  {i+1}. {badge} [{entry['source']}] {entry['title'][:50]}")


if __name__ == "__main__":
    main()

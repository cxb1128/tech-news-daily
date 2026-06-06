#!/usr/bin/env python3
"""
每日科技新闻邮件发送脚本
聚合全球科技媒体 RSS，标题+摘要，MyMemory 翻译为中文。
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
from html import escape, strip_tags

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
}

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


def clean_html(raw):
    """去掉 HTML 标签，保留纯文本"""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_summary(entry):
    """从 RSS entry 提取摘要，限制长度"""
    # 优先取 summary，其次 description，其次 content
    candidates = [
        entry.get("summary", ""),
        entry.get("description", ""),
    ]
    # 有些源把摘要放在 content[0].value
    content_list = entry.get("content", [])
    if content_list:
        candidates.append(content_list[0].get("value", ""))

    for c in candidates:
        text = clean_html(c)
        if len(text) > 20:  # 有效摘要至少 20 字
            # 限制在 300 字内（翻译后会更短）
            if len(text) > 300:
                text = text[:300].rsplit(" ", 1)[0] + "..."
            return text

    return ""


def fetch_feeds():
    """拉取所有 RSS 源"""
    all_entries = []

    for source, url in get_all_feeds().items():
        try:
            print(f"  📡 拉取 {source} ...", end=" ")
            feed = feedparser.parse(url)
            count = len(feed.entries)
            print(f"{count} 条")

            for entry in feed.entries[:10]:  # 每个源最多 10 条
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
                summary = extract_summary(entry)

                all_entries.append({
                    "source": source,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "date": entry_date,
                    "international": is_international,
                })
        except Exception as e:
            print(f"  ⚠️  {source} 失败: {e}", file=sys.stderr)
            continue

    return all_entries


def translate_text(text):
    """MyMemory 单条翻译"""
    from deep_translator import MyMemoryTranslator
    translator = MyMemoryTranslator(source="en-GB", target="zh-CN")
    try:
        return translator.translate(text)
    except Exception:
        return text


def translate_entries(entries, top_k=12):
    """
    先打分筛选出国际条目的候选，再翻译标题+摘要。
    只翻译最终入选的条目，大幅减少翻译量。
    """
    from deep_translator import MyMemoryTranslator
    translator = MyMemoryTranslator(source="en-GB", target="zh-CN")

    # 找出需要翻译的国际条目
    to_translate = []
    for i, entry in enumerate(entries):
        if entry["international"]:
            chinese_chars = len(re.findall(r'[一-鿿]', entry["title"]))
            if chinese_chars < 3:
                to_translate.append(i)

    if not to_translate:
        print("  🌐 无需翻译")
        return entries

    total = len(to_translate)
    print(f"  🌐 MyMemory 翻译 {total} 条英文（标题 + 摘要）...")

    done = 0
    for idx in to_translate:
        entry = entries[idx]
        try:
            # 翻译标题
            zh_title = translator.translate(entry["title"])
            if zh_title and zh_title != entry["title"]:
                entry["title_en"] = entry["title"]
                entry["title"] = zh_title

            # 翻译摘要
            if entry.get("summary"):
                zh_summary = translator.translate(entry["summary"])
                if zh_summary and zh_summary != entry["summary"]:
                    entry["summary_en"] = entry["summary"]
                    entry["summary"] = zh_summary

            done += 1
            if done % 10 == 0:
                print(f"    ⏳ {done}/{total} ...")
        except Exception as e:
            print(f"    ⚠️ 翻译失败 [{entry['source']}]: {str(e)[:60]}", file=sys.stderr)

    print(f"    ✅ 完成 {done}/{total}")
    return entries


def score_entry(entry):
    """打分"""
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

    if entry["international"]:
        score += 20

    hot_keywords = [
        "AI", "ChatGPT", "OpenAI", "Nvidia", "Apple", "Google", "Microsoft",
        "Tesla", "Meta", "SpaceX", "芯片", "模型", "发布", "融资",
        "大模型", "机器人", "量子", "半导体", "iPhone", "GPU",
        "人形", "Agent", "开源", "收购", "上市", "突破",
        "Intel", "AMD", "ARM", "DeepSeek", "Starlink",
        "字节", "腾讯", "阿里", "华为", "小米",
        "卫星", "基因", "电池", "关税",
    ]
    text = (entry["title"] + " " + entry["summary"]).lower()
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


def select_balanced(entries, count=10, intl_ratio=0.8):
    """按 80/20 选择 10 条（含摘要后篇幅变长，减少条数）"""
    intl = [e for e in entries if e["international"]]
    dom = [e for e in entries if not e["international"]]

    need_intl = int(count * intl_ratio)
    need_dom = count - need_intl

    actual_intl = min(need_intl, len(intl))
    actual_dom = min(need_dom, len(dom))

    if actual_intl < need_intl:
        actual_dom = min(count - actual_intl, len(dom))
    if actual_dom < need_dom:
        actual_intl = min(count - actual_dom, len(intl))

    return intl[:actual_intl] + dom[:actual_dom]


def generate_html(entries):
    """生成 HTML 邮件（含标题+摘要）"""
    date_display = get_date_display()
    total = len(entries)
    intl_count = sum(1 for e in entries if e["international"])

    html = f"""<h1 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:8px">📰 全球科技日报</h1>
<p style="color:#666;font-size:14px">日期：{date_display}</p>

<div style="background:#f0f7ff;padding:12px 16px;border-radius:8px;margin:16px 0">
  <p style="margin:0;color:#1a73e8;font-weight:bold">
    🌍 国际 {intl_count} 条（{intl_count * 100 // total}%）| 🇨🇳 国内 {total - intl_count} 条 |
    来源：TechCrunch、The Verge、Ars Technica、MIT TR、BBC、36氪、IT之家 等
  </p>
</div>
"""

    for entry in entries:
        source = escape(entry["source"])
        title = escape(entry["title"])
        link = escape(entry["link"])
        badge = "🌍" if entry["international"] else "🇨🇳"
        summary = escape(entry.get("summary", ""))

        html += f'<div style="margin:20px 0;padding:12px 16px;border-left:3px solid #1a73e8;background:#fafafa;border-radius:0 8px 8px 0">'
        html += f'<p style="margin:0 0 6px 0;font-size:16px;font-weight:bold;line-height:1.5">{badge} <b>[{source}]</b> {title} <a href="{link}" style="font-size:13px">🔗 原文</a></p>'

        # 原标题（翻译前）
        title_en = entry.get("title_en", "")
        if title_en:
            html += f'<p style="margin:0 0 8px 0;font-size:12px;color:#999">原文标题：{escape(title_en)}</p>'

        # 摘要
        if summary:
            html += f'<p style="margin:0;font-size:14px;color:#444;line-height:1.7">{summary}</p>'

        html += '</div>\n'

    html += """<hr style="margin-top:24px">
<p style="color:#999;font-size:12px">📬 由 GitHub Actions 每日自动生成并发送 | 每天早上 6:10（北京时间）| MyMemory 翻译 | 国际占比 ≥80%</p>"""

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
    print(f"   国际源 {len(INTERNATIONAL_FEEDS)} + 国内源 {len(DOMESTIC_FEEDS)}\n")

    # 1. 拉取
    entries = fetch_feeds()
    intl_total = sum(1 for e in entries if e["international"])
    print(f"\n📥 共拉取 {len(entries)} 条（🌍 {intl_total} / 🇨🇳 {len(entries) - intl_total}）")

    if len(entries) == 0:
        print("❌ 未拉取到任何新闻", file=sys.stderr)
        sys.exit(0)

    # 2. 翻译
    print()
    entries = translate_entries(entries)

    # 3. 打分 + 去重
    entries.sort(key=score_entry, reverse=True)
    entries = deduplicate(entries)
    print(f"📋 去重后 {len(entries)} 条")

    # 4. 精选 10 条（含摘要篇幅长）
    selected = select_balanced(entries, count=10, intl_ratio=0.8)
    intl_sel = sum(1 for e in selected if e["international"])
    print(f"✨ 精选 {len(selected)} 条（🌍 {intl_sel} + 🇨🇳 {len(selected) - intl_sel}）")

    # 5. 生成 HTML + 发送
    html = generate_html(selected)
    print("\n📧 发送邮件...")
    send_email(html)

    # 6. 摘要
    print("\n📰 今日新闻：")
    for i, entry in enumerate(selected):
        badge = "🌍" if entry["international"] else "🇨🇳"
        s = entry.get("summary", "")[:60]
        print(f"  {i+1}. {badge} [{entry['source']}] {entry['title'][:50]}")
        if s:
            print(f"     {s}...")


if __name__ == "__main__":
    main()

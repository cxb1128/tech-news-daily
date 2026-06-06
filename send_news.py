#!/usr/bin/env python3
"""
每日科技新闻邮件发送脚本
通过 RSS 聚合全球中文科技媒体，生成 HTML 邮件并通过 QQ 邮箱发送。
GitHub Actions 每天早上 6:10 CST 自动运行。
80% 国际内容：BBC中文、NYT中文、FT中文、DW、日经中文、联合早报、VOA中文 等。
全人工翻译中文源，零机器翻译错误。
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

# ── RSS 源（80% 国际 + 20% 国内） ─────────────────────
# 国际源 — 国际媒体中文版，人工翻译，内容权威
INTERNATIONAL_FEEDS = {
    "BBC中文": "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml",
    "纽约时报中文": "https://cn.nytimes.com/rss/",
    "FT中文网": "https://www.ftchinese.com/rss/feed",
    "日经中文": "https://cn.nikkei.com/rss.html",
    "DW中文": "https://rss.dw.com/rdf/rss-chi-all",
    "联合早报": "https://www.zaobao.com.sg/news/tech/feed",
    "VOA中文": "https://www.voachinese.com/api/zq$omekvi$omrko",
    "韩联社中文": "https://cn.yna.co.kr/RSS/news.xml",
    "路透中文": "https://www.reuters.com/arc/outboundfeeds/v3/all/?outputType=xml&section=technology",
}

# 国内源 — 补充本土视角
DOMESTIC_FEEDS = {
    "36氪": "https://36kr.com/feed",
    "IT之家": "https://www.ithome.com/rss/",
    "少数派": "https://sspai.com/feed",
    "量子位": "https://www.qbitai.com/feed",
}


def get_all_feeds():
    """合并所有源，国际源排在前面"""
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
    feeds = get_all_feeds()

    for source, url in feeds.items():
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

                # 至少含有中文字符才算有效
                chinese_chars = len(re.findall(r'[一-鿿]', title))
                if chinese_chars < 2:
                    continue

                pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
                entry_date = None
                if pub_date:
                    try:
                        entry_date = datetime(*pub_date[:6]).date()
                    except Exception:
                        pass

                # 标记国际/国内
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

    # 国际源加权 20%，确保 80% 国际内容
    if entry["international"]:
        score += 20

    hot_keywords = [
        "AI", "ChatGPT", "OpenAI", "Nvidia", "苹果", "Google", "微软",
        "特斯拉", "Meta", "SpaceX", "芯片", "大模型", "发布", "融资",
        "机器人", "量子", "半导体", "iPhone", "GPU", "自动驾驶",
        "人形", "Agent", "开源", "收购", "上市", "突破",
        "Intel", "AMD", "ARM", "DeepSeek", "Starlink", "Copilot",
        "字节", "腾讯", "阿里", "华为", "小米", "比亚迪",
        "卫星", "核聚变", "基因", "电池", "关税", "制裁",
        "IPO", "纳斯达克", "硅谷", "欧盟", "白宫",
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
        key = re.sub(r"[^\w\s]", "", entry["title"])
        key = re.sub(r"\s+", "", key)[:60]
        if key not in seen:
            seen[key] = entry
    return list(seen.values())


def select_balanced(entries, count=15, intl_ratio=0.8):
    """
    按比例选择：80% 国际 + 20% 国内
    确保国际新闻占主导地位
    """
    intl_entries = [e for e in entries if e["international"]]
    dom_entries = [e for e in entries if not e["international"]]

    intl_count = int(count * intl_ratio)   # 12 条国际
    dom_count = count - intl_count          # 3 条国内

    # 如果国际内容不够，用国内补；如果国内不够，用国际补
    actual_intl = min(intl_count, len(intl_entries))
    actual_dom = min(dom_count, len(dom_entries))

    if actual_intl < intl_count:
        actual_dom = min(count - actual_intl, len(dom_entries))
    if actual_dom < dom_count:
        actual_intl = min(count - actual_dom, len(intl_entries))

    selected = intl_entries[:actual_intl] + dom_entries[:actual_dom]
    return selected


def generate_html(entries):
    """生成 HTML 邮件"""
    date_display = get_date_display()
    actual_count = len(entries)
    intl_count = sum(1 for e in entries if e["international"])

    html = f"""<h1 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:8px">📰 全球科技日报</h1>
<p style="color:#666;font-size:14px">日期：{date_display}</p>

<div style="background:#f0f7ff;padding:12px 16px;border-radius:8px;margin:16px 0">
  <p style="margin:0;color:#1a73e8;font-weight:bold">
    🌍 国际新闻 {intl_count} 条（{intl_count * 100 // actual_count}%）| 国内 {actual_count - intl_count} 条 |
    来源：BBC中文、NYT中文、FT中文、日经中文、DW、联合早报 等
  </p>
</div>

<ol style="line-height:2;font-size:15px">
"""

    for entry in entries:
        source = escape(entry["source"])
        title = escape(entry["title"])
        link = escape(entry["link"])
        badge = "🌍" if entry["international"] else "🇨🇳"
        html += f'  <li>{badge} <b>[{source}]</b> {title} <a href="{link}">🔗</a></li>\n'

    html += """</ol>

<hr style="margin-top:24px">
<p style="color:#999;font-size:12px">📬 由 GitHub Actions 每日自动生成并发送 | 每天早上 6:10（北京时间）| 国际媒体中文版 RSS 聚合</p>"""

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
    print(f"   国际源 {len(INTERNATIONAL_FEEDS)} 个 + 国内源 {len(DOMESTIC_FEEDS)} 个\n")

    # 1. 拉取
    entries = fetch_feeds()
    intl_total = sum(1 for e in entries if e["international"])
    print(f"\n📥 共拉取 {len(entries)} 条（国际 {intl_total} / 国内 {len(entries) - intl_total}）")

    if len(entries) == 0:
        print("❌ 未拉取到任何新闻", file=sys.stderr)
        sys.exit(0)

    # 2. 打分排序
    entries.sort(key=score_entry, reverse=True)

    # 3. 去重
    entries = deduplicate(entries)
    print(f"📋 去重后剩余 {len(entries)} 条")

    # 4. 按 80/20 比例选择 15 条
    selected = select_balanced(entries, count=15, intl_ratio=0.8)
    intl_selected = sum(1 for e in selected if e["international"])
    print(f"✨ 精选 {len(selected)} 条（🌍 国际 {intl_selected} + 🇨🇳 国内 {len(selected) - intl_selected}）")

    # 5. 生成 HTML
    html = generate_html(selected)

    # 6. 发送
    print("\n📧 发送邮件...")
    send_email(html)

    # 7. 摘要
    print("\n📰 今日新闻摘要：")
    for i, entry in enumerate(selected):
        badge = "🌍" if entry["international"] else "🇨🇳"
        print(f"  {i+1}. {badge} [{entry['source']}] {entry['title'][:70]}")


if __name__ == "__main__":
    main()

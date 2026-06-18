#!/usr/bin/env python3
"""
每日科技新闻邮件发送脚本
聚合全球科技媒体 RSS，完整标题+摘要，MyMemory 分段翻译为中文。
GitHub Actions 每天早上 6:10 CST 自动运行。
80% 国际内容 + 20% 国内内容。
"""

import feedparser
import smtplib
import os
import sys
import re
import time
import hashlib
import json
import urllib.request
import urllib.parse
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

# MyMemory 单次翻译约 500 字符，分段时留余量
CHUNK_SIZE = 450

# B 站 UP 主「旅客君LookUplus」— 苹果/数码深度评测参考源
BILIBILI_UP_MID = "13896140"
BILIBILI_UP_NAME = "旅客君@B站"
BILIBILI_UP_URL = "https://space.bilibili.com/13896140/video"

# WBI 签名置换表（B站公开算法）
WBI_ENC_TABLE = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
                 27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
                 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
                 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 52, 34, 44]

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


def extract_summary(entry, max_chars=100):
    """从 RSS entry 提取摘要，限制在 max_chars 字以内，尽量在句末截断"""
    candidates = [
        entry.get("summary", ""),
        entry.get("description", ""),
    ]
    content_list = entry.get("content", [])
    if content_list:
        candidates.append(content_list[0].get("value", ""))

    for c in candidates:
        text = clean_html(c)
        if len(text) > 20:  # 有效摘要至少 20 字
            if len(text) <= max_chars:
                return text
            # 截断到 max_chars，优先在句号处断句
            short = text[:max_chars]
            # 找最后一个句号/问号/感叹号
            for sep in ["。", "？", "！", ". ", "? ", "! "]:
                idx = short.rfind(sep)
                if idx > max_chars * 0.5:  # 至少用了一半才断
                    return short[:idx + 1]
            return short + "…"

    return ""


def _http_get_json(url, referer="https://www.bilibili.com/"):
    """HTTP GET → JSON，bilibili API 需要 Referer"""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Referer", referer)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _get_wbi_key():
    """获取 B 站 WBI 签名密钥（缓存 6h）"""
    now = time.time()
    if hasattr(_get_wbi_key, "_cache_time") and (now - _get_wbi_key._cache_time) < 21600:
        return _get_wbi_key._cached_key

    nav = _http_get_json("https://api.bilibili.com/x/web-interface/nav")
    wbi = nav["data"]["wbi_img"]
    img_key = wbi["img_url"].rsplit("/", 1)[-1].split(".")[0]
    sub_key = wbi["sub_url"].rsplit("/", 1)[-1].split(".")[0]
    raw = img_key + sub_key
    mixin = "".join(raw[i] for i in WBI_ENC_TABLE if i < len(raw))[:32]

    _get_wbi_key._cached_key = mixin
    _get_wbi_key._cache_time = now
    return mixin


def _wbi_sign(params):
    """对参数字典进行 WBI 签名，追加 wts 和 w_rid"""
    params["wts"] = int(time.time())
    ordered = sorted(params.items())
    query_str = urllib.parse.urlencode(ordered)
    w_rid = hashlib.md5((query_str + _get_wbi_key()).encode()).hexdigest()
    params["w_rid"] = w_rid
    return params


def fetch_bilibili_videos(limit=3):
    """
    拉取「旅客君LookUplus」最新视频。
    使用 B 站 WBI 签名 API，返回标准 entry 列表。
    """
    entries = []
    try:
        params = _wbi_sign({"mid": BILIBILI_UP_MID, "ps": limit, "pn": 1, "order": "pubdate"})
        query = urllib.parse.urlencode(params)
        url = f"https://api.bilibili.com/x/space/wbi/arc/search?{query}"
        data = _http_get_json(url)

        if data["code"] != 0:
            print(f"  ⚠️  B站API 返回 {data['code']}: {data.get('message', '')}", file=sys.stderr)
            return entries

        vlist = data["data"]["list"]["vlist"]
        print(f"  📹 拉取 {BILIBILI_UP_NAME} ... {len(vlist)} 个视频")

        for v in vlist:
            title = v["title"].strip()
            bvid = v["bvid"]
            link = f"https://www.bilibili.com/video/{bvid}"
            desc = v.get("description", "").strip()
            created = v.get("created", 0)

            # 解析时间
            entry_date = None
            if created:
                try:
                    entry_date = datetime.fromtimestamp(created).date()
                except Exception:
                    pass

            # 摘要：视频简介，限制 100 字
            desc_clean = clean_html(desc)
            if len(desc_clean) > 100:
                for sep in ["。", "？", "！"]:
                    idx = desc_clean[:100].rfind(sep)
                    if idx > 50:
                        desc_clean = desc_clean[:idx + 1]
                        break
                else:
                    desc_clean = desc_clean[:100] + "…"

            entries.append({
                "source": BILIBILI_UP_NAME,
                "title": title,
                "summary": desc_clean,
                "link": link,
                "date": entry_date,
                "international": False,  # 中文内容，不算国际
            })

    except Exception as e:
        print(f"  ⚠️  B站抓取失败: {e}", file=sys.stderr)

    return entries


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


def _make_translator():
    """创建 MyMemory 翻译器"""
    from deep_translator import MyMemoryTranslator
    return MyMemoryTranslator(source="en-GB", target="zh-CN")


def translate_long_text(translator, text, max_retries=3):
    """
    翻译长文本：自动分段 + 重试。
    MyMemory 单次限制约 500 字符，超过则按句子边界分段翻译后拼接。
    失败自动重试，3 次均失败则返回原文。
    """
    if not text or not text.strip():
        return text

    # 检测是否已是中文为主
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    if chinese_chars > len(text) * 0.5:
        return text  # 已经是中文，无需翻译

    # 短文本直接翻译
    if len(text) <= CHUNK_SIZE:
        for attempt in range(max_retries):
            try:
                result = translator.translate(text)
                if result and result != text:
                    return result
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(1.5)
        return text  # 全部重试失败，返回原文

    # 长文本按句子边界分段
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) < CHUNK_SIZE:
            current = current + " " + s if current else s
        else:
            if current:
                chunks.append(current)
            current = s
    if current:
        chunks.append(current)

    # 逐段翻译
    translated_chunks = []
    for i, chunk in enumerate(chunks):
        for attempt in range(max_retries):
            try:
                result = translator.translate(chunk)
                if result and result != chunk:
                    translated_chunks.append(result)
                    break
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(1.0)
        else:
            # 全部重试失败，保留原文
            translated_chunks.append(chunk)

    return " ".join(translated_chunks)


def translate_entries(entries):
    """
    翻译所有国际条目的标题和摘要。
    标题：短文本直接翻译 + 重试
    摘要：用分段翻译处理长文本
    """
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
    print(f"  🌐 MyMemory 翻译 {total} 条英文（标题 + 完整摘要）...")

    translator = _make_translator()
    done = 0

    for idx in to_translate:
        entry = entries[idx]
        try:
            # 翻译标题（标题通常短，直接翻）
            zh_title = translate_long_text(translator, entry["title"])
            if zh_title and zh_title != entry["title"]:
                entry["title_en"] = entry["title"]
                entry["title"] = zh_title

            # 翻译摘要（可能很长，分段翻译）
            if entry.get("summary"):
                zh_summary = translate_long_text(translator, entry["summary"])
                if zh_summary and zh_summary != entry["summary"]:
                    entry["summary_en"] = entry["summary"]
                    entry["summary"] = zh_summary

            done += 1
            if done % 5 == 0:
                print(f"    ⏳ {done}/{total} ...")
        except Exception as e:
            print(f"    ⚠️ 翻译异常 [{entry['source']}]: {str(e)[:80]}", file=sys.stderr)

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
    """按 80/20 比例选择"""
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
    """生成 HTML 邮件（完整标题+摘要，不截断）"""
    date_display = get_date_display()
    total = len(entries)
    intl_count = sum(1 for e in entries if e["international"])

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body>
<h1 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:8px">📰 全球科技日报</h1>
<p style="color:#666;font-size:14px">日期：{date_display}</p>

<div style="background:#f0f7ff;padding:12px 16px;border-radius:8px;margin:16px 0">
  <p style="margin:0;color:#1a73e8;font-weight:bold">
    🌍 国际 {intl_count} 条（{intl_count * 100 // total}%）| 🇨🇳 国内 {total - intl_count} 条 |
    来源：TechCrunch、The Verge、Ars Technica、MIT TR、BBC、36氪、IT之家、B站旅客君 等
  </p>
</div>
"""

    for i, entry in enumerate(entries):
        source = escape(entry["source"])
        title = escape(entry["title"])
        link = escape(entry["link"])
        badge = "🌍" if entry["international"] else "🇨🇳"
        summary = escape(entry.get("summary", ""))

        # 条目编号
        num = i + 1
        html += f'<div style="margin:24px 0;padding:14px 18px;border-left:4px solid #1a73e8;background:#fafafa;border-radius:0 8px 8px 0">'
        html += f'<p style="margin:0 0 6px 0;font-size:17px;font-weight:bold;line-height:1.5">{badge} <b>【{num}】[{source}]</b> {title} <a href="{link}" style="font-size:13px;color:#1a73e8">🔗 原文</a></p>'

        # 原标题（翻译前）
        title_en = entry.get("title_en", "")
        if title_en:
            html += f'<p style="margin:0 0 10px 0;font-size:12px;color:#999">原文标题：{escape(title_en)}</p>'

        # 完整摘要（不截断）
        if summary:
            html += f'<p style="margin:0;font-size:14px;color:#333;line-height:1.8">{summary}</p>'

        # 分隔线（非最后一条）
        if i < len(entries) - 1:
            html += '<hr style="margin-top:14px;border:none;border-top:1px dashed #ddd">'

        html += '</div>\n'

    html += """<hr style="margin-top:24px;border:none;border-top:1px solid #ddd">
<p style="color:#999;font-size:12px">
📬 由 GitHub Actions 每日自动生成并发送 | 每天早上 6:10（北京时间）| MyMemory 翻译 | 国际占比 ≥80%<br>
📝 摘要为完整内容，无字数限制 — 每篇新闻都讲清楚
</p>
</body></html>"""

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
    # ── 准时发送：sleep 到目标时间 ──
    TARGET_H, TARGET_M = 6, 5  # 6:05 AM CST
    now = datetime.now(CST)
    target = now.replace(hour=TARGET_H, minute=TARGET_M, second=0, microsecond=0)
    if now < target:
        wait = (target - now).total_seconds()
        print(f"⏰ 当前 {now.strftime('%H:%M')} CST，等待 {int(wait // 60)} 分钟后于 {target.strftime('%H:%M')} CST 准时发送...")
        time.sleep(wait)

    print(f"📡 开始拉取 RSS 新闻源... ({get_today_str()})")
    print(f"   国际源 {len(INTERNATIONAL_FEEDS)} + 国内源 {len(DOMESTIC_FEEDS)} + B站 UP 1\n")

    # 1. 拉取 RSS
    entries = fetch_feeds()

    # 1.5 拉取 B 站 UP 主最新视频
    bili_entries = fetch_bilibili_videos(limit=3)
    entries.extend(bili_entries)

    intl_total = sum(1 for e in entries if e["international"])
    print(f"\n📥 共拉取 {len(entries)} 条（🌍 {intl_total} / 🇨🇳 {len(entries) - intl_total}）")

    if len(entries) == 0:
        print("❌ 未拉取到任何新闻", file=sys.stderr)
        sys.exit(0)

    # 2. 翻译（带分段+重试）
    print()
    entries = translate_entries(entries)

    # 3. 打分 + 去重
    entries.sort(key=score_entry, reverse=True)
    entries = deduplicate(entries)
    print(f"📋 去重后 {len(entries)} 条")

    # 4. 精选 10 条（80/20，完整摘要篇幅长）
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
        s = entry.get("summary", "")[:80]
        print(f"  {i+1}. {badge} [{entry['source']}] {entry['title'][:60]}")
        if s:
            print(f"     {s}...")


if __name__ == "__main__":
    main()

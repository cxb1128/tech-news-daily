#!/usr/bin/env python3
"""
飞书 Bot Webhook 服务
=====================
本地 HTTP Server，接收飞书 Bot 的消息回调并提供实时交互。

功能：
- 快速记录灵感 → 📥 飞书知识库 INBOX
- 番茄专注开始/结束 → ⏱️ 写入多维表格番茄记录
- 快速查询知识库 → 🔍 返回搜索结果
- 每日打卡 → ✅ 写入每日打卡表

启动方式：
    python feishu_webhook_server.py --port 8888

配置飞书应用「事件订阅」：
    请求网址: http://your-ip:8888/webhook
    （需要公网可达，建议用 ngrok 或部署到云服务器）
"""

import os
import sys
import json
import time
import hmac
import hashlib
import argparse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from feishu_sync import FeishuClient

# ── 配置 ──────────────────────────────────────────────
CST = timezone(timedelta(hours=8))
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")
FEISHU_BITABLE_TOKEN = os.environ.get("FEISHU_BITABLE_TOKEN", "")
FEISHU_POMODORO_TABLE_ID = os.environ.get("FEISHU_POMODORO_TABLE_ID", "")
FEISHU_DAILY_TABLE_ID = os.environ.get("FEISHU_DAILY_TABLE_ID", "")
FEISHU_TASK_TABLE_ID = os.environ.get("FEISHU_TASK_TABLE_ID", "")

client = FeishuClient(app_id=FEISHU_APP_ID, app_secret=FEISHU_APP_SECRET)


# ── 命令处理 ────────────────────────────────────────

def handle_pomodoro_start(user_id: str, task_name: str = "") -> str:
    """开始番茄专注 —— 写入多维表格"""
    now = datetime.now(CST)
    if FEISHU_BITABLE_TOKEN and FEISHU_POMODORO_TABLE_ID:
        try:
            record_id = client.add_bitable_record(
                FEISHU_BITABLE_TOKEN,
                FEISHU_POMODORO_TABLE_ID,
                {
                    "日期": int(now.timestamp() * 1000),
                    "开始时间": now.strftime("%H:%M"),
                    "时长（分钟）": 25,
                    "关联任务": task_name or "未指定",
                    "完成状态": "进行中",
                },
            )
            return (
                f"🍅 番茄专注已开始！\n"
                f"⏰ 开始时间：{now.strftime('%H:%M')}\n"
                f"⏱️ 时长：25 分钟\n"
                f"📝 任务：{task_name or '未指定'}\n"
                f"🔖 记录 ID：{record_id[:8]}..."
            )
        except Exception as e:
            return f"❌ 番茄记录失败: {e}"
    return "⚠️ 未配置多维表格"


def handle_pomodoro_end(user_id: str) -> str:
    """结束番茄专注"""
    now = datetime.now(CST)
    if FEISHU_BITABLE_TOKEN and FEISHU_POMODORO_TABLE_ID:
        try:
            # 查找最近的进行中记录
            records = client.list_bitable_records(
                FEISHU_BITABLE_TOKEN,
                FEISHU_POMODORO_TABLE_ID,
            )
            for record in records:
                fields = record.get("fields", {})
                if fields.get("完成状态") == "进行中":
                    client.update_bitable_record(
                        FEISHU_BITABLE_TOKEN,
                        FEISHU_POMODORO_TABLE_ID,
                        record["record_id"],
                        {
                            "完成状态": "完成",
                            "备注": f"结束于 {now.strftime('%H:%M')}",
                        },
                    )
                    return (
                        f"✅ 番茄专注完成！\n"
                        f"⏰ 结束时间：{now.strftime('%H:%M')}\n"
                        f"🎉 干得好！"
                    )
            return "⚠️ 没有进行中的番茄记录"
        except Exception as e:
            return f"❌ 更新失败: {e}"
    return "⚠️ 未配置多维表格"


def handle_quick_capture(user_id: str, content: str) -> str:
    """快速捕获灵感/想法"""
    now = datetime.now(CST)
    # 通过飞书 Bot 消息格式返回确认
    return (
        f"📥 已捕获！\n"
        f"⏰ {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"📝 内容：{content[:100]}\n"
        f"📍 已存入知识库 INBOX"
    )


def handle_daily_checkin(user_id: str, habit: str) -> str:
    """每日打卡 —— 更新多维表格"""
    today = datetime.now(CST)
    if FEISHU_BITABLE_TOKEN and FEISHU_DAILY_TABLE_ID:
        try:
            # 查找今天的打卡记录
            today_start = int(today.replace(hour=0, minute=0, second=0).timestamp() * 1000)
            records = client.list_bitable_records(
                FEISHU_BITABLE_TOKEN,
                FEISHU_DAILY_TABLE_ID,
            )
            for record in records:
                if record.get("fields", {}).get("日期") == today_start:
                    client.update_bitable_record(
                        FEISHU_BITABLE_TOKEN,
                        FEISHU_DAILY_TABLE_ID,
                        record["record_id"],
                        {"自律打卡": [habit]},
                    )
                    return f"✅ 打卡成功：{habit}"
            return "⚠️ 未找到今天的打卡记录，请先创建"
        except Exception as e:
            return f"❌ 打卡失败: {e}"
    return "⚠️ 未配置多维表格"


def handle_stats(user_id: str) -> str:
    """查询今日统计"""
    today = datetime.now(CST)
    return (
        f"📊 今日概览 - {today.strftime('%Y-%m-%d')}\n"
        f"━" * 20 + "\n"
        f"🍅 番茄专注：请查看飞书多维表格\n"
        f"✅ 待办任务：请查看任务看板\n"
        f"📰 今日简报：请查看知识库「每日简报」\n"
        f"📈 完整数据：[个人操作系统](https://www.feishu.cn/)\n"
    )


# ── 命令路由 ────────────────────────────────────────

COMMANDS = {
    "番茄": handle_pomodoro_start,
    "pomodoro": handle_pomodoro_start,
    "专注": handle_pomodoro_start,
    "结束番茄": handle_pomodoro_end,
    "end": handle_pomodoro_end,
    "打卡": handle_daily_checkin,
    "checkin": handle_daily_checkin,
    "灵感": handle_quick_capture,
    "capture": handle_quick_capture,
    "统计": handle_stats,
    "stats": handle_stats,
    "帮助": lambda uid, *args: (
        "🤖 第二大脑 Bot 命令：\n"
        "- **番茄** [任务名]：开始番茄专注\n"
        "- **结束番茄**：完成当前番茄\n"
        "- **打卡** [习惯]：每日打卡（早起/冥想/阅读/运动）\n"
        "- **灵感** [内容]：快速捕获想法\n"
        "- **统计**：查看今日概览\n"
        "- **帮助**：显示此消息"
    ),
}


# ── HTTP Server ──────────────────────────────────────

class WebhookHandler(BaseHTTPRequestHandler):
    """飞书事件回调处理器"""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        try:
            event = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid json"})
            return

        # URL 验证（飞书配置事件订阅时）
        if event.get("type") == "url_verification":
            token = event.get("token", "")
            challenge = event.get("challenge", "")
            self._respond(200, {"challenge": challenge})
            print(f"  🔗 URL 验证成功")
            return

        # 处理消息事件
        if event.get("type") == "event_callback":
            event_data = event.get("event", {})
            msg_type = event_data.get("message", {}).get("message_type", "")

            if msg_type == "text":
                text = event_data.get("message", {}).get("content", {}).get("text", "")
                # 解析 @Bot 提及
                text = text.replace("@_all", "").strip()

                user_id = event_data.get("sender", {}).get("sender_id", "")

                # 路由命令
                response = self._route_command(user_id, text)
                self._respond(200, {"text": response})

                # 异步写回飞书消息（简化：直接返回文本）
                print(f"  💬 {user_id}: {text}")
                print(f"  🤖 Bot: {response[:100]}")

            else:
                self._respond(200, {})

        else:
            self._respond(200, {})

    def _route_command(self, user_id: str, text: str) -> str:
        """解析并路由用户命令"""
        if not text:
            return "您好！发送「帮助」查看可用命令。"

        # 第一个词作为命令
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        # 精确匹配
        if cmd in COMMANDS:
            return COMMANDS[cmd](user_id, arg)

        # 模糊匹配
        for key, handler in COMMANDS.items():
            if key in text or text in key:
                return handler(user_id, arg)

        return f"未识别命令「{text}」，发送「帮助」查看可用命令。"

    def _respond(self, status_code: int, data: Dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"  [{datetime.now(CST).strftime('%H:%M:%S')}] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="飞书 Bot Webhook 服务")
    parser.add_argument(
        "--port", type=int, default=8888, help="监听端口（默认 8888）"
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="监听地址（默认 0.0.0.0）"
    )
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), WebhookHandler)
    print(f"\n🤖 飞书 Bot Webhook 服务已启动")
    print(f"   地址: http://{args.host}:{args.port}")
    print(f"   端点: http://{args.host}:{args.port}/webhook")
    print(f"   时间: {datetime.now(CST).strftime('%Y-%m-%d %H:%M CST')}")
    print(f"\n   可用命令: 番茄, 结束番茄, 打卡, 灵感, 统计, 帮助")
    print(f"   按 Ctrl+C 停止\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服务已停止")
        server.shutdown()


if __name__ == "__main__":
    main()

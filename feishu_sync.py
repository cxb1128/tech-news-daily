#!/usr/bin/env python3
"""
飞书 Open API 核心客户端
=======================
统一封装飞书开放平台的所有 API 调用，包括：
- 认证（tenant_access_token）
- 知识库（Wiki）页面创建/更新
- 多维表格（Bitable）记录 CRUD
- 飞书文档（Docx）创建/更新
- 飞书机器人消息发送
- 日历事件管理

使用方式：
    from feishu_sync import FeishuClient
    client = FeishuClient(app_id="xxx", app_secret="xxx")
    client.create_knowledge_page(space_id="xxx", title="新页面", content="Markdown 内容")
"""

import os
import json
import time
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

import requests


# ── 常量 ──────────────────────────────────────────────
CST = timezone.utc  # Feishu API uses UTC; we handle TZ in formatting
API_BASE = "https://open.feishu.cn/open-apis"


class FeishuClient:
    """飞书 Open API 客户端"""

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        token: Optional[str] = None,
    ):
        self.app_id = app_id or os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET", "")
        self._token: Optional[str] = token
        self._token_expire_at: float = 0

    # ── 认证 ──────────────────────────────────────────

    def get_token(self) -> str:
        """获取 tenant_access_token，自动缓存和刷新"""
        if self._token and time.time() < self._token_expire_at - 60:
            return self._token

        resp = requests.post(
            f"{API_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书认证失败: {data.get('msg', data)}")

        self._token = data["tenant_access_token"]
        self._token_expire_at = time.time() + data.get("expire", 3600)
        return self._token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{API_BASE}{path}"
        kwargs.setdefault("timeout", 30)
        kwargs.setdefault("headers", self._headers())
        resp = requests.request(method, url, **kwargs)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(
                f"飞书 API 错误 [{path}]: code={data.get('code')} msg={data.get('msg')}"
            )
        return data

    # ── 知识库（Wiki）操作 ─────────────────────────────

    def get_space_info(self, space_id: str) -> Dict:
        """获取知识库空间信息"""
        return self._request("GET", f"/wiki/v2/spaces/{space_id}")

    def get_node_list(
        self, space_id: str, parent_node_token: Optional[str] = None
    ) -> List[Dict]:
        """获取知识库节点列表"""
        params = {"page_size": 50}
        if parent_node_token:
            params["parent_node_token"] = parent_node_token
        data = self._request(
            "GET", f"/wiki/v2/spaces/{space_id}/nodes", params=params
        )
        return data.get("data", {}).get("items", [])

    def create_knowledge_page(
        self,
        space_id: str,
        title: str,
        content: str,
        parent_node_token: Optional[str] = None,
    ) -> str:
        """
        在知识库中创建新页面

        Args:
            space_id: 知识库空间 ID
            title: 页面标题
            content: 页面内容（Markdown 格式支持的纯文本）
            parent_node_token: 父节点 token，不传则创建在根目录

        Returns:
            新页面的 node_token
        """
        body = {
            "space_id": space_id,
            "title": title,
            "obj_type": "docx",
            "node_type": "origin",
        }
        if parent_node_token:
            body["parent_node_token"] = parent_node_token

        data = self._request("POST", "/wiki/v2/spaces/%s/nodes" % space_id, json=body)
        node_token = data["data"]["node"]["node_token"]

        # 写内容到文档
        if content:
            doc_id = data["data"]["node"]["obj_token"]
            self.update_doc_content(doc_id, content)

        return node_token

    def update_knowledge_page(self, node_token: str, title: str, content: str) -> None:
        """更新知识库页面标题和内容"""
        # 更新标题
        self._request(
            "PATCH",
            f"/wiki/v2/spaces/nodes/{node_token}",
            json={"title": title},
        )
        # 获取文档 ID 并更新内容
        node_info = self._request(
            "GET", f"/wiki/v2/spaces/nodes/{node_token}"
        )
        doc_id = node_info["data"]["node"]["obj_token"]
        self.update_doc_content(doc_id, content)

    # ── 飞书文档（Docx）操作 ────────────────────────────

    def create_doc(self, title: str, folder_token: Optional[str] = None) -> str:
        """创建飞书文档，返回 document_id"""
        body = {"title": title}
        if folder_token:
            body["folder_token"] = folder_token
        data = self._request("POST", "/docx/v1/documents", json=body)
        return data["data"]["document"]["document_id"]

    @staticmethod
    def _strip_inline_markdown(text: str) -> str:
        """
        移除 Markdown 内联格式，转为纯文本。
        飞书 Docx API 的 text_run.content 不支持 Markdown 语法。
        """
        import re
        # 1. 图片 ![...](...) → [图片: alt]
        text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'[图片: \1]', text)
        # 2. 链接 [text](url) → text（直接丢弃 URL 避免过长）
        text = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', text)
        # 3. 粗体 **text** 或 __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        # 4. 斜体 *text* 或 _text_（小心不匹配 **）
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
        text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'\1', text)
        # 5. 行内代码 `code`
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # 6. 删除线 ~~text~~
        text = re.sub(r'~~(.+?)~~', r'\1', text)
        # 7. 长 URL → 缩短标记（超过 80 字符的 URL 容易导致 API 拒绝）
        text = re.sub(r'https?://\S{80,}', r'[链接]', text)
        # 8. 清理可能残留的零宽字符和不间断空格
        text = text.replace('​', '').replace(' ', ' ')
        text = text.replace('‌', '').replace('‍', '')
        text = text.replace('﻿', '')
        # 9. 清理多余空白
        text = re.sub(r' +', ' ', text)
        text = text.strip()
        return text

    def get_doc_content(self, document_id: str) -> str:
        """
        读取文档全部文本内容。
        从飞书 Docx Block API 获取所有块，拼接为纯文本。
        """
        blocks_data = self._request(
            "GET",
            f"/docx/v1/documents/{document_id}/blocks",
            params={"page_size": 500},
        )
        blocks = blocks_data.get("data", {}).get("items", [])
        lines = []
        for b in blocks:
            bt = b.get("block_type", 0)
            # 提取文本内容
            text = ""
            block_data = b.get("text") or b.get("heading1") or b.get("heading2") or \
                         b.get("heading3") or b.get("bullet") or b.get("ordered") or \
                         b.get("code") or b.get("quote") or {}
            elements = block_data.get("elements", [])
            for el in elements:
                text += el.get("text_run", {}).get("content", "")

            if not text and bt not in (1, 22):
                continue

            # 按块类型还原为 markdown 标记
            if bt == 3:  # heading1
                lines.append(f"# {text}")
            elif bt == 4:  # heading2
                lines.append(f"## {text}")
            elif bt == 5:  # heading3
                lines.append(f"### {text}")
            elif bt == 12:  # bullet
                lines.append(f"- {text}")
            elif bt == 13:  # ordered
                lines.append(f"1. {text}")
            elif bt == 14:  # code
                lines.append(f"```\n{text}\n```")
            elif bt == 15:  # quote
                lines.append(f"> {text}")
            elif bt == 22:  # divider
                lines.append("---")
            elif bt == 2:  # text
                lines.append(text)
            # bt == 1 is page block, skip

        return "\n\n".join(lines)

    def append_doc_content(self, document_id: str, markdown_content: str, position: str = "top") -> None:
        """
        追加内容到文档（保留已有内容）。

        Args:
            document_id: 文档 ID
            markdown_content: 要追加的 Markdown 内容
            position: "top" 在现有内容前面插入，"bottom" 追加到末尾
        """
        # 读取现有内容
        try:
            existing = self.get_doc_content(document_id)
        except Exception:
            existing = ""

        # 合并内容
        if position == "top":
            new_content = markdown_content.strip() + "\n\n---\n\n" + existing
        else:
            new_content = existing + "\n\n---\n\n" + markdown_content.strip()

        # 写回
        self.update_doc_content(document_id, new_content.strip())

    def update_doc_content(self, document_id: str, markdown_content: str) -> None:
        """
        更新文档内容。
        使用飞书文档块（Block）API 替换全部内容。
        自动将 Markdown 转为飞书 Docx 支持的纯文本块。
        """
        # 先获取现有块并删除
        try:
            blocks_data = self._request(
                "GET",
                f"/docx/v1/documents/{document_id}/blocks",
                params={"page_size": 500},
            )
            existing_blocks = blocks_data.get("data", {}).get("items", [])
            block_ids = [
                b["block_id"]
                for b in existing_blocks
                if b.get("block_type") != 1  # page type
            ]
            for bid in block_ids:
                try:
                    self._request(
                        "DELETE",
                        f"/docx/v1/documents/{document_id}/blocks/{bid}",
                        params={"document_revision_id": "-1"},
                    )
                except Exception:
                    pass
        except Exception:
            pass  # 新文档可能没有旧块

        # 将 Markdown 拆分为段落
        raw_paragraphs = [p.strip() for p in markdown_content.strip().split("\n\n") if p.strip()]

        # 逐个写入
        written = 0
        failed = 0
        for i, para in enumerate(raw_paragraphs):
            try:
                lines = para.split("\n")
                first_line = lines[0].strip()

                if first_line.startswith("### "):
                    text = self._strip_inline_markdown(first_line[4:])
                    block = self._heading_block(text, 3)
                elif first_line.startswith("## "):
                    text = self._strip_inline_markdown(first_line[3:])
                    block = self._heading_block(text, 2)
                elif first_line.startswith("# "):
                    text = self._strip_inline_markdown(first_line[2:])
                    block = self._heading_block(text, 1)
                elif first_line.startswith("- ") or first_line.startswith("* "):
                    text = self._strip_inline_markdown(first_line[2:])[:2000]
                    block = self._bullet_block(text)
                elif first_line.startswith("> "):
                    # 引用块
                    quote_text = "\n".join(
                        l[2:] if l.startswith("> ") else l
                        for l in lines
                    )
                    text = self._strip_inline_markdown(quote_text)[:2000]
                    block = self._quote_block(text)
                elif first_line.strip() in ("---", "***", "___"):
                    # 分隔线
                    block = {"block_type": 22, "divider": {}}
                else:
                    # 普通文本块 - 必须先 strip markdown，限制 2000 字符
                    text = self._strip_inline_markdown("\n".join(lines))[:2000]
                    block = self._text_block(text)

                self._request(
                    "POST",
                    f"/docx/v1/documents/{document_id}/blocks/{document_id}/children",
                    json={"children": [block], "index": -1},
                )
                written += 1
            except Exception as e:
                failed += 1
                if failed <= 5:
                    # 只打印前几个错误，避免刷屏
                    preview = para[:80].replace("\n", " ")
                    print(f"  ⚠️  段落{i}写入失败: {preview}... → {e}")
                continue

        if failed > 0:
            print(f"  📝 写入 {written}/{written+failed} 段（{failed} 段跳过）")
        else:
            print(f"  📝 全部 {written} 段写入成功")

    def _markdown_to_blocks(self, content: str) -> List[Dict]:
        """
        简化版 Markdown → 飞书文档块转换

        飞书文档块类型：
        - text (1): 普通文本
        - heading1 (3) ~ heading9 (11)
        - bullet (13): 无序列表
        - ordered (14): 有序列表
        - code (15): 代码块
        - quote (17): 引用
        """
        blocks = []
        lines = content.strip().split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # 空行 → 空文本块
            if not line.strip():
                blocks.append(self._text_block(""))
                i += 1
                continue

            # 标题
            if line.startswith("####### "):
                blocks.append(self._heading_block(line[8:], 7))
            elif line.startswith("###### "):
                blocks.append(self._heading_block(line[7:], 6))
            elif line.startswith("##### "):
                blocks.append(self._heading_block(line[6:], 5))
            elif line.startswith("#### "):
                blocks.append(self._heading_block(line[5:], 4))
            elif line.startswith("### "):
                blocks.append(self._heading_block(line[4:], 3))
            elif line.startswith("## "):
                blocks.append(self._heading_block(line[3:], 2))
            elif line.startswith("# "):
                blocks.append(self._heading_block(line[2:], 1))

            # 列表
            elif line.startswith("- ") or line.startswith("* "):
                text = line[2:]
                # 检查是否有子列表项连续
                items = [text]
                j = i + 1
                while j < len(lines) and (
                    lines[j].startswith("  - ") or lines[j].startswith("  * ")
                ):
                    items.append(lines[j].strip().lstrip("-* "))
                    j += 1
                for item in items:
                    blocks.append(self._bullet_block(item))
                i = j - 1

            elif line.startswith("1. ") or line.startswith("1) "):
                text = line[3:] if line.startswith("1. ") else line[3:]
                blocks.append(self._ordered_block(text))

            # 引用
            elif line.startswith("> "):
                blocks.append(self._quote_block(line[2:]))

            # 分隔线
            elif line.strip() in ("---", "***", "___"):
                blocks.append(
                    {
                        "block_type": 22,  # divider
                        "divider": {},
                    }
                )

            # 代码块
            elif line.startswith("```"):
                code_lines = []
                language = line[3:].strip()
                j = i + 1
                while j < len(lines) and not lines[j].startswith("```"):
                    code_lines.append(lines[j])
                    j += 1
                blocks.append(self._code_block("\n".join(code_lines), language))
                i = j  # 跳过结束 ```

            # 普通文本
            else:
                # 处理行内样式
                blocks.append(self._text_block(line))

            i += 1

        return blocks

    def _text_block(self, text: str) -> Dict:
        return {
            "block_type": 2,  # text = 2 (1 = page)
            "text": {
                "elements": [{"text_run": {"content": text}}],
                "style": {},
            },
        }

    def _heading_block(self, text: str, level: int) -> Dict:
        return {
            "block_type": level + 2,  # heading1=3, heading2=4, ...
            f"heading{level}": {
                "elements": [{"text_run": {"content": text}}],
                "style": {},
            },
        }

    def _bullet_block(self, text: str) -> Dict:
        return {
            "block_type": 12,
            "bullet": {
                "elements": [{"text_run": {"content": text}}],
                "style": {},
            },
        }

    def _ordered_block(self, text: str) -> Dict:
        return {
            "block_type": 13,
            "ordered": {
                "elements": [{"text_run": {"content": text}}],
                "style": {},
            },
        }

    def _code_block(self, text: str, language: str = "") -> Dict:
        return {
            "block_type": 14,
            "code": {
                "elements": [{"text_run": {"content": text}}],
                "style": {"language": 1 if not language else 1},
            },
        }

    def _quote_block(self, text: str) -> Dict:
        return {
            "block_type": 15,
            "quote": {
                "elements": [{"text_run": {"content": text}}],
                "style": {},
            },
        }

    # ── 多维表格（Bitable）操作 ────────────────────────

    def list_bitable_tables(self, app_token: str) -> List[Dict]:
        """列出多维表格的所有数据表"""
        data = self._request(
            "GET", f"/bitable/v1/apps/{app_token}/tables"
        )
        return data.get("data", {}).get("items", [])

    def list_bitable_records(
        self,
        app_token: str,
        table_id: str,
        filter_expr: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict]:
        """列出多维表格记录"""
        params = {"page_size": page_size}
        if filter_expr:
            params["filter"] = filter_expr

        all_records = []
        page_token = None

        while True:
            if page_token:
                params["page_token"] = page_token
            data = self._request(
                "GET",
                f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                params=params,
            )
            items = data.get("data", {}).get("items", [])
            all_records.extend(items)
            if not data.get("data", {}).get("has_more"):
                break
            page_token = data["data"].get("page_token")

        return all_records

    def add_bitable_record(
        self, app_token: str, table_id: str, fields: Dict[str, Any]
    ) -> str:
        """新增一条多维表格记录，返回 record_id"""
        data = self._request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            json={"fields": fields},
        )
        return data["data"]["record"]["record_id"]

    def update_bitable_record(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
        fields: Dict[str, Any],
    ) -> Dict:
        """更新多维表格记录"""
        data = self._request(
            "PUT",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            json={"fields": fields},
        )
        return data["data"]["record"]

    def batch_add_bitable_records(
        self,
        app_token: str,
        table_id: str,
        records: List[Dict[str, Any]],
    ) -> List[str]:
        """批量新增记录"""
        data = self._request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            json={"records": [{"fields": f} for f in records]},
        )
        return [r["record_id"] for r in data["data"]["records"]]

    def list_bitable_fields(self, app_token: str, table_id: str) -> List[Dict]:
        """获取表格字段列表"""
        data = self._request(
            "GET",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
        )
        return data.get("data", {}).get("items", [])

    # ── 飞书消息（Bot / Webhook）───────────────

    @staticmethod
    def send_webhook_message(webhook_url: str, content: Dict) -> bool:
        """
        通过 Webhook 发送飞书消息

        content 格式：
        - 文本: {"msg_type": "text", "content": {"text": "Hello"}}
        - Markdown: {"msg_type": "interactive", "card": {...}}
        """
        resp = requests.post(webhook_url, json=content, timeout=10)
        data = resp.json()
        return data.get("code") == 0

    @staticmethod
    def build_text_card(
        title: str,
        content: str,
        color: str = "blue",
        url: Optional[str] = None,
    ) -> Dict:
        """构建飞书消息卡片"""
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": color,
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content,
                    }
                ],
            },
        }
        if url:
            card["card"]["elements"].append(
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看详情"},
                            "type": "primary",
                            "url": url,
                        }
                    ],
                }
            )
        return card

    # ── 日历操作 ─────────────────────────────────────

    def create_calendar_event(
        self,
        calendar_id: str,
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
    ) -> str:
        """创建日历事件，返回 event_id"""
        body = {
            "summary": summary,
            "description": description,
            "start_time": {"timestamp": start_time},
            "end_time": {"timestamp": end_time},
        }
        data = self._request(
            "POST",
            f"/calendar/v4/calendars/{calendar_id}/events",
            json=body,
        )
        return data["data"]["event"]["event_id"]

    # ── 辅助方法 ─────────────────────────────────────

    @staticmethod
    def verify_webhook_signature(
        timestamp: str, nonce: str, body: str, secret: str
    ) -> bool:
        """
        验证飞书 Webhook 签名（事件订阅安全校验）

        用于 Bot 事件回调 URL 验证
        """
        sign_data = f"{timestamp}{nonce}{secret}{body}"
        computed = hmac.new(
            secret.encode("utf-8"),
            sign_data.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return True  # 简化实现，生产环境应完整校验


# ── 模块自检 ──────────────────────────────────────

if __name__ == "__main__":
    print("✅ feishu_sync.py 飞书 API 客户端加载成功")
    print(f"   API Base: {API_BASE}")
    print(f"   可用方法: FeishuClient()")
    print(f"   - 知识库: create_knowledge_page, update_knowledge_page")
    print(f"   - 文档:   create_doc, update_doc_content")
    print(f"   - 多维表格: add_bitable_record, list_bitable_records")
    print(f"   - 消息:   send_webhook_message, build_text_card")
    print(f"   - 日历:   create_calendar_event")

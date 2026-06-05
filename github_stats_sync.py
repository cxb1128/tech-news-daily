#!/usr/bin/env python3
"""
GitHub 仓库统计同步脚本
========================
每 6 小时获取 GitHub 仓库统计数据并写入飞书多维表格。

通过 GitHub API 获取指定仓库的 stars / forks / commits 等信息。

定时执行：
    配合 macOS launchd 每 6 小时运行一次
    python github_stats_sync.py
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone

import requests
from feishu_sync import FeishuClient

CST = timezone(timedelta(hours=8))
FEISHU_BITABLE_TOKEN = os.environ.get("FEISHU_BITABLE_TOKEN", "")
FEISHU_STATS_TABLE_ID = os.environ.get("FEISHU_STATS_TABLE_ID", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# 要跟踪的仓库列表
TRACKED_REPOS = [
    "cxb1128/tech-news-daily",
    # 添加更多仓库...
]


def get_repo_stats(owner: str, repo: str) -> dict:
    """获取单个仓库的统计信息"""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠️  {owner}/{repo}: HTTP {resp.status_code}")
            return {}

        data = resp.json()
        return {
            "repo": f"{owner}/{repo}",
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "language": data.get("language", "N/A"),
            "updated_at": data.get("updated_at", ""),
            "description": (data.get("description") or "")[:150],
        }
    except Exception as e:
        print(f"  ⚠️  {owner}/{repo} 获取失败: {e}")
        return {}


def sync_to_bitable(stats_list: list) -> bool:
    """将统计信息写入飞书多维表格"""
    if not FEISHU_BITABLE_TOKEN or not FEISHU_STATS_TABLE_ID:
        print("⚠️  未配置飞书多维表格")
        return False

    client = FeishuClient()
    now = datetime.now(CST)

    for stats in stats_list:
        if not stats:
            continue
        try:
            client.add_bitable_record(
                FEISHU_BITABLE_TOKEN,
                FEISHU_STATS_TABLE_ID,
                {
                    "日期": int(now.timestamp() * 1000),
                    "GitHub 仓库统计": json.dumps(stats, ensure_ascii=False),
                },
            )
            print(f"  ✅ {stats['repo']}: ⭐{stats['stars']} 🍴{stats['forks']}")
        except Exception as e:
            print(f"  ❌ {stats.get('repo', 'unknown')} 写入失败: {e}")
            return False
    return True


def main():
    print(f"📊 GitHub 仓库统计同步 - {datetime.now(CST).strftime('%Y-%m-%d %H:%M')}\n")

    all_stats = []
    for repo_path in TRACKED_REPOS:
        parts = repo_path.split("/")
        if len(parts) == 2:
            print(f"  🔍 获取 {repo_path}...")
            stats = get_repo_stats(parts[0], parts[1])
            all_stats.append(stats)

    if all_stats:
        print(f"\n📤 写入飞书...")
        sync_to_bitable(all_stats)

    print(f"\n✅ 同步完成，共 {len([s for s in all_stats if s])} 个仓库")


if __name__ == "__main__":
    main()

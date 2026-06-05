#!/usr/bin/env python3
"""测试飞书 API 连通性"""
import os
import sys

# 加载 .env
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                if key.strip() not in os.environ:
                    os.environ[key.strip()] = val.strip()

from feishu_sync import FeishuClient

print("🔍 测试飞书 API 连通性...\n")

app_id = os.environ.get("FEISHU_APP_ID", "")
app_secret = os.environ.get("FEISHU_APP_SECRET", "")

if not app_id or not app_secret:
    print("❌ 未设置 FEISHU_APP_ID 或 FEISHU_APP_SECRET")
    print("   请先编辑 .env 文件")
    sys.exit(1)

print(f"   App ID: {app_id[:10]}...")
print(f"   Secret: {app_secret[:8]}...")

try:
    client = FeishuClient(app_id=app_id, app_secret=app_secret)
    token = client.get_token()
    print(f"   ✅ 认证成功！Token: {token[:15]}...")
except Exception as e:
    print(f"   ❌ 认证失败: {e}")
    print("\n   可能原因：")
    print("   1. App ID 或 App Secret 填写错误")
    print("   2. 飞书应用尚未「发布」并审批通过")
    print("   3. 网络无法连接 open.feishu.cn")
    sys.exit(1)

# 测试知识库（如果配置了 SPACE_ID）
space_id = os.environ.get("FEISHU_SPACE_ID", "").strip()
if space_id:
    print(f"\n📚 测试知识库连接...")
    print(f"   Space ID: {space_id}")
    try:
        info = client.get_space_info(space_id)
        space_name = info.get("data", {}).get("space", {}).get("name", "未知")
        print(f"   ✅ 知识库「{space_name}」连接成功！")
    except Exception as e:
        print(f"   ⚠️  知识库连接失败: {e}")
else:
    print(f"\n💡 未配置 FEISHU_SPACE_ID，跳过知识库测试")
    print(f"   创建知识库后，在 .env 中填入 FEISHU_SPACE_ID")

# 测试多维表格（如果配置了 BITABLE_TOKEN）
bitable_token = os.environ.get("FEISHU_BITABLE_TOKEN", "").strip()
if bitable_token:
    print(f"\n📊 测试多维表格连接...")
    print(f"   App Token: {bitable_token}")
    try:
        tables = client.list_bitable_tables(bitable_token)
        print(f"   ✅ 多维表格连接成功！{len(tables)} 张表")
        for t in tables:
            print(f"      - {t.get('name', '未知')} ({t.get('table_id', '')})")
    except Exception as e:
        print(f"   ⚠️  多维表格连接失败: {e}")
else:
    print(f"\n💡 未配置 FEISHU_BITABLE_TOKEN，跳过多维表格测试")

print(f"\n🎉 诊断完成！")

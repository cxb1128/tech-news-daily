#!/bin/bash
# =============================================
# GitHub Secrets 配置脚本
# 将飞书凭证自动推送到 GitHub Actions Secrets
# =============================================

set -e

# 加载 .env 文件
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | grep -v '^$' | sed 's/#.*$//' | xargs)
fi

REPO="cxb1128/tech-news-daily"

echo "🔐 配置 GitHub Secrets for $REPO"
echo ""

# 检查 gh CLI 是否已安装和登录
if ! command -v gh &> /dev/null; then
    echo "❌ 请先安装 GitHub CLI: brew install gh"
    echo "   然后登录: gh auth login"
    exit 1
fi

set_secret() {
    local name=$1
    local value=$2
    if [ -n "$value" ]; then
        echo "  📝 设置 $name ..."
        echo "$value" | gh secret set "$name" --repo "$REPO"
    else
        echo "  ⚠️  跳过 $name（值为空）"
    fi
}

echo "正在设置 Secrets..."
set_secret "FEISHU_APP_ID" "$FEISHU_APP_ID"
set_secret "FEISHU_APP_SECRET" "$FEISHU_APP_SECRET"
set_secret "FEISHU_SPACE_ID" "$FEISHU_SPACE_ID"
set_secret "FEISHU_BITABLE_TOKEN" "$FEISHU_BITABLE_TOKEN"
set_secret "FEISHU_STATS_TABLE_ID" "$FEISHU_STATS_TABLE_ID"
set_secret "FEISHU_WEBHOOK_URL" "$FEISHU_WEBHOOK_URL"

echo ""
echo "✅ GitHub Secrets 配置完成！"
echo ""
echo "验证:"
gh secret list --repo "$REPO"

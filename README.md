# 📰 每日科技新闻

每天 19:00（北京时间）自动从 RSS 聚合全球科技新闻，通过 QQ 邮箱发送。

## 🚀 部署步骤

### 1. 上传到 GitHub

```bash
git init
git add .
git commit -m "init: 每日科技新闻"
git branch -M main
git remote add origin https://github.com/cxb1128/tech-news-daily.git
git push -u origin main
```

### 2. 设置 Secret

在 GitHub 仓库页面：
**Settings → Secrets and variables → Actions → New repository secret**

- Name: `QQ_AUTH_CODE`
- Value: `tdydzixovljicaba`

### 3. 手动测试

**Actions → 每日科技新闻 → Run workflow**

## 📡 RSS 源

| 源 | 类型 |
|---|------|
| TechCrunch | 英文 |
| The Verge | 英文 |
| Ars Technica | 英文 |
| Wired | 英文 |
| Hacker News | 英文 |
| The Register | 英文 |
| CNET | 英文 |
| 36氪 | 中文 |
| IT之家 | 中文 |
| 品玩 | 中文 |
| 机器之心 | 中文 |
| 雷锋网 | 中文 |
| 少数派 | 中文 |

## ⚠️ 注意

- 首次推送后 GitHub Actions 即开始运行
- 每天 19:00 自动触发（CST = UTC+8）
- 如果 RSS 源太少，邮件仍会发送已有内容
- 零费用，无需任何 API Key

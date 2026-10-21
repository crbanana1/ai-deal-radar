# AI 羊毛雷达（ai-deal-radar）

监控国内 AI 厂商的免费额度、试用、赠送、学生/开发者福利和降价活动，发现**新的**羊毛后用邮件即时通知；每天 10:30 另发一封综合简报。

本项目基于开源项目 [TrendRadar](https://github.com/sansan0/TrendRadar) v6.11.0 改造，遵循 GPL-3.0。上游文档见 [TrendRadar 仓库](https://github.com/sansan0/TrendRadar)。

## 它怎么工作

```
GitHub Actions（每 15 分钟尝试一次）
        │
        ├─ 18 个 RSS / Google News 源
        │    ├─ 15 家国内 AI 厂商（Google News 关键词查询）
        │    ├─ 华为云/盘古、昆仑万维/天工、360智脑、面壁等补充
        │    └─ IT之家、量子位、InfoQ、钛媒体
        │
        ├─ 关键词过滤（只保留羊毛相关）
        ├─ 增量去重（只处理新增内容）
        └─ 有新增命中 → 发 HTML 邮件；没有 → 不发
```

- 羊毛监控关闭热榜平台，避免娱乐/社会新闻噪声。
- 不调用大模型，不需要额外的 LLM API Key。
- 只配置了邮件渠道；微信/飞书/钉钉等渠道保持关闭。
- 首次运行会发送一封“当前匹配汇总”；之后只发新增。

## 每日综合简报（10:30 起）

`.github/workflows/daily-digest.yml` 在北京时间 10:00-14:50 每 10 分钟尝试一次，10:30 前跳过；当天第一次发送成功后写入缓存，后续运行不再重复。GitHub 仍可能延迟或跳过，无法保证正好 10:30。它和羊毛告警互不影响：

- 今日要闻：60s API，15 条；限流时自动回退到今日头条热榜
- AI 行业摘要：橘鸦 AI 早报概览 8 条，附完整早报链接；失败时回退到 IT之家 AI 标题
- GitHub Trending：每日热门项目，8 条
- 知乎热榜：6 条
- 今日头条：6 条

橘鸦早报通常在 08:54-10:26 更新，所以日报放在 10:30。数据源都是公开 API/RSS/页面，不需要额外 Key。可以在 Actions → **Daily Digest** → Run workflow 手动触发；本地预览：

```bash
bash scripts/run-digest.sh --dry-run
```

## 一键部署到 GitHub Actions

> 本机部署可以走捷径：创建 PAT → 粘贴到 `github-token.txt` → 双击 `scripts/deploy-github.cmd`，脚本会自动建仓库、推送、写 Secrets 并触发首次运行。PAT 只保存在本机且已被 `.gitignore` 忽略。下面是手动步骤。

1. **创建 GitHub 仓库**。建议用 **public** 仓库：免费 runner 的定时任务是 public 仓库不限分钟；private 仓库每月只有 2000 分钟，15 分钟一次的频率不够用。
2. 把本项目目录上传到仓库（不要提交 `output/`、`local.env`、`index.html`，`.gitignore` 已覆盖）。
3. 在仓库 **Settings → Secrets and variables → Actions** 添加：

   | Secret | 必填 | 说明 |
   |---|---|---|
   | `EMAIL_FROM` | 是 | 发件邮箱，例如 `xxx@qq.com` |
   | `EMAIL_PASSWORD` | 是 | QQ/163 的 **SMTP 授权码**，不是登录密码 |
   | `EMAIL_TO` | 是 | 收件邮箱，多个用逗号分隔 |
   | `EMAIL_SMTP_SERVER` | 否 | 留空自动识别；QQ=`smtp.qq.com`，163=`smtp.163.com` |
   | `EMAIL_SMTP_PORT` | 否 | 留空自动识别；QQ/163 通常为 `465` |

4. 打开 **Actions → AI Wool Radar → Run workflow** 手动跑一次。首次运行会发当前匹配汇总。
5. **Actions → Daily Digest → Run workflow** 可立即测试每日简报；之后每天 10:30 起按多次尝试发送，当天只发一次。
6. **每 7 天运行一次 `Check In` workflow**。TrendRadar 的 Actions 版本有 7 天试用期，不签到会自动停用 crawler workflow。

### 邮箱设置

- QQ 邮箱：设置 → 账户 → 开启 SMTP 服务 → 生成授权码；`EMAIL_PASSWORD` 填授权码。
- 163 邮箱：设置 → POP3/SMTP/IMAP → 开启 SMTP → 获取授权码。
- 其他邮箱：设置 `EMAIL_SMTP_SERVER` 和 `EMAIL_SMTP_PORT`；465 端口走 SSL，587 端口走 STARTTLS。

### 运行频率与免费额度

`.github/workflows/crawler.yml` 默认：

```yaml
- cron: "*/15 * * * *"
```

每日简报的 cron 是 `*/10 2-6 * * *`，对应北京时间 10:00-14:50；10:30 前跳过，首次成功后当天不再发。

GitHub 的 scheduled workflow **不保证准时**，高峰时可能延迟几分钟到数小时；这是免费 runner 的固有限制。Actions 的 cron 使用 UTC 时间。

如果仓库是 private，建议改成每小时一次：

```yaml
- cron: "33 * * * *"
```

### 自动清理

项目自带 `.github/workflows/cleanup.yml`，每 3 天清理一次：

- `actions/cache` 里超过 3 天的旧缓存；
- Actions artifacts 中超过 3 天的构建产物。

它**不会删除 workflow run**，因为 TrendRadar 的 7 天签到计时依赖这些记录；运行记录的清理由每周的 `Check In` 完成。仓库本身不保存抓取结果（`output/` 已被 `.gitignore` 忽略），所以不会因为每天运行而不断变大。

## 本地运行 / 测试

需要 Node 不是必需，项目是 Python 3.12+，依赖用 `uv` 管理。

```bash
uv sync --frozen --no-dev

# 复制模板，填入自己的邮箱授权码；local.env 已被 .gitignore 忽略
cp local.env.example local.env

# 发送测试邮件（不会跑抓取）
bash scripts/test-email.sh

# 手动跑一轮抓取
bash scripts/run-local.sh
```

`local.env` 示例：

```bash
EMAIL_FROM=your_account@qq.com
EMAIL_PASSWORD=your_smtp_authorization_code
EMAIL_TO=your_account@qq.com
# EMAIL_SMTP_SERVER=smtp.qq.com
# EMAIL_SMTP_PORT=465
```

Windows 下可在 Git Bash 中运行上述命令。

## 配置

### 信息源

编辑 `config/config.yaml` 的 `rss.feeds`。每项：

```yaml
- id: "gnews-example"
  name: "示例源"
  url: "https://example.com/feed.xml"
  max_age_days: 7
  max_items: 30
```

当前 15 家厂商的 Google News 查询使用：

```text
(厂商标识 OR 别名) (免费 OR 额度 OR 赠送 OR 降价 OR 优惠 OR 学生 OR 开发者 OR 补贴) when:14d
```

Google News 负责召回，最终是否命中由 `config/frequency_words.txt` 决定。

### 关键词

`config/frequency_words.txt`：

- `[GLOBAL_FILTER]`：全局排除词，命中即丢弃。
- `+xxx`：该组必须匹配。
- 普通行：组内任意一个匹配即可。
- 多个组之间是“或”关系。
- `/.../` 是正则。

当前包含四组：免费额度/试用、学生/开发者福利、降价/限时优惠、AI 羊毛线索。教程、融资、教育政策、日报/早报等噪声已加入全局过滤。

### 通知

`config/config.yaml` 的 `notification.channels` 只启用 `email`；其他渠道留空。GitHub Actions 用 Secrets 覆盖，**不要把邮箱授权码写进配置文件**。

## 已知限制

- **时效性**：GitHub Actions 的 cron 是尽力而为，无法保证“立刻”。实测/社区反馈可能延迟几分钟到数小时。
- **7 天签到**：Actions 版 TrendRadar 每 7 天需要手动运行 `Check In`，否则 crawler 自动停用。
- **GitHub 定时不可靠**：实测 Daily Digest 的单次 10:30 cron 没有触发，crawler 的 15 分钟 cron 也被延迟到数小时一次。日报已改为 10:30 起多次尝试并做当天去重，但仍可能晚到或漏发。
- **跨媒体重复**：同一活动被多家媒体报道时，标题不同、链接不同，可能收到近似重复的邮件。当前只做 URL/来源级去重，未做语义去重。
- **覆盖范围**：只监控 RSS / Google News 能收录的内容；官网独有的活动页（限时券、注册送额度等）如果没被媒体收录，可能漏掉。本项目暂未实现官网页面 diff 监控。
- **硬件类优惠**：如“买手机送 Token”“豆包手机降价”也会命中；如果只想要 API/云服务羊毛，可在关键词中排除手机/耳机/眼镜等词。
- **首次运行 / 缓存丢失**：首次运行会发汇总；Actions 缓存被清理后可能重新按首次运行处理。
- **每日简报来源**：依赖 60s、NewsNow、橘鸦 AI 早报、IT之家、GitHub Trending 的公开接口/页面；60s 限流时回退今日头条，橘鸦失败时回退 IT之家，其它源失效时邮件会带失败警告。
- **邮件送达**：163 邮箱的测试邮件已实际发送成功；如未收到请检查垃圾箱。

## 验证记录（2026-10-20）

- `uv run --with pytest python -m pytest tests -q`：**23 passed, 9 subtests passed**（18 项上游测试 + 5 项自定义关键词回归测试）。
- 首轮抓取：18/18 源成功，396 条，新鲜度过滤后 317 条新增，原始命中 16 条。
- 去重后约 14 个标题、8 个不同事件；示例：腾讯云免费赠送标准带宽、WorkBuddy 限时免费至 10/31、阶跃星辰开放权重免费下载、OpenCode 免费提供 DeepSeek V4.1 Flash。
- 第二轮：396 条，检测到 12 条新增，其中 1 条命中（OpenCode 同一事件的另一家媒体）；说明 URL 级增量去重生效，但跨媒体重复仍需后续优化。
- 邮件构造：假 SMTP 验证通过，主题格式为 `[AI羊毛] 增量分析 - 10月20日 12:23`，HTML 正文约 99 KB。
- 仓库已部署为 public；首次 crawler Actions 运行成功（2026-10-20）。
- 每日简报本地预览：橘鸦 AI 摘要 8 条；60s 限流时自动回退到今日头条，整体约 38-43 条。
- **待验证**：每日简报的 Actions 云端运行和最终邮件（工作流已写好，等待下一次推送后触发）。

## 目录

```
ai-deal-radar/
├─ config/config.yaml          # 源、报告、通知、存储配置
├─ config/frequency_words.txt  # 羊毛关键词规则
├─ .github/workflows/         # 羊毛扫描、每日简报、Check In（续期）、Cleanup Caches（清理缓存）
├─ scripts/                   # 本地运行/测试邮件
├─ trendradar/                # TrendRadar 核心
├─ output/                    # 本地状态与报告（不提交）
└─ local.env.example          # 本地邮箱配置模板
```

## License

GPL-3.0。基于 [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar) v6.11.0；本仓库对信息源、关键词、邮件主题、Actions 缓存和运行配置做了修改。上游许可证见 [LICENSE](LICENSE)。

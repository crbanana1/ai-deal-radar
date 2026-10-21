#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

GH_BIN="C:/Users/wucha/AppData/Local/GitHubCLI/bin/gh.exe"
TOKEN_FILE="github-token.txt"
REPO_NAME="${REPO_NAME:-ai-deal-radar}"
LOG_FILE="deploy.log"

exec > >(tee "$LOG_FILE") 2>&1

step() {
  echo
  echo "== $* =="
}

fail() {
  echo
  echo "失败：$*"
  exit 1
}

if [ ! -s "$TOKEN_FILE" ]; then
  fail "缺少 $TOKEN_FILE。请先运行 scripts\\open-github-token.cmd，把 GitHub PAT 粘贴进去并保存。"
fi

TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
if [ -z "$TOKEN" ]; then
  fail "GitHub PAT 为空。"
fi
export GH_TOKEN="$TOKEN"

step "检查 GitHub 账号"
USER="$("$GH_BIN" api user --jq .login)" || fail "PAT 无效或没有权限。"
echo "账号：$USER"

set -a
# shellcheck disable=SC1091
. ./local.env
set +a

for key in EMAIL_FROM EMAIL_PASSWORD EMAIL_TO; do
  if [ -z "${!key:-}" ]; then
    fail "local.env 缺少 $key。"
  fi
done
echo "邮箱配置：已读取（不显示授权码）"

step "准备本地提交"
if [ ! -d .git ]; then
  git init -b main
fi
git add -A
if git ls-files --error-unmatch "$TOKEN_FILE" >/dev/null 2>&1; then
  fail "$TOKEN_FILE 被 git 跟踪了，已停止。请确认 .gitignore 生效。"
fi
if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  COMMIT_MESSAGE="Initial AI deal radar monitor"
else
  COMMIT_MESSAGE="Add daily digest workflow"
fi
if ! git diff --cached --quiet; then
  git -c user.name="$USER" -c user.email="${USER}@users.noreply.github.com" \
    commit -m "$COMMIT_MESSAGE"
fi

step "创建或连接仓库"
if "$GH_BIN" repo view "$USER/$REPO_NAME" >/dev/null 2>&1; then
  echo "仓库已存在，直接推送：https://github.com/$USER/$REPO_NAME"
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$USER/$REPO_NAME.git"
else
  echo "创建 public 仓库：$REPO_NAME"
  "$GH_BIN" repo create "$REPO_NAME" --public --source=. --remote=origin
fi

step "推送代码"
git -c credential.helper='!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f' \
  push -u origin main

step "写入 GitHub Actions Secrets"
printf '%s' "$EMAIL_FROM" | "$GH_BIN" secret set EMAIL_FROM --repo "$USER/$REPO_NAME"
printf '%s' "$EMAIL_PASSWORD" | "$GH_BIN" secret set EMAIL_PASSWORD --repo "$USER/$REPO_NAME"
printf '%s' "$EMAIL_TO" | "$GH_BIN" secret set EMAIL_TO --repo "$USER/$REPO_NAME"
if [ -n "${EMAIL_SMTP_SERVER:-}" ]; then
  printf '%s' "$EMAIL_SMTP_SERVER" | "$GH_BIN" secret set EMAIL_SMTP_SERVER --repo "$USER/$REPO_NAME"
fi
if [ -n "${EMAIL_SMTP_PORT:-}" ]; then
  printf '%s' "$EMAIL_SMTP_PORT" | "$GH_BIN" secret set EMAIL_SMTP_PORT --repo "$USER/$REPO_NAME"
fi
echo "Secrets 已写入。"

step "触发第一次扫描"
"$GH_BIN" workflow run crawler.yml --repo "$USER/$REPO_NAME"
sleep 8
RUN_ID="$("$GH_BIN" run list --repo "$USER/$REPO_NAME" --workflow crawler.yml --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)"
if [ -z "$RUN_ID" ] || [ "$RUN_ID" = "null" ]; then
  echo "暂时没拿到运行 ID，请打开 Actions 页面查看。"
else
  echo "运行地址：https://github.com/$USER/$REPO_NAME/actions/runs/$RUN_ID"
  set +e
  "$GH_BIN" run watch "$RUN_ID" --repo "$USER/$REPO_NAME" --exit-status
  RUN_STATUS=$?
  set -e
  if [ "$RUN_STATUS" -eq 0 ]; then
    echo "首次运行成功。"
  else
    echo "首次运行失败，请把 deploy.log 最后 40 行发给我。"
  fi
fi

step "触发每日简报测试"
"$GH_BIN" workflow run daily-digest.yml --repo "$USER/$REPO_NAME"
sleep 8
DIGEST_ID="$("$GH_BIN" run list --repo "$USER/$REPO_NAME" --workflow daily-digest.yml --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)"
if [ -z "$DIGEST_ID" ] || [ "$DIGEST_ID" = "null" ]; then
  echo "暂时没拿到日报运行 ID，请打开 Actions 页面查看。"
else
  echo "日报运行地址：https://github.com/$USER/$REPO_NAME/actions/runs/$DIGEST_ID"
  set +e
  "$GH_BIN" run watch "$DIGEST_ID" --repo "$USER/$REPO_NAME" --exit-status
  DIGEST_STATUS=$?
  set -e
  if [ "$DIGEST_STATUS" -eq 0 ]; then
    echo "每日简报发送成功。"
  else
    echo "每日简报发送失败，请把 deploy.log 最后 40 行发给我。"
  fi
fi

step "完成"
echo "仓库：https://github.com/$USER/$REPO_NAME"
echo "Actions：https://github.com/$USER/$REPO_NAME/actions"
echo
echo "下一步："
echo "1. 查收 163 邮箱的羊毛汇总和每日简报（可能在垃圾箱）。"
echo "2. 每日简报 10:30 起多次尝试，当天只发一次（GitHub 仍可能延迟）。"
echo "3. 每 7 天运行一次 Check In workflow。"
echo "4. 缓存/产物每 3 天自动清理。"
echo "5. 确认成功后删除 github-token.txt：PAT 很敏感。"

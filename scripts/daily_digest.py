#!/usr/bin/env python3
# coding=utf-8
"""每日综合简报：今日要闻、AI 摘要、GitHub Trending、知乎/头条热榜。"""

import argparse
import html
import json
import os
import re
import smtplib
import ssl
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

TZ = timezone(timedelta(hours=8))
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
LIMITS = {"news60": 15, "ai": 8, "trending": 8, "zhihu": 6, "toutiao": 6}
ITHOME_AI_LIMIT = 5
AI_PATTERN = re.compile(
    r"AI|人工智能|大模型|模型|智能体|Agent|机器人|具身智能|算力|芯片|GPU|"
    r"英伟达|AMD|昇腾|推理|训练|Copilot|ChatGPT|DeepSeek|通义|豆包|文心|"
    r"智谱|Kimi|MiniMax|阶跃|讯飞|商汤|百川",
    re.I,
)
WEEKDAYS = "一二三四五六日"


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def strip_tags(value):
    value = re.sub(r"<[^>]+>", "", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def load_news60():
    try:
        payload = json.loads(fetch("https://60s.viki.moe/v2/60s"))
        data = payload.get("data") or {}
        items = [strip_tags(x) for x in data.get("news", []) if strip_tags(x)]
        if not items:
            raise ValueError("60s 未返回新闻")
        return {
            "source": "60s",
            "date": data.get("date", ""),
            "items": items[: LIMITS["news60"]],
        }
    except Exception as exc:
        items = load_newsnow("toutiao", 10)
        return {
            "source": "toutiao",
            "date": datetime.now(TZ).strftime("%Y-%m-%d"),
            "items": items,
            "fallback_reason": str(exc),
        }


def load_ithome_ai():
    root = ET.fromstring(fetch("https://www.ithome.com/rss/"))
    items = []
    for node in root.findall(".//item"):
        title = strip_tags(node.findtext("title") or "")
        link = (node.findtext("link") or "").strip()
        if title and link and AI_PATTERN.search(title):
            items.append({"title": title, "url": link})
        if len(items) >= ITHOME_AI_LIMIT:
            break
    if not items:
        raise ValueError("IT之家未找到 AI 相关条目")
    return items


def load_juya_ai():
    raw = fetch("https://daily.juya.uk/rss.xml")
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("橘鸦 RSS 缺少 channel")
    node = channel.find("item")
    if node is None:
        raise ValueError("橘鸦 RSS 没有条目")

    issue_url = (node.findtext("link") or "").strip()
    issue_date = strip_tags(node.findtext("title") or "")
    content = (
        node.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
        or node.findtext("description")
        or ""
    )
    match = re.search(r"<h2[^>]*>\s*概览\s*</h2>", content)
    start = match.end() if match else 0
    next_h2 = re.search(r"<h2[^>]*>", content[start:])
    overview = content[start : start + (next_h2.start() if next_h2 else 6000)]

    category = ""
    items = []
    for token in re.finditer(r"<h3[^>]*>(.*?)</h3>|<li>(.*?)</li>", overview, re.S):
        if token.group(1):
            category = strip_tags(token.group(1))
        elif token.group(2):
            item_html = token.group(2)
            link_match = re.search(r'<a[^>]+href="([^"]+)"', item_html)
            title = strip_tags(item_html)
            title = re.sub(r"(?:\s*[↗#]\s*\d*)+$", "", title).strip()
            if title:
                items.append(
                    {
                        "title": title,
                        "url": link_match.group(1) if link_match else issue_url,
                        "category": category,
                    }
                )
        if len(items) >= LIMITS["ai"]:
            break

    if not items:
        raise ValueError("橘鸦早报概览解析为空")
    return {
        "source": "juya",
        "date": issue_date,
        "issue_url": issue_url,
        "items": items,
    }


def load_ai_section():
    try:
        return load_juya_ai()
    except Exception as juya_error:
        items = load_ithome_ai()
        return {
            "source": "ithome",
            "items": items,
            "fallback_reason": str(juya_error),
        }


def load_trending():
    page = fetch("https://github.com/trending?since=daily").decode("utf-8", "ignore")
    articles = re.findall(r'<article class="Box-row">(.*?)</article>', page, re.S)
    items = []
    for article in articles:
        repo_match = re.search(
            r'<h2[^>]*>.*?<a[^>]*href="/([^"/]+/[^"/]+)"[^>]*>(.*?)</a>',
            article,
            re.S,
        )
        if not repo_match:
            continue
        repo = repo_match.group(1).strip()
        desc = re.search(
            r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', article, re.S
        )
        lang = re.search(
            r'<span itemprop="programmingLanguage">(.*?)</span>', article, re.S
        )
        stars = re.search(
            r'href="/[^"]+/stargazers"[^>]*>\s*(.*?)\s*</a>', article, re.S
        )
        items.append(
            {
                "repo": repo,
                "url": f"https://github.com/{repo}",
                "description": strip_tags(desc.group(1)) if desc else "",
                "language": strip_tags(lang.group(1)) if lang else "",
                "stars": strip_tags(stars.group(1)) if stars else "",
            }
        )
        if len(items) >= LIMITS["trending"]:
            break
    if not items:
        raise ValueError("GitHub Trending 解析为空")
    return items


def load_newsnow(source, limit):
    payload = json.loads(
        fetch(f"https://newsnow.busiyi.world/api/s?id={source}")
    )
    items = []
    for node in payload.get("items", [])[:limit]:
        title = strip_tags(node.get("title", ""))
        url = (node.get("url") or node.get("mobileUrl") or "").strip()
        if not title:
            continue
        if url.startswith("/"):
            url = "https://newsnow.busiyi.world" + url
        items.append({"title": title, "url": url})
    if not items:
        raise ValueError(f"{source} 未返回条目")
    return items


def li_list(items, with_links=True):
    rows = []
    for idx, item in enumerate(items, 1):
        if isinstance(item, str):
            title, url = item, ""
        else:
            title, url = item.get("title", ""), item.get("url", "")
        label = html.escape(title)
        if with_links and url:
            label = (
                f'<a href="{html.escape(url, quote=True)}" '
                f'style="color:#1f4ed8;text-decoration:none">{label}</a>'
            )
        rows.append(
            f'<li style="margin:8px 0;line-height:1.65">{idx}. {label}</li>'
        )
    return '<ol style="padding-left:22px;margin:8px 0">' + "".join(rows) + "</ol>"


def trending_html(items):
    cards = []
    for item in items:
        meta = " · ".join(
            x for x in (item["language"], f"★ {item['stars']}" if item["stars"] else "") if x
        )
        cards.append(
            f'<div style="border:1px solid #e6e8ef;border-radius:10px;padding:12px 14px;margin:10px 0">'
            f'<a href="{html.escape(item["url"], quote=True)}" '
            f'style="color:#1f4ed8;text-decoration:none;font-weight:600">{html.escape(item["repo"])}</a>'
            f'<div style="color:#4b5563;margin-top:4px;line-height:1.55">{html.escape(item["description"])}</div>'
            f'<div style="color:#8a8f9c;font-size:12px;margin-top:6px">{html.escape(meta)}</div>'
            f"</div>"
        )
    return "".join(cards)


def section(title, body, note=""):
    note_html = (
        f'<div style="color:#9aa0ad;font-size:12px;margin:-4px 0 8px">{html.escape(note)}</div>'
        if note
        else ""
    )
    return (
        f'<section style="margin:28px 0">'
        f'<h2 style="font-size:18px;color:#111827;margin:0 0 10px;'
        f'border-left:4px solid #2563eb;padding-left:10px">{html.escape(title)}</h2>'
        f"{note_html}{body}</section>"
    )


def build_digest(now):
    data = {}
    errors = {}
    loaders = [
        ("news60", "今日要闻", load_news60),
        ("ai", "AI 行业摘要", load_ai_section),
        ("trending", "GitHub Trending", load_trending),
        ("zhihu", "知乎热榜", lambda: load_newsnow("zhihu", LIMITS["zhihu"])),
        ("toutiao", "今日头条", lambda: load_newsnow("toutiao", LIMITS["toutiao"])),
    ]
    for key, label, loader in loaders:
        try:
            data[key] = loader()
        except Exception as exc:
            errors[label] = str(exc)

    if not data:
        raise RuntimeError("所有简报数据源都失败了：" + json.dumps(errors, ensure_ascii=False))

    parts = []
    if "news60" in data:
        news_data = data["news60"]
        if news_data.get("source") == "toutiao":
            parts.append(
                section(
                    "今日要闻",
                    li_list(news_data["items"]),
                    "60s 暂时限流，已回退到今日头条热榜",
                )
            )
        else:
            note = f"来源日期：{news_data['date']}" if news_data.get("date") else ""
            parts.append(section("今日要闻", li_list(news_data["items"], False), note))
    if "ai" in data:
        ai = data["ai"]
        if ai["source"] == "juya":
            rows = []
            for idx, item in enumerate(ai["items"], 1):
                cat = (
                    f'<span style="color:#8a8f9c;font-size:12px">[{html.escape(item["category"])}]</span> '
                    if item.get("category")
                    else ""
                )
                rows.append(
                    f'<li style="margin:8px 0;line-height:1.65">{idx}. {cat}'
                    f'<a href="{html.escape(item["url"], quote=True)}" '
                    f'style="color:#1f4ed8;text-decoration:none">{html.escape(item["title"])}</a></li>'
                )
            body = '<ol style="padding-left:22px;margin:8px 0">' + "".join(rows) + "</ol>"
            if ai.get("issue_url"):
                body += (
                    f'<p style="margin:10px 0 0"><a href="{html.escape(ai["issue_url"], quote=True)}" '
                    f'style="color:#1f4ed8;text-decoration:none">查看完整早报（{html.escape(ai["date"])}）→</a></p>'
                )
            parts.append(
                section(
                    "AI 行业摘要",
                    body,
                    f"来源：橘鸦AI早报 {ai['date']}（AI 辅助生成，仅供参考）",
                )
            )
        else:
            parts.append(
                section(
                    "AI 行业摘要",
                    li_list(ai["items"]),
                    "来源：IT之家（橘鸦暂不可用，已回退到 AI 标题筛选）",
                )
            )
    if "trending" in data:
        parts.append(section("GitHub Trending", trending_html(data["trending"])))
    if "zhihu" in data:
        parts.append(section("知乎热榜", li_list(data["zhihu"])))
    if "toutiao" in data:
        parts.append(section("今日头条", li_list(data["toutiao"])))

    warning = ""
    if errors:
        warning = (
            '<div style="background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;'
            'padding:10px 12px;border-radius:8px;font-size:13px;margin:16px 0">'
            "部分来源获取失败："
            + "；".join(f"{html.escape(k)}（{html.escape(v)}）" for k, v in errors.items())
            + "</div>"
        )

    date_text = f"{now.year}年{now.month}月{now.day}日 星期{WEEKDAYS[now.weekday()]}"
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>每日简报</title></head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif">
<div style="max-width:680px;margin:0 auto;padding:24px 14px">
<div style="background:#ffffff;border-radius:14px;padding:24px 22px;border:1px solid #e6e8ef">
<div style="font-size:13px;color:#6b7280;letter-spacing:1px">AI 每日简报</div>
<h1 style="font-size:26px;color:#111827;margin:6px 0 4px">{date_text}</h1>
<div style="color:#6b7280;font-size:13px">今日要闻 · AI · GitHub · 热榜</div>
{warning}
{''.join(parts)}
<div style="border-top:1px solid #eef0f5;margin-top:26px;padding-top:14px;color:#9aa0ad;font-size:12px;line-height:1.7">
精选来源：60s API · IT之家（AI 筛选） · GitHub Trending · NewsNow<br>
生成时间：{now.strftime('%Y-%m-%d %H:%M')}（北京时间）
</div>
</div></div></body></html>"""

    text_lines = [f"AI 每日简报 - {date_text}", ""]
    if "news60" in data:
        news_data = data["news60"]
        if news_data.get("source") == "toutiao":
            text_lines += ["【今日要闻】（60s 限流，回退到今日头条）"] + [
                f"{i}. {x['title']} {x['url']}" for i, x in enumerate(news_data["items"], 1)
            ] + [""]
        else:
            text_lines += ["【今日要闻】"] + [
                f"{i}. {x}" for i, x in enumerate(news_data["items"], 1)
            ] + [""]
    if "ai" in data:
        ai = data["ai"]
        if ai["source"] == "juya":
            text_lines += ["【AI 行业摘要】", f"来源：橘鸦AI早报 {ai['date']}"]
            for i, item in enumerate(ai["items"], 1):
                cat = f"[{item['category']}] " if item.get("category") else ""
                text_lines.append(f"{i}. {cat}{item['title']} {item['url']}")
            if ai.get("issue_url"):
                text_lines.append(f"完整早报：{ai['issue_url']}")
            text_lines.append("")
        else:
            text_lines += ["【AI 行业摘要】"] + [f"{i}. {x['title']} {x['url']}" for i, x in enumerate(ai["items"], 1)] + [""]
    if "trending" in data:
        text_lines += ["【GitHub Trending】"] + [
            f"{i}. {x['repo']} - {x['description']} {x['url']}"
            for i, x in enumerate(data["trending"], 1)
        ] + [""]
    if "zhihu" in data:
        text_lines += ["【知乎热榜】"] + [f"{i}. {x['title']}" for i, x in enumerate(data["zhihu"], 1)] + [""]
    if "toutiao" in data:
        text_lines += ["【今日头条】"] + [f"{i}. {x['title']}" for i, x in enumerate(data["toutiao"], 1)] + [""]
    if errors:
        text_lines += ["【部分来源失败】"] + [f"{k}: {v}" for k, v in errors.items()] + [""]
    text = "\n".join(text_lines)
    subject = f"[每日简报] {now.month}月{now.day}日 星期{WEEKDAYS[now.weekday()]}"
    return subject, html_doc, text, data, errors


def send_digest(subject, html_doc, text):
    sender = os.environ.get("EMAIL_FROM", "").strip()
    password = os.environ.get("EMAIL_PASSWORD", "").strip()
    recipients = [x.strip() for x in os.environ.get("EMAIL_TO", "").split(",") if x.strip()]
    if not sender or not password or not recipients:
        raise RuntimeError("EMAIL_FROM / EMAIL_PASSWORD / EMAIL_TO 未配置")

    host = os.environ.get("EMAIL_SMTP_SERVER", "").strip()
    port_raw = os.environ.get("EMAIL_SMTP_PORT", "").strip()
    if not host:
        domain = sender.split("@")[-1].lower()
        host = "smtp.163.com" if domain == "163.com" else f"smtp.{domain}"
    port = int(port_raw) if port_raw else 465

    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr(("AI 每日简报", sender))
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = Header(subject, "utf-8")
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html_doc, "html", "utf-8"))

    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=30, context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(host, port, timeout=30)
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
    try:
        server.login(sender, password)
        server.send_message(msg)
    finally:
        server.quit()
    print(f"每日简报已发送：{subject} -> {', '.join(recipients)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只抓取并生成预览，不发邮件")
    args = parser.parse_args()

    now = datetime.now(TZ)
    subject, html_doc, text, data, errors = build_digest(now)
    preview_dir = Path("output")
    preview_dir.mkdir(exist_ok=True)
    preview = preview_dir / "daily-digest-preview.html"
    preview.write_text(html_doc, encoding="utf-8")
    print("各栏目数量：", {k: len(v["items"]) if isinstance(v, dict) and "items" in v else len(v) for k, v in data.items()})
    if errors:
        print("失败来源：", errors)
    print(f"预览：{preview}")

    if args.dry_run:
        print("dry-run，不发送邮件")
        return
    send_digest(subject, html_doc, text)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"每日简报失败：{exc}", file=sys.stderr)
        raise

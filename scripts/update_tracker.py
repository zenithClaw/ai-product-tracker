import os
import re
from datetime import datetime, timedelta, timezone
from html import escape

import requests
from bs4 import BeautifulSoup

GITHUB_REPO = "openclaw/openclaw"
TRENDING_URL = "https://github.com/trending?since=daily"
INDEX_FILE = "index.html"
TIMEZONE = timezone(timedelta(hours=8))  # Asia/Shanghai


def gh_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "openclaw-insider-bot",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_trending_ai(min_items: int = 10, max_items: int = 15):
    """Fetch at least 10 trending repos, prioritize AI-related repos by keywords."""
    resp = requests.get(TRENDING_URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("article.Box-row")

    keywords = [
        "ai", "agent", "llm", "rag", "gpt", "diffusion", "vision", "embedding",
        "inference", "prompt", "nlp", "model", "ml", "deep learning",
    ]

    ai_first = []
    others = []

    for row in rows:
        h2 = row.select_one("h2 a")
        if not h2:
            continue

        full_name = " ".join(h2.get_text(" ", strip=True).split()).replace(" / ", "/").replace("/ ", "/").replace(" /", "/")
        href = h2.get("href", "")
        link = f"https://github.com{href}" if href.startswith("/") else href

        desc_el = row.select_one("p")
        desc = desc_el.get_text(" ", strip=True) if desc_el else ""

        stars_today_el = row.select_one("span.d-inline-block.float-sm-right")
        stars_today = stars_today_el.get_text(" ", strip=True) if stars_today_el else ""
        stars_today = stars_today.replace("stars today", "stars today").strip()

        lang_el = row.select_one("span[itemprop='programmingLanguage']")
        lang = lang_el.get_text(strip=True) if lang_el else "Unknown"

        item = {
            "title": full_name.split("/")[-1],
            "full_name": full_name,
            "desc": desc or "No description provided.",
            "link": link,
            "action": f"⭐ {stars_today}" if stars_today else "⭐ Trending today",
            "tag": "AI Trending",
            "tech": f"GitHub: {full_name} · {lang}",
        }

        signal = f"{full_name} {desc}".lower()
        if any(k in signal for k in keywords):
            ai_first.append(item)
        else:
            others.append(item)

    selected = (ai_first + others)[:max_items]
    if len(selected) < min_items:
        selected = selected[:min_items]
    return selected


def fetch_openclaw_latest_release_all_updates():
    """Fetch latest release and keep ALL bullet updates (Breaking/Changes/Fixes/etc)."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=5"
    resp = requests.get(url, headers=gh_headers(), timeout=30)
    resp.raise_for_status()
    releases = resp.json()
    if not releases:
        return None

    # Prefer latest non-draft; keep prerelease if it is the newest official published one.
    latest = next((r for r in releases if not r.get("draft", False)), releases[0])

    body = latest.get("body", "") or ""
    html_url = latest.get("html_url", f"https://github.com/{GITHUB_REPO}/releases")
    tag_name = latest.get("tag_name", "latest")
    published_at = latest.get("published_at")

    current_section = "Updates"
    updates = []

    for raw in body.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        # section headers
        m = re.match(r"^#{2,4}\s+(.+)$", line.strip())
        if m:
            current_section = m.group(1).strip()
            continue

        # bullet line
        if re.match(r"^\s*[-*]\s+", line):
            text = re.sub(r"^\s*[-*]\s+", "", line).strip()
            if not text:
                continue

            # remove markdown links for cleaner title/desc
            plain = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
            plain = re.sub(r"`([^`]+)`", r"\1", plain)
            plain = re.sub(r"\s+", " ", plain).strip()

            pr_match = re.search(r"\(#(\d+)\)", text)
            link = f"https://github.com/{GITHUB_REPO}/pull/{pr_match.group(1)}" if pr_match else html_url

            title = plain
            if len(title) > 88:
                title = title[:88].rstrip() + "..."

            tag = current_section
            if len(tag) > 20:
                tag = tag[:20]

            updates.append({
                "title": title,
                "desc": plain,
                "link": link,
                "tag": tag or "Update",
                "tech": f"Release: {tag_name}",
                "action": "🔎 View source",
            })

    # Fallback: no list bullets in body
    if not updates:
        updates = [{
            "title": f"{tag_name} release",
            "desc": "Official release notes available on GitHub.",
            "link": html_url,
            "tag": "Release",
            "tech": f"Release: {tag_name}",
            "action": "🔎 View source",
        }]

    return {
        "tag": tag_name,
        "url": html_url,
        "published_at": published_at,
        "updates": updates,
    }


def card_html(item):
    return f"""
            <a href=\"{escape(item['link'])}\" target=\"_blank\" class=\"card\"> 
                <span class=\"tag\">{escape(item['tag'])}</span>
                <h3>{escape(item['title'])}</h3>
                <p>{escape(item['desc'])}</p>
                <div class=\"tech\">{escape(item['tech'])}</div>
                <div class=\"action\">{escape(item['action'])}</div>
            </a>"""


def build_html(trending_items, insider_release):
    now_cn = datetime.now(TIMEZONE).strftime("%Y.%m.%d")
    insider_count = len(insider_release["updates"]) if insider_release else 0

    trending_cards = "\n".join(card_html(x) for x in trending_items)
    insider_cards = "\n".join(card_html(x) for x in insider_release["updates"]) if insider_release else ""

    insider_tag = insider_release["tag"] if insider_release else "latest"

    return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>OpenClaw Insider - 追踪 AI Agent 进化</title>
    <style>
        :root {{
            --primary: #2563eb;
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --success: #10b981;
        }}
        body {{
            font-family: -apple-system, system-ui, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            background-color: var(--bg);
            color: var(--text);
        }}
        header {{ text-align: center; margin-bottom: 40px; border-bottom: 1px solid #334155; padding-bottom: 28px; }}
        h1 {{ font-size: 2.6em; margin-bottom: 10px; color: var(--accent); }}
        .subtitle {{ font-size: 1.1em; color: var(--text-muted); }}
        .meta {{ margin-top: 10px; color: var(--text-muted); font-size: 0.9em; }}

        .tab-container {{ display: flex; justify-content: center; gap: 16px; margin-bottom: 30px; }}
        .tab-btn {{
            background: #334155; color: white; border: none; padding: 10px 18px;
            border-radius: 8px; cursor: pointer; font-weight: 600; transition: 0.2s;
        }}
        .tab-btn.active {{ background: var(--primary); box-shadow: 0 0 15px rgba(37, 99, 235, 0.35); }}

        .version-block {{ display: none; margin-bottom: 80px; }}
        .version-block.active {{ display: block; }}

        .version-header {{
            display: flex; align-items: center; gap: 12px; margin-bottom: 20px;
            padding-bottom: 10px; border-bottom: 2px solid var(--primary);
        }}
        .version-tag {{ background: var(--primary); color: white; padding: 4px 12px; border-radius: 6px; font-family: monospace; font-size: 1em; }}
        .version-date {{ color: var(--text-muted); font-size: 1em; }}

        .card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }}
        .card {{
            background: var(--card-bg); border-radius: 12px; padding: 18px; border: 1px solid #334155;
            display: flex; flex-direction: column; text-decoration: none; color: inherit;
            transition: transform 0.15s, border-color 0.15s, background-color 0.15s;
        }}
        .card:hover {{ transform: translateY(-3px); border-color: var(--accent); background: #24344f; }}
        .tag {{
            display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.75em; font-weight: 700;
            background: rgba(56, 189, 248, 0.14); color: var(--accent); margin-bottom: 10px; width: fit-content;
        }}
        .card h3 {{ margin: 0 0 8px 0; font-size: 1.04em; line-height: 1.45; }}
        .card p {{ color: #cbd5e1; font-size: 0.93em; flex-grow: 1; margin: 0; }}
        .card .tech {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.8em; color: var(--text-muted); margin-top: 10px; padding: 8px; background: rgba(0,0,0,0.22); border-radius: 6px; }}
        .card .action {{ margin-top: 10px; font-weight: 700; color: var(--success); font-size: 0.9em; }}

        footer {{ text-align: center; margin-top: 60px; padding-top: 24px; border-top: 1px solid #334155; color: var(--text-muted); }}
    </style>
</head>
<body>
    <header>
        <h1>🚀 OpenClaw Insider</h1>
        <p class=\"subtitle\">每日追踪 OpenClaw 官方日志 + AI Trending，所有卡片可点击跳转到源头。</p>
        <div class=\"meta\">Updated: {now_cn} · AI Trending: {len(trending_items)} 条 · OpenClaw Updates: {insider_count} 条</div>
        <div class=\"meta\">
            <a href=\"https://github.com/zenithClaw/ai-product-tracker\" style=\"color:#38bdf8;text-decoration:none;\">GitHub 仓库</a>
            &nbsp;|&nbsp;
            <a href=\"https://github.com/openclaw/openclaw/releases\" style=\"color:#38bdf8;text-decoration:none;\">OpenClaw 官方 Releases</a>
        </div>
    </header>

    <div class=\"tab-container\">
        <button class=\"tab-btn active\" data-tab=\"trending\">🔥 AI Trending（≥10）</button>
        <button class=\"tab-btn\" data-tab=\"insider\">🛡️ OpenClaw 当天全部更新</button>
    </div>

    <div id=\"tab-trending\" class=\"version-block active\">
        <div class=\"version-header\">
            <span class=\"version-tag\">v{now_cn}</span>
            <span class=\"version-date\">AI Trending Daily Feed (Top {len(trending_items)})</span>
        </div>
        <div class=\"card-grid\">
{trending_cards}
        </div>
    </div>

    <div id=\"tab-insider\" class=\"version-block\">
        <div class=\"version-header\">
            <span class=\"version-tag\">{escape(insider_tag)}</span>
            <span class=\"version-date\">OpenClaw Official Release Notes (All {insider_count} items)</span>
        </div>
        <div class=\"card-grid\">
{insider_cards}
        </div>
    </div>

    <footer>
        <p>Generated by 小 z 🐛 (Antigravity) · Auto-updated daily</p>
        <p>© 2026 ZenithClaw Labs</p>
    </footer>

    <script>
        const tabs = document.querySelectorAll('.tab-btn');
        tabs.forEach(btn => {{
            btn.addEventListener('click', () => {{
                tabs.forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.version-block').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
            }});
        }});
    </script>
</body>
</html>
"""


def main():
    trending = fetch_trending_ai(min_items=10, max_items=14)
    insider = fetch_openclaw_latest_release_all_updates()

    html = build_html(trending, insider)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Updated {INDEX_FILE}: trending={len(trending)}, insider={len(insider['updates']) if insider else 0}")


if __name__ == "__main__":
    main()

import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from html import escape

GITHUB_REPO = "openclaw/openclaw"
TRENDING_URL = "https://github.com/trending?since=daily"
INDEX_FILE = "index.html"
TIMEZONE = timezone(timedelta(hours=8))

def gh_headers():
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "openclaw-insider-bot"}
    token = os.environ.get("GITHUB_TOKEN")
    if token: headers["Authorization"] = f"Bearer {token}"
    return headers

def fetch_trending_ai(max_items=15):
    try:
        resp = requests.get(TRENDING_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("article.Box-row")
        items = []
        for row in rows[:max_items]:
            h2 = row.select_one("h2 a")
            if not h2: continue
            full_name = h2.get_text(strip=True).replace(" ", "").replace("\n", "")
            link = f"https://github.com{h2['href']}"
            desc = row.select_one("p").get_text(strip=True) if row.select_one("p") else "No description."
            stars = row.select_one("span.d-inline-block.float-sm-right").get_text(strip=True) if row.select_one("span.d-inline-block.float-sm-right") else "Trending"
            items.append({"title": full_name.split("/")[-1], "full_name": full_name, "desc": desc, "link": link, "action": f"⭐ {stars}", "tag": "Trending"})
        return items
    except: return []

def fetch_openclaw_insider():
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=1"
        resp = requests.get(url, headers=gh_headers(), timeout=30)
        resp.raise_for_status()
        release = resp.json()[0]
        body = release.get("body", "")
        tag = release.get("tag_name", "latest")
        
        # 总结逻辑：按关键词归类
        categories = {"Breaking": [], "Security": [], "Feature": [], "Fix": []}
        summary_points = []
        
        lines = body.splitlines()
        current_cat = "Feature"
        
        for line in lines:
            line = line.strip()
            if not line: continue
            if "Breaking" in line: current_cat = "Breaking"
            elif "Security" in line or "Fixes" in line: current_cat = "Security"
            elif "Changes" in line: current_cat = "Feature"
            
            if line.startswith(("- ", "* ")):
                clean = line.lstrip("- *").strip()
                clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", clean) # 移除链接
                pr_match = re.search(r"\(#(\d+)\)", clean)
                link = f"https://github.com/{GITHUB_REPO}/pull/{pr_match.group(1)}" if pr_match else release['html_url']
                
                item = {"title": clean[:80] + "..." if len(clean) > 80 else clean, "desc": clean, "link": link, "tag": current_cat}
                categories[current_cat].append(item)

        # 核心亮点总结（Antigravity 预置逻辑）
        if "v2026.3.22" in tag:
            summary_points = [
                "🚀 <b>ClawHub 时代开启</b>：技能发现与安装正式原生化，支持 openclaw skills 指令。",
                "🔒 <b>安全大底座</b>：彻底移除了不安全的 Chrome Extension Relay，强制转向 host-attached 模式。",
                "⚡ <b>性能飞跃</b>：Control UI v2 实装，支持 /fast 模式切换及多级代理 yield 挂起。",
                "🌍 <b>生态大爆炸</b>：新增 Matrix、Chutes、Exa、Tavily、Firecrawl 等 5+ 官方插件。"
            ]
        
        return {"tag": tag, "url": release['html_url'], "summary": summary_points, "categories": categories}
    except: return None

def build_html(trending, insider):
    now_cn = datetime.now(TIMEZONE).strftime("%Y.%m.%d")
    
    trending_cards = "\n".join([f'<a href="{x["link"]}" target="_blank" class="card"><span class="tag">{x["tag"]}</span><h3>{x["title"]}</h3><p>{x["desc"]}</p><div class="tech">{x["full_name"]}</div><div class="action">{x["action"]}</div></a>' for x in trending])
    
    # Insider 渲染逻辑
    insider_html = ""
    if insider:
        # 1. 亮点总结区
        insider_html += '<div class="summary-box"><h3>💡 核心更新情报</h3><ul>'
        for p in insider['summary']: insider_html += f'<li>{p}</li>'
        insider_html += '</ul><p style="margin-top:10px; font-size:0.9em; color:var(--warning);">⚠️ <b>行动建议</b>：执行 openclaw doctor --fix 修复浏览器环境。</p></div>'
        
        # 2. 分类卡片区（每类选 Top 3）
        for cat, items in insider['categories'].items():
            if not items: continue
            insider_html += f'<h2 style="margin:40px 0 20px 0; color:var(--accent); font-size:1.4em;">{cat} Highlights</h2><div class="card-grid">'
            for item in items[:6]: # 每类最多显 6 个
                tag_class = "tag-red" if cat == "Breaking" else "tag-blue"
                insider_html += f'<a href="{item["link"]}" target="_blank" class="card"><span class="tag {tag_class}">{cat}</span><h3>{item["title"]}</h3><p>{item["desc"]}</p><div class="tech">Release: {insider["tag"]}</div><div class="action">🔎 查看详情</div></a>'
            insider_html += '</div>'
            
    # HTML Template (简化部分 CSS 以减小体积)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClaw Insider</title>
    <style>
        :root {{ --primary: #2563eb; --bg: #0f172a; --card-bg: #1e293b; --text: #f8fafc; --text-muted: #94a3b8; --accent: #38bdf8; --success: #10b981; --warning: #f59e0b; --red: #ef4444; }}
        body {{ font-family: sans-serif; line-height: 1.6; max-width: 1100px; margin: 0 auto; padding: 30px 20px; background: var(--bg); color: var(--text); }}
        header {{ text-align: center; margin-bottom: 30px; border-bottom: 1px solid #334155; padding-bottom: 20px; }}
        .tab-container {{ display: flex; justify-content: center; gap: 15px; margin-bottom: 30px; }}
        .tab-btn {{ background: #334155; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; }}
        .tab-btn.active {{ background: var(--primary); }}
        .version-block {{ display: none; }} .version-block.active {{ display: block; }}
        .summary-box {{ background: rgba(56, 189, 248, 0.05); border: 1px solid var(--accent); padding: 20px; border-radius: 12px; margin-bottom: 30px; }}
        .summary-box h3 {{ margin-top: 0; color: var(--accent); }}
        .card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
        .card {{ background: var(--card-bg); border-radius: 12px; padding: 20px; border: 1px solid #334155; text-decoration: none; color: inherit; display: flex; flex-direction: column; }}
        .card:hover {{ border-color: var(--accent); background: #243147; transform: translateY(-2px); transition: 0.2s; }}
        .tag {{ padding: 2px 8px; border-radius: 6px; font-size: 0.75em; font-weight: 700; background: rgba(56, 189, 248, 0.1); color: var(--accent); margin-bottom: 10px; width: fit-content; }}
        .tag-red {{ background: rgba(239, 68, 68, 0.1); color: var(--red); }}
        .tech {{ font-family: monospace; font-size: 0.8em; color: var(--text-muted); margin-top: 10px; padding: 8px; background: rgba(0,0,0,0.2); border-radius: 6px; }}
        .action {{ margin-top: 10px; font-weight: 700; color: var(--success); font-size: 0.9em; }}
    </style>
</head>
<body>
    <header><h1>🚀 OpenClaw Insider</h1><p>已更新至 {now_cn} · 深度总结官方更新与 AI 趋势</p></header>
    <div class="tab-container">
        <button class="tab-btn active" onclick="showTab('trending')">🔥 AI Trending</button>
        <button class="tab-btn" onclick="showTab('insider')">🛡️ OpenClaw 深度报告</button>
    </div>
    <div id="tab-trending" class="version-block active"><div class="card-grid">{trending_cards}</div></div>
    <div id="tab-insider" class="version-block">{insider_html}</div>
    <script>
        function showTab(t) {{
            document.querySelectorAll('.version-block').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-' + t).classList.add('active');
            event.currentTarget.classList.add('active');
        }}
    </script>
</body></html>"""

def main():
    t = fetch_trending_ai()
    i = fetch_openclaw_insider()
    html = build_html(t, i)
    with open(INDEX_FILE, "w", encoding="utf-8") as f: f.write(html)
    print(f"Report generated: Trending={len(t)}, Insider_Cat={len(i['categories']) if i else 0}")

if __name__ == "__main__": main()

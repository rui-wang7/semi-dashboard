#!/usr/bin/env python3
"""
Semiconductor Stock Weekly Monitor
Fetches 7-day price data, detects spikes, fetches related news,
calls Claude Code CLI for AI analysis, outputs data/stock_events.json

Usage:
  python3 scripts/update_stocks.py

Requirements:
  pip3 install yfinance requests
  Claude Code CLI must be installed (claude command available)
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

try:
    import yfinance as yf
except ImportError:
    print("Installing yfinance...")
    subprocess.run([sys.executable, "-m", "pip", "install", "yfinance", "--quiet"], check=True)
    import yfinance as yf

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "--quiet"], check=True)
    import requests

# ─────────────────────────────────────────────────────────────────────
#  STOCK UNIVERSE  (ticker → {name, group, threshold, region})
# ─────────────────────────────────────────────────────────────────────
STOCKS = {
    # Group 1 — Cloud / CSP / Mag7
    "NVDA":     {"name": "Nvidia",             "group": "Cloud & CSP (Mag7)", "threshold": 0.05, "region": "US"},
    "MSFT":     {"name": "Microsoft",          "group": "Cloud & CSP (Mag7)", "threshold": 0.05, "region": "US"},
    "GOOGL":    {"name": "Alphabet",           "group": "Cloud & CSP (Mag7)", "threshold": 0.05, "region": "US"},
    "AMZN":     {"name": "Amazon",             "group": "Cloud & CSP (Mag7)", "threshold": 0.05, "region": "US"},
    "META":     {"name": "Meta",               "group": "Cloud & CSP (Mag7)", "threshold": 0.05, "region": "US"},
    "AAPL":     {"name": "Apple",              "group": "Cloud & CSP (Mag7)", "threshold": 0.05, "region": "US"},
    "TSLA":     {"name": "Tesla",              "group": "Cloud & CSP (Mag7)", "threshold": 0.05, "region": "US"},

    # Group 2 — AI Chip Designers / Fabless
    "AMD":      {"name": "AMD",                "group": "AI Chip / Fabless",  "threshold": 0.05, "region": "US"},
    "INTC":     {"name": "Intel",              "group": "AI Chip / Fabless",  "threshold": 0.05, "region": "US"},
    "QCOM":     {"name": "Qualcomm",           "group": "AI Chip / Fabless",  "threshold": 0.05, "region": "US"},
    "AVGO":     {"name": "Broadcom",           "group": "AI Chip / Fabless",  "threshold": 0.05, "region": "US"},
    "MRVL":     {"name": "Marvell",            "group": "AI Chip / Fabless",  "threshold": 0.10, "region": "US"},
    "SNPS":     {"name": "Synopsys",           "group": "AI Chip / Fabless",  "threshold": 0.05, "region": "US"},
    "CDNS":     {"name": "Cadence",            "group": "AI Chip / Fabless",  "threshold": 0.05, "region": "US"},
    "MPWR":     {"name": "Monolithic Power",   "group": "AI Chip / Fabless",  "threshold": 0.10, "region": "US"},
    "SMCI":     {"name": "Super Micro",        "group": "AI Chip / Fabless",  "threshold": 0.10, "region": "US"},
    "CEVA":     {"name": "CEVA",               "group": "AI Chip / Fabless",  "threshold": 0.10, "region": "US"},
    "2454.TW":  {"name": "MediaTek 聯發科",    "group": "AI Chip / Fabless",  "threshold": 0.10, "region": "TW"},

    # Group 3 — Foundry & IDM
    "TSM":      {"name": "TSMC (ADR)",         "group": "Foundry & IDM",      "threshold": 0.05, "region": "US"},
    "2330.TW":  {"name": "TSMC 台積電",        "group": "Foundry & IDM",      "threshold": 0.05, "region": "TW"},
    "GFS":      {"name": "GlobalFoundries",    "group": "Foundry & IDM",      "threshold": 0.10, "region": "US"},
    "UMC":      {"name": "UMC (ADR)",          "group": "Foundry & IDM",      "threshold": 0.10, "region": "US"},
    "2303.TW":  {"name": "UMC 聯電",           "group": "Foundry & IDM",      "threshold": 0.10, "region": "TW"},
    "STM":      {"name": "STMicro",            "group": "Foundry & IDM",      "threshold": 0.10, "region": "EU"},
    "NXPI":     {"name": "NXP Semi",           "group": "Foundry & IDM",      "threshold": 0.10, "region": "EU"},
    "ON":       {"name": "onsemi",             "group": "Foundry & IDM",      "threshold": 0.10, "region": "US"},
    "WOLF":     {"name": "Wolfspeed",          "group": "Foundry & IDM",      "threshold": 0.10, "region": "US"},
    "TSEM":     {"name": "Tower Semi",         "group": "Foundry & IDM",      "threshold": 0.10, "region": "US"},
    "005930.KS":{"name": "Samsung 삼성전자",   "group": "Foundry & IDM",      "threshold": 0.05, "region": "KR"},

    # Group 4 — Equipment / Lithography
    "ASML":     {"name": "ASML",              "group": "Equipment",           "threshold": 0.05, "region": "EU"},
    "AMAT":     {"name": "Applied Materials", "group": "Equipment",           "threshold": 0.05, "region": "US"},
    "LRCX":     {"name": "Lam Research",      "group": "Equipment",           "threshold": 0.05, "region": "US"},
    "KLAC":     {"name": "KLA",               "group": "Equipment",           "threshold": 0.05, "region": "US"},
    "ONTO":     {"name": "Onto Innovation",   "group": "Equipment",           "threshold": 0.10, "region": "US"},
    "ACLS":     {"name": "Axcelis",           "group": "Equipment",           "threshold": 0.10, "region": "US"},
    "8035.T":   {"name": "東京エレクトロン (TEL)", "group": "Equipment",      "threshold": 0.05, "region": "JP"},
    "6920.T":   {"name": "レーザーテック Lasertec", "group": "Equipment",     "threshold": 0.10, "region": "JP"},
    "7735.T":   {"name": "SCREEN Holdings",   "group": "Equipment",           "threshold": 0.10, "region": "JP"},
    "6857.T":   {"name": "Advantest",         "group": "Equipment",           "threshold": 0.10, "region": "JP"},
    "6525.T":   {"name": "Kokusai Electric",  "group": "Equipment",           "threshold": 0.10, "region": "JP"},
    "BESI.AS":  {"name": "Besi Semi",         "group": "Equipment",           "threshold": 0.10, "region": "EU"},

    # Group 5 — Materials & Chemicals
    "ENTG":     {"name": "Entegris",          "group": "Materials",           "threshold": 0.10, "region": "US"},
    "MKSI":     {"name": "MKS Instruments",   "group": "Materials",           "threshold": 0.10, "region": "US"},
    "AZTA":     {"name": "Azenta",            "group": "Materials",           "threshold": 0.10, "region": "US"},
    "4063.T":   {"name": "信越化学 Shin-Etsu", "group": "Materials",          "threshold": 0.10, "region": "JP"},
    "3436.T":   {"name": "SUMCO",             "group": "Materials",           "threshold": 0.10, "region": "JP"},
    "7741.T":   {"name": "Hoya",              "group": "Materials",           "threshold": 0.10, "region": "JP"},
    "7912.T":   {"name": "大日本印刷 DNP",     "group": "Materials",          "threshold": 0.10, "region": "JP"},

    # Group 6 — OSAT / Packaging & Test
    "AMKR":     {"name": "Amkor",             "group": "OSAT / Packaging",    "threshold": 0.10, "region": "US"},
    "ASX":      {"name": "ASE Group (ADR)",   "group": "OSAT / Packaging",    "threshold": 0.10, "region": "TW"},
    "3711.TW":  {"name": "日月光 ASE",        "group": "OSAT / Packaging",    "threshold": 0.10, "region": "TW"},
    "COHU":     {"name": "Cohu",              "group": "OSAT / Packaging",    "threshold": 0.10, "region": "US"},
    "FORM":     {"name": "FormFactor",        "group": "OSAT / Packaging",    "threshold": 0.10, "region": "US"},

    # Group 7 — Networking / Optical / Connectivity
    "ANET":     {"name": "Arista Networks",   "group": "Networking / Optical","threshold": 0.10, "region": "US"},
    "COHR":     {"name": "Coherent",          "group": "Networking / Optical","threshold": 0.10, "region": "US"},
    "LITE":     {"name": "Lumentum",          "group": "Networking / Optical","threshold": 0.10, "region": "US"},
    "VIAV":     {"name": "Viavi Solutions",   "group": "Networking / Optical","threshold": 0.10, "region": "US"},
    "AAOI":     {"name": "Applied Opto",      "group": "Networking / Optical","threshold": 0.10, "region": "US"},
    "300308.SZ":{"name": "中际旭创",           "group": "Networking / Optical","threshold": 0.10, "region": "CN"},

    # Group 8 — Memory
    "MU":       {"name": "Micron",            "group": "Memory",              "threshold": 0.05, "region": "US"},
    "WDC":      {"name": "Western Digital",   "group": "Memory",              "threshold": 0.10, "region": "US"},
    "SNDK":     {"name": "SanDisk",           "group": "Memory",              "threshold": 0.10, "region": "US"},
    "STX":      {"name": "Seagate",           "group": "Memory",              "threshold": 0.10, "region": "US"},
    "000660.KS":{"name": "SK Hynix",          "group": "Memory",              "threshold": 0.05, "region": "KR"},

    # Group 9 — HK Listed
    "0981.HK":  {"name": "中芯国际 SMIC",     "group": "HK Listed",           "threshold": 0.10, "region": "CN"},
    "1347.HK":  {"name": "华虹半导体",         "group": "HK Listed",           "threshold": 0.10, "region": "CN"},
    "0522.HK":  {"name": "ASM Pacific",       "group": "HK Listed",           "threshold": 0.10, "region": "HK"},
    "0992.HK":  {"name": "联想 Lenovo",        "group": "HK Listed",           "threshold": 0.10, "region": "CN"},
    "9988.HK":  {"name": "阿里巴巴 Alibaba",   "group": "HK Listed",           "threshold": 0.10, "region": "CN"},
    "0700.HK":  {"name": "腾讯 Tencent",       "group": "HK Listed",           "threshold": 0.10, "region": "CN"},

    # Group 10 — A Shares
    "002371.SZ":{"name": "北方华创 NAURA",     "group": "A Shares",            "threshold": 0.10, "region": "CN"},
    "688012.SH":{"name": "中微公司 AMEC",      "group": "A Shares",            "threshold": 0.10, "region": "CN"},
    "688256.SH":{"name": "寒武纪 Cambricon",   "group": "A Shares",            "threshold": 0.10, "region": "CN"},
    "688041.SH":{"name": "海光信息",            "group": "A Shares",            "threshold": 0.10, "region": "CN"},
    "600584.SS":{"name": "长电科技 JCET",      "group": "A Shares",            "threshold": 0.10, "region": "CN"},
    "002129.SZ":{"name": "中环股份",            "group": "A Shares",            "threshold": 0.10, "region": "CN"},
    "002384.SZ":{"name": "东山精密",            "group": "A Shares",            "threshold": 0.10, "region": "CN"},
    "002463.SZ":{"name": "沪电股份",            "group": "A Shares",            "threshold": 0.10, "region": "CN"},

    # Group 11 — Taiwan Listed
    "6488.TW":  {"name": "環球晶 GlobalWafers","group": "Taiwan Listed",       "threshold": 0.10, "region": "TW"},
    "2382.TW":  {"name": "廣達 Quanta",        "group": "Taiwan Listed",       "threshold": 0.10, "region": "TW"},
    "2317.TW":  {"name": "鴻海 Foxconn",       "group": "Taiwan Listed",       "threshold": 0.10, "region": "TW"},
    "3037.TW":  {"name": "欣興 Unimicron",     "group": "Taiwan Listed",       "threshold": 0.10, "region": "TW"},

    # Group 12 — Japan Non-Equipment
    "6501.T":   {"name": "日立 Hitachi",       "group": "Japan (Non-Equip)",   "threshold": 0.10, "region": "JP"},
    "6758.T":   {"name": "ソニー Sony",         "group": "Japan (Non-Equip)",   "threshold": 0.10, "region": "JP"},
    "7911.T":   {"name": "凸版印刷 Toppan",    "group": "Japan (Non-Equip)",   "threshold": 0.10, "region": "JP"},

    # Group 13 — Server & Datacenter Cooling
    "VRT":      {"name": "Vertiv",             "group": "Server & Cooling",    "threshold": 0.10, "region": "US"},
    "DELL":     {"name": "Dell",               "group": "Server & Cooling",    "threshold": 0.10, "region": "US"},
    "HPE":      {"name": "HPE",                "group": "Server & Cooling",    "threshold": 0.10, "region": "US"},

    # Group 14 — Energy for AI Datacenters
    "GEV":      {"name": "GE Vernova",         "group": "AI Energy",           "threshold": 0.10, "region": "US"},
    "CEG":      {"name": "Constellation Energy","group": "AI Energy",          "threshold": 0.10, "region": "US"},
    "VST":      {"name": "Vistra",             "group": "AI Energy",           "threshold": 0.10, "region": "US"},
    "SMR":      {"name": "NuScale Power",      "group": "AI Energy",           "threshold": 0.10, "region": "US"},
    "BWXT":     {"name": "BWX Technologies",   "group": "AI Energy",           "threshold": 0.10, "region": "US"},
}

CN_REGIONS = {"CN", "HK"}

# ─────────────────────────────────────────────────────────────────────
#  FETCH PRICE DATA
# ─────────────────────────────────────────────────────────────────────
def fetch_price_history(ticker):
    """Returns list of {date, open, close, change_pct} for past 7 trading days."""
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="10d", interval="1d")
        if hist.empty:
            return []
        rows = []
        closes = list(hist["Close"])
        dates = [str(d.date()) for d in hist.index]
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            curr = closes[i]
            if prev and prev > 0:
                pct = (curr - prev) / prev
                rows.append({
                    "date": dates[i],
                    "open": round(float(hist["Open"].iloc[i]), 4),
                    "close": round(float(curr), 4),
                    "change_pct": round(pct * 100, 2),
                })
        return rows[-7:]
    except Exception as e:
        print(f"  [price error] {ticker}: {e}")
        return []

# ─────────────────────────────────────────────────────────────────────
#  FETCH NEWS
# ─────────────────────────────────────────────────────────────────────
def fetch_news(ticker, spike_date_str):
    """Fetch Yahoo Finance news for ticker, filter to ±2 days of spike."""
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={ticker}&newsCount=20&enableFuzzyQuery=false"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        news_items = data.get("news", [])
        spike_dt = datetime.strptime(spike_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        window_start = spike_dt - timedelta(days=2)
        window_end = spike_dt + timedelta(days=1)
        filtered = []
        for item in news_items:
            pub_ts = item.get("providerPublishTime", 0)
            pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
            if window_start <= pub_dt <= window_end:
                filtered.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "source": item.get("publisher", ""),
                    "published": pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
        return filtered[:5]
    except Exception as e:
        print(f"  [news error] {ticker}: {e}")
        return []

# ─────────────────────────────────────────────────────────────────────
#  AI EXPLANATION via Claude Code CLI
# ─────────────────────────────────────────────────────────────────────
def get_ai_explanation(ticker, meta, date_str, change_pct, news_items):
    """Call claude CLI to generate explanation. Returns string."""
    if not news_items:
        return ""

    news_text = "\n".join([f"- [{n['source']}] {n['title']}" for n in news_items])
    is_cn = meta["region"] in CN_REGIONS or meta["region"] == "CN"
    lang_instruction = (
        "请用中文回答。" if is_cn else
        "Respond in English, but switch to Chinese if the news is primarily about China-related events."
    )

    direction = "上涨" if change_pct > 0 else "下跌"
    prompt = f"""Stock: {ticker} ({meta['name']})
Date: {date_str}
Price move: {'+' if change_pct > 0 else ''}{change_pct:.1f}% ({direction if is_cn else ('up' if change_pct > 0 else 'down')} {abs(change_pct):.1f}%)

Related news on/around this date:
{news_text}

{lang_instruction}
Analyze what caused this price move in 3-5 sentences. Focus on: technology roadmap changes, order/demand changes, financial events (earnings, revenue guidance, debt/equity raise), product competitiveness (chip launches, competitive wins/losses, benchmark results), investor days or analyst days.
Be specific about which news item most likely drove the move."""

    # Find claude CLI — try common install locations + auto-discover newer versions
    import glob
    claude_paths = [
        "claude",
        "/usr/local/bin/claude",
        "/opt/homebrew/bin/claude",
        os.path.expanduser("~/.local/bin/claude"),
    ]
    # Auto-discover any installed claude-code version (e.g., 2.1.87, 2.1.128, …)
    for app in sorted(glob.glob(os.path.expanduser("~/Library/Application Support/Claude/claude-code/*/claude.app/Contents/MacOS/claude")), reverse=True):
        claude_paths.append(app)
    for vm in sorted(glob.glob(os.path.expanduser("~/Library/Application Support/Claude/claude-code-vm/*/claude")), reverse=True):
        claude_paths.append(vm)
    claude_bin = None
    for p in claude_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            claude_bin = p
            break
    if not claude_bin:
        # try `which claude`
        try:
            res = subprocess.run(["which", "claude"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                claude_bin = res.stdout.strip()
        except Exception:
            pass
    if not claude_bin:
        print("  [claude CLI not found] — skipping AI explanation")
        return ""

    try:
        result = subprocess.run(
            [claude_bin, "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=90
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            print(f"  [claude error] {ticker}: {result.stderr[:100]}")
            return ""
    except subprocess.TimeoutExpired:
        print(f"  [claude timeout] {ticker}")
        return ""
    except Exception as e:
        print(f"  [claude error] {ticker}: {e}")
        return ""

# ─────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────
def main():
    output_path = "data/stock_events.json"
    now = datetime.now(tz=timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end = now.strftime("%Y-%m-%d")

    print(f"Semiconductor Stock Monitor — {week_start} to {week_end}")
    print(f"Tracking {len(STOCKS)} tickers across 14 groups\n")

    all_prices = {}   # ticker → [day rows]
    spikes = []

    # ── Phase 1: fetch prices ──────────────────────────────────────
    print("Phase 1: Fetching price data...")
    for ticker, meta in STOCKS.items():
        sys.stdout.write(f"  {ticker:16s}")
        sys.stdout.flush()
        rows = fetch_price_history(ticker)
        all_prices[ticker] = rows
        if rows:
            spike_days = [r for r in rows if abs(r["change_pct"]) >= meta["threshold"] * 100]
            sys.stdout.write(f" {len(rows)} days, {len(spike_days)} spikes\n")
            for day in spike_days:
                spikes.append({
                    "ticker": ticker,
                    "company": meta["name"],
                    "group": meta["group"],
                    "region": meta["region"],
                    "date": day["date"],
                    "change_pct": day["change_pct"],
                    "close": day["close"],
                    "threshold_pct": meta["threshold"] * 100,
                    "news": [],
                    "ai_explanation": "",
                    "price_history_7d": rows,
                })
        else:
            sys.stdout.write(" [no data]\n")
        time.sleep(0.3)  # rate limit

    # ── Phase 2: fetch news for each spike ────────────────────────
    print(f"\nPhase 2: Fetching news for {len(spikes)} spike events...")
    for spike in spikes:
        print(f"  {spike['ticker']} {spike['date']} ({spike['change_pct']:+.1f}%)")
        spike["news"] = fetch_news(spike["ticker"], spike["date"])
        print(f"    → {len(spike['news'])} news items")
        time.sleep(0.5)

    # ── Phase 3: AI explanations ──────────────────────────────────
    print(f"\nPhase 3: Generating AI explanations for {len(spikes)} events...")
    for spike in spikes:
        if spike["news"]:
            print(f"  {spike['ticker']} {spike['date']}...")
            explanation = get_ai_explanation(
                spike["ticker"], STOCKS[spike["ticker"]],
                spike["date"], spike["change_pct"], spike["news"]
            )
            spike["ai_explanation"] = explanation
            if explanation:
                print(f"    → {explanation[:80]}...")
        time.sleep(1)

    # ── Sort spikes by abs move descending ────────────────────────
    spikes.sort(key=lambda x: abs(x["change_pct"]), reverse=True)

    # ── Write output ──────────────────────────────────────────────
    output = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "week_start": week_start,
        "week_end": week_end,
        "total_tickers": len(STOCKS),
        "spike_count": len(spikes),
        "all_prices": all_prices,
        "spikes": spikes,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Done. {len(spikes)} spike events written to {output_path}")
    print(f"  Tickers tracked: {len(STOCKS)}")
    print(f"  Spikes detected: {len(spikes)}")


if __name__ == "__main__":
    main()

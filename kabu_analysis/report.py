"""分析結果からHTML / Markdown / JSONレポートを生成する。"""

import json
from datetime import datetime
from html import escape
from pathlib import Path

from .scoring import (
    SIGNAL_AVOID,
    SIGNAL_BUY_DIP,
    SIGNAL_BUY_TREND,
    SIGNAL_WATCH_HOT,
    StockAnalysis,
    buy_candidates,
    rank_by_sector,
)

DISCLAIMER = (
    "本レポートは公開データに基づく機械的な分析であり、投資勧誘や利益の保証ではありません。"
    "投資の最終判断はご自身の責任で行ってください。"
)

_SIGNAL_CLASS = {
    SIGNAL_BUY_DIP: "buy",
    SIGNAL_BUY_TREND: "buy",
    SIGNAL_WATCH_HOT: "hot",
    SIGNAL_AVOID: "avoid",
}


def _fmt_pct(v: float | None, signed: bool = True) -> str:
    if v is None:
        return "—"
    sign = "+" if signed and v > 0 else ""
    return f"{sign}{v * 100:.1f}%"


def _fmt_num(v: float | None, suffix: str = "") -> str:
    if v is None:
        return "—"
    return f"{v:,.1f}{suffix}"


def _score_bar(label: str, value: float) -> str:
    return (
        f'<div class="bar-row"><span class="bar-label">{escape(label)}</span>'
        f'<div class="bar"><div class="bar-fill" style="width:{value:.0f}%"></div></div>'
        f'<span class="bar-value">{value:.0f}</span></div>'
    )


def _stock_card(a: StockAnalysis, rank: int) -> str:
    code = a.ticker.replace(".T", "")
    sig_class = _SIGNAL_CLASS.get(a.signal, "watch")
    reasons = "".join(f"<li>{escape(r)}</li>" for r in a.reasons[:6])
    cautions = "".join(f"<li>{escape(c)}</li>" for c in a.cautions[:4])
    cautions_html = f'<ul class="cautions">{cautions}</ul>' if cautions else ""
    t, f = a.technicals, a.fundamentals
    return f"""
    <div class="card">
      <div class="card-head">
        <span class="rank">{rank}位</span>
        <span class="name">{escape(a.name)} <span class="code">({code})</span></span>
        <span class="signal {sig_class}">{escape(a.signal)}</span>
      </div>
      <div class="score-total">総合 {a.composite_score:.0f}<span class="score-max">/100</span></div>
      {_score_bar("トレンド", a.trend_score)}
      {_score_bar("ファンダ", a.fundamental_score)}
      {_score_bar("低リスク", a.risk_score)}
      <table class="metrics">
        <tr><td>株価</td><td>{_fmt_num(a.price, "円")}</td><td>RSI(14)</td><td>{_fmt_num(t.get("rsi14"))}</td></tr>
        <tr><td>6ヶ月</td><td>{_fmt_pct(t.get("mom_6m"))}</td><td>12ヶ月</td><td>{_fmt_pct(t.get("mom_12m"))}</td></tr>
        <tr><td>PER</td><td>{_fmt_num(f.get("per"), "倍")}</td><td>ROE</td><td>{_fmt_pct(f.get("roe"), signed=False)}</td></tr>
        <tr><td>配当利回り</td><td>{_fmt_pct(f.get("dividend_yield"), signed=False)}</td><td>年率ボラ</td><td>{_fmt_pct(t.get("volatility_1y"), signed=False)}</td></tr>
      </table>
      <ul class="reasons">{reasons}</ul>
      {cautions_html}
    </div>"""


def build_html(analyses: list[StockAnalysis], top_n: int = 3, demo: bool = False) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sectors = rank_by_sector(analyses, top_n)
    picks = buy_candidates(analyses)

    demo_banner = (
        '<div class="demo-banner">⚠ デモモード: 合成データによるサンプルレポートです。実際の株価ではありません。</div>'
        if demo
        else ""
    )

    picks_rows = "".join(
        f"<tr><td>{i + 1}</td><td>{escape(a.name)} ({a.ticker.replace('.T', '')})</td>"
        f"<td>{escape(a.sector)}</td><td class='num'>{a.composite_score:.0f}</td>"
        f"<td><span class='signal {_SIGNAL_CLASS.get(a.signal, 'watch')}'>{escape(a.signal)}</span></td></tr>"
        for i, a in enumerate(picks[:15])
    )
    picks_html = (
        f"""<table class="picks"><thead><tr><th>#</th><th>銘柄</th><th>セクター</th><th>総合</th><th>シグナル</th></tr></thead>
        <tbody>{picks_rows}</tbody></table>"""
        if picks
        else "<p>本日は買い候補シグナルの銘柄がありません。押し目や地合いの改善を待ちましょう。</p>"
    )

    sector_sections = ""
    for sector, items in sectors.items():
        cards = "".join(_stock_card(a, i + 1) for i, a in enumerate(items))
        sector_sections += f'<section><h2>{escape(sector)}</h2><div class="cards">{cards}</div></section>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>日次株式分析レポート {now[:10]}</title>
<style>
  :root {{ --bg:#f6f7f9; --card:#fff; --text:#1a202c; --muted:#64748b; --line:#e2e8f0;
           --buy:#0f766e; --buy-bg:#ccfbf1; --hot:#b45309; --hot-bg:#fef3c7;
           --watch:#475569; --watch-bg:#e2e8f0; --avoid:#b91c1c; --avoid-bg:#fee2e2;
           --accent:#2563eb; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0f172a; --card:#1e293b; --text:#e2e8f0; --muted:#94a3b8; --line:#334155;
             --buy-bg:#134e4a; --buy:#5eead4; --hot-bg:#78350f; --hot:#fcd34d;
             --watch-bg:#334155; --watch:#cbd5e1; --avoid-bg:#7f1d1d; --avoid:#fca5a5; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif;
         background:var(--bg); color:var(--text); line-height:1.6; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:24px 16px 48px; }}
  h1 {{ font-size:1.5rem; margin:0 0 4px; }}
  h2 {{ font-size:1.15rem; border-left:4px solid var(--accent); padding-left:10px; margin:36px 0 14px; }}
  .sub {{ color:var(--muted); font-size:.9rem; margin-bottom:20px; }}
  .demo-banner {{ background:var(--hot-bg); color:var(--hot); padding:10px 14px; border-radius:8px;
                 margin-bottom:20px; font-weight:600; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:14px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; }}
  .card-head {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:8px; }}
  .rank {{ background:var(--accent); color:#fff; border-radius:6px; padding:1px 8px; font-size:.8rem; font-weight:700; }}
  .name {{ font-weight:700; }}
  .code {{ color:var(--muted); font-weight:400; font-size:.85rem; }}
  .signal {{ margin-left:auto; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:700; white-space:nowrap; }}
  .signal.buy {{ background:var(--buy-bg); color:var(--buy); }}
  .signal.hot {{ background:var(--hot-bg); color:var(--hot); }}
  .signal.watch {{ background:var(--watch-bg); color:var(--watch); }}
  .signal.avoid {{ background:var(--avoid-bg); color:var(--avoid); }}
  .score-total {{ font-size:1.4rem; font-weight:800; margin:4px 0 8px; }}
  .score-max {{ font-size:.85rem; color:var(--muted); font-weight:400; }}
  .bar-row {{ display:flex; align-items:center; gap:8px; margin:3px 0; font-size:.8rem; }}
  .bar-label {{ width:64px; color:var(--muted); }}
  .bar {{ flex:1; height:8px; background:var(--line); border-radius:4px; overflow:hidden; }}
  .bar-fill {{ height:100%; background:var(--accent); border-radius:4px; }}
  .bar-value {{ width:26px; text-align:right; color:var(--muted); }}
  table.metrics {{ width:100%; border-collapse:collapse; margin:10px 0 6px; font-size:.82rem; }}
  table.metrics td {{ padding:3px 6px; border-top:1px solid var(--line); }}
  table.metrics td:nth-child(odd) {{ color:var(--muted); width:24%; }}
  ul.reasons {{ margin:8px 0 0; padding-left:18px; font-size:.83rem; }}
  ul.cautions {{ margin:6px 0 0; padding-left:18px; font-size:.83rem; color:var(--avoid); }}
  table.picks {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line);
                border-radius:12px; overflow:hidden; font-size:.9rem; }}
  table.picks th, table.picks td {{ padding:8px 12px; text-align:left; border-top:1px solid var(--line); }}
  table.picks thead th {{ background:var(--line); border-top:none; }}
  td.num {{ font-weight:700; }}
  .disclaimer {{ margin-top:40px; padding:14px; border:1px solid var(--line); border-radius:8px;
                color:var(--muted); font-size:.8rem; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>📈 日次株式分析レポート</h1>
  <div class="sub">生成日時: {now} ｜ 対象: {len(analyses)}銘柄 ｜ 手法: トレンド×ファンダ×リスクの複合スコア(1〜5年の中期投資向け)</div>
  {demo_banner}
  <h2>本日の買い候補</h2>
  {picks_html}
  {sector_sections}
  <div class="disclaimer">{DISCLAIMER}</div>
</div>
</body>
</html>"""


def build_markdown(analyses: list[StockAnalysis], top_n: int = 3, demo: bool = False) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# 日次株式分析レポート ({now})", ""]
    if demo:
        lines += ["> ⚠ デモモード: 合成データによるサンプルです。", ""]
    picks = buy_candidates(analyses)
    lines += ["## 本日の買い候補", ""]
    if picks:
        lines += ["| # | 銘柄 | セクター | 総合 | シグナル |", "|---|------|---------|------|---------|"]
        for i, a in enumerate(picks[:15]):
            code = a.ticker.replace(".T", "")
            lines.append(f"| {i + 1} | {a.name} ({code}) | {a.sector} | {a.composite_score:.0f} | {a.signal} |")
    else:
        lines.append("本日は買い候補シグナルの銘柄がありません。")
    lines.append("")
    for sector, items in rank_by_sector(analyses, top_n).items():
        lines += [f"## {sector}", ""]
        for i, a in enumerate(items):
            code = a.ticker.replace(".T", "")
            lines.append(f"### {i + 1}位: {a.name} ({code}) — 総合{a.composite_score:.0f} / {a.signal}")
            for r in a.reasons[:5]:
                lines.append(f"- {r}")
            for c in a.cautions[:3]:
                lines.append(f"- ⚠ {c}")
            lines.append("")
    lines += ["---", "", DISCLAIMER, ""]
    return "\n".join(lines)


def to_json(analyses: list[StockAnalysis], top_n: int = 3) -> str:
    def encode(a: StockAnalysis) -> dict:
        return {
            "ticker": a.ticker,
            "name": a.name,
            "sector": a.sector,
            "price": a.price,
            "composite_score": a.composite_score,
            "trend_score": a.trend_score,
            "fundamental_score": a.fundamental_score,
            "risk_score": a.risk_score,
            "signal": a.signal,
            "reasons": a.reasons,
            "cautions": a.cautions,
        }

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "buy_candidates": [encode(a) for a in buy_candidates(analyses)],
        "sector_rankings": {
            sector: [encode(a) for a in items]
            for sector, items in rank_by_sector(analyses, top_n).items()
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def write_reports(
    analyses: list[StockAnalysis],
    output_dir: Path,
    top_n: int = 3,
    demo: bool = False,
) -> list[Path]:
    """latest.{html,md,json} と日付付きHTMLを書き出し、生成パスを返す。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    html = build_html(analyses, top_n=top_n, demo=demo)
    md = build_markdown(analyses, top_n=top_n, demo=demo)
    js = to_json(analyses, top_n=top_n)

    paths = []
    for name, content in [
        ("latest.html", html),
        (f"{date_str}.html", html),
        ("latest.md", md),
        ("latest.json", js),
    ]:
        path = output_dir / name
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths

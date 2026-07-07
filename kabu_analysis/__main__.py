"""CLIエントリポイント。

使い方:
  python -m kabu_analysis                     # 実データで分析しreports/に出力
  python -m kabu_analysis --demo             # 合成データで動作確認
  python -m kabu_analysis --sectors 銀行 商社・卸売 --top 3
  python -m kabu_analysis check 7203         # 個別銘柄の買い目診断(任意のコード可)
  python -m kabu_analysis check トヨタ 9984   # 銘柄名でも複数でも可
"""

import argparse
import logging
import re
import sys
from pathlib import Path

from .indicators import compute_technicals
from .report import write_reports
from .scoring import analyze_stock, buy_candidates
from .universe import all_sectors, find_stock, get_universe

logger = logging.getLogger("kabu_analysis")


def _resolve_query(query: str) -> tuple[str, str, str] | None:
    """検索語を (ticker, 銘柄名, セクター) に解決。ユニバース外はコード指定のみ受け付ける。"""
    stock = find_stock(query)
    if stock:
        return stock.ticker, stock.name, stock.sector
    code = query.strip().upper().removesuffix(".T")
    if re.fullmatch(r"[0-9][0-9A-Z]{3}", code):  # 東証コード (例: 7203, 285A)
        return f"{code}.T", code, "ユニバース外"
    return None


def run_check(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="kabu_analysis check", description="個別銘柄の買い目診断")
    parser.add_argument("queries", nargs="+", help="証券コード(例: 7203)または銘柄名(ユニバース内のみ)")
    parser.add_argument("--demo", action="store_true", help="合成データで実行(動作確認用)")
    args = parser.parse_args(argv)

    resolved = []
    for q in args.queries:
        r = _resolve_query(q)
        if r is None:
            print(f"✗ 「{q}」を解決できません。銘柄名検索は収録銘柄のみ対応です。任意の銘柄は証券コード(例: 7203)で指定してください。")
            continue
        resolved.append(r)
    if not resolved:
        return 1

    tickers = [t for t, _, _ in resolved]
    if args.demo:
        from .demo import generate_benchmark, generate_fundamentals, generate_price_history

        prices = {t: generate_price_history(t) for t in tickers}
        benchmark = generate_benchmark()
        fundamentals = {t: generate_fundamentals(t) for t in tickers}
    else:
        from .data import fetch_benchmark, fetch_fundamentals, fetch_price_history

        prices = fetch_price_history(tickers)
        benchmark = fetch_benchmark()
        fundamentals = fetch_fundamentals([t for t in tickers if t in prices])

    ok = False
    for ticker, name, sector in resolved:
        hist = prices.get(ticker)
        if hist is None:
            print(f"✗ {ticker}: 株価データを取得できませんでした(コードが正しいか確認してください)。")
            continue
        f = fundamentals.get(ticker, {})
        if f.get("name") and sector == "ユニバース外":
            name = f["name"]
        technicals = compute_technicals(hist["Close"], volume=hist.get("Volume"), benchmark=benchmark)
        a = analyze_stock(ticker, name, sector, technicals, f)
        _print_check_result(a)
        ok = True
    if ok:
        print("※ 本結果は機械的な分析であり、投資判断はご自身の責任で行ってください。")
    return 0 if ok else 1


def _print_check_result(a) -> None:
    t = a.technicals
    code = a.ticker.removesuffix(".T")

    def pct(v, signed=True):
        if v is None:
            return "—"
        sign = "+" if signed and v > 0 else ""
        return f"{sign}{v * 100:.1f}%"

    print()
    print(f"=== {code} {a.name} [{a.sector}] ===")
    print(f"シグナル: {a.signal}")
    print(f"総合スコア: {a.composite_score:.0f}/100 (トレンド {a.trend_score:.0f} / ファンダ {a.fundamental_score:.0f} / 低リスク {a.risk_score:.0f})")
    price = f"{a.price:,.0f}円" if a.price is not None else "—"
    rsi = f"{t['rsi14']:.0f}" if t.get("rsi14") is not None else "—"
    print(f"株価: {price} | RSI(14): {rsi} | 12ヶ月: {pct(t.get('mom_12m'))} | 対日経12ヶ月: {pct(t.get('rel_12m'))}")
    if a.reasons:
        print("[根拠]")
        for r in a.reasons:
            print(f"  ・{r}")
    if a.cautions:
        print("[注意点]")
        for c in a.cautions:
            print(f"  ・{c}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if argv and argv[0] == "check":
        return run_check(argv[1:])

    parser = argparse.ArgumentParser(prog="kabu_analysis", description="日本株の日次分析レポートを生成")
    parser.add_argument("--demo", action="store_true", help="ネットワーク不要の合成データで実行")
    parser.add_argument("--output", type=Path, default=Path("reports"), help="出力ディレクトリ (default: reports)")
    parser.add_argument("--top", type=int, default=3, help="セクターごとの表示数 (default: 3)")
    parser.add_argument("--sectors", nargs="*", default=None, help="対象セクターを限定 (default: 全セクター)")
    parser.add_argument("--list-sectors", action="store_true", help="セクター一覧を表示して終了")
    args = parser.parse_args(argv)

    if args.list_sectors:
        print("\n".join(all_sectors()))
        return 0

    stocks = get_universe(args.sectors)
    if not stocks:
        logger.error("対象銘柄がありません。--list-sectors でセクター名を確認してください。")
        return 1

    tickers = [s.ticker for s in stocks]
    if args.demo:
        from .demo import generate_benchmark, generate_fundamentals, generate_price_history

        prices = {t: generate_price_history(t) for t in tickers}
        benchmark = generate_benchmark()
        fundamentals = {t: generate_fundamentals(t) for t in tickers}
    else:
        from .data import fetch_benchmark, fetch_fundamentals, fetch_price_history

        prices = fetch_price_history(tickers)
        if not prices:
            logger.error("株価データを1件も取得できませんでした。ネットワークを確認してください。")
            return 1
        benchmark = fetch_benchmark()
        if benchmark is None:
            logger.warning("ベンチマーク取得失敗のため、対市場相対力は中立扱いで継続します。")
        fundamentals = fetch_fundamentals(list(prices.keys()))

    analyses = []
    for stock in stocks:
        hist = prices.get(stock.ticker)
        if hist is None:
            continue
        technicals = compute_technicals(hist["Close"], volume=hist.get("Volume"), benchmark=benchmark)
        analyses.append(
            analyze_stock(stock.ticker, stock.name, stock.sector, technicals, fundamentals.get(stock.ticker, {}))
        )

    if not analyses:
        logger.error("分析可能な銘柄がありませんでした。")
        return 1

    paths = write_reports(analyses, args.output, top_n=args.top, demo=args.demo)
    picks = buy_candidates(analyses)
    logger.info("分析完了: %d銘柄 / 買い候補 %d銘柄", len(analyses), len(picks))
    for a in picks[:10]:
        logger.info("  %s %s [%s] 総合%.0f", a.ticker.replace(".T", ""), a.name, a.signal, a.composite_score)
    for p in paths:
        logger.info("出力: %s", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

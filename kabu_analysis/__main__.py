"""CLIエントリポイント。

使い方:
  python -m kabu_analysis                # 実データで分析しreports/に出力
  python -m kabu_analysis --demo        # 合成データで動作確認
  python -m kabu_analysis --sectors 銀行 商社・卸売 --top 3
"""

import argparse
import logging
import sys
from pathlib import Path

from .indicators import compute_technicals
from .report import write_reports
from .scoring import analyze_stock, buy_candidates
from .universe import all_sectors, get_universe

logger = logging.getLogger("kabu_analysis")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kabu_analysis", description="日本株の日次分析レポートを生成")
    parser.add_argument("--demo", action="store_true", help="ネットワーク不要の合成データで実行")
    parser.add_argument("--output", type=Path, default=Path("reports"), help="出力ディレクトリ (default: reports)")
    parser.add_argument("--top", type=int, default=3, help="セクターごとの表示数 (default: 3)")
    parser.add_argument("--sectors", nargs="*", default=None, help="対象セクターを限定 (default: 全セクター)")
    parser.add_argument("--list-sectors", action="store_true", help="セクター一覧を表示して終了")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

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

"""yfinanceによる株価・財務データの取得。

- 株価: yf.download で一括取得(2年分・調整後終値)
- 財務: Ticker.info から必要項目のみ抽出。1日TTLのディスクキャッシュ付き
"""

import json
import logging
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data/cache")
FUNDAMENTALS_TTL_SEC = 20 * 60 * 60  # 20時間(日次実行で再利用しない程度)


BENCHMARK_TICKER = "^N225"  # 相対力の基準となる日経平均


def fetch_price_history(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    """各銘柄のOHLCV DataFrame (Close/Volume) を返す。取得失敗銘柄は含まれない。"""
    import yfinance as yf

    logger.info("株価データ取得中: %d銘柄 (期間: %s)", len(tickers), period)
    df = yf.download(
        tickers=tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    result: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            hist = df[ticker] if isinstance(df.columns, pd.MultiIndex) else df
            close = hist["Close"].dropna()
        except KeyError:
            logger.warning("株価取得失敗: %s", ticker)
            continue
        if len(close) < 60:
            logger.warning("データ不足のためスキップ: %s (%d日分)", ticker, len(close))
            continue
        result[ticker] = hist[["Close", "Volume"]].dropna(subset=["Close"])
    logger.info("株価取得完了: %d/%d銘柄", len(result), len(tickers))
    return result


def fetch_benchmark(period: str = "2y") -> pd.Series | None:
    """ベンチマーク(日経平均)の終値Series。取得失敗時はNone(相対力は無効化)。"""
    import yfinance as yf

    try:
        hist = yf.download(BENCHMARK_TICKER, period=period, interval="1d", auto_adjust=True, progress=False)
        close = hist["Close"].dropna()
        if isinstance(close, pd.DataFrame):  # 単一銘柄でも列がMultiIndexになる場合がある
            close = close.iloc[:, 0]
        return close if len(close) >= 60 else None
    except Exception as e:
        logger.warning("ベンチマーク取得失敗: %s", e)
        return None


def _load_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > FUNDAMENTALS_TTL_SEC:
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _extract_fundamentals(info: dict) -> dict:
    """yfinanceのinfo辞書からスコアリングに使う項目のみ抽出・正規化。"""
    dividend_yield = info.get("dividendYield")
    # yfinanceのバージョンにより % 表記(3.2)と小数表記(0.032)が混在するため補正
    if dividend_yield is not None and dividend_yield > 0.5:
        dividend_yield = dividend_yield / 100

    market_cap = info.get("marketCap")
    free_cashflow = info.get("freeCashflow")
    fcf_yield = None
    if market_cap and free_cashflow is not None:
        fcf_yield = free_cashflow / market_cap

    return {
        "name": info.get("longName") or info.get("shortName"),
        "per": info.get("trailingPE"),
        "forward_per": info.get("forwardPE"),
        "pbr": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "operating_margin": info.get("operatingMargins"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "dividend_yield": dividend_yield,
        "market_cap": market_cap,
        "debt_to_equity": info.get("debtToEquity"),  # % 表記 (例 85.3)
        "fcf_yield": fcf_yield,
        "target_price": info.get("targetMeanPrice"),
        "recommendation": info.get("recommendationMean"),  # 1(強気買い)〜5(売り)
    }


def fetch_fundamentals(tickers: list[str], cache_dir: Path = CACHE_DIR) -> dict[str, dict]:
    """各銘柄の財務指標を返す。失敗した銘柄は空dict。"""
    import yfinance as yf

    cache_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, dict] = {}
    for i, ticker in enumerate(tickers):
        cache_path = cache_dir / f"{ticker}.json"
        cached = _load_cache(cache_path)
        if cached is not None:
            result[ticker] = cached
            continue
        try:
            info = yf.Ticker(ticker).info or {}
            fundamentals = _extract_fundamentals(info)
            result[ticker] = fundamentals
            cache_path.write_text(json.dumps(fundamentals, ensure_ascii=False))
        except Exception as e:  # ネットワーク・レート制限など
            logger.warning("財務データ取得失敗: %s (%s)", ticker, e)
            result[ticker] = {}
        if i % 10 == 9:
            logger.info("財務データ取得中: %d/%d", i + 1, len(tickers))
            time.sleep(1.0)  # レート制限対策
    return result

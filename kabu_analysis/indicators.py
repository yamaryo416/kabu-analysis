"""テクニカル指標の計算。入力は日次終値のpandas.Series(昇順の日付index)。"""

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 245  # 日本市場の年間営業日数の近似


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window, min_periods=window).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder方式のRSI。"""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(100.0).where(avg_loss.notna(), np.nan)


def macd_histogram(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def momentum(close: pd.Series, months: int) -> float | None:
    """monthsヶ月リターン(約21営業日/月)。データ不足時はNone。"""
    days = months * 21
    if len(close) <= days:
        return None
    past = close.iloc[-days - 1]
    if past <= 0:
        return None
    return float(close.iloc[-1] / past - 1)


def annualized_volatility(close: pd.Series, lookback_days: int = 245) -> float | None:
    rets = close.pct_change().dropna().iloc[-lookback_days:]
    if len(rets) < 30:
        return None
    return float(rets.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def max_drawdown(close: pd.Series, lookback_days: int = 245) -> float | None:
    """直近lookback_daysの最大ドローダウン(負の値、例 -0.25)。"""
    window = close.iloc[-lookback_days:]
    if len(window) < 30:
        return None
    running_max = window.cummax()
    dd = window / running_max - 1
    return float(dd.min())


def distance_from_52w_high(close: pd.Series) -> float | None:
    """52週高値からの乖離(負の値、例 -0.08 = 高値から8%下)。"""
    window = close.iloc[-TRADING_DAYS_PER_YEAR:]
    if len(window) < 60:
        return None
    high = window.max()
    if high <= 0:
        return None
    return float(window.iloc[-1] / high - 1)


def slope(series: pd.Series, lookback_days: int = 20) -> float | None:
    """直近lookback_daysの変化率ベースの傾き(期間リターン)。"""
    s = series.dropna()
    if len(s) <= lookback_days:
        return None
    past = s.iloc[-lookback_days - 1]
    if past == 0:
        return None
    return float(s.iloc[-1] / past - 1)


def compute_technicals(close: pd.Series) -> dict[str, float | None]:
    """スコアリングに必要なテクニカル指標一式を返す。"""
    close = close.dropna()
    last = float(close.iloc[-1]) if len(close) else None
    sma25 = sma(close, 25)
    sma75 = sma(close, 75)
    sma200 = sma(close, 200)

    def last_of(s: pd.Series) -> float | None:
        v = s.iloc[-1] if len(s) else np.nan
        return None if pd.isna(v) else float(v)

    rsi_series = rsi(close)
    macd_hist = macd_histogram(close)
    return {
        "close": last,
        "sma25": last_of(sma25),
        "sma75": last_of(sma75),
        "sma200": last_of(sma200),
        "sma200_slope": slope(sma200, 20),
        "rsi14": last_of(rsi_series),
        "macd_hist": last_of(macd_hist),
        "mom_3m": momentum(close, 3),
        "mom_6m": momentum(close, 6),
        "mom_12m": momentum(close, 12),
        "volatility_1y": annualized_volatility(close),
        "max_drawdown_1y": max_drawdown(close),
        "dist_52w_high": distance_from_52w_high(close),
    }

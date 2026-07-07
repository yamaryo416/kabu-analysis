import numpy as np
import pandas as pd
import pytest

from kabu_analysis.indicators import (
    annualized_volatility,
    compute_technicals,
    distance_from_52w_high,
    max_drawdown,
    momentum,
    relative_strength,
    rsi,
    sma,
    volume_trend,
)


def make_series(values) -> pd.Series:
    index = pd.bdate_range(end="2026-07-06", periods=len(values))
    return pd.Series(values, index=index, dtype=float)


def uptrend(days=500) -> pd.Series:
    rng = np.random.default_rng(42)
    rets = rng.normal(0.001, 0.005, days)
    return make_series(1000 * np.exp(np.cumsum(rets)))


def downtrend(days=500) -> pd.Series:
    rng = np.random.default_rng(42)
    rets = rng.normal(-0.001, 0.005, days)
    return make_series(1000 * np.exp(np.cumsum(rets)))


def test_sma_last_value():
    s = make_series(range(1, 101))
    assert sma(s, 10).iloc[-1] == pytest.approx(95.5)


def test_rsi_bounds_and_direction():
    up = rsi(uptrend()).iloc[-1]
    down = rsi(downtrend()).iloc[-1]
    assert 0 <= down < up <= 100


def test_momentum_uptrend_positive():
    assert momentum(uptrend(), 6) > 0
    assert momentum(downtrend(), 6) < 0


def test_momentum_insufficient_data():
    assert momentum(make_series(range(10)), 12) is None


def test_volatility_positive():
    vol = annualized_volatility(uptrend())
    assert vol is not None and 0 < vol < 1


def test_max_drawdown_negative_or_zero():
    mdd = max_drawdown(downtrend())
    assert mdd is not None and mdd < 0


def test_distance_from_52w_high():
    dist = distance_from_52w_high(downtrend())
    assert dist is not None and dist < 0
    # 単調増加の系列は常に高値圏
    assert distance_from_52w_high(make_series(range(1, 300))) == pytest.approx(0.0)


def test_relative_strength_vs_benchmark():
    # 上昇銘柄 vs 下落ベンチマーク → プラスの相対力
    assert relative_strength(uptrend(), downtrend(), 6) > 0
    assert relative_strength(downtrend(), uptrend(), 6) < 0


def test_volume_trend_detects_surge():
    flat = make_series([1_000_000.0] * 200)
    assert volume_trend(flat) == pytest.approx(1.0)
    surge = make_series([1_000_000.0] * 180 + [3_000_000.0] * 20)
    assert volume_trend(surge) > 1.5


def test_compute_technicals_keys():
    t = compute_technicals(uptrend(), volume=make_series([1e6] * 500), benchmark=downtrend())
    for key in ("close", "sma25", "sma200", "rsi14", "mom_12m", "volatility_1y"):
        assert t[key] is not None, key
    assert t["close"] > t["sma200"]  # 上昇トレンドなら株価は200日線の上
    assert t["rel_12m"] > 0
    assert t["volume_trend"] == pytest.approx(1.0)


def test_compute_technicals_without_optional_inputs():
    t = compute_technicals(uptrend())
    assert t["rel_12m"] is None
    assert t["volume_trend"] is None

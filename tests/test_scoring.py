from kabu_analysis.scoring import (
    SIGNAL_AVOID,
    SIGNAL_BUY_DIP,
    SIGNAL_WATCH_HOT,
    analyze_stock,
    buy_candidates,
    decide_signal,
    fundamental_score,
    rank_by_sector,
    trend_score,
)

STRONG_TECHNICALS = {
    "close": 1100.0,
    "sma25": 1080.0,
    "sma75": 1000.0,
    "sma200": 900.0,
    "sma200_slope": 0.03,
    "rsi14": 52.0,
    "macd_hist": 1.5,
    "mom_3m": 0.08,
    "mom_6m": 0.15,
    "mom_12m": 0.30,
    "volatility_1y": 0.22,
    "max_drawdown_1y": -0.12,
    "dist_52w_high": -0.03,
}

WEAK_TECHNICALS = {
    "close": 800.0,
    "sma25": 850.0,
    "sma75": 900.0,
    "sma200": 950.0,
    "sma200_slope": -0.02,
    "rsi14": 35.0,
    "macd_hist": -2.0,
    "mom_3m": -0.10,
    "mom_6m": -0.15,
    "mom_12m": -0.20,
    "volatility_1y": 0.45,
    "max_drawdown_1y": -0.35,
    "dist_52w_high": -0.30,
}

GOOD_FUNDAMENTALS = {
    "per": 15.0,
    "roe": 0.15,
    "operating_margin": 0.18,
    "revenue_growth": 0.10,
    "earnings_growth": 0.15,
    "dividend_yield": 0.03,
}

BAD_FUNDAMENTALS = {
    "per": 60.0,
    "roe": 0.02,
    "operating_margin": 0.02,
    "revenue_growth": -0.05,
    "earnings_growth": -0.20,
    "dividend_yield": 0.0,
}


def test_trend_score_orders_strong_above_weak():
    strong, _ = trend_score(STRONG_TECHNICALS)
    weak, _ = trend_score(WEAK_TECHNICALS)
    assert strong > 80 > 40 > weak


def test_fundamental_score_orders_good_above_bad():
    good, _, _ = fundamental_score(GOOD_FUNDAMENTALS)
    bad, _, cautions = fundamental_score(BAD_FUNDAMENTALS)
    assert good > bad
    assert cautions  # 割高・減益の注意点が付く


def test_fundamental_score_missing_data_is_neutral():
    score, _, _ = fundamental_score({})
    assert 40 <= score <= 60


def test_strong_stock_gets_buy_dip_signal():
    a = analyze_stock("0000.T", "テスト", "テスト", STRONG_TECHNICALS, GOOD_FUNDAMENTALS)
    assert a.signal == SIGNAL_BUY_DIP
    assert a.composite_score > 60
    assert a.reasons


def test_weak_stock_gets_avoid_signal():
    a = analyze_stock("0001.T", "テスト", "テスト", WEAK_TECHNICALS, BAD_FUNDAMENTALS)
    assert a.signal == SIGNAL_AVOID


def test_overheated_stock_gets_watch_hot():
    hot = dict(STRONG_TECHNICALS, rsi14=80.0)
    signal, notes = decide_signal(70.0, 85.0, hot)
    assert signal == SIGNAL_WATCH_HOT
    assert notes


def test_rank_by_sector_top_n():
    analyses = [
        analyze_stock(f"{i:04d}.T", f"銘柄{i}", "銀行", STRONG_TECHNICALS, GOOD_FUNDAMENTALS)
        for i in range(5)
    ]
    ranked = rank_by_sector(analyses, top_n=3)
    assert len(ranked["銀行"]) == 3
    scores = [a.composite_score for a in ranked["銀行"]]
    assert scores == sorted(scores, reverse=True)


def test_buy_candidates_excludes_avoid():
    good = analyze_stock("0000.T", "良い", "銀行", STRONG_TECHNICALS, GOOD_FUNDAMENTALS)
    bad = analyze_stock("0001.T", "悪い", "銀行", WEAK_TECHNICALS, BAD_FUNDAMENTALS)
    picks = buy_candidates([good, bad])
    assert good in picks and bad not in picks

"""デモモード: ネットワーク不要の合成データ生成。

銘柄コードからシードを決めて決定的に生成するため、同じ銘柄は常に同じ結果になる。
レポート生成や画面確認、CIでの動作検証に使う。
"""

import hashlib

import numpy as np
import pandas as pd


def _seed_for(ticker: str) -> int:
    return int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16)


def generate_price_history(ticker: str, days: int = 500) -> pd.DataFrame:
    """銘柄ごとに傾向の異なる合成株価(Close/Volume)を生成。"""
    rng = np.random.default_rng(_seed_for(ticker))
    # 年率ドリフト -20%〜+40%、ボラティリティ 18%〜45% を銘柄ごとに固定
    drift = rng.uniform(-0.20, 0.40)
    vol = rng.uniform(0.18, 0.45)
    dt = 1 / 245
    rets = rng.normal(drift * dt, vol * np.sqrt(dt), size=days)
    price0 = rng.uniform(800, 12000)
    prices = price0 * np.exp(np.cumsum(rets))
    volumes = rng.lognormal(mean=13.0, sigma=0.4, size=days)
    index = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    return pd.DataFrame({"Close": prices, "Volume": volumes}, index=index)


def generate_benchmark(days: int = 500) -> pd.Series:
    """ベンチマーク(市場平均)の合成終値。年率+8%・ボラ18%の緩やかな上昇。"""
    rng = np.random.default_rng(_seed_for("BENCHMARK"))
    dt = 1 / 245
    rets = rng.normal(0.08 * dt, 0.18 * np.sqrt(dt), size=days)
    index = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    return pd.Series(30000 * np.exp(np.cumsum(rets)), index=index, name="Close")


def generate_fundamentals(ticker: str) -> dict:
    rng = np.random.default_rng(_seed_for(ticker) + 1)
    return {
        "per": float(rng.uniform(6, 45)),
        "forward_per": float(rng.uniform(6, 40)),
        "pbr": float(rng.uniform(0.6, 5.0)),
        "roe": float(rng.uniform(0.02, 0.22)),
        "operating_margin": float(rng.uniform(0.02, 0.25)),
        "revenue_growth": float(rng.uniform(-0.08, 0.20)),
        "earnings_growth": float(rng.uniform(-0.15, 0.30)),
        "dividend_yield": float(rng.uniform(0.0, 0.045)),
        "market_cap": float(rng.uniform(3e11, 5e13)),
        "debt_to_equity": float(rng.uniform(10, 250)),
        "fcf_yield": float(rng.uniform(-0.02, 0.10)),
        "target_price": None,  # デモでは株価と整合しないため省略
        "recommendation": float(rng.uniform(1.5, 3.5)),
    }

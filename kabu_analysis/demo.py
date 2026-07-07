"""デモモード: ネットワーク不要の合成データ生成。

銘柄コードからシードを決めて決定的に生成するため、同じ銘柄は常に同じ結果になる。
レポート生成や画面確認、CIでの動作検証に使う。
"""

import hashlib

import numpy as np
import pandas as pd


def _seed_for(ticker: str) -> int:
    return int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16)


def generate_price_history(ticker: str, days: int = 500) -> pd.Series:
    """銘柄ごとに傾向の異なる合成株価(調整後終値)を生成。"""
    rng = np.random.default_rng(_seed_for(ticker))
    # 年率ドリフト -20%〜+40%、ボラティリティ 18%〜45% を銘柄ごとに固定
    drift = rng.uniform(-0.20, 0.40)
    vol = rng.uniform(0.18, 0.45)
    dt = 1 / 245
    rets = rng.normal(drift * dt, vol * np.sqrt(dt), size=days)
    price0 = rng.uniform(800, 12000)
    prices = price0 * np.exp(np.cumsum(rets))
    index = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    return pd.Series(prices, index=index, name="Close")


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
    }

"""複合スコアリングと売買シグナル判定。

方針: 1〜5年保有で年率10〜50%を狙う「手堅いトレンド投資」。
  - トレンド (40%): 上昇トレンドが確立している銘柄に順張り
  - ファンダメンタルズ (40%): 収益性・成長性が高く、割高すぎない銘柄
  - リスク (20%): ボラティリティ・ドローダウンが小さい銘柄を優遇
買いシグナルは「トレンドは強いが短期的に過熱していない(押し目)」場面で点灯する。
"""

from dataclasses import dataclass, field

# シグナル定義
SIGNAL_BUY_DIP = "買い候補(押し目)"
SIGNAL_BUY_TREND = "買い候補(トレンド)"
SIGNAL_WATCH_HOT = "監視(過熱・押し目待ち)"
SIGNAL_WATCH = "監視"
SIGNAL_AVOID = "見送り"

_SIGNAL_ORDER = {
    SIGNAL_BUY_DIP: 0,
    SIGNAL_BUY_TREND: 1,
    SIGNAL_WATCH_HOT: 2,
    SIGNAL_WATCH: 3,
    SIGNAL_AVOID: 4,
}


@dataclass
class StockAnalysis:
    ticker: str
    name: str
    sector: str
    price: float | None
    trend_score: float
    fundamental_score: float
    risk_score: float
    composite_score: float
    signal: str
    reasons: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    technicals: dict = field(default_factory=dict)
    fundamentals: dict = field(default_factory=dict)

    @property
    def signal_rank(self) -> int:
        return _SIGNAL_ORDER.get(self.signal, 9)


def _scale(value: float, lo: float, hi: float, max_points: float) -> float:
    """value を [lo, hi] で線形に [0, max_points] へ写像(範囲外はクリップ)。"""
    if hi == lo:
        return 0.0
    ratio = (value - lo) / (hi - lo)
    return max(0.0, min(1.0, ratio)) * max_points


def trend_score(t: dict) -> tuple[float, list[str]]:
    """テクニカル指標からトレンドスコア(0-100)と根拠を算出。"""
    score = 0.0
    reasons: list[str] = []
    close, sma25, sma75, sma200 = t.get("close"), t.get("sma25"), t.get("sma75"), t.get("sma200")

    # 移動平均線の並び (最大20点)
    if all(v is not None for v in (close, sma25, sma75, sma200)):
        if close > sma25 > sma75 > sma200:
            score += 20
            reasons.append("株価>25日>75日>200日線のパーフェクトオーダー(強い上昇トレンド)")
        elif close > sma75 > sma200:
            score += 14
            reasons.append("株価が75日・200日線の上で推移(中期上昇トレンド)")
        elif close > sma200:
            score += 8
            reasons.append("株価が200日線の上で推移(長期トレンドは維持)")

    # 200日線の傾き (最大8点)
    s200_slope = t.get("sma200_slope")
    if s200_slope is not None and s200_slope > 0:
        score += _scale(s200_slope, 0.0, 0.05, 8)
        if s200_slope > 0.01:
            reasons.append("200日移動平均線が右肩上がり")

    # 12ヶ月モメンタム (最大18点)
    mom12 = t.get("mom_12m")
    if mom12 is not None:
        score += _scale(mom12, -0.20, 0.40, 18)
        if mom12 > 0.15:
            reasons.append(f"直近12ヶ月リターン +{mom12 * 100:.0f}%と中期モメンタム良好")

    # 6ヶ月モメンタム (最大10点)
    mom6 = t.get("mom_6m")
    if mom6 is not None:
        score += _scale(mom6, -0.15, 0.30, 10)

    # 52週高値への近さ (最大12点)
    dist = t.get("dist_52w_high")
    if dist is not None:
        score += _scale(dist, -0.25, 0.0, 12)
        if dist > -0.05:
            reasons.append("52週高値圏で推移(高値更新の期待)")

    # MACDヒストグラム (最大8点)
    macd_hist = t.get("macd_hist")
    if macd_hist is not None and macd_hist > 0 and close:
        score += 8
        reasons.append("MACDが買い優勢")

    # 対市場相対力: 日経平均に対する12ヶ月超過リターン (最大16点、データ欠損時は中立8点)
    rel12 = t.get("rel_12m")
    if rel12 is None:
        score += 8.0
    else:
        score += _scale(rel12, -0.10, 0.20, 16)
        if rel12 >= 0.10:
            reasons.append(f"日経平均を12ヶ月で+{rel12 * 100:.0f}%上回る相対的な強さ")
        elif rel12 <= -0.10:
            pass  # 市場に対する劣後はスコア減点のみで理由には出さない

    # 出来高トレンド: 20日平均/60日平均 (最大8点、欠損時は中立4点)
    vol_trend = t.get("volume_trend")
    if vol_trend is None:
        score += 4.0
    else:
        score += _scale(vol_trend, 0.85, 1.30, 8)
        if vol_trend >= 1.20:
            reasons.append(f"出来高が増加傾向(直近20日は60日平均の{vol_trend:.1f}倍)で資金流入")

    return min(score, 100.0), reasons


def fundamental_score(f: dict) -> tuple[float, list[str], list[str]]:
    """財務指標からファンダメンタルスコア(0-100)と根拠・注意点を算出。

    欠損項目は中立点(配点の半分)を与え、データ欠損だけで不当に沈まないようにする。
    """
    score = 0.0
    reasons: list[str] = []
    cautions: list[str] = []

    roe = f.get("roe")  # 例 0.12 = 12%
    if roe is None:
        score += 9.0
    else:
        score += _scale(roe, 0.0, 0.15, 18)
        if roe >= 0.10:
            reasons.append(f"ROE {roe * 100:.1f}%と資本効率が高い")
        elif roe < 0.05:
            cautions.append(f"ROE {roe * 100:.1f}%と資本効率は低め")

    margin = f.get("operating_margin")
    if margin is None:
        score += 5.0
    else:
        score += _scale(margin, 0.0, 0.15, 10)
        if margin >= 0.12:
            reasons.append(f"営業利益率 {margin * 100:.1f}%と収益性が高い")

    rev_g = f.get("revenue_growth")
    if rev_g is None:
        score += 5.0
    else:
        score += _scale(rev_g, 0.0, 0.15, 10)
        if rev_g >= 0.08:
            reasons.append(f"増収率 +{rev_g * 100:.1f}%と成長継続")
        elif rev_g < 0:
            cautions.append(f"減収({rev_g * 100:.1f}%)")

    earn_g = f.get("earnings_growth")
    if earn_g is None:
        score += 6.0
    else:
        score += _scale(earn_g, 0.0, 0.20, 12)
        if earn_g >= 0.10:
            reasons.append(f"増益率 +{earn_g * 100:.1f}%")
        elif earn_g < 0:
            cautions.append(f"減益({earn_g * 100:.1f}%)")

    dividend = f.get("dividend_yield")
    if dividend is None:
        score += 4.0
    else:
        score += _scale(dividend, 0.0, 0.03, 8)
        if dividend >= 0.03:
            reasons.append(f"配当利回り {dividend * 100:.2f}%")

    # バリュエーションガード (最大16点): 高すぎるPERは減点
    per = f.get("per")
    if per is None:
        score += 8.0
    elif per <= 0:
        score += 0.0
        cautions.append("赤字(PER算出不可)")
    elif per <= 25:
        score += 16.0
        reasons.append(f"PER {per:.1f}倍と割高感なし")
    elif per <= 40:
        score += 8.0
    else:
        cautions.append(f"PER {per:.1f}倍と割高(期待先行に注意)")

    # 財務健全性: 負債資本倍率 D/E (最大10点、% 表記)
    dte = f.get("debt_to_equity")
    if dte is None:
        score += 5.0
    else:
        score += _scale(-dte, -200.0, -50.0, 10)
        if dte <= 50:
            reasons.append(f"D/E {dte:.0f}%と財務健全")
        elif dte >= 200:
            cautions.append(f"D/E {dte:.0f}%と負債依存度が高い")

    # フリーキャッシュフロー利回り (最大8点)
    fcf = f.get("fcf_yield")
    if fcf is None:
        score += 4.0
    else:
        score += _scale(fcf, 0.0, 0.06, 8)
        if fcf >= 0.05:
            reasons.append(f"FCF利回り {fcf * 100:.1f}%と現金創出力が高い")
        elif fcf < 0:
            cautions.append("フリーキャッシュフローがマイナス")

    # アナリスト評価: 目標株価との乖離 (最大8点)
    upside = f.get("target_upside")
    if upside is None:
        score += 4.0
    else:
        score += _scale(upside, 0.0, 0.25, 8)
        if upside >= 0.15:
            reasons.append(f"アナリスト目標株価まで+{upside * 100:.0f}%の余地")
        elif upside < -0.05:
            cautions.append("株価がアナリスト目標を上回っている(織り込み済みの可能性)")

    return min(score, 100.0), reasons, cautions


def risk_score(t: dict) -> tuple[float, list[str], list[str]]:
    """価格リスクからリスクスコア(0-100、高いほど低リスク)を算出。"""
    score = 0.0
    reasons: list[str] = []
    cautions: list[str] = []

    vol = t.get("volatility_1y")
    if vol is None:
        score += 25.0
    else:
        score += _scale(-vol, -0.50, -0.20, 50)
        if vol <= 0.25:
            reasons.append(f"年率ボラティリティ {vol * 100:.0f}%と値動きが安定")
        elif vol >= 0.45:
            cautions.append(f"年率ボラティリティ {vol * 100:.0f}%と値動きが荒い")

    mdd = t.get("max_drawdown_1y")
    if mdd is None:
        score += 25.0
    else:
        score += _scale(mdd, -0.40, -0.10, 50)
        if mdd <= -0.30:
            cautions.append(f"直近1年の最大下落率 {mdd * 100:.0f}%")

    return min(score, 100.0), reasons, cautions


def decide_signal(composite: float, trend: float, t: dict) -> tuple[str, list[str]]:
    """総合スコアとテクニカル状態から売買シグナルを決める。"""
    notes: list[str] = []
    rsi14 = t.get("rsi14")
    close, sma25 = t.get("close"), t.get("sma25")
    ext25 = None  # 25日線からの上方乖離率
    if close is not None and sma25:
        ext25 = close / sma25 - 1

    if trend < 40:
        return SIGNAL_AVOID, ["上昇トレンドが確認できない(下落・横ばい局面)"]
    if composite < 55:
        return SIGNAL_WATCH, ["総合スコアが基準未達(トレンドかファンダのどちらかが弱い)"]

    overheated = (rsi14 is not None and rsi14 >= 72) or (ext25 is not None and ext25 >= 0.10)
    if overheated:
        if rsi14 is not None and rsi14 >= 72:
            notes.append(f"RSI {rsi14:.0f}と短期過熱。押し目を待ちたい")
        if ext25 is not None and ext25 >= 0.10:
            notes.append(f"25日線から+{ext25 * 100:.0f}%乖離と買われすぎ")
        return SIGNAL_WATCH_HOT, notes

    pullback = (rsi14 is not None and rsi14 <= 60) or (ext25 is not None and -0.05 <= ext25 <= 0.03)
    if pullback:
        if rsi14 is not None and rsi14 <= 55:
            notes.append(f"RSI {rsi14:.0f}で過熱感なく、押し目の買い場")
        elif ext25 is not None and ext25 <= 0.03:
            notes.append("25日移動平均線近辺まで調整しており、エントリーしやすい水準")
        else:
            notes.append("過熱感のない上昇トレンド継続中")
        return SIGNAL_BUY_DIP, notes

    notes.append("強いトレンド継続中(打診買い・分割エントリー向き)")
    return SIGNAL_BUY_TREND, notes


def analyze_stock(
    ticker: str,
    name: str,
    sector: str,
    technicals: dict,
    fundamentals: dict,
) -> StockAnalysis:
    # アナリスト目標株価との乖離を事前計算してスコアリングに渡す
    fundamentals = dict(fundamentals)
    target, close = fundamentals.get("target_price"), technicals.get("close")
    if target and close:
        fundamentals["target_upside"] = target / close - 1

    t_score, t_reasons = trend_score(technicals)
    f_score, f_reasons, f_cautions = fundamental_score(fundamentals)
    r_score, r_reasons, r_cautions = risk_score(technicals)
    composite = round(0.4 * t_score + 0.4 * f_score + 0.2 * r_score, 1)
    signal, notes = decide_signal(composite, t_score, technicals)

    return StockAnalysis(
        ticker=ticker,
        name=name,
        sector=sector,
        price=technicals.get("close"),
        trend_score=round(t_score, 1),
        fundamental_score=round(f_score, 1),
        risk_score=round(r_score, 1),
        composite_score=composite,
        signal=signal,
        reasons=t_reasons + f_reasons + r_reasons + notes,
        cautions=f_cautions + r_cautions,
        technicals=technicals,
        fundamentals=fundamentals,
    )


def rank_by_sector(analyses: list[StockAnalysis], top_n: int = 3) -> dict[str, list[StockAnalysis]]:
    """セクターごとに総合スコア降順で上位top_nを返す。"""
    by_sector: dict[str, list[StockAnalysis]] = {}
    for a in analyses:
        by_sector.setdefault(a.sector, []).append(a)
    return {
        sector: sorted(items, key=lambda a: a.composite_score, reverse=True)[:top_n]
        for sector, items in by_sector.items()
    }


def buy_candidates(analyses: list[StockAnalysis]) -> list[StockAnalysis]:
    """全銘柄から買い候補シグナルの銘柄をスコア降順で返す。"""
    picks = [a for a in analyses if a.signal in (SIGNAL_BUY_DIP, SIGNAL_BUY_TREND)]
    return sorted(picks, key=lambda a: (a.signal_rank, -a.composite_score))

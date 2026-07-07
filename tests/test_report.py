from pathlib import Path

from kabu_analysis.demo import generate_fundamentals, generate_price_history
from kabu_analysis.indicators import compute_technicals
from kabu_analysis.report import build_html, build_markdown, to_json, write_reports
from kabu_analysis.scoring import analyze_stock
from kabu_analysis.universe import get_universe


def make_analyses(n=10):
    stocks = get_universe()[:n]
    return [
        analyze_stock(
            s.ticker,
            s.name,
            s.sector,
            compute_technicals(generate_price_history(s.ticker)),
            generate_fundamentals(s.ticker),
        )
        for s in stocks
    ]


def test_build_html_contains_stocks():
    analyses = make_analyses()
    html = build_html(analyses, demo=True)
    assert "<!DOCTYPE html>" in html
    assert "デモモード" in html
    assert analyses[0].name in html


def test_build_markdown_and_json():
    analyses = make_analyses()
    md = build_markdown(analyses)
    js = to_json(analyses)
    assert "# 日次株式分析レポート" in md
    assert '"sector_rankings"' in js


def test_write_reports(tmp_path: Path):
    paths = write_reports(make_analyses(), tmp_path, demo=True)
    assert (tmp_path / "latest.html").exists()
    assert (tmp_path / "latest.md").exists()
    assert (tmp_path / "latest.json").exists()
    assert len(paths) == 4

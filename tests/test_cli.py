from kabu_analysis.__main__ import _resolve_query, main
from kabu_analysis.universe import find_stock


def test_find_stock_by_code():
    assert find_stock("7203").name == "トヨタ自動車"
    assert find_stock("7203.T").name == "トヨタ自動車"


def test_find_stock_by_name():
    assert find_stock("トヨタ自動車").ticker == "7203.T"
    assert find_stock("ソニー").ticker == "6758.T"  # 部分一致


def test_find_stock_not_found():
    assert find_stock("存在しない銘柄") is None


def test_resolve_query_universe_and_arbitrary_code():
    assert _resolve_query("トヨタ")[0] == "7203.T"
    # ユニバース外の任意コードも受け付ける
    ticker, _, sector = _resolve_query("9101")  # 収録済み → セクター付き
    assert ticker == "9101.T"
    ticker, _, sector = _resolve_query("6594X"[:4])  # 6594 収録済み
    assert ticker == "6594.T"
    ticker, _, sector = _resolve_query("4755")  # 未収録コード
    assert (ticker, sector) == ("4755.T", "ユニバース外")
    assert _resolve_query("architecture") is None  # コードでも銘柄名でもない


def test_check_command_demo(capsys):
    assert main(["check", "7203", "--demo"]) == 0
    out = capsys.readouterr().out
    assert "トヨタ自動車" in out
    assert "総合スコア" in out
    assert "シグナル" in out


def test_check_command_unresolvable(capsys):
    assert main(["check", "unknown-stock", "--demo"]) == 1
    assert "解決できません" in capsys.readouterr().out

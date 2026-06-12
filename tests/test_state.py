import datetime as dt
import os

from congress_mirror.state import SeenStore
from tests.conftest import make_trade


def test_new_trades_then_marked(tmp_path):
    store = SeenStore(path=os.path.join(tmp_path, "seen.json"))
    day = dt.date(2025, 6, 1)
    t1 = make_trade("AAA", "buy", day)
    t2 = make_trade("BBB", "sell", day)

    assert store.new_trades([t1, t2]) == [t1, t2]
    store.mark([t1])

    fresh = SeenStore(path=store.path)
    new = fresh.new_trades([t1, t2])
    assert [t.ticker for t in new] == ["BBB"]

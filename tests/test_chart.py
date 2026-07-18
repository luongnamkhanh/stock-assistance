"""Anh dashboard PNG — skip neu thieu Pillow (system python local; venv/Railway co)."""


def run():
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("test_chart SKIP (thieu Pillow)")
        return
    from src.adapters.chart import daily_png
    from src.domain.entities import DayFlow
    ctx = {"date": "2026-07-17", "net_ty": -193.0,
           "index": {"close": 1782.12, "change": -24.51, "pct": -1.36},
           "rows": [DayFlow(f"2026-07-{d:02d}", v * 1e9)
                    for d, v in zip(range(1, 11), (120, -80, 200, -350, 90, -60, 150, -500, 300, -193))],
           "gom": [("HPG", 120e9, 22300, 1.2), ("FPT", 85e9, 98700, 3.1)],
           "xa": [("VND", -95e9, 15600, -3.5)]}
    png = daily_png(ctx)
    assert png[:4] == b"\x89PNG" and len(png) > 20_000, len(png)
    # du lieu thieu (API loi / DB moi): van ra anh, khong crash
    png2 = daily_png({**ctx, "index": None, "rows": [], "gom": [], "xa": []})
    assert png2[:4] == b"\x89PNG"
    print("test_chart OK")


if __name__ == "__main__":
    run()

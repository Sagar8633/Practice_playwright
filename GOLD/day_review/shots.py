"""Full-day screenshots of every trading day the GEX page holds (5-minute candles, side panels hidden).
    python shots.py            -> screens/YYYY-MM-DD.png and screens/sheet_N.jpg (4 days per sheet)
Uses a throwaway browser profile: MT5 trading off, no alarm, nothing sent anywhere."""
import pathlib, sys
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).parent
PAGE = (HERE.parent / "heatmap" / "gold_gex.html").as_uri()
OUT = HERE / "screens"
OUT.mkdir(exist_ok=True)
SETTINGS = {"tf": "5m", "signals": False, "bars": False, "profile": True, "zones": True, "abs": False, "gld": False,
            "alarm": False, "mt5": False, "bpx": False, "instrument": "XAUUSD"}

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1600, "height": 900})
    ctx.add_init_script("".join(f"localStorage.setItem('gex.{k}', JSON.stringify({str(v).lower() if isinstance(v, bool) else repr(v)}));" for k, v in SETTINGS.items()))
    pg = ctx.new_page()
    pg.goto(PAGE)
    pg.wait_for_function("() => typeof H !== 'undefined' && H.days.length > 0 && !H.loading && H.zones.length > 0", timeout=180000)
    pg.wait_for_timeout(2000)
    days = pg.evaluate("H.days.map(d => ({ start: d.start, date: d.date, label: d.label }))")
    files = []
    for d in days:
        pg.select_option("#day", str(d["start"]))
        pg.wait_for_timeout(700)
        f = OUT / f"{d['date']}.png"
        pg.screenshot(path=str(f))
        files.append((f, d))
        print("saved", f.name, d["label"])
    b.close()

# contact sheets: 4 days per image, each day at half size, newest last
W, Hh = 800, 450
for k in range(0, len(files), 4):
    sheet = Image.new("RGB", (2 * W, 2 * Hh), "white")
    for j, (f, d) in enumerate(files[k:k + 4]):
        im = Image.open(f).convert("RGB").crop((0, 0, 1600, 900)).resize((W, Hh))
        sheet.paste(im, ((j % 2) * W, (j // 2) * Hh))
        ImageDraw.Draw(sheet).rectangle([(j % 2) * W, (j // 2) * Hh, (j % 2) * W + W - 1, (j // 2) * Hh + Hh - 1], outline="white", width=2)
    sheet.save(OUT / f"sheet_{k // 4 + 1}.jpg", quality=72)
print(len(files), "days,", (len(files) + 3) // 4, "sheets in", OUT)

import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import sma18_engine as E, common as C
R = json.load(open(os.path.join(ROOT, "study3", "results", "study3.json"))); P = R["final"]["params"]
t = time.time()
base = dict(tf_minutes=240, start=C.DATA_START, end=C.DATA_END, margin_check=True, use_sl_pct=False, **C.COST["B_real"], **P)
p = E.Params(**{**base, "start_balance": 100000.0, "margin_check": False}); tr, st = E.run(p)
print("regression final fixed 0.01:", len(tr), round(tr.pnl.sum(), 2), "(expect 306 / 2529.9)")
for nm, kw in (("$200 fixed 0.01", dict(start_balance=200.0)), ("$200 tiered lots", dict(start_balance=200.0, sizing=2, base_balance=200.0, max_lots=5.0)),
               ("$200 tiered + partial (skip at min lot)", dict(start_balance=200.0, sizing=2, base_balance=200.0, max_lots=5.0, partial_enable=True)),
               ("$200 tiered + partial (close all at min lot)", dict(start_balance=200.0, sizing=2, base_balance=200.0, max_lots=5.0, partial_enable=True, partial_min_mode=1))):
    p = E.Params(**{**base, **kw}); tr, st = E.run(p)
    parts = int((tr.reason == 14).sum())
    print(f"{nm:44} rows {len(tr):4} partials {parts:3} end balance {st['final_balance']:9.2f} max lot {tr.lots.max():.2f} maxDD eq {st['maxdd_equity']:8.2f} ruin {st['ruin']} tiers {sorted(tr.stage.unique().tolist())}")
print("done %.1fs" % (time.time() - t))

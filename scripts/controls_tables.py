"""Markdown tables for docs/pipeline/controls.md from controls_eval.json and controls_upland.json -> docs/pipeline/controls_tables.md"""
import json
J = json.load(open("docs/pipeline/controls_eval.json")); U = json.load(open("docs/pipeline/controls_upland.json"))
rows = J["rows"]
def g(pair, pol, res, dom, ft="all", f="auc"):
    r = next((x for x in rows if x["pair"] == pair and x["pol"] == pol and x["res_m"] == res and x["domain"] == dom and x["forest_type"] == ft), None)
    return r[f] if r else None
fmt = lambda v: "n/a" if v is None else f"{v:.3f}"
A, B, C = "A storm 10-05->10-17", "B no storm 2025-10-22->11-03", "C no storm 2026-09-11->09-23"
L = []
for dom in ("all", "upland"):
    L += [f"**{'All forest' if dom == 'all' else 'Upland forest only'}**", "",
          "| Pol | Res (m) | Forest type | A storm | B 2025 | C 2026 pre | A − B | A − C | n damage (A) |", "|---|---|---|---|---|---|---|---|---|"]
    for p in ("HV", "HH"):
        for res in (10, 30, 100):
            for ft in ("all", "evergreen", "deciduous", "woody_wetland"):
                a, b, c = g(A, p, res, dom, ft), g(B, p, res, dom, ft), g(C, p, res, dom, ft)
                d = lambda x, y: "n/a" if x is None or y is None else f"{x - y:+.3f}"
                L.append(f"| {p} | {res} | {ft.replace('_', ' ')} | {fmt(a)} | {fmt(b)} | {fmt(c)} | {d(a, b)} | {d(a, c)} | {g(A, p, res, dom, ft, 'n_damage'):,} |")
    L.append("")
L += ["**Block bootstrap (10 km tiles) of the storm-minus-control AUC difference**", "", "| Comparison | Pol | Res | Domain | AUC A | AUC control | A − control | 95% CI |", "|---|---|---|---|---|---|---|---|"]
for k, v in J["bootstrap"].items():
    c, p, res, dom = [s.strip() for s in k.split("|")]
    L.append(f"| {c} | {p} | {res} | {dom} | {v['auc_A']:.3f} | {v['auc_control']:.3f} | {v['diff']:+.3f} | {v['ci95_block'][0]:+.3f} to {v['ci95_block'][1]:+.3f} |")
L += ["", "**Other 12-day pairs, HV, all forest (AUC 10 / 30 / 100 m)**", "", "| Pair | 10 m | 30 m | 100 m |", "|---|---|---|---|"]
for n in ("pre-pre 09-23->10-05", "post-post 10-17->10-29", "persist 10-05->10-29", "headline 09-23,10-05->10-17,10-29"):
    L.append(f"| {n} | " + " | ".join(fmt(g(n, 'HV', r, 'all')) for r in (10, 30, 100)) + " |")
L += ["", "**Main table on upland only: NISAR HV stack vs S1 VH stack with October-only posts**", "", "| Comparison | Res | Domain | AUC NISAR | AUC S1 Oct | NISAR − S1 | 95% CI (block) | n damage |", "|---|---|---|---|---|---|---|---|"]
for k, v in U["main_table"].items():
    c, res, dom = [s.strip() for s in k.split("|")]
    L.append(f"| {c.replace(' vs S1 VH Oct-only', '')} | {res} | {dom} | {v['auc_nisar']:.3f} | {v['auc_s1_oct']:.3f} | {v['diff']:+.3f} | {v['ci95_block'][0]:+.3f} to {v['ci95_block'][1]:+.3f} | {v['n_damage']:,} |")
L += ["", "**Persistence: damage minus intact, recentred dB difference (30 m blocks)**", "", "| Series | Upland | Woody wetland |", "|---|---|---|"]
up, ww = U["persistence"]["upland | 30 m"], U["persistence"]["woody_wetland | 30 m"]
for k in up: L.append(f"| {k} | {up[k][0]:+.2f} | {ww[k][0]:+.2f} |")
open("docs/pipeline/controls_tables.md", "w", encoding="utf8").write("\n".join(L) + "\n")

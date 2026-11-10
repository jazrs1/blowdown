"""Markdown tables for docs/pipeline/controls.md from controls_eval.json, controls_strict.json, controls_upland.json
-> docs/pipeline/controls_tables.md. Cells: AUC (damage-minus-intact recentred dB difference)."""
import json
J = json.load(open("docs/pipeline/controls_eval.json")); T = json.load(open("docs/pipeline/controls_strict.json")); U = json.load(open("docs/pipeline/controls_upland.json"))
rows = J["rows"]
def g(pair, pol, res, dom, ft="all"):
    return next((x for x in rows if x["pair"] == pair and x["pol"] == pol and x["res_m"] == res and x["domain"] == dom and x["forest_type"] == ft), None)
def cell(r): return "n/a" if r is None or r["auc"] is None else f"{r['auc']:.3f} ({r['delta_dB']:+.2f})"
def dif(a, b): return "n/a" if a is None or b is None or a["auc"] is None or b["auc"] is None else f"{a['auc'] - b['auc']:+.3f}"
A, B, C = "A storm 10-05->10-17", "B no storm 2025-10-22->11-03", "C no storm 2026-09-11->09-23"
L = ["### Step 2, all forest: AUC (Δ dB = damage minus intact, recentred)", "",
     "| Pol | Res (m) | Forest type | A storm | C 2026 pre | B 2025 | A − C | A − B | n damage |", "|---|---|---|---|---|---|---|---|---|"]
for p in ("HV", "HH"):
    for res in (10, 30, 100):
        for ft in ("all", "evergreen", "deciduous", "woody_wetland"):
            a, b, c = g(A, p, res, "all", ft), g(B, p, res, "all", ft), g(C, p, res, "all", ft)
            if res == 100 and ft == "deciduous": continue
            L.append(f"| {p} | {res} | {ft.replace('_', ' ')} | {cell(a)} | {cell(c)} | {cell(b)} | {dif(a, c)} | {dif(a, b)} | {a['n_damage']:,} |")
L += ["", "Deciduous at 100 m: 23 damage blocks, not scored.", "",
      "### Step 2, block bootstrap of A minus control, all forest (10 km tiles)", "",
      "| Comparison | Pol | Res | AUC A | AUC control | A − control | 95% CI |", "|---|---|---|---|---|---|---|"]
for k, v in J["bootstrap"].items():
    c, p, res, dom = [s.strip() for s in k.split("|")]
    if dom == "all": L.append(f"| {c} | {p} | {res} | {v['auc_A']:.3f} | {v['auc_control']:.3f} | {v['diff']:+.3f} | {v['ci95_block'][0]:+.3f} to {v['ci95_block'][1]:+.3f} |")
L += ["", "### Step 3, strict upland (blocks >= 90% upland forest): AUC (Δ dB)", "",
      "| Pol | Res | A storm | C 2026 pre | B 2025 | A − C (95% CI) | A − B (95% CI) | 10-05 -> 10-29 | n damage / intact (A) |", "|---|---|---|---|---|---|---|---|---|"]
for p in ("HV", "HH"):
    u = g(A, p, 10, "upland"); uc, ub = g(C, p, 10, "upland"), g(B, p, 10, "upland"); up_ = g("persist 10-05->10-29", p, 10, "upland")
    L.append(f"| {p} | 10 m (pixels, all upland) | {cell(u)} | {cell(uc)} | {cell(ub)} | {dif(u, uc)} | {dif(u, ub)} | {cell(up_)} | {u['n_damage']:,} / {u['n_intact']:,} |")
    for res in (30, 100):
        P = lambda n: T["pairs"][f"{n} | {p} | {res} m"]; f = lambda r: f"{r['auc']:.3f} ({r['contrast_dB']:+.2f})"
        bc, bb = T["boot"][f"A minus C | {p} | {res} m"], T["boot"][f"A minus B | {p} | {res} m"]
        ci = lambda b: f"{b['diff']:+.3f} ({b['ci95_block'][0]:+.3f} to {b['ci95_block'][1]:+.3f})"
        L.append(f"| {p} | {res} m | {f(P(A))} | {f(P(C))} | {f(P(B))} | {ci(bc)} | {ci(bb)} | {f(P('persist 10-05->10-29'))} | {P(A)['n_damage']:,} / {P(A)['n_intact']:,} |")
L += ["", "### Step 3, main table: NISAR HV stack vs S1 VH stack with October-only posts", "",
      "| NISAR arm | Res | Domain | AUC NISAR | AUC S1 Oct | NISAR − S1 | 95% CI (block) | n damage |", "|---|---|---|---|---|---|---|---|"]
for k, v in U["main_table"].items():
    c, res, dom = [s.strip() for s in k.split("|")]
    if dom == "all": L.append(f"| {c.replace(' vs S1 VH Oct-only', '').replace('NISAR HV stack, ', '')} | {res} | all forest | {v['auc_nisar']:.3f} | {v['auc_s1_oct']:.3f} | {v['diff']:+.3f} | {v['ci95_block'][0]:+.3f} to {v['ci95_block'][1]:+.3f} | {v['n_damage']:,} |")
for k, v in T["main_table"].items():
    c, res = [s.strip() for s in k.split("|")]
    L.append(f"| {c.replace(' vs S1 VH Oct-only', '').replace('NISAR HV stack, ', '')} | {res} | strict upland | {v['auc_first']:.3f} | {v['auc_second']:.3f} | {v['diff']:+.3f} | {v['ci95_block'][0]:+.3f} to {v['ci95_block'][1]:+.3f} | {v['n_damage']:,} |")
L += ["", "### Step 4, persistence: damage minus intact, recentred dB (30 m blocks; upland here = the looser 50%-upland labels)", "", "| Series | Upland | Woody wetland |", "|---|---|---|"]
up, ww = U["persistence"]["upland | 30 m"], U["persistence"]["woody_wetland | 30 m"]
for k in up: L.append(f"| {k} | {up[k][0]:+.2f} | {ww[k][0]:+.2f} |")
open("docs/pipeline/controls_tables.md", "w", encoding="utf8").write("\n".join(L) + "\n")

# New Lenskart Store — Starter Kit (what to provide for a fresh layout)

Hand these to a new session and it will have everything needed to design a new store to
the same standard. Files marked **[REQUIRED]** are essential; **[RECOMMENDED]** materially
improves quality; **[OPTIONAL]** fills gaps.

---

## A. Input files to attach

**1. The new site shell — [REQUIRED]**
- The empty base CAD for the new location (equivalent of `BASE CAD.dxf`), as **DXF** (not DWG — DWG can't be read directly; export to DXF first).
- Must contain: outer walls, glazing/shopfront, entry door, rolling shutter, columns, staircase, and any **existing toilet / services**. These drive the whole layout.

**2. The fixture/block library — [REQUIRED]  (UPDATED 2026-06-19)**
- **`BASE LIBRARY.dxf`** — the current, trimmed kit-of-parts (62 blocks: wall units, euros/half-euros, billing, greeter, clinic furniture, seating, toilet/BOH). **This is the ONLY furniture source.** The old `FURNITURE BLOCKS.dxf` and `FURNITURE BLOCKS CLINIC 1/2.dxf` are **retired — do not use.**
- **`2 CLINIC LIBRARY.dxf`** and **`3 CLINIC LIBRARY.dxf`** — the pre-made clinic **room blocks** (`A$C15b5f610` = SINK 2600×1700, `A$Cc304dd19` = RO 2600×1700) shown in their **canonical relative arrangements**. Place clinics from these arrangements directly; don't invent clinic positions. (Full catalog: optimization guide §15.)
- Removed from the library (don't expect them): LOOKER, NESTING TABLES, discussion tables, sofas, POS, generic CABINET, PICK UP COUNTER, 55"/49"/43" TV blocks.
- These are reusable across stores — same files each time.

**3. The rule set — [REQUIRED]**
- `LENSKART LAYOUT — OPTIMIZATION GUIDE (portable).md` ← **the master doc.** Self-contained: efficiency playbook, anthropometry, workflow, validation, fixture catalogue. Start here.
- `FURNITURE PLACEMENT RULES.md` (the brand Design-Manual rules it builds on).

**4. The gold-standard worked examples — [RECOMMENDED]**
- `BASE CAD WITH FP.dxf` and `BASE 2 FP.dxf` (real, expert-placed stores). The single most useful learning input — a new session should study these to calibrate density/efficiency before placing anything. **`BASE 2 FP.dxf` is the expert layout for the BASE 2 shell and is the current density benchmark** — it shows the moves our early drafts missed (see §12 "[XP]" in the optimization guide): aisles held to 1150–1200, **two double-euro rows (4 euros)** with screens back-to-back between them, walls merchandised from the glazing, retail pushed to ~87% depth, **L-shaped clinics** opening via curtains on the lower side, packed BOH, a proposed back-corner toilet, and **3 fire extinguishers**. Match this standard.

**5. Source manual — [OPTIONAL]**
- `DESIGN MANUAL.pdf` (only if rules need to be re-derived or the merch-mix matrix on p.10 is needed for exact per-brand counts).

> You do **not** need to send the iteration files (`STORE LAYOUT v1–v5`, clinic options) — they're history, not inputs.

---

## B. Decisions to state (so the session doesn't guess)

- **[REQUIRED] Proto tier** (≤₹12L / ₹12–15L / >₹15L) → sets clinic count (2 / 3 / 4).
- **[REQUIRED] Retail fixture-count target** (e.g. "15 retail display fixtures"), and **what counts** toward it (display wall + floor only, or including billing, etc.).
- **[RECOMMENDED] Site facts not obvious from the DXF:** is there an existing toilet to reuse? mezzanine/first floor? which side is premium vs value? any landlord constraints?
- **[OPTIONAL] Per-brand merch-mix numbers** (from Design Manual p.10) if you want exact facings per brand.

---

## C. Ready-to-paste kickoff prompt

> "Design a Lenskart store layout for a new location.
> Inputs attached: the site shell DXF (`<name>.dxf`), `FURNITURE BLOCKS.dxf` (+ clinic block files), and the rule docs `LENSKART LAYOUT — OPTIMIZATION GUIDE (portable).md` and `FURNITURE PLACEMENT RULES.md`. A reference placed store is in `BASE CAD WITH FP.dxf`.
> First, **study `BASE CAD WITH FP.dxf`** to calibrate density and the efficiency playbook. Then read the shell, set the local frame, and propose a layout following the guide: central double-euro spine, full-perimeter brand-sequenced walls with mirrors between fixtures, a ~60/40 retail/back-band partition, clinics as loose furniture in back nooks, dedicated pickup zone, reuse the existing toilet, billing/AR/lensometer pod.
> Proto tier: `<tier>`. Retail fixture target: `<N>` (counting display wall + floor only).
> Honour anthropometry/accessibility: strike-zone loading, shelf depth ≤600, primary aisles ≥1200, wheelchair 900 clear / 1500 turning, doors ≥900 where feasible.
> Output a DXF saved to my folder plus a rendered PNG, and run the clearance audit before finalising."

---

## D. What the session will do (workflow recap — full detail in the guide §8)

1. Study the reference (`BASE CAD WITH FP`) → 2. Read the new shell, set origin/frame, measure area, note columns/existing toilet → 3. Lay the central spine (greeter → 2 euros + screens → billing pod) → 4. Run both walls full length, brand-front-loaded, mirror between each → 5. Drop the 60/40 partition; place clinics (nooks) + pickup + store + storage + UPS + water dispenser; reuse existing toilet → 6. Apply anthropometry/accessibility → 7. **Clearance audit + iterate** → 8. Render + verify door swings, clinic access not behind cash, toilet clear.

## E. Acceptance checks before sign-off  (updated with [XP] density rules)

- Fixture count ≥ target (target is a **minimum**, not a cap — add product wherever it fits).
- **Aisles held to 1100–1200 mm** (functional minimum — no luxuriously wide aisles wasting selling space); wheelchair turning 1500 only at entry/billing; clinic openings (curtains) clear.
- **Two double-euro rows (4 euros)** flanking a 1200 central aisle + ~1150 side aisles; walls merchandised **from the glazing line** to the back; **retail ≈85–88% of depth**.
- **L-shaped clinics** in one back corner, opening via **curtains on the lower/corridor side**; ≥1 RO clinic + ≥1 sink/storage clinic; access never behind the cash.
- **≥3 fire extinguishers** distributed; **4× 55"** (2 facade + 2 euro back-to-back); greeter off-centre at entry (not blocking the aisle).
- ≥1 waiting bench; BOH packed (pickup/storage/UPS/water/QC); toilet provided (reused or proposed back-corner); finishes tagged by zone.
- DXF round-trips cleanly (no open profiles), saved to the folder with a PNG.

---

## F. Tip — reusable placement engine

The v5 build script (`two_clinics_v5.py`, in the working outputs) already contains reusable
helpers — `place()` (bbox-aligned block insertion with rotation), `wall_run()` (sequenced
wall fixtures + mirrors), `rect()`/`hdim()` (zones + dimensions), and the **clearance audit**
that records every fixture bbox and reports aisle gaps. Bring that script as a scaffold to
avoid rebuilding the placement/QA tooling from scratch.

---

### Minimum bundle (the short answer)
1. New **site shell DXF**, 2. `FURNITURE BLOCKS.dxf` (+ 2 clinic block files), 3. `LENSKART LAYOUT — OPTIMIZATION GUIDE (portable).md` (+ `FURNITURE PLACEMENT RULES.md`), 4. `BASE CAD WITH FP.dxf` as the reference, plus **proto tier + fixture-count target** in the prompt. That covers every rule and best practice captured so far.

---
name: lenskart-store-design
description: >-
  Design a complete Lenskart retail store layout from an empty base-CAD shell, producing a
  finished DXF + PNG render + clearance audit. Use this skill WHENEVER the user wants to lay out,
  furnish, or "fill" a Lenskart (optical/eyewear) store from a base CAD/DXF/floor-plan shell:
  placing wall display fixtures, Euro Centers, billing, greeter, blue zero, eye-test clinics
  (2/3/4), back-of-house and a toilet into a base plan. Triggers include "design a store",
  "store layout", "fill this base CAD with furniture", "fixture placement", "Lenskart store",
  "place the clinics", "2 clinic / 3 clinic store", "new store from this shell", or any base
  shell DXF that needs a retail furniture layout. It bundles the current furniture library, the
  full rule + optimization guides, the canonical clinic arrangements, and ready-to-run ezdxf
  tooling, so a new session needs nothing but the shell DXF and a couple of decisions.
---

# Lenskart store design (base shell → final DXF)

Turn an empty Lenskart base-CAD shell into a finished, rule-compliant store layout. Everything
needed is bundled here — do not ask the user for the furniture library, rules, or clinic files.

## Setup

```bash
pip install ezdxf matplotlib --break-system-packages -q
```

Bundled in this skill:
- `assets/BASE LIBRARY.dxf` — the **only** furniture library to use.
- `assets/2 CLINIC LIBRARY.dxf`, `assets/3 CLINIC LIBRARY.dxf` — clinic room blocks + arrangements.
- `assets/CLINIC ARRANGEMENTS - 2 clinic.png`, `- 3 clinic.png` — visual catalog.
- `assets/calibration/` — three expert "FP" layouts (`BASE 3 FP`, `BASE 2 FP`, `BASE CAD WITH FP`) to study for density.
- `references/` — `FURNITURE PLACEMENT RULES.md`, `LENSKART LAYOUT — OPTIMIZATION GUIDE (portable).md`, `NEW STORE — STARTER KIT.md`.
- `scripts/` — `dxf_engine.py`, `extract_shell.py`, `audit.py`, `clinic_arrangements.py`.

**Read `references/LENSKART LAYOUT — OPTIMIZATION GUIDE (portable).md` first** (it is the master doc;
§15 is the current library + clinic catalog; **§16 is the OPTIONAL "try & A/B-compare" menu** — variants that
often improve a design, e.g. prefer the L-shape clinic 2B, wall-heavy density, slim euro spine, super-premium
front-loading). `FURNITURE PLACEMENT RULES.md` is the brand-manual baseline. When the user wants the *best*
(not just a compliant) layout, build the base then spin the relevant §16 [OPT] variants, audit each, and keep
the strongest — these are options to explore, never new hard constraints.

## Ask the user when in doubt — before building

It is not only OK but expected to **pause and ask clarifying questions before executing**, using the
AskUserQuestion tool. A store layout is a big, mostly-irreversible build; a wrong assumption wastes a
lot of work. Ask whenever something is unclear or genuinely optional, e.g.:
- **Proto tier / clinic count** (2, 3, or 4) if not stated.
- **Retail fixture-count target**, if not given.
- **Which side is premium vs value**, and which wall the entry/glazing is on, if the shell is ambiguous.
- **Which clinic arrangement** to use when more than one fits, or where to put the clinic cluster.
- **Existing toilet** — reuse it (default) or relocate? Any mezzanine/first floor?
- **Anything the shell doesn't make obvious** (landlord constraints, a wall that's glazing vs solid, etc.).

Don't guess on consequential choices — a quick question up front is cheaper than a rebuild. For things
the rules already settle (fixture-count definition, no column overlap, euro joining, etc.), just apply them.

## The non-negotiable rules (these override convenience — burned-in lessons)

1. **Use ONLY `assets/BASE LIBRARY.dxf`.** The old `FURNITURE BLOCKS.dxf` is retired. Removed blocks you must NOT expect: LOOKER, NESTING TABLES, discussion tables, sofas, POS, generic CABINET, PICK UP COUNTER, and the 55"/49"/43" TV blocks. Substitutions: TV → rectangle on layer `LK-TV SCREEN`; storage/UPS/staff racks → labelled rectangles on `LK-FURNITURE`/`LENS-PARTITION`; pickup counter → `Pickup table PC` + a labelled rectangle.
2. **NEVER overlap a column or beam.** Run `extract_shell.py` first and treat every `column` and `beam` (including free-standing mid-floor columns) as a hard no-overlap zone. A fixture may *butt* a face (align to it) but never overlap. Re-run `audit.py` before sign-off — obstruction hits must be 0.
3. **Clinics: use the canonical arrangements, don't invent positions.** Place whole room blocks via `clinic_arrangements.py` (2A/2B/2C for two clinics, 3A/3B/3C for three). Only design a custom clinic position if none physically fit. Each room opens on a LONG side → face that opening at a clear corridor, never at the toilet door.
4. **Fixture count = wall + floor DISPLAY units only** (wall units + euros + blue zero). Not billing/greeter/pickup/AR/lensometer/bench/mirror/clinic/BOH/TV. The target is **approximate** — over preferred, under acceptable if space-limited. Don't ask the user about this.
5. **Euros join NON-DRAWER to NON-DRAWER.** Drawer banks are on the 1040 (±y) faces; join on the clean ±x faces (side-by-side in x → 2080×1175), drawers exposed along the long edges. Never drawer-to-drawer.
6. **Reuse the existing toilet; keep its door swing + approach clear.** Find the WC door in the shell; never block it. Give BOH a door.
7. **Seating leaves walk-around space** — never pinch a bench against a euro/island; benches go in open waiting space.

## Decisions to get from the user (only these)

- **Proto tier → clinic count:** ≤₹12L = 2, ₹12–15L = 3, >₹15L = 4. (If the user just says "2 clinics", tier is implied.)
- **Retail fixture-count target** (e.g. "19"). Approximate per rule 4.
- Anything non-obvious from the DXF: existing toilet? mezzanine? premium vs value side? Ask only if unclear.

Use the AskUserQuestion tool for these before building.

## Workflow

Work in the LOCAL frame (world − A-WALL min). The engine handles the conversion.

1. **Read the shell + map the structure.**
   ```bash
   python scripts/extract_shell.py "/path/to/SHELL.dxf"
   ```
   This prints (and writes `*.structure.json`) the A-WALL bbox, **columns**, **beams**, column-hatch,
   labels (find the SHAFT + EXISTING TOILET), and doors/entry. Render the bare shell to see its shape
   (`dxf_engine.render_png`). Identify: entry/glazing side (usually WEST), the back, side walls,
   columns/beams/shaft (no-overlap), the existing toilet + its door.

2. **Study a calibration FP** (`assets/calibration/BASE 3 FP.dxf` etc.) to calibrate density — especially
   how walls are merchandised continuously and how columns are absorbed into the fixture line.

3. **Build the layout** (a Python script using `dxf_engine.Placer`). Order:
   - **Walls, dense + continuous, glazing→back, both side walls.** Brand sequence — premium wall: super-premium → JJ-EYE → OD-EYE → JJ-SUN → C-LENS breaker; value wall: LK-Air → VC-EYE → Hooper → C-LENS. Mirror every 2–3 fixtures (`wall_run(..., every=2)`). Run fixtures *over* low column footprints (set the back baseline just clear of the column) and *stop at* tall column faces. Use a `VC HD 1010` on a free shaft face.
   - **Central euro spine:** `EURO 1040 x 1175` joined side-by-side in x (rule 5), clear of all columns; 2 facade screens + screens back-to-back over a euro (rectangles on `LK-TV SCREEN`).
   - **Greeter** off-centre at the entry (faces the door, doesn't block the swing); **Blue Zero** on the front glazing, right-hand side.
   - **Billing** counter at the rear/centre-east of the spine; **AR** as a separate station; lensometer; a **bench** in open waiting space.
   - **Clinics:** pick an arrangement and place it:
     ```python
     from clinic_arrangements import place_arrangement
     place_arrangement(placer, "2C", ox, oy, arr_rot=0)   # 2C = twin portrait + corridor
     ```
     Choose by back-zone shape: wide+shallow → 2A/3A; deep/corner → 2B/2C/3B/3C. Rotate (`arr_rot`) so openings face a clear corridor and clear the toilet door.
   - **Toilet:** reuse existing (tag tiles, keep door clear). **BOH** (storage/staff/UPS/water/QC) packed in the rear wing, behind a door (draw racks as labelled rectangles — no CABINET block now).
   - **Safety/finish:** ≥3 fire extinguishers (`placer.fire`) distributed front/mid/back; tag finishes (tiles in clinics+toilet, fluted cash-back, paint BOH).

4. **Audit + iterate.**
   ```python
   from extract_shell import extract_structure
   from audit import audit, print_report
   struct = extract_structure(shell_path)
   rep = audit(placer, struct, target_count=19,
               extra_obstructions={"SHAFT": (..), "TOILET": (..)})
   print_report(rep)
   ```
   Obstruction hits and fixture overlaps must be **0**. Also check aisles directly from `placer.placed`
   coords: primary aisles ~1100–1500, clinic corridor ≥1100, toilet-door approach clear, clinic opening
   on a long side. Iterate until clean.

5. **Deliverables — always produce all three:**
   - the final **DXF** (`doc.saveas(...)`, verify it round-trips with `ezdxf.readfile`, 0 open polylines),
   - a **PNG** render (`dxf_engine.render_png`),
   - a short **audit report** (the `print_report` output: 0 obstruction hits, 0 overlaps, fixture count, key aisles).
   Save DXF + PNG to the user's folder and present them.

## Acceptance checklist (before sign-off)

Fixtures ≥ target (approx) · walls merchandised continuously, brand-sequenced, mirrors every 2–3 ·
euros joined non-drawer-to-non-drawer, clear of columns · **0 column/beam overlaps** · clinics from a
canonical arrangement, opening on a long side onto a clear corridor · existing toilet reused, door clear ·
BOH behind a door · ≥3 fire extinguishers · ≥1 bench with walk-around space · finishes tagged ·
DXF round-trips · PNG + audit report produced.

## Reference files (read as needed)

- `references/LENSKART LAYOUT — OPTIMIZATION GUIDE (portable).md` — master rules; §1 efficiency playbook, §3 anthropometry, §12 expert density [XP], §13 client feedback [FB], §14 BASE 3 expert learnings, **§15 current library + clinic arrangement catalog**.
- `references/FURNITURE PLACEMENT RULES.md` — brand-manual baseline + §15 counting conventions + the hard column/beam/clinic/library rules.
- `references/NEW STORE — STARTER KIT.md` — what a fresh store needs.
- `scripts/clinic_arrangements.py` — run `python scripts/clinic_arrangements.py` to list the 6 arrangements.

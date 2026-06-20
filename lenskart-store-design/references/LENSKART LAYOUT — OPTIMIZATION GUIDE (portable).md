# Lenskart Store Layout — Optimization & Rules Guide (portable handoff)

Purpose: a self-contained brief for designing a **new Lenskart store** from a different
base-CAD shell in a fresh session. It consolidates three sources:

1. **Design Manual rules** — see companion `FURNITURE PLACEMENT RULES.md` (the brand manual, v1.0). Don't re-derive; treat as the baseline.
2. **Anthropometry rules** — human-factors dimensions (new in this guide).
3. **Efficiency rules reverse-engineered from a real, professionally placed store** (`BASE CAD WITH FP.dxf`). These are the *unstated* rules that make the real plan far more space-efficient than a naive rules-only layout. **This is the most important section — read it first.**

Each rule is tagged: **[MANUAL]** already in the manual file · **[ANTHRO]** human-factors · **[FP]** newly derived from the real layout (not in the manual).

---

## 0. How to read a Lenskart base-CAD shell (technical setup)

- Tooling: Python `ezdxf` (+ `matplotlib` for PNG previews). Units are **millimetres** (header `$INSUNITS` may say "feet" but geometry is mm).
- The store shell often lives **inside a single block** (e.g. `A$C65ba2408`) inserted into modelspace. Find that INSERT; its insertion point is your **origin (OX,OY)**. Work in **local coords = world − (OX,OY)**.
- Establish the frame: **−y = shopfront/entrance (south)**, **+y = back of store (north)**; left/right walls are the x extremes. Confirm by finding the glazing/rolling-shutter and the entrance door.
- Some fixtures may be **parked off-drawing** (huge x/y offsets) — ignore them for placement; they're a kit-of-parts palette.
- Build clinics/fixtures as **block references**; align by computing the block's bbox (`ezdxf.bbox.extents`) and shifting the insert so the bbox-min (or centre) lands on the target — this makes placement robust to each block's internal base point and rotation.
- **You may rotate any block** (clinics included) to fit — rotation is a free variable; align by bbox afterwards.

---

## 1. THE EFFICIENCY PLAYBOOK  (★ derived from the real layout — read first)

A rules-only layout (single Euro + scattered discussion tables + clinics-as-big-blocks +
a newly built toilet) wastes space and creates tight gaps. The professional plan is far
tighter because of these moves:

1. **[FP] One central SPINE, not scattered floor fixtures.** The entire centre of the store is a single continuous island running down the centreline: `Greeter → Euro Center 1 → Euro Center 2 → Billing/AR pod → (partition) → back band`. Everything else hangs off the two walls. One island = two clean, wide aisles.

2. **[FP] Double Euro Center, back-to-back, as the island core.** Use **two** `EURO 1040 x 1175` placed back-to-back (not one). Faces merchandise in all directions (e.g. TENTPOLE + HUSTLR on the front euro, VC-SUN on both faces of the rear euro). **55" screens mount back-to-back on top** of the euro pair (the manual's "TV above euro center, back-to-back"). This doubles display per m² versus a single euro plus separate tables. *Discussion tables are largely replaced by the euro + billing — don't pack the centre with separate tables.*

3. **[FP] Merchandise the FULL perimeter of BOTH side walls, end to end.** Wall fixtures run the entire length of each wall, front to back, with a **mirror between every single fixture** (or "mirror on site" using columns/wall returns). Don't stop the wall run early — wall area is the cheapest, highest-capacity display.

4. **[FP] Front-load brand value on the walls.** Premium wall, front→back: **super-premium first** (LPL, Fossil/branded) → JJ-EYE → OD-EYE → JJ-SUN/Meller. Value wall, front→back: LK-Air → VC-Eye → Hooper → **C-Lens as the end breaker**. **VC-SUN goes on the central euro**, not the wall. (Extends the manual's wall sequence with the super-premium-at-front nuance.)

5. **[FP] Split the store ~60/40 with a partition line.** Open retail occupies the front ~60%; a single **back service band** (behind one partition line spanning the width, with curtain/door openings) holds *everything back-of-house*: clinics, pickup, store, storage, UPS, water dispenser. Concentrating all "back" functions behind one line maximises the open selling floor.

6. **[FP] Clinics = loose furniture in partitioned nooks, NOT monolithic blocks.** Build each clinic from its parts (chair unit, doctor stool, screen/acuity, trial-set cabinet, and sink/mop for the sink clinic) inside light partition walls + a curtain door. This lets clinics tuck into irregular back-band nooks and share the back circulation — far tighter than dropping a rigid 2600×1700 room that forces a dedicated corridor. (If you *do* use the pre-made clinic block, still enter from its long side.)

7. **[FP] Reuse existing site services.** If the site has an **existing toilet**, reuse it — don't build a new one (saves ~20 sqft and plumbing). Same for usable existing partitions/glazing.

8. **[FP] Add a dedicated PICKUP zone** (often missed): pickup counter/table + `PICKUP STORAGE-900` + a PC/keyboard station, in the back band near the entrance side of BOH. This is the "Accomplish / repair-pickup" step of the journey.

9. **[FP] Billing = a compact dispensing pod**, not just a till: `Billing Counter (1800)` + `AR` station + `Lensometer` + doctor stool, sitting at the **rear-centre end of the central spine**, facing the floor and backing onto the clinic/pickup band.

10. **[FP] Integrate digital walls.** `VC HD 1010/1200` video units sit in the wall runs (esp. the value/VC wall) as digital merchandising; facade 55" screens face the street.

**Net effect:** perimeter fully merchandised + one central island + back band behind a partition ⇒ wide aisles *for free*, more facings, and clinics/BOH packed efficiently.

---

## 2. Zoning model (front → back)   [MANUAL + FP]

| Depth band | Contents | Notes |
|---|---|---|
| Facade / entry | Glazing, rolling shutter, entry door (≥1050 W), facade 55" screens, "Free Eye Test" signage | [MANUAL] |
| Establish | **Greeter** at entry centre; **Blue Zero** at entry front-centre (impulse, visible on entry) | [MANUAL] |
| Retail (front ~60%) | Two side walls fully merchandised; **central double-euro island**; mirrors between fixtures | [FP] spine concept |
| Billing / engage | Billing Counter + AR + Lensometer pod at rear-centre of the spine | [FP] |
| **Partition line** | One line across the width separating retail from the back band; curtain/door openings | [FP] |
| Back band (~40%) | Clinics (nooks), **Pickup zone**, Store, full-height storage, UPS, water dispenser, dining/QC | [FP] |
| Toilet | **Reuse existing** if present; else min 1500×1500 or 1200×2250, off a common passage | [MANUAL]+[FP] |

---

## 3. Anthropometry & clearances  [ANTHRO]  (accessibility usually governs — design to it)

**Vertical display zones (most important):**
- **Strike/golden zone ~900–1500 mm** (waist–eye): highest-value, impulse, best-margin stock. ("Eye level is buy level," ~1500–1600 mm.)
- **Stretch (top) up to ~1800 mm**: max comfortable self-service reach — nothing grabbable above this.
- **Stoop (bottom) below ~600 mm**: bulky/heavy/low-priority only; nothing sellable below ~250 mm.
- Wall fixtures are 2400 mm tall — load the 900–1600 band with hero SKUs, top shelf = display/stock dummies, bottom = backstock.

**Reach & shelf depth:** comfortable forward reach ~600 mm (max ~700). Keep **shelf depth 300–600 mm**. Design to the **5th-percentile female** reach so the shortest shoppers reach prime stock.

**Aisles / circulation:**
- One person: 600–750 mm min. Two passing / person+basket: 900–1100 mm.
- **Primary aisles: 1200–1800 mm.**
- **Wheelchair: 900 mm clear min, 1500 mm turning circle — this usually governs; design to it.**
- Min clear door opening **815–900 mm** for accessibility (so push clinic/BOH doors toward 900 where possible, not the bare 750 manual minimum).

**Counters:** service/sales counter 900–1100 mm high; checkout/cash-wrap 850–950 mm; **accessible segment at 760 mm with knee clearance**.

**Garment-style rails** (if used): double-hang high 1700–1800 / low 1050–1200; single-hang 1400–1500.

**Two governing principles:** design to **percentile extremes** (short reach, wide body), and treat **accessibility minimums as the binding constraint** (they're the most generous, so they win).

---

## 4. Wall merchandising rules  [MANUAL + FP]

- Both walls, full length, fixtures back-to-back-ish with a **mirror (≥300 mm) between every fixture**; use columns/returns as "mirror on site" (≥250 mm) where space is tight; corner boxing mirror ≥300.
- Wall fixture depth ~250 mm (CLens, JJ Super Hybrid, Looker, VC HD). 2400 tall.
- **Premium wall** front→back: LPL/Fossil (super-premium) → JJ-EYE → OD-EYE → JJ-SUN/Meller. **Value wall**: LK-Air → VC-Eye → Hooper → C-Lens (breaker). VC-SUN → central euro.
- Keep the **strike zone (900–1500)** stocked with the best margin lines per [ANTHRO].

---

## 5. Central island rules  [FP + MANUAL]

- **2× Euro Center back-to-back** on the centreline = the island core (min 1 euro is the manual floor; 2 is the efficient norm for tent-pole + sun).
- **55" screens back-to-back** on top (bottom of TV ≥1950 on euro; ≥2100 elsewhere). Facade 55" screens face the street.
- Greeter at the island's front tip (entry); Blue Zero just inside the entry.
- Free-standing mirrors near the island for try-on.
- Keep the island ~1000–1200 mm wide so both side aisles stay 1500–1900 mm.

---

## 6. Clinics  [MANUAL + FP]

- **Count by proto:** ≤₹12L → 2 (1 op RO + 1 non-op); ₹12–15L → 3 (1 reg + 1 RO op + 1 non-op); >₹15L → 4. All at the back band.
- **1 clinic must have sink + storage; 1 must have RO provision.** With MF/FF, ≥1 clinic on ground (the RO).
- Sizes: standard 1500×2400 (viewing 1800); compact MC5S 1350–1500×1800 (viewing 1000); RO 2500×1500 or 1500×2400.
- **[FP] Build from loose furniture in partitioned nooks**; enter from the long side; door/curtain ≥750 (push to ~900 for accessibility); keep a clear path to every clinic that does **not** pass behind the cash counter and does **not** clash with the toilet or another door. Chair faces the acuity chart along the long axis.

---

## 7. Pickup, BOH & services  [FP + MANUAL]

- **Pickup zone:** pickup counter/table + PICKUP STORAGE-900 + PC/keyboard station, in the back band.
- **BOH (behind a door):** Store room, customized **full-height storage**, **UPS rack**, **water dispenser**, **dining/QC/repair table** (1–3), staff rack. Pack along the back wall.
- **Reuse existing toilet** if present; else build to min size off a common passage (not through retail or behind cash).

---

## 8. Workflow for a NEW store  (step-by-step)

1. **Read the shell:** load base CAD, find the shell block & origin, set the local frame, locate glazing/entry/columns/existing toilet, measure width/depth, compute usable area (sqft). Note columns (use as mirrors).
2. **Pick proto tier** → number of clinics (2/3/4) and whether a pickup/dining is required.
3. **Lay the central spine** down the centreline: greeter → double euro + screens → billing/AR/lensometer pod.
4. **Run both walls full length**, brand-sequenced & front-loaded, mirror between each; VC-SUN on euro.
5. **Drop the partition line** ~60% back; behind it place clinics (nooks), pickup, store, storage, UPS, water dispenser; reuse existing toilet.
6. **Check anthropometry & accessibility:** strike-zone loading, shelf depth ≤600, aisles ≥1200 primary / 900 wheelchair, doors ≥900 where feasible, counter heights, 1500 turning circle near entry & billing.
7. **Run the clearance audit (below); iterate** until no flag.
8. Render a PNG (dark background) and a rear close-up; verify door swings, clinic access not behind cash, toilet door unobstructed.

---

## 9. Validation checklist + clearance audit

**Hard checks (script them):**
- Fixture count matches the agreed target (count INSERTs on the retail layers only; exclude mirrors/clinics/billing/BOH unless told otherwise).
- For every pair of fixtures, compute bbox gaps; **flag any primary-aisle gap < 1200, any secondary < 900, any door clear < 815**.
- Clinic doors: path to each does not pass behind the cash; no door swing overlaps another door or the toilet door.
- Toilet opening kept clear (no fixture within its access passage).
- All cut/zone polylines closed; file round-trips via `ezdxf.readfile`.

**Approval checklist [MANUAL p.29]:** fixture/merch requirement · number of clinics · seating (≥1 bench near billing/clinics) · mandatory equipment · BOH requirements · toilet.

---

## 10. Fixture catalogue (mm)  — ⚠️ SUPERSEDED, see §15 for the CURRENT library

The block names below were the *old* `FURNITURE BLOCKS.dxf` palette. **That file is retired.** The current, trimmed library is **`BASE LIBRARY.dxf`** and is the ONLY furniture source to use now — see **§15** for the authoritative block list and the clinic-arrangement catalog. (Old palette kept here only for historical reference; do not source blocks from it.)

Wall: `JJ SH 1200/900`, `CLENS 1200/900/600`, `LOOKER 900`, `VC HD 1010/1200` (digital), `MIRROR` (300×250). Depth ~250, H 2400.
Floor: `EURO 1040 x 1175` (use ×2 back-to-back), `Half Euro`, `NESTING TABLES`, `D-TABLE 900/1200/1500` (450 deep), `blu zero rack`.
Billing/engage: `Billing Counter 1800/2100` (Lensbar), `POS 900–1800`, `AR`, `LENSOMETER`, `GREETR 450×450`, `Pickup table PC`, `PICKUP STORAGE-900`.
Clinic: `CHAIR UNIT`, `DOCTOR STOOL`/`DR STOOL`, `CLINIC SCREEN`, `CLINIC - CABINET SINK`, `CLINIC - MOP CLOSET`, `TRIAL SET CABINET 633x500`, `MOROTISED TABLE-TRIAL SET 950x600`, `32INCH VC FOR CLINIC`.
Seating: `2 seater bench`, `3 seater Bench 1385`, `2/3 seater Sofa`.
BOH/toilet: `CABINET`, `Standing Table 700X600`, `WC`, `Wash Basin`, full-height storage, UPS rack, water dispenser.
Screens: `55INCH`, `49INCH` (facade + on euro).

---

## 11. What's already covered vs new

- **Already in `FURNITURE PLACEMENT RULES.md` [MANUAL]:** zoning gradient, wall brand sequence (base), CLens breakers, mirror cadence, euro≥1, discussion tables≥2, POS central, clinic counts & sizes, circulation minimums, BOH equipment list, toilet sizing, TV/signage, fixture dimensions, area statements, merch-mix logic.
- **New here:** all **[ANTHRO]** vertical-zone/reach/aisle/counter/accessibility rules; all **[FP]** efficiency rules — central double-euro spine, full-perimeter merchandising, super-premium-front brand loading, the 60/40 partition line + back band, clinics-as-loose-furniture-in-nooks, dedicated pickup zone, reuse-existing-toilet, billing-as-dispensing-pod, integrated VC-HD video walls, and the single-island→wide-aisle circulation principle.

---

## 12. EXPERT FIELD-LAYOUT LESSONS  ★★ (reverse-engineered from `BASE 2 FP.dxf`, a real expert-placed store on the SAME shell we designed for — READ THIS FIRST, IT SUPERSEDES EARLIER DENSITY GUIDANCE)

Tag: **[XP]** = learned from the expert field plan. Where these conflict with earlier sections, **[XP] wins** — the earlier rules under-used the floor. The expert plan fits **~2× the floor display** of our v1–v3 by refusing to waste aisle space. Measured on the identical 6800 × 12805 mm shell.

**The single biggest miss: we made aisles too wide and the back band too deep.** Correct the following:

1. **[XP] Aisles = the FUNCTIONAL MINIMUM, never generous.** Primary circulation in the expert plan is **1100–1200 mm — full stop.** We were leaving ~2300 mm "wide aisles for free"; that is wasted selling space. Design every shopping aisle to **1150–1200 mm** (wheelchair-OK) and convert the reclaimed width into more fixtures/euros. "Enough gaps to move" means 1100–1200, not 2000+.

2. **[XP] TWO euro rows, not one central island → 4 euros, not 2.** The expert runs **two euro blocks of 2-stacked euros each (4 euros total)**, one left-of-centre (x≈1600–2775) and one right-of-centre (x≈3975–5150), with a **1200 mm central aisle between them** and **~1150 mm aisles** to each side wall. So the floor reads as **three parallel aisles** (side / centre / side) framing two double-euro islands. This roughly doubles tentpole/collection floor display vs a single skinny spine. **55" screens mount back-to-back in the central aisle between the two euro blocks.**

3. **[XP] Push RETAIL to ~85–88% of the depth; squeeze BOH + clinics into the rear ~12–18%.** The expert "trade area" runs to **y≈10955 of 12555 (≈87%)**. Our 60/40 split gave away far too much to a giant back corridor. **Replace "60/40" with "≈85/15".** Wall merchandising and euros fill almost the whole plate; services are packed tight at the very back.

4. **[XP] Merchandise walls from the GLAZING LINE.** Wall fixtures start at **y≈300 (right at the shopfront)** and run continuously to the back partition — no empty front-wall segment. Premium wall here = **3× JJ SHD 1200 (JJ-EYE) → JJ-SUN → OD-EYE → C.LENS breaker → JJ-SUN**, value wall = **VC HD 1200 ×4 (VC-EYE / LK-AIR / HOOPER)**. Every fixture is brand-tagged on the drawing (TENTPOLE, HUSTLR, VC-SUN on the euros).

5. **[XP] Clinics as an L-SHAPE wrapping the back corner — share walls, open on the LOWER side.** Instead of two separate rectangular rooms + a dedicated corridor, the two clinics form **one L** in the back-right: a **vertical leg along the right wall** (Clinic-1 SINK, x≈5080–6550, y≈8555–10955) and a **horizontal leg along the back wall** (Clinic-2 RO, x≈4180–6580, y≈11055–12555). The **inside of the L is the shared corridor**, and each clinic **opens via a CURTAIN on its lower/corridor-facing side** (never the back). The L can be mirrored to either back corner depending on where services/toilet sit. This is the most space-efficient clinic arrangement — adopt it as the default for 2 clinics; avoid two free-standing boxes with a wide aisle between them.

6. **[XP] Clinic openings are CURTAINS (LK-CURTAIN), not hinged doors.** Cheaper, take zero swing space, and satisfy the "open on the lower side" rule. Keep the opening clear; the patient enters from the corridor side.

7. **[XP] FIRE EXTINGUISHERS are mandatory and were missing from our rules.** The expert places **3**, distributed: one in the front retail field, one mid-store near BOH, one at the back. Add ≥1 per ~40–50 m² on a column/wall, always on `F-FIRE EXTINGUISHER` layer.

8. **[XP] FOUR 55" screens, used in two roles.** **2 facade screens** at the glazing facing the street (QMS/marketing) + **2 back-to-back on the euro centre**. Don't ship a layout with a single screen.

9. **[XP] Greeter sits OFF-CENTRE toward the entry, never blocking the central aisle.** Expert greeter is to the **right of the entry door** (x≈4338–4788, y≈1795–2368), angled to face incoming customers — it does not sit on the centreline obstructing the euro spine.

10. **[XP] Distribute the dispensing functions; don't lump one big billing pod.** Expert uses a **smaller Billing Counter-1350 at the end of the central aisle** (y≈6774) and places the **AR station separately in the back-of-house** (back-left, near pickup) rather than welding billing+AR+lensometer into one block. Frees the rear-retail centre.

11. **[XP] Pack BOH into the back-left + centre, tight.** Expert back zone (x≈250–4080, y≈9705–12555) holds, densely: **AR station, PICKUP area (pickup table + PICKUP STORAGE-1200), FULL-HEIGHT STORAGE, DINING/QC table, UPS RACK, WATER DISPENSER**, plus the toilet — no blank floor. A single waiting **bench** sits just in front (x≈2708–4093, y≈9120–9605).

12. **[XP] Toilet: a PROPOSED ~1500-wide toilet in the back-left corner**, tiled, accessed off the BOH passage (not through retail, not behind cash). If the shell already has a usable toilet, reuse it; otherwise propose one here.

13. **[XP] Specify FLOOR FINISHES as zoning.** The expert tags finishes by zone: **tiles in clinics + toilet (wet/clinical), fluted panel on the cash-back wall, carpet/painted floor in retail/BOH**. Carry a finish layer even in a planning DXF — it communicates zoning and is part of "expert-grade."

**Net effect of [XP]:** narrow (1150–1200) triple-aisle floor + two double-euro rows + glazing-to-back wall merchandising + an L-clinic squeezed into one back corner + tightly packed BOH = **maximum facings with legal circulation**. This is the target standard. When in doubt, **add product and tighten the aisle to 1150**, don't widen it.

### One-line build recipe (optimal in one pass)
Walls glazing→back, both sides, brand-tagged, mirrors interleaved → **two double-euro blocks** flanking a **1200 central aisle**, **2 screens back-to-back** between them + **2 facade screens** → side aisles **1150** → greeter off-centre at entry → Billing-1350 at central-aisle end, AR in BOH → **retail to ~87% depth** → **L-clinic** (curtains, open on lower side) in one back corner → BOH (pickup/storage/UPS/water/QC) + **toilet** packed in the other back corner → **3 fire extinguishers** → finishes tagged. Audit aisles to **≥1100 (target 1150–1200)**, not ≥1200-and-wider.

---

## 13. CLIENT / ITERATION FEEDBACK RULES  [FB] (learned directly from review of our v1→v3 drafts — apply these on every store)

These came from explicit client direction while iterating, not from the manual or the expert file. They are firm requirements:

1. **[FB] Euro Centers are turned 90° and JOINED into solid blocks.** Don't leave euros at their default rotation, and don't separate them — orient and butt them so each block reads as one island (e.g. two euros back-to-back = a 1175 × 2080 block; or a 2×2). **Never pad a euro with a lone half-euro** — drop it entirely if not needed.

   **[FB] Join euros NON-DRAWER side to NON-DRAWER side — never drawer-to-drawer.** The `EURO 1040 x 1175` block carries its drawer banks on the two **1040-wide faces** (the short ±y faces in the block's local frame); the **left/right (±x) faces are the clean non-drawer sides.** Join euros along those non-drawer faces — **side-by-side in x**, giving a 2080 × 1175 double block — so the drawers stay exposed and accessible along the long edges. **Never butt them drawer-face to drawer-face** (i.e. don't stack along the 1040/drawer edge); that buries the drawers and is wrong. Verify drawer faces are exposed before finalising.

   **[FB] Fill open retail floor with EUROS, not nesting tables.** Euros are the hero tent-pole/collection display. Don't pad the fixture count with nesting tables — add more correctly-joined euro blocks instead. Nesting tables are accessories, not a euro substitute.

2. **[FB] Fixture targets are MINIMUMS, never caps.** If the client says "15 fixtures," treat 15 as the floor and add as many more as fit cleanly while respecting aisles. More product is the goal.

3. **[FB] The greeter must FACE the main door and sit in FRONT of the euro island — and must NOT obstruct the doorway or door swing.** Combine with [XP] rule 9 (off-centre toward the entry): greeter is forward, off the centreline, oriented to face incoming customers, clear of the entry-door swing arc.

4. **[FB] Blue Zero goes against the FRONT GLAZING, right-hand side** (unless directed otherwise).

5. **[FB] NO discussion tables.** Removed by the client; euros + billing replace them. (Overrides the manual's old "min 2 discussion tables.")

6. **[FB] Clinic entry is on the LONG side AND the access must be genuinely clear** — never trap a clinic door behind a narrow/blocked slot. The opening (curtain) faces the corridor on the clinic's lower/long side, with a real ≥1100–1200 mm corridor leading to it. Verify in the audit that you can actually walk to every clinic door.

7. **[FB] The back-of-house must be SPACE-EFFICIENT — no large blank/dead corridor.** Don't leave a wide empty void between clinics on one wall and services on the other. Shrink circulation to the functional minimum and pack the freed area with storage/BOH/clinic. Every back-zone square metre should do a job. (This is the failure mode of our v1–v2; the fix is the tight corridor + densely packed blocks of v3 and the [XP] back-corner packing.)

8. **[FB] Clinics may be L-shaped, and the L can face EITHER back corner** (mirror it to suit where the toilet/services sit). The L always opens on its lower/corridor side. Pick the orientation that packs the back tightest for the given shell.

**Precedence:** where rules conflict, **[FB] (client) ≥ [XP] (expert field plan) > [ANTHRO] > [MANUAL]**. Always design to the strictest applicable accessibility minimum regardless of source.

---

## 14. EXPERT LEARNINGS from `BASE 3 FP.dxf`  ★★ [XP3] (reverse-engineered from the expert layout on the BASE 3 shell — measured in the local A-WALL-min frame)

These refine/extend the earlier sections with what the expert actually did on a large, irregular, column-heavy shell. **[XP3] wins over earlier density guidance where they conflict.**

1. **[XP3] Merchandise the walls DENSELY and CONTINUOUSLY — this is where the count comes from.** The expert ran **8 fixtures along the south wall** (continuous, x367→8767) + **6 VC HD on the north wall** + a CLENS on the west (entry) wall + **1 VC HD on the shaft face** ≈ **16–18 wall fixtures**. Walls are the cheapest, highest-capacity display — fill them end to end before reaching for floor fixtures. Don't split a long wall into two short runs with a big empty gap (an earlier mistake); run it continuously, packed fixture-after-fixture.

2. **[XP3] Mirror cadence ≈ every 2–3 fixtures, not every fixture.** The expert used ~6 mirrors across ~14 wall fixtures. A mirror after every single fixture wastes wall length; interleave one every 2–3 units (still ≥1 between any pair of unlike categories / per the manual minimum).

3. **[XP3] ABSORB columns into the fixture line; never leave dead space around them, never overlap them.** (a) Run wall fixtures straight **past/over a low column footprint** when the fixture is clear in the perpendicular axis — e.g. south fixtures at y560+ run over the bottom column whose footprint is y230–580. (b) **Stop a wall run exactly at a column face** (north VC HD ends at the column, x≈6737). (c) A euro/floor fixture may **butt against a column face** (touching, e.g. a euro just south of the mid-hall column) but must not overlap it. **Extract EVERY column — including free-standing mid-floor columns and the `beam` layer — and audit against all of them.**

4. **[XP3] Use the SHAFT / structural faces as display surfaces.** The expert mounted a `VC HD 1010` on the **west face of the shaft** (digital merchandising) — turning an obstruction into a fixture. Look for usable column/shaft faces.

5. **[XP3] Euros: rotate 90° (drawers facing E/W), ~3 euros, a stacked pair + a single, placed clear of / butting the columns.** (Joining is still non-drawer-to-non-drawer per §13.1 — after r90 the non-drawer faces are the ±y edges, so a y-stacked pair is correct.) Keep euros out of the mid-hall column footprint.

6. **[XP3] Distribute the engage/dispensing functions:** **Billing Counter rotated (r90) in the centre-east** facing the floor, **AR as a separate station just south of billing**, **pickup (table + PC + keyboard) over by the SINK clinic** — not one lumped billing+AR+lensometer pod.

7. **[XP3] Clinics stacked along the EAST/back wall, clear of the toilet.** Expert placed the **SINK clinic in the lower-right** (y≈284–2630) and the **RO clinic in the mid-right** (y≈4555–6181), both against the east wall and opening WEST (long side) onto the retail/centre-east floor. The **existing toilet stays in its own upper-right corner**, and **BOH packs into the upper-right wing around the toilet** — so clinics never clash with the WC or its door. Prefer this east-wall-stack over cramming clinics up against the toilet.

8. **[XP3] Bench in open waiting space.** Expert bench sits in the open north-centre (x≈8315–9700, y≈5273–5758) near the billing/clinic zone — not pinched against a euro. Leave full walk-around clearance around islands.

9. **[XP3] Expert display count on this shell ≈ 22** (18 wall + 3 euro + 1 blue zero). On a large plate, ~19 is a floor, not a ceiling — dense walls get you there comfortably without nesting-table filler.

---

## 15. CURRENT BLOCK LIBRARY + CLINIC ARRANGEMENT CATALOG  ★★ [FB] (authoritative — 2026-06-19; supersedes all earlier library references)

### 15.1 Use ONLY the new trimmed library
- **The one and only furniture source is `BASE LIBRARY.dxf`.** Do **NOT** use the old `FURNITURE BLOCKS.dxf` / `FURNITURE BLOCKS CLINIC 1/2.dxf` ever again — they are retired. Import blocks from `BASE LIBRARY.dxf` only.
- The library was deliberately **cut down to the useful blocks (62)**. Blocks that were **REMOVED — do not use / do not expect them:** `LOOKER 900`, `NESTING TABLES`, `D-TABLE` (discussion tables), sofas, `POS 900–1800`, generic `CABINET`, `PICK UP COUNTER`, and the **`55INCH`/`49INCH`/`43INCH` TV blocks**.
- **Available wall display:** `JJ SH 1200/900`, `JJ SHD 1010/1200/900`, `JJ STSH 1200/900`, `CLENS 1200/900/600`, `VC HD 1010`, `LENS SELECTION-1500x450`, `MIRROR` (300×250), `MIRROR SEE THROUGH/FREE STANDING`.
- **Floor display:** `EURO 1040 x 1175`, `HALF EURO 1040` / `HALF EURO WITH SHELVES 1040` / `Half Euro center`, `AWEC 1500`, `AWOEC 1200`, `blu zero rack details`.
- **Billing/engage:** `Billing Counter 900/1350/1800/2100`, `AR`, `LENSOMETER`, `GREETR 450x450` / `Greetr-1200x600`, `Pickup table PC`, `KEYBOARD`, `I-PAD Frame`, `Standing Table 700X600`.
- **Clinic furniture (loose):** `CHAIR UNIT`, `DOCTOR STOOL`/`DR STOOL`, `Stool`, `CLINIC SCREEN`, `CLINIC - CABINET SINK`, `CLINIC - MOP CLOSET`, `TRIAL SET CABINET 633x500`, `TRIAL SET ROC`, `MOROTISED TABLE-TRIAL SET 950x600`, `MINGSING`, `PHOROPTER`, `32INCH VC FOR CLINIC`, `MIC`.
- **Seating:** `2 seater bench`, `3 seater Bench 1385`. **Toilet/BOH:** `WC`, `Wash Basin`, `Urinal`, `Standing Table 700X600`.
- **Substitutions for removed blocks:** TV screens → draw a rectangle on layer **`LK-TV SCREEN`** (no TV block exists now); BOH storage/staff/UPS racks → draw rectangles on `LK-FURNITURE`/`LENS-PARTITION` and label, or use `Standing Table 700X600`; pickup counter → `Pickup table PC` + a labelled rectangle.

### 15.2 Clinics: use the PRE-MADE ROOM BLOCKS, never invent furniture layout
Two complete clinic-room blocks are provided (import from the clinic library files). Place these **whole rooms**; do not hand-arrange clinic furniture.
- **SINK clinic room** = block `A$C15b5f610`, footprint **2600 × 1700**. Contains: cabinet-sink, mop closet, clinic screen, trial-set cabinet, chair unit, doctor stool. (This is the "1 clinic must have sink+storage" room.)
- **RO clinic room** = block `A$Cc304dd19`, footprint **2600 × 1700** (it carries a stray `DIMENSION` entity — ignore it / exclude it when bbox-aligning). Contains: phoropter, Mingsing, motorised trial table, trial-set ROC, 32" VC, mic, 2 stools. (This is the "1 clinic must have RO" room.)
- Source files: **`2 CLINIC LIBRARY.dxf`** and **`3 CLINIC LIBRARY.dxf`** (also hold these blocks).

### 15.3 [FB] Use the CANONICAL clinic arrangements directly — do not invent clinic positions
The two/three clinic rooms must be placed in **one of the pre-defined relative arrangements below** (taken from `2/3 CLINIC LIBRARY.dxf`). Pick whichever fits the back zone; only invent a custom arrangement if **none** of these physically fit. Each room opens (curtain) on a **long side**; orient the chosen arrangement so those openings face a clear corridor/floor and stay clear of the toilet door. Reference images: `CLINIC ARRANGEMENTS - 2 clinic.png` / `- 3 clinic.png`.

**TWO-clinic arrangements (1 SINK + 1 RO):**
- **2A — Twin landscape, side-by-side.** Both rooms rot0 (2600 W × 1700 deep), butted on the shared vertical wall, both opening on the **long bottom (south) side**. Combined ≈ **5200 × 1700**. Best for a **wide, shallow** back band.
- **2B — L-shape.** SINK rot0 landscape (2600×1700) + RO rot270 portrait (1700×2600) tucked to its right and dropping down → wraps a corner. Combined ≈ **4300 × 2600**. SINK opens bottom, RO opens toward the inner corner.
- **2C — Twin portrait + central 750 corridor.** SINK rot90 (1700×2600) + RO rot270 (1700×2600) side-by-side with a **750 mm corridor between them**; the two rooms open **toward each other** into that corridor. Combined ≈ **4150 × 2600**. Best for a **narrow, deep** back band.

**THREE-clinic arrangements (mix of SINK + RO rooms):**
- **3A — Triple landscape row.** SINK + SINK + RO, all rot0 landscape, in a row, all opening on the long bottom side. Combined ≈ **7800 × 1700**. For a wide, shallow back.
- **3B — Portrait–landscape–portrait cluster.** RO rot90 (portrait) + SINK rot0 (landscape) + RO rot270 (portrait); the two portrait ROs flank the central landscape SINK with **750 mm corridors**. Combined ≈ **5800 × 2600**.
- **3C — Mixed row.** RO rot90 (portrait) + SINK rot0 (landscape) + RO rot0 (landscape), with a 750 corridor. Combined ≈ **6700 × 2600**.

**Rule of thumb for choosing:** wide+shallow back → the all-landscape rows (2A / 3A); deep back or corner → the portrait/L/cluster options (2B, 2C / 3B, 3C). Mirror/rotate the whole chosen arrangement to suit which corner the toilet/BOH occupy, but keep the internal relative configuration intact. **[OPT] Among the combos that fit, TRY the L-shape (2B) first — it is usually the most space-efficient (shares a wall, no dedicated corridor) and avoids the "two disjoint rooms" feel of 2C; only fall back to 2A/2C if the L doesn't fit or the toilet/BOH corner forces it. See §16.1.**

---

## 16. OPTIONAL DESIGN VARIATIONS — try & A/B-compare  ★ [OPT] (from `BASE CAD WITH FP` expert plan vs our 2-clinic/15-fixture draft, 2026-06-19)

**Framing — these are NOT new hard rules.** They are alternative moves the expert field plan used that *often (not always)* improve a design. When a layout is already rule-complete, **generate the variant, audit + eyeball it against the base, and keep whichever is genuinely better for the specific shell.** Treat this as a menu to explore — especially on constrained / narrow plates — not as constraints. None of these override the hard rules (no column/beam overlap, canonical clinic blocks, euro non-drawer joining, reuse toilet, ≥3 fire extinguishers, etc.).

1. **[OPT] Try the L-shape clinic (2B) BEFORE settling on disjoint twin rooms (2C).** The L wraps one back corner (SINK leg along a side wall + RO leg along the back wall, sharing the inner corner as the corridor) and is **usually more space-efficient than two separate boxes** — it shares a wall, needs no dedicated central corridor, and conforms to an irregular back. 2C (twin portrait + 750 corridor) reads as two *disjoint* rooms and tends to waste its corridor on a narrow plate. **Selection order among the canonical combos that physically fit: try 2B (L) first; fall back to 2A (wide+shallow) or 2C only if the L doesn't fit or the toilet/BOH corner forces it.** The expert `BASE CAD WITH FP` plan effectively used a corner-wrapped two-clinic cluster — closest to the L. Mirror the L to whichever back corner leaves the toilet approach + BOH clear.

2. **[OPT] Wall-heavy density distribution — hit the count with MORE WALL, fewer floor islands.** The expert reached 15 display with **12 wall + 2 euro + 1 blue zero**, vs our **10 wall + 4 euro + 1 blue zero**. Walls are the cheapest, highest-capacity display, so when a count target must be met, first try **maxing wall fixtures** (narrower **900-wide** units packed continuously from the glazing line, mirrors every 2–3) and keep the spine slim. Compare against the euro-heavy version and keep the one with the better aisles + facings.

3. **[OPT] Slim central euro spine option (narrow plates <~6 m wide).** 2 euros **rotated 90° and stacked** along the centreline (drawers facing the side aisles; non-drawer ±y faces joined) → a **1175-wide island giving ~1900 mm side aisles**, vs a 2080-wide side-by-side block giving ~1450 aisles. On a narrow shell, try the slim stacked spine + dense walls; on a wider shell the fat block / two euro rows may win. Put **VC-SUN on the rear euro** (TENTPOLE / HUSTLR on the front euro).

4. **[OPT] Super-premium front-loading on the premium wall (easy to forget — verify every time).** Lead the premium wall *at the glazing* with **super-premium (LPL → FOSSIL / branded)**, THEN JJ-EYE → OD-EYE → MELLER / JJ-SUN → C-LENS breaker. Don't open the wall with JJ-EYE. (Restates §1.4/§4 — but the draft missed it, so call it out and check it.)

5. **[OPT] Richer, explicitly-zoned BOH.** When space allows, spell out the full back-of-house wing wrapping the toilet: a dedicated **PICKUP AREA** (pickup table + PICKUP STORAGE-900 + PC/keyboard), **CUSTOMIZED FULL-HEIGHT STORAGE**, a **STORE** nook, **DINING / QC TABLE**, **WATER DISPENSER**, **UPS RACK** — each labelled — rather than a few generic rectangles.

6. **[OPT] Billing as a prominent central pod.** A larger **Billing Counter 1800 centred at mid-depth with AR right beside it** can read better than a compact 1350 + AR-in-BOH. Both valid — try the central 1800+AR pod and compare. (Alternative to §12.10's distribute-the-functions guidance; pick per shell.)

7. **[OPT] Two benches.** A **facade/entry bench** PLUS a waiting bench near billing/clinics (brand minimum is 1; the expert used 2). Add the facade bench if there's room.

**How to use this section:** when the ask is for the *best* layout (not merely a compliant one), build the base layout, then spin the relevant [OPT] variants — **especially the L-clinic (#1) and the wall-heavy / slim-spine pair (#2–3)** — audit each, and present/keep the strongest.

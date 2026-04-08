# Worked Example: IRT/ELO Agent Context Document

This is a reference example of what File 3 (Agent Context Document) looks like when generated alongside the IRT/ELO handoff. Use it as a template and quality bar.

---

# Agent Context: IRT Algorithm Validation
*Generated March 2026 — load this into your Claude session before starting work*

## Project Telos

Validate whether IRT 1PL (Rasch model) can replace ChalkTalk's current skill-level system for predicting student exam performance. A +0.585 improvement in Pearson r has been demonstrated in exploratory analysis. Engineering needs to verify the numbers independently before scoping Phase 1.

## Current State

Exploratory analysis is complete. Four scripts exist and produce results end-to-end against the local DB:
- Data export, ELO simulation, IRT simulation, and comparison report all run successfully
- 63 districts with sufficient data have been evaluated (out of 370 total)
- Aggregate Pearson r values: IRT 1PL = 0.834, IRT 2PL = 0.815, ELO = 0.808, Current = 0.249

No production code has been written. This is validation-only.

## Key Decisions and Rationale

- **Decision:** Used logit(proportion_wrong) for IRT difficulty estimation instead of joint EM estimation
  **Why:** Sparse response matrix (~7% density) caused the `girth` library to fail during joint estimation
  **Alternative considered:** Joint EM via girth — abandoned after repeated convergence failures on real data

- **Decision:** Included all 370 districts without filtering, then excluded those with insufficient data from r calculations
  **Why:** Avoids cherry-picking. The 63-district subset is determined by data availability, not researcher choice
  **Alternative considered:** Pre-filtering to "active" districts — rejected because the definition of "active" would introduce subjectivity

- **Decision:** Used created timestamp for temporal ordering in ELO updates
  **Why:** Practice session responses need ordering for ELO math; created timestamp is the most reliable field available
  **Alternative considered:** session start time — not consistently populated

## Evidence vs. Assumptions

| # | Claim | Status | Evidence/Source |
|---|---|---|---|
| 1 | IRT 1PL achieves r = 0.834 aggregate | Verified | Output of `python3 elo_compare.py` against local DB |
| 2 | Current system achieves r = 0.249 | Verified | Same comparison script, same dataset |
| 3 | Practice session responses are independent | Assumed | Required for ELO math; temporal ordering partially mitigates |
| 4 | logit(proportion_wrong) approximates true IRT difficulty | Partially verified | This is classical test theory, not textbook IRT. The r = 0.834 is likely a lower bound |
| 5 | Results generalize beyond these 63 districts | Assumed | No filtering was applied, but districts with sparse data were excluded from r |

## Known Risks

| Risk | Impact | Likelihood | Detection |
|---|---|---|---|
| Local DB snapshot is stale | Med | Med | Compare row counts against production; check `helper db_download` last-run date |
| IRT difficulty approximation underestimates true model performance | Low | High | This makes the claim conservative, not inflated — not a risk to validity |
| Cannot validate against official TSIA2 scores due to anonymized emails | High | Confirmed | Blocking Phase 1 scoping. Eagle Mountain-Saginaw and Laredo ISD files exist but can't be matched |

## Domain Knowledge

- **Hattie effect size thresholds:** In education research, Pearson r > 0.7 is "Exceptional," 0.5-0.7 is "Strong," < 0.3 is "Weak." The current system's r = 0.249 is below the weak threshold. This isn't an arbitrary benchmark — Hattie (2009) is the standard reference.
- **Response matrix density:** ChalkTalk's data is ~7% dense (most students answer a small fraction of total questions). This is normal for adaptive learning platforms but breaks many standard IRT estimation libraries that expect denser matrices.
- **"Skill level" in ChalkTalk:** The current system assigns students a skill level (1-5) per topic based on practice session performance. This is what IRT would replace. The skill level is rule-based, not statistically estimated.

## File Map

- `export_data.sh` — Exports student response data from local postgres to CSV
- `elo_simulation.py` — Runs ELO rating simulation across 347M response updates
- `irt_simulation.py` — Runs IRT 1PL and 2PL parameter estimation and scoring
- `elo_compare.py` — Generates per-district Pearson r comparison table across all models

All files in: `/Users/mohannadarbaji/Desktop/Claude Code/Question Migration`

## Reproduction Quick-Start

```bash
cd "/Users/mohannadarbaji/Desktop/Claude Code/Question Migration"

# Prerequisites: local Docker postgres (container: postgres, db: chalktalk), Python 3 + scipy/numpy/pandas

bash export_data.sh          # ~10 min
python3 elo_simulation.py    # ~20 min, 347M updates
python3 irt_simulation.py    # ~15 min
python3 elo_compare.py       # <1 min — produces the comparison table
```

Expected output from final step: table with aggregate averages IRT 1PL = 0.834, IRT 2PL = 0.815, ELO = 0.808, Current = 0.249.

## The Task

Run `python3 elo_compare.py` and confirm the aggregate Pearson r values match: IRT 1PL = 0.834, IRT 2PL = 0.815, ELO = 0.808, Current = 0.249.

**Success:** Numbers match within rounding tolerance (0.01).
**Failure:** Flag which districts diverge — do not attempt to debug the algorithm.
**Out of scope:** Code review, algorithm changes, production architecture. This is verification only.

# Worked Example: IRT/ELO Algorithm Validation Handoff

This is a reference example of what the Technical Handoff Writer skill produces when applied to a real project. Use it as a template and quality bar.

---

# IRT Algorithm Validation — Engineering Handoff
*March 2026 | Author: Mo | Status: Awaiting verification*

## The Claim

IRT 1PL (Rasch model) predicts student performance on ChalkTalk's internal exam scores with an average Pearson r of 0.834 across 63 districts and 119,525 students — compared to r = 0.249 for ChalkTalk's current skill level system. This is a +0.585 improvement, placing IRT 1PL in the "Exceptional" range by education research standards (Hattie, 2009). ELO achieves r = 0.808. The current system is classified as "Weak."

## How to Reproduce

**Prerequisites:** local Docker postgres container named `postgres`, database `chalktalk`, Python 3 with scipy/numpy/pandas installed.

```bash
# Step 1: Export data (~10 min)
bash export_data.sh

# Step 2: Run ELO simulation (~20 min, 347M updates)
python3 elo_simulation.py

# Step 3: Run IRT simulation (~15 min)
python3 irt_simulation.py

# Step 4: Generate comparison report (<1 min)
python3 elo_compare.py
```

**Expected output from step 4:** a table showing Pearson r per district. The aggregate averages should be: IRT 1PL = 0.834, IRT 2PL = 0.815, ELO = 0.808, Current = 0.249.

**Estimated total time:** ~45 minutes.

**Working directory:** `/Users/mohannadarbaji/Desktop/Claude Code/Question Migration`

## Assumptions and Limitations

```
Assumption: Practice session responses are independent
Why: Simplification required for ELO update math
Risk: Low — temporal ordering is respected via created timestamp

Assumption: IRT 1PL difficulty estimated as logit(proportion_wrong) rather than
            joint EM estimation
Why: Sparse response matrix (~7% density) caused girth library to fail
Risk: Moderate — this is classical test theory, not textbook IRT. True joint
      estimation would likely push r higher. Current r = 0.834 is a lower bound.

Assumption: All districts in the DB are included (370 total, 63 had sufficient
            data for validation)
Why: No filtering applied beyond minimum sample size threshold
Risk: Low — districts with insufficient data are excluded from r calculations

Known blocker: Cannot yet validate against official TSIA2 scores. Files exist for
               Eagle Mountain-Saginaw ISD and Laredo ISD but student emails are
               anonymized in the local DB dump, preventing matching.
```

## What I Need From You

**What I need:** Run `python3 elo_compare.py` and confirm the aggregate Pearson r values match the table above. That's it — no need to review the code or validate the math yet.

**If the numbers match:** we take this to the team as Phase 0 complete and scope Phase 1 (de-anonymizing the DB to validate against real TSIA2 scores).

**If the numbers don't match:** flag which districts are off and we'll debug together.

**Estimated time:** ~45 minutes to reproduce + 5 minutes to check the output table.

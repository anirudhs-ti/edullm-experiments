# Experiment: Brute-Force Validation (October 2025)

**Purpose:** Validate the original curriculum mapping experiment by exhaustively checking all sequences

**Date:** October 27, 2025  
**Status:** ✅ Complete

---

## The Finding

**60% false negative rate** - The original experiment missed FAIR matches in 3 of 5 sampled substandards because Phase 1 didn't select the right skills.

---

## Key Results

- **Sampled:** 5 of 63 substandards with "no matches" (seed=42)
- **False negatives:** 3 (60%) - missed FAIR matches in Problem Solving & Data Analysis skills
- **True negatives:** 2 (40%) - confirmed no matches exist
- **Impact:** Original coverage likely ~78% not ~44% (+34 points)

---

## Root Cause

Phase 1 skill selection is too narrow:
- Only checks 1-2 skills based on keywords
- Misses "Problem Solving" (has word problems) and "Data Analysis" (has graphs/plots)
- Wrong skill → sequences never evaluated → false negative

---

## Recommendation

**Use pure brute-force** - skip Phase 1, check all sequences:
- Cost: ~$10 for all 63 substandards, 40 minutes
- Accuracy: 100% recall vs 40% in original
- Actually FASTER: 24s vs 60s per substandard

---

## Files

- **`VALIDATION_SUMMARY.md`** - One-page summary
- **`bruteforce_rechecks.json`** - All 190 ratings
- **`bruteforce_rechecks_summary.json`** - Statistics
- **`bruteforce_rechecks_report.md`** - Findings
- **`bruteforce_validation.py`** - Script to extend validation
- **`bruteforce_validation.log`** - Processing logs

---

## To Extend Validation

```python
# In bruteforce_validation.py, line ~64:
NUM_SAMPLES = 63  # Validate all "no match" substandards

# Then run:
python bruteforce_validation.py
```

**Time:** ~40 minutes  
**Cost:** ~$10

---

**Bottom line:** Phase 1 skill selection has major recall issues. Use brute-force instead.


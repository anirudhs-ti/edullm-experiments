# Brute-Force Validation Summary

**Date:** October 27, 2025  
**Status:** ✅ Complete

---

## The Finding

**60% false negative rate** - 3 of 5 substandards marked "no matches" actually have FAIR matches.

---

## What Was Missed

### Case 1: "Solve real-world multiplication problems"
- **Original:** Checked "Multiplication" skill only → no matches
- **Validation:** Found 3 FAIR matches in "Problem Solving" skill
- **Why missed:** Word problems are in Problem Solving, not Multiplication

### Case 2: "Generate measurement data using rulers"  
- **Original:** Checked "Measurement" skill only → no matches
- **Validation:** Found 1 FAIR match in "Data Analysis" skill (line plots)
- **Why missed:** Line plot sequences are in Data Analysis, not Measurement

### Case 3: "Solve two-step word problems"
- **Original:** Checked "Problem Solving" skill only → no matches
- **Validation:** Found 1 FAIR match in "Data Analysis" skill (graph problems)
- **Why missed:** Graph-based problems are in Data Analysis, not Problem Solving

---

## Root Cause

**Phase 1 skill selection creates a bottleneck:**
```
Substandard → Select 1-2 skills → Only check those skills → Miss sequences in other skills
```

Phase 1 has 0% accuracy in finding ALL relevant skills.

---

## Impact

**Original claim:** 63 of 112 substandards (56%) have no matches  
**Likely reality:** ~25 of 112 (22%) truly have no matches  
**Coverage:** Probably ~78% not ~44% (+34 points)

---

## Recommendations

### For This Experiment
Run full validation on all 63 substandards (~40 min, ~$10) to get exact numbers.

### For Future Work
**Use pure brute-force** - skip Phase 1, check all sequences directly:
- Cost: ~1.5x more
- Time: Actually FASTER (24s vs 60s per substandard)
- Accuracy: 100% recall vs 40%

---

## Files

- **`output/bruteforce_rechecks.json`** - All 190 ratings
- **`output/bruteforce_rechecks_summary.json`** - Statistics  
- **`output/bruteforce_rechecks_report.md`** - Readable findings
- **`bruteforce_validation.py`** - Script to reproduce/extend
- **`bruteforce_validation.log`** - Processing logs

---

## Bottom Line

Your experiment methodology has a systematic blind spot that causes false negatives. The DI curriculum probably covers MORE standards than reported. Easy fix: eliminate Phase 1 skill selection.


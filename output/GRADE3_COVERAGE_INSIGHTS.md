# Grade 3 Coverage Insights

**Generated:** October 27, 2025  
**Source:** `substandard_to_sequence_mappings.v3.json`

---

## Bottom Line

**47.3% of Grade 3 CCSS standards** have good alignment with DI curriculum (53/112 substandards).

---

## Key Numbers

| Metric | Count | % |
|--------|-------|---|
| **Substandards with matches** | 53 | 47.3% |
| **No matches** | 59 | 52.7% |
| **EXCELLENT sequence matches** | 34 | - |
| **FAIR sequence matches** | 64 | - |
| **Total sequence matches** | 98 | - |

---

## What Changed from Original

| Version | Coverage | EXCELLENT | FAIR | Total Matches |
|---------|----------|-----------|------|---------------|
| **Original** | 23/112 (20.5%) | 28 | 0 | 28 |
| **v3 (All Grade 3)** | 53/112 (47.3%) | 34 | 64 | 98 |
| **Gain** | **+30 subs (+26.8 pts)** | +6 | +64 | +70 |

### Why the Jump?

1. **Included FAIR matches** (original only kept EXCELLENT)
2. **Brute-force across all skills** (original Phase 1 missed Problem Solving, Data Analysis)
3. **Used CSV assessment boundaries** (more accurate constraints)

---

## Match Quality Distribution

**53 substandards with matches:**
- 15 have ≥1 EXCELLENT match only
- 28 have FAIR matches only  
- 10 have both EXCELLENT and FAIR

**Common patterns:**
- `E=1 F=0`: 15 substandards (single perfect match)
- `E=0 F=1`: 18 substandards (single partial match)
- `E=2 F=3`: 2 substandards (multiple strong + partial)

---

## Skills Contributing Matches

| Skill | EXCELLENT | FAIR | Total |
|-------|-----------|------|-------|
| **Multiplication** | 11 | 18 | 29 |
| **Problem Solving** | 8 | 21 | 29 |
| **Division** | 7 | 8 | 15 |
| **Data Analysis** | 3 | 3 | 6 |
| **Geometry** | 3 | 6 | 9 |
| **Fractions** | 2 | 5 | 7 |
| **Measurement** | 0 | 3 | 3 |

**Insight**: Problem Solving (word problems) is critical but was often missed by Phase 1.

---

## Gap Analysis: 59 Substandards with No Matches

### Common patterns in unmatchable standards:

**1. Specific pedagogical methods** (21 standards)
- "using number lines"
- "using place value blocks"
- "by tiling"
- "using tables where the question asks for the rule"

**2. Properties of operations** (4 standards)
- Commutative, associative, distributive properties
- "Identify the properties of multiplication"

**3. Pattern creation/identification** (6 standards)
- "Given a rule, create numbers in a pattern"
- "Identify the rule for a [operation] pattern"

**4. Highly specific question formats** (12 standards)
- "Questions should say: 'Complete the multiplication sentence that describes the array'"
- "Must ask: 'What is ___ rounded to the nearest ___?'"
- Exact question stem requirements

**5. Time-related** (3 standards)
- Elapsed time, start/end time problems
- "Write the time shown on the clock"

**6. Ultra-specific constraints** (13 standards)
- "Factors limited to 2, 3, 4, 5, and 10 only"
- "One factor must be 5 or 10"
- "Never ask for the end product"
- "Problems with one unknown per equation"

---

## Actionable Insights

### For Curriculum Use
✅ **Use the 15 EXCELLENT-only substandards** with confidence  
⚠️ **Review the 28 FAIR-only substandards** - usable but need adaptation  
✅ **The 10 mixed (E+F) substandards** have both strong and supplementary options  

### For Curriculum Development
The 59 "no match" substandards fall into **6 clear buckets** above. Consider:
1. Developing sequences for **time-related standards** (high-value, low count)
2. Adding **pattern/rule sequences** (6 standards, reusable across grades)
3. Creating **property-focused sequences** (commutative, etc.)

### Quality Threshold Guidance
- **Alignment score ≥90**: Strong, use with confidence (18 matches)
- **Alignment score 75-89**: Good, minor gaps (25 matches)
- **Alignment score 60-74**: Fair, needs review (55 matches)

28 matches scored <70 but made top 5 due to lack of alternatives.

---

## Comparison to Original Experiment Claims

| Claim | Original | After Brute-Force | Reality |
|-------|----------|-------------------|---------|
| Coverage | "56% have no matches" | "53% have no matches" | Close! |
| False negatives | "~60% based on sample" | "+30 found from 112" | ~27% actual |
| Coverage % | "Likely ~78%" | 47.3% | Over-optimistic |

**Conclusion**: The validation experiment's 60% flip rate was sampling bias. True improvement is 20.5% → 47.3%.

---

## Files

- **`substandard_to_sequence_mappings.v3.json`** - Complete Grade 3 mappings
- **`bruteforce_remap_report_all_grade3.md`** - Full list of matches
- **`generate_all_grade3_mappings.py`** - Script (reusable)
- **`GRADE3_COVERAGE_INSIGHTS.md`** - This file


# Quick Start: Format-Augmented Mappings Viewer

## 🚀 View the Results

1. **Open the viewer**:
   ```bash
   # Open mappings_viewer.html in your browser
   # Or start a local server:
   python3 -m http.server 8000
   # Then visit: http://localhost:8000/mappings_viewer.html
   ```

2. **Browse substandards**:
   - Use the search box to find specific substandards
   - Green indicator = has excellent matches
   - Red indicator = no excellent matches
   - Click any substandard to see details

3. **View format information**:
   - **Top section**: Green box shows excellent matches with their formats
   - **Rating cards**: Each sequence shows related formats (if available)
   - **Format details**: Includes format number, title, and part count

## 📋 What You'll See

### For Each Substandard

#### Excellent Matches Summary (Top)
```
✓ Excellent Matches Found (2)

[Multiplication (Grade 3) - Sequence 1]
📚 Related Formats:
  Format 9.1 - SINGLE DIGIT MULTIPLICATION
```

#### Sequence Ratings (Below)
```
[Sequence 1] One digit times one digit [EXCELLENT]

Explanation: This sequence perfectly aligns...

📚 Related Formats:
  Format 9.1 - SINGLE DIGIT MULTIPLICATION
  5 parts: Part A: Pictorial Demonstration, Part B: Analyzing Problems, ...
```

## 📊 Key Statistics

- **Total Substandards**: 112
- **With Excellent Matches**: 23 (20.5%)
- **Total Format Associations**: 151
- **Sequence Format Coverage**: 31.6%

### Coverage by Skill Type
- **Fractions**: 100% (42/42 sequences)
- **Multiplication**: 75% (45/60 sequences)
- **Symbol ID & Place Value**: 75% (9/12 sequences)
- **Division**: 66.7% (14/21 sequences)
- **Geometry**: 16.7% (20/120 sequences)
- **Others**: 0% (no formats defined yet)

## 🔄 Regenerate After Updates

If you update the source data:

```bash
python augment_mappings_with_formats.py
```

Output:
```
Loading data files...
Building format lookup...
  Found 104 unique (skill, grade, sequence) combinations with formats
Augmenting substandard mappings with format information...
Saving augmented data...

✓ Successfully augmented mappings!
  Total formats added: 151
```

## 📖 Understanding the Display

### Format Section Color Coding

| Element | Color | Meaning |
|---------|-------|---------|
| Excellent matches | Green | Perfect alignment with substandard |
| Format sections | Light blue | Related instructional formats |
| Match quality badges | Various | EXCELLENT (green), FAIR (yellow), POOR (red), NON-EXISTENT (gray) |

### Format Information Includes

1. **Format Number**: e.g., "9.1", "13.2"
2. **Format Title**: e.g., "SINGLE DIGIT MULTIPLICATION"
3. **Part Count**: Number of instructional parts
4. **Part Names**: Preview of instructional components
5. **Full Steps**: Available in the JSON (not shown in viewer to save space)

## 🎯 Use Cases

### For Educators
- Find the exact DI format to teach a curriculum substandard
- See detailed instructional steps (in the JSON file)
- Understand the teaching sequence (parts A, B, C, etc.)

### For Curriculum Designers
- Verify alignment between standards and instruction
- Identify gaps where formats may be needed
- Analyze coverage across skill areas

### For Researchers
- Study the mapping between standards and proven instructional methods
- Analyze format usage patterns
- Identify areas with high/low format availability

## 💡 Tips

1. **Search is your friend**: Use the search box to quickly find specific substandards
2. **Check coverage**: Green indicators show which substandards have proven methods
3. **Review formats**: Even FAIR or POOR matches show related formats for context
4. **Export data**: The JSON file contains all details for programmatic access

## 📂 JSON Structure

For programmatic access:

```javascript
// Load the data
fetch('output/substandard_to_sequence_mappings_with_formats.json')
  .then(r => r.json())
  .then(data => {
    // Access a substandard
    const substandard = data.mappings[0];
    
    // Access excellent matches with formats
    const matches = substandard.final_excellent_matches;
    matches.forEach(match => {
      console.log(match.skill, match.related_formats);
    });
    
    // Access all ratings with formats
    substandard.phase2_results.forEach(result => {
      result.all_ratings.forEach(rating => {
        console.log(rating.sequence_number, rating.related_formats);
      });
    });
  });
```

## ❓ FAQ

**Q: Why do some sequences not have formats?**
A: Not all sequences have explicit instructional formats in the DI materials. Some are conceptual progressions without specific teaching formats.

**Q: Can I add my own formats?**
A: Yes! Edit `di_formats_with_mappings.json` to add new formats, then regenerate.

**Q: Why is coverage different for different skills?**
A: The DI materials focus heavily on certain skills (Fractions, Multiplication) with detailed formats, while others (Problem Solving) may rely on general strategies.

**Q: Where are the full format details?**
A: In `output/substandard_to_sequence_mappings_with_formats.json` - each format includes complete `parts` and `steps` arrays.

## 🏁 Quick Validation

Test that everything works:

```bash
# Check the file exists
ls -lh output/substandard_to_sequence_mappings_with_formats.json

# Validate JSON
python3 -c "import json; json.load(open('output/substandard_to_sequence_mappings_with_formats.json')); print('✅ Valid JSON')"

# Count formats
python3 -c "import json; d=json.load(open('output/substandard_to_sequence_mappings_with_formats.json')); print(f'Total formats: {d[\"metadata\"][\"format_augmentation\"][\"total_formats_added\"]}')"
```

---

**Ready to use!** Open `mappings_viewer.html` and explore the enhanced mappings. 🎉


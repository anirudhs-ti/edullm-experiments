#!/usr/bin/env python3
"""
Comprehensive verification script to check if all 4 tasks are completed successfully.

TASK 1: Identify 59 lessons without FAIR/EXCELLENT sequences
TASK 2: Generate sequences for those 59 lessons (with at least 1 "Keep" per lesson)
TASK 3: Generate formats for the newly generated sequences
TASK 4: Generate formats for sequences that had no formats before
"""

import json
from pathlib import Path
from typing import Dict, Set, List, Tuple

def load_json(file_path: str) -> dict:
    """Load a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def task1_verify_59_lessons(mappings_file: str) -> Tuple[bool, Set[str], Dict]:
    """
    TASK 1: Verify that 59 lessons were identified as having no FAIR/EXCELLENT sequences.
    
    Returns:
        (success, set of 59 substandard_ids, detailed info)
    """
    print("=" * 80)
    print("TASK 1: Identify lessons without FAIR/EXCELLENT sequences")
    print("=" * 80)
    
    mappings_data = load_json(mappings_file)
    
    lessons_without_good_sequences = set()
    total_lessons = 0
    lessons_with_good_sequences = 0
    
    for lesson in mappings_data.get('mappings', []):
        total_lessons += 1
        substandard_id = lesson['substandard_id']
        
        # Check if lesson has at least one FAIR or EXCELLENT sequence
        has_good_sequence = False
        for match in lesson.get('final_excellent_matches', []):
            quality = match.get('quality', '').upper()
            if quality in ['FAIR', 'EXCELLENT']:
                has_good_sequence = True
                break
        
        if has_good_sequence:
            lessons_with_good_sequences += 1
        else:
            lessons_without_good_sequences.add(substandard_id)
    
    success = len(lessons_without_good_sequences) == 59
    
    info = {
        'total_lessons': total_lessons,
        'lessons_with_good_sequences': lessons_with_good_sequences,
        'lessons_without_good_sequences': len(lessons_without_good_sequences),
        'expected': 59,
        'substandard_ids': list(lessons_without_good_sequences)
    }
    
    print(f"\n📊 Total lessons in original mapping: {total_lessons}")
    print(f"   ✅ Lessons with FAIR/EXCELLENT sequences: {lessons_with_good_sequences}")
    print(f"   ❌ Lessons WITHOUT FAIR/EXCELLENT sequences: {len(lessons_without_good_sequences)}")
    print(f"   🎯 Expected: 59")
    
    if success:
        print(f"\n✅ TASK 1 PASSED: Found exactly 59 lessons without good sequences")
    else:
        print(f"\n❌ TASK 1 FAILED: Found {len(lessons_without_good_sequences)} lessons, expected 59")
    
    return success, lessons_without_good_sequences, info

def task2_verify_sequences(sequences_file: str, validation_files: List[str], 
                          expected_lesson_ids: Set[str]) -> Tuple[bool, Dict]:
    """
    TASK 2: Verify that sequences were generated for all 59 lessons and each has at least 1 "Keep".
    
    Returns:
        (success, detailed info)
    """
    print("\n" + "=" * 80)
    print("TASK 2: Verify generated sequences (must have at least 1 'Keep' per lesson)")
    print("=" * 80)
    
    sequences_data = load_json(sequences_file)
    
    # Load validation results
    print(f"\n📥 Loading validation results from {len(validation_files)} files...")
    validation_map = {}
    for val_file in validation_files:
        val_data = load_json(val_file)
        print(f"   - {Path(val_file).name}")
        for lesson in val_data.get('validation_results', []):
            substandard_id = lesson['substandard_id']
            # Later files override earlier ones (for regenerated sequences)
            validation_map[substandard_id] = lesson
    
    # Check sequences
    generated_lesson_ids = set()
    lessons_with_sequences = 0
    lessons_with_keep = 0
    lessons_without_keep = []
    lessons_missing = []
    
    for lesson in sequences_data.get('generated_sequences', []):
        substandard_id = lesson['substandard_id']
        generated_lesson_ids.add(substandard_id)
        lessons_with_sequences += 1
        
        # Check validation results
        if substandard_id in validation_map:
            validation = validation_map[substandard_id]
            sequences_kept = validation.get('sequences_kept', 0)
            
            if sequences_kept > 0:
                lessons_with_keep += 1
            else:
                lessons_without_keep.append({
                    'substandard_id': substandard_id,
                    'lesson_title': lesson.get('lesson_title', 'N/A'),
                    'total_sequences': validation.get('total_sequences', 0),
                    'sequences_rejected': validation.get('sequences_rejected', 0)
                })
    
    # Check if all expected lessons are present
    missing_lessons = expected_lesson_ids - generated_lesson_ids
    if missing_lessons:
        lessons_missing = list(missing_lessons)
    
    # Check if there are extra lessons
    extra_lessons = generated_lesson_ids - expected_lesson_ids
    
    success = (
        len(generated_lesson_ids) == 59 and
        len(lessons_without_keep) == 0 and
        len(missing_lessons) == 0
    )
    
    info = {
        'total_sequences_generated': lessons_with_sequences,
        'expected': 59,
        'lessons_with_keep': lessons_with_keep,
        'lessons_without_keep': len(lessons_without_keep),
        'lessons_without_keep_details': lessons_without_keep,
        'missing_lessons': lessons_missing,
        'extra_lessons': list(extra_lessons)
    }
    
    print(f"\n📊 Sequence Generation Results:")
    print(f"   Total lessons with sequences: {lessons_with_sequences}")
    print(f"   Expected: 59")
    print(f"   ✅ Lessons with at least 1 'Keep' sequence: {lessons_with_keep}")
    print(f"   ❌ Lessons with 0 'Keep' sequences: {len(lessons_without_keep)}")
    
    if missing_lessons:
        print(f"\n⚠️  Missing {len(missing_lessons)} expected lessons:")
        for lesson_id in list(missing_lessons)[:5]:
            print(f"      - {lesson_id}")
        if len(missing_lessons) > 5:
            print(f"      ... and {len(missing_lessons) - 5} more")
    
    if extra_lessons:
        print(f"\n⚠️  Found {len(extra_lessons)} extra lessons not in original 59:")
        for lesson_id in list(extra_lessons)[:5]:
            print(f"      - {lesson_id}")
        if len(extra_lessons) > 5:
            print(f"      ... and {len(extra_lessons) - 5} more")
    
    if lessons_without_keep:
        print(f"\n❌ Lessons with 0 'Keep' sequences:")
        for lesson in lessons_without_keep:
            print(f"      - {lesson['substandard_id']}: {lesson['lesson_title']}")
            print(f"        (Total: {lesson['total_sequences']}, Rejected: {lesson['sequences_rejected']})")
    
    if success:
        print(f"\n✅ TASK 2 PASSED: All 59 lessons have sequences with at least 1 'Keep'")
    else:
        print(f"\n❌ TASK 2 FAILED:")
        if len(generated_lesson_ids) != 59:
            print(f"   - Expected 59 lessons, got {len(generated_lesson_ids)}")
        if len(lessons_without_keep) > 0:
            print(f"   - {len(lessons_without_keep)} lessons have 0 'Keep' sequences")
        if len(missing_lessons) > 0:
            print(f"   - {len(missing_lessons)} expected lessons are missing")
    
    return success, info

def task3_verify_formats_for_new_sequences(sequences_file: str, formats_file: str) -> Tuple[bool, Dict]:
    """
    TASK 3: Verify that formats were generated for all newly generated sequences.
    
    Returns:
        (success, detailed info)
    """
    print("\n" + "=" * 80)
    print("TASK 3: Verify formats for newly generated sequences")
    print("=" * 80)
    
    sequences_data = load_json(sequences_file)
    formats_data = load_json(formats_file)
    
    # Build set of (substandard_id, sequence_number) from sequences
    sequence_keys = set()
    total_sequences = 0
    
    for lesson in sequences_data.get('generated_sequences', []):
        substandard_id = lesson['substandard_id']
        for seq in lesson.get('generated_sequences', []):
            sequence_number = seq.get('sequence_number')
            sequence_keys.add((substandard_id, sequence_number))
            total_sequences += 1
    
    # Build set of (substandard_id, sequence_number) from formats
    format_keys = set()
    total_formats = 0
    
    for format_entry in formats_data.get('generated_formats', []):
        substandard_id = format_entry.get('substandard_id')
        sequence_number = format_entry.get('sequence_number')
        format_keys.add((substandard_id, sequence_number))
        total_formats += 1
    
    # Find sequences without formats
    sequences_without_formats = sequence_keys - format_keys
    
    # Find formats without sequences (shouldn't happen, but check)
    formats_without_sequences = format_keys - sequence_keys
    
    success = len(sequences_without_formats) == 0
    
    info = {
        'total_sequences': total_sequences,
        'total_formats': total_formats,
        'sequences_with_formats': total_sequences - len(sequences_without_formats),
        'sequences_without_formats': len(sequences_without_formats),
        'sequences_without_formats_details': list(sequences_without_formats)[:20],
        'formats_without_sequences': len(formats_without_sequences)
    }
    
    print(f"\n📊 Format Generation Results:")
    print(f"   Total sequences: {total_sequences}")
    print(f"   Total formats: {total_formats}")
    print(f"   ✅ Sequences with formats: {total_sequences - len(sequences_without_formats)}")
    print(f"   ❌ Sequences without formats: {len(sequences_without_formats)}")
    
    if sequences_without_formats:
        print(f"\n❌ Sequences missing formats (showing first 10):")
        for substandard_id, seq_num in list(sequences_without_formats)[:10]:
            print(f"      - {substandard_id}, Sequence #{seq_num}")
    
    if formats_without_sequences:
        print(f"\n⚠️  Found {len(formats_without_sequences)} formats without corresponding sequences")
    
    if success:
        print(f"\n✅ TASK 3 PASSED: All sequences have corresponding formats")
    else:
        print(f"\n❌ TASK 3 FAILED: {len(sequences_without_formats)} sequences are missing formats")
    
    return success, info

def task4_verify_formats_for_existing_sequences(di_formats_with_mappings_file: str, 
                                               generated_formats_file: str) -> Tuple[bool, Dict]:
    """
    TASK 4: Verify that formats were generated for existing sequences that had no formats.
    
    Returns:
        (success, detailed info)
    """
    print("\n" + "=" * 80)
    print("TASK 4: Verify formats for existing sequences without formats")
    print("=" * 80)
    
    try:
        # Load the original DI formats with mappings
        print(f"\n📥 Loading original DI formats: {Path(di_formats_with_mappings_file).name}")
        di_formats_data = load_json(di_formats_with_mappings_file)
        
        # Load the newly generated formats
        print(f"📥 Loading generated formats: {Path(generated_formats_file).name}")
        generated_formats_data = load_json(generated_formats_file)
        
        # Find sequences and check which ones have formats (GRADE 3 ONLY)
        sequences_without_formats = []
        total_sequences = 0
        sequences_with_formats = 0
        
        TARGET_GRADE = 3  # Only check Grade 3 sequences
        
        skills_data = di_formats_data.get('skills', {})
        
        for skill_name, skill_data in skills_data.items():
            # Get all formats for this skill
            skill_formats = {}
            for fmt in skill_data.get('formats', []):
                grade = fmt.get('grade')
                if grade == TARGET_GRADE:  # Only Grade 3 formats
                    key = (skill_name, grade)
                    if key not in skill_formats:
                        skill_formats[key] = []
                    skill_formats[key].append(fmt)
            
            # Get all sequences for this skill (GRADE 3 ONLY)
            for progression in skill_data.get('progression', []):
                grade = progression.get('grade')
                if grade != TARGET_GRADE:  # Skip non-Grade 3
                    continue
                    
                for seq in progression.get('sequence', []):
                    total_sequences += 1
                    seq_number = seq.get('sequence_number')
                    
                    # Check if this sequence has a format
                    # A sequence "has a format" if there's at least one format for this skill+grade combo
                    has_format = (skill_name, grade) in skill_formats and len(skill_formats[(skill_name, grade)]) > 0
                    
                    if has_format:
                        sequences_with_formats += 1
                    else:
                        sequences_without_formats.append({
                            'skill': skill_name,
                            'grade': grade,
                            'sequence_number': seq_number
                        })
        
        # Create a set of (skill, grade, sequence_number) from generated formats
        generated_format_keys = set()
        for gen_format in generated_formats_data.get('generated_formats', []):
            skill = gen_format.get('skill', '')
            grade = gen_format.get('grade')
            seq_number = gen_format.get('sequence_number')
            generated_format_keys.add((skill, grade, seq_number))
        
        # Check which sequences now have formats
        now_have_formats = []
        still_missing_formats = []
        
        for seq in sequences_without_formats:
            key = (seq['skill'], seq['grade'], seq['sequence_number'])
            if key in generated_format_keys:
                now_have_formats.append(seq)
            else:
                still_missing_formats.append(seq)
        
        success = len(still_missing_formats) == 0
        
        info = {
            'total_sequences_in_original': total_sequences,
            'sequences_originally_with_formats': sequences_with_formats,
            'sequences_originally_without_formats': len(sequences_without_formats),
            'formats_generated': len(now_have_formats),
            'still_missing_formats': len(still_missing_formats),
            'still_missing_details': still_missing_formats[:20]
        }
        
        print(f"\n📊 Format Generation for Existing Sequences (Grade 3 Only):")
        print(f"   Total Grade 3 sequences in original DI formats: {total_sequences}")
        print(f"   Originally with formats: {sequences_with_formats}")
        print(f"   Originally WITHOUT formats: {len(sequences_without_formats)}")
        print(f"   ✅ Formats successfully generated: {len(now_have_formats)}")
        print(f"   ❌ Still missing formats: {len(still_missing_formats)}")
        
        if still_missing_formats:
            print(f"\n❌ Sequences still missing formats (showing first 10):")
            for seq in still_missing_formats[:10]:
                print(f"      - {seq['skill']} (Grade {seq['grade']}) - Sequence #{seq['sequence_number']}")
        
        if success:
            print(f"\n✅ TASK 4 PASSED: All existing Grade 3 sequences without formats now have them")
        else:
            print(f"\n❌ TASK 4 FAILED: {len(still_missing_formats)} Grade 3 sequences still missing formats")
        
        return success, info
        
    except Exception as e:
        print(f"\n❌ Error loading formats files: {e}")
        import traceback
        traceback.print_exc()
        return False, {'error': str(e)}

def main():
    """Main execution function."""
    
    print("\n" + "🔍" * 40)
    print("COMPREHENSIVE VERIFICATION OF ALL 4 TASKS")
    print("🔍" * 40)
    
    script_dir = Path(__file__).parent
    generate_mappings_root = script_dir.parent  # "Experiment - Generate mappings"
    project_root = generate_mappings_root.parent  # Root directory containing both experiments
    
    # File paths
    mappings_file = project_root / "Experiment - Find existing mappings" / "outputs" / "substandard_to_sequence_mappings.v3.json"
    di_formats_with_mappings_file = project_root / "Experiment - Find existing mappings" / "inputs" / "di_formats_with_mappings.json"
    sequences_file = generate_mappings_root / "outputs" / "results" / "sequences.json"
    formats_file = generate_mappings_root / "outputs" / "results" / "formats.json"
    generated_formats_file = generate_mappings_root / "outputs" / "generated_formats_20251030_125804.json"
    
    validation_files = [
        str(generate_mappings_root / "outputs" / "filter" / "sequence_validation_20251030_224655.json"),
        str(generate_mappings_root / "outputs" / "filter" / "sequence_validation_20251031_124549.json")
    ]
    
    # Track overall success
    all_tasks_passed = True
    results = {}
    
    # TASK 1: Identify 59 lessons
    try:
        task1_success, lesson_ids_59, task1_info = task1_verify_59_lessons(str(mappings_file))
        results['task1'] = {'success': task1_success, 'info': task1_info}
        if not task1_success:
            all_tasks_passed = False
    except Exception as e:
        print(f"\n❌ TASK 1 ERROR: {e}")
        results['task1'] = {'success': False, 'error': str(e)}
        all_tasks_passed = False
        lesson_ids_59 = set()
    
    # TASK 2: Verify sequences generated with at least 1 'Keep'
    try:
        task2_success, task2_info = task2_verify_sequences(
            str(sequences_file), 
            validation_files, 
            lesson_ids_59
        )
        results['task2'] = {'success': task2_success, 'info': task2_info}
        if not task2_success:
            all_tasks_passed = False
    except Exception as e:
        print(f"\n❌ TASK 2 ERROR: {e}")
        results['task2'] = {'success': False, 'error': str(e)}
        all_tasks_passed = False
    
    # TASK 3: Verify formats for new sequences
    try:
        task3_success, task3_info = task3_verify_formats_for_new_sequences(
            str(sequences_file),
            str(formats_file)
        )
        results['task3'] = {'success': task3_success, 'info': task3_info}
        if not task3_success:
            all_tasks_passed = False
    except Exception as e:
        print(f"\n❌ TASK 3 ERROR: {e}")
        results['task3'] = {'success': False, 'error': str(e)}
        all_tasks_passed = False
    
    # TASK 4: Verify formats for existing sequences
    try:
        task4_success, task4_info = task4_verify_formats_for_existing_sequences(
            str(di_formats_with_mappings_file),
            str(generated_formats_file)
        )
        results['task4'] = {'success': task4_success, 'info': task4_info}
        if not task4_success:
            all_tasks_passed = False
    except Exception as e:
        print(f"\n❌ TASK 4 ERROR: {e}")
        results['task4'] = {'success': False, 'error': str(e)}
        all_tasks_passed = False
    
    # FINAL SUMMARY
    print("\n" + "=" * 80)
    print("FINAL VERIFICATION SUMMARY")
    print("=" * 80)
    
    print(f"\n{'Task':<50} {'Status':<20}")
    print("-" * 70)
    print(f"{'1. Identify 59 lessons without good sequences':<50} {'✅ PASS' if results.get('task1', {}).get('success') else '❌ FAIL':<20}")
    print(f"{'2. Generate sequences (≥1 Keep per lesson)':<50} {'✅ PASS' if results.get('task2', {}).get('success') else '❌ FAIL':<20}")
    print(f"{'3. Generate formats for new sequences':<50} {'✅ PASS' if results.get('task3', {}).get('success') else '❌ FAIL':<20}")
    print(f"{'4. Generate formats for Grade 3 existing sequences':<50} {'✅ PASS' if results.get('task4', {}).get('success') else '❌ FAIL':<20}")
    
    print("\n" + "=" * 80)
    if all_tasks_passed:
        print("🎉 ALL TASKS COMPLETED SUCCESSFULLY! 🎉")
    else:
        print("⚠️  SOME TASKS FAILED - SEE DETAILS ABOVE")
    print("=" * 80 + "\n")
    
    # Save detailed results to JSON
    output_file = generate_mappings_root / "outputs" / "verification_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"📝 Detailed results saved to: {output_file.name}\n")

if __name__ == "__main__":
    main()


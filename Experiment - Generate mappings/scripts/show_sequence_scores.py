#!/usr/bin/env python3
"""
Display validation scores for all sequences in sequences.json.
"""

import json
from pathlib import Path
from typing import Dict, List

def load_json(file_path: str) -> dict:
    """Load a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    """Main execution function."""
    
    print("="*80)
    print("SEQUENCE VALIDATION SCORES")
    print("="*80)
    
    script_dir = Path(__file__).parent
    outputs_dir = script_dir.parent / "outputs"
    
    # Load sequences
    sequences_file = outputs_dir / "sequences.json"
    print(f"\n📥 Loading sequences from: {sequences_file.name}")
    sequences_data = load_json(str(sequences_file))
    
    # Load BOTH validation results files
    # Original validation for all 59 sequences
    validation_file_original = outputs_dir / "filter" / "sequence_validation_20251030_224655.json"
    print(f"📥 Loading original validation scores from: {validation_file_original.name}")
    validation_data_original = load_json(str(validation_file_original))
    
    # Regenerated validation for 10 sequences (overrides)
    validation_file_regenerated = outputs_dir / "filter" / "sequence_validation_20251031_124549.json"
    print(f"📥 Loading regenerated validation scores from: {validation_file_regenerated.name}")
    validation_data_regenerated = load_json(str(validation_file_regenerated))
    
    # Create a mapping of substandard_id -> validation results
    # Start with original, then override with regenerated
    validation_map = {}
    for lesson in validation_data_original.get('validation_results', []):
        substandard_id = lesson['substandard_id']
        validation_map[substandard_id] = lesson
    
    print(f"   Original validation entries: {len(validation_data_original.get('validation_results', []))}")
    
    # Override with regenerated (newer) validation
    regenerated_count = 0
    for lesson in validation_data_regenerated.get('validation_results', []):
        substandard_id = lesson['substandard_id']
        validation_map[substandard_id] = lesson
        regenerated_count += 1
    
    print(f"   Regenerated validation entries (overrides): {regenerated_count}")
    print(f"   Total unique validations: {len(validation_map)}")
    
    print(f"\n{'='*80}")
    print("SEQUENCE SCORES BY SUBSTANDARD")
    print(f"{'='*80}\n")
    
    total_sequences = 0
    total_kept = 0
    total_rejected = 0
    lessons_with_scores = 0
    lessons_without_scores = 0
    lessons_with_zero_kept = 0
    
    for seq_data in sequences_data.get('generated_sequences', []):
        substandard_id = seq_data['substandard_id']
        lesson_title = seq_data.get('substandard_description', 'N/A')[:60]
        num_sequences = len(seq_data.get('generated_sequences', []))
        
        print(f"📊 {substandard_id}")
        print(f"   Title: {lesson_title}...")
        print(f"   Total Sequences: {num_sequences}")
        
        if substandard_id in validation_map:
            lessons_with_scores += 1
            validation = validation_map[substandard_id]
            sequences_kept = validation.get('sequences_kept', 0)
            sequences_rejected = validation.get('sequences_rejected', 0)
            
            total_sequences += num_sequences
            total_kept += sequences_kept
            total_rejected += sequences_rejected
            
            if sequences_kept == 0:
                lessons_with_zero_kept += 1
            
            print(f"   ✅ Kept: {sequences_kept} | ❌ Rejected: {sequences_rejected}")
            
            # Show individual sequence scores
            for seq_val in validation.get('sequence_validations', []):
                seq_num = seq_val['sequence_number']
                score = seq_val['alignment_score']
                should_keep = seq_val['should_keep']
                status = "🟢 KEEP" if should_keep else "🔴 REJECT"
                
                print(f"      Seq #{seq_num}: Score {score:.2f} - {status}")
                
                # If rejected, show brief reason
                if not should_keep:
                    reasoning = seq_val.get('reasoning', '')[:80]
                    print(f"               Reason: {reasoning}...")
        else:
            lessons_without_scores += 1
            print(f"   ⚠️  No validation scores found")
        
        print()  # Empty line between lessons
    
    # Summary
    print(f"{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total Lessons: {len(sequences_data.get('generated_sequences', []))}")
    print(f"Lessons with validation scores: {lessons_with_scores}")
    print(f"Lessons without validation scores: {lessons_without_scores}")
    print(f"⚠️  Lessons with 0 kept sequences: {lessons_with_zero_kept}")
    print(f"\nTotal Sequences validated: {total_sequences}")
    print(f"   ✅ Kept: {total_kept} ({total_kept/total_sequences*100:.1f}%)")
    print(f"   ❌ Rejected: {total_rejected} ({total_rejected/total_sequences*100:.1f}%)")
    
    if lessons_without_scores > 0:
        print(f"\n⚠️  Warning: {lessons_without_scores} lessons don't have validation scores.")
        print(f"   These may be newly regenerated sequences that haven't been validated yet.")

if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
Check if each sequence in sequences.json has a corresponding format in formats.json.
"""

import json
from pathlib import Path
from typing import Dict, Set, Tuple

def load_json(file_path: str) -> dict:
    """Load a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    """Main execution function."""
    
    print("="*80)
    print("SEQUENCE-FORMAT MAPPING CHECKER")
    print("="*80)
    
    script_dir = Path(__file__).parent
    outputs_dir = script_dir.parent / "outputs"
    
    # Load sequences
    sequences_file = outputs_dir / "sequences.json"
    print(f"\n📥 Loading sequences from: {sequences_file.name}")
    sequences_data = load_json(str(sequences_file))
    
    # Load formats
    formats_file = outputs_dir / "formats.json"
    print(f"📥 Loading formats from: {formats_file.name}")
    formats_data = load_json(str(formats_file))
    
    # Create a set of (substandard_id, sequence_number) tuples from formats
    format_keys: Set[Tuple[str, int]] = set()
    for fmt in formats_data.get('generated_formats', []):
        substandard_id = fmt['substandard_id']
        sequence_number = fmt['sequence_number']
        format_keys.add((substandard_id, sequence_number))
    
    print(f"\n✅ Total formats loaded: {len(formats_data.get('generated_formats', []))}")
    print(f"✅ Unique (substandard_id, sequence_number) pairs: {len(format_keys)}")
    
    print(f"\n{'='*80}")
    print("CHECKING SEQUENCE-FORMAT MAPPINGS")
    print(f"{'='*80}\n")
    
    total_sequences = 0
    sequences_with_formats = 0
    sequences_without_formats = 0
    substandards_with_missing_formats = []
    
    for seq_data in sequences_data.get('generated_sequences', []):
        substandard_id = seq_data['substandard_id']
        lesson_title = seq_data.get('substandard_description', 'N/A')[:60]
        sequences = seq_data.get('generated_sequences', [])
        
        print(f"📊 {substandard_id}")
        print(f"   Title: {lesson_title}...")
        print(f"   Total Sequences: {len(sequences)}")
        
        missing_formats = []
        for seq in sequences:
            seq_num = seq['sequence_number']
            total_sequences += 1
            
            key = (substandard_id, seq_num)
            if key in format_keys:
                sequences_with_formats += 1
                print(f"      ✅ Seq #{seq_num}: Format exists")
            else:
                sequences_without_formats += 1
                missing_formats.append(seq_num)
                print(f"      ❌ Seq #{seq_num}: NO FORMAT FOUND")
        
        if missing_formats:
            substandards_with_missing_formats.append({
                'substandard_id': substandard_id,
                'lesson_title': lesson_title,
                'missing_sequence_numbers': missing_formats
            })
        
        print()  # Empty line between lessons
    
    # Summary
    print(f"{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total Sequences: {total_sequences}")
    print(f"   ✅ Sequences with formats: {sequences_with_formats} ({sequences_with_formats/total_sequences*100:.1f}%)")
    print(f"   ❌ Sequences without formats: {sequences_without_formats} ({sequences_without_formats/total_sequences*100:.1f}%)")
    
    print(f"\nTotal Substandards: {len(sequences_data.get('generated_sequences', []))}")
    print(f"   ✅ Substandards with all formats: {len(sequences_data.get('generated_sequences', [])) - len(substandards_with_missing_formats)}")
    print(f"   ❌ Substandards with missing formats: {len(substandards_with_missing_formats)}")
    
    if substandards_with_missing_formats:
        print(f"\n{'='*80}")
        print("SUBSTANDARDS WITH MISSING FORMATS")
        print(f"{'='*80}")
        for item in substandards_with_missing_formats:
            print(f"\n❌ {item['substandard_id']}")
            print(f"   Title: {item['lesson_title']}...")
            print(f"   Missing formats for sequences: {item['missing_sequence_numbers']}")
    
    # Check for extra formats (formats without corresponding sequences)
    print(f"\n{'='*80}")
    print("CHECKING FOR EXTRA FORMATS (formats without sequences)")
    print(f"{'='*80}\n")
    
    sequence_keys: Set[Tuple[str, int]] = set()
    for seq_data in sequences_data.get('generated_sequences', []):
        substandard_id = seq_data['substandard_id']
        for seq in seq_data.get('generated_sequences', []):
            seq_num = seq['sequence_number']
            sequence_keys.add((substandard_id, seq_num))
    
    extra_formats = []
    for fmt in formats_data.get('generated_formats', []):
        substandard_id = fmt['substandard_id']
        sequence_number = fmt['sequence_number']
        key = (substandard_id, sequence_number)
        
        if key not in sequence_keys:
            extra_formats.append({
                'substandard_id': substandard_id,
                'sequence_number': sequence_number,
                'format_number': fmt['generated_format'].get('format_number', 'N/A')
            })
    
    if extra_formats:
        print(f"⚠️  Found {len(extra_formats)} formats without corresponding sequences:")
        for item in extra_formats:
            print(f"   - {item['substandard_id']} Seq #{item['sequence_number']} (Format: {item['format_number']})")
    else:
        print(f"✅ No extra formats found. All formats have corresponding sequences.")
    
    # Final verdict
    print(f"\n{'='*80}")
    print("FINAL VERDICT")
    print(f"{'='*80}")
    if sequences_without_formats == 0 and len(extra_formats) == 0:
        print("✅ PERFECT MAPPING: All sequences have formats, and all formats have sequences!")
    elif sequences_without_formats == 0:
        print(f"⚠️  All sequences have formats, but there are {len(extra_formats)} extra formats.")
    elif len(extra_formats) == 0:
        print(f"⚠️  All formats have sequences, but {sequences_without_formats} sequences are missing formats.")
    else:
        print(f"❌ INCOMPLETE MAPPING: {sequences_without_formats} sequences missing formats, and {len(extra_formats)} extra formats.")

if __name__ == "__main__":
    main()


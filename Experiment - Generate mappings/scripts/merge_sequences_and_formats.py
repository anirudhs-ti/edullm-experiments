#!/usr/bin/env python3
"""
Merge all generated sequences and formats into single consolidated files.
Takes the latest versions when there are overlaps.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

def load_json(file_path: str) -> dict:
    """Load a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def merge_sequences(original_sequences_file: str, regenerated_sequences_file: str, output_file: str):
    """
    Merge original and regenerated sequences.
    Regenerated sequences (latest) override original ones for the same substandard_id.
    """
    print("="*80)
    print("MERGING SEQUENCES")
    print("="*80)
    
    # Load files
    print(f"\n📥 Loading original sequences: {Path(original_sequences_file).name}")
    original_data = load_json(original_sequences_file)
    
    print(f"📥 Loading regenerated sequences: {Path(regenerated_sequences_file).name}")
    regenerated_data = load_json(regenerated_sequences_file)
    
    # Create a dictionary keyed by substandard_id for easy lookup
    sequences_dict = {}
    
    # First, add all original sequences
    for seq in original_data.get('generated_sequences', []):
        substandard_id = seq['substandard_id']
        sequences_dict[substandard_id] = seq
    
    print(f"   Original sequences loaded: {len(sequences_dict)}")
    
    # Then, override with regenerated sequences (latest)
    regenerated_count = 0
    regenerated_ids = []
    for seq in regenerated_data.get('generated_sequences', []):
        substandard_id = seq['substandard_id']
        sequences_dict[substandard_id] = seq
        regenerated_count += 1
        regenerated_ids.append(substandard_id)
    
    print(f"   Regenerated sequences (overrides): {regenerated_count}")
    print(f"\n🔄 Overridden substandards:")
    for sid in sorted(regenerated_ids):
        print(f"      - {sid}")
    
    # Sort by substandard_id for consistency
    merged_sequences = [sequences_dict[key] for key in sorted(sequences_dict.keys())]
    
    # Create output
    output_data = {
        "metadata": {
            "merge_timestamp": datetime.now().isoformat(),
            "total_substandards": len(merged_sequences),
            "original_sequences_count": len(original_data.get('generated_sequences', [])),
            "regenerated_sequences_count": regenerated_count,
            "final_count": len(merged_sequences),
            "llm_model": "gemini-2.5-pro",
            "version": "1.0_merged",
            "sources": {
                "original": Path(original_sequences_file).name,
                "regenerated": Path(regenerated_sequences_file).name
            }
        },
        "generated_sequences": merged_sequences
    }
    
    # Save
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Merged sequences saved to: {output_file}")
    print(f"   Total unique substandards: {len(merged_sequences)}")
    
    return output_data

def merge_formats(formats_files: List[str], sequences_data: dict, output_file: str):
    """
    Merge multiple format files.
    Later files override earlier ones for the same substandard_id.
    """
    print("\n" + "="*80)
    print("MERGING FORMATS")
    print("="*80)
    
    # Get list of substandard IDs from merged sequences
    valid_substandard_ids = {seq['substandard_id'] for seq in sequences_data.get('generated_sequences', [])}
    
    # Create a dictionary keyed by (substandard_id, sequence_number) for easy lookup
    formats_dict: Dict[tuple, dict] = {}
    
    for file_path in formats_files:
        print(f"\n📥 Loading formats: {Path(file_path).name}")
        data = load_json(file_path)
        
        formats_added = 0
        for fmt in data.get('generated_formats', []):
            substandard_id = fmt['substandard_id']
            
            # Only include formats for substandards that are in our final sequences
            if substandard_id not in valid_substandard_ids:
                continue
            
            sequence_number = fmt['sequence_number']
            key = (substandard_id, sequence_number)
            formats_dict[key] = fmt
            formats_added += 1
        
        print(f"   Formats loaded: {formats_added}")
    
    # Sort by substandard_id and sequence_number for consistency
    merged_formats = [formats_dict[key] for key in sorted(formats_dict.keys())]
    
    # Create output
    output_data = {
        "metadata": {
            "merge_timestamp": datetime.now().isoformat(),
            "total_formats": len(merged_formats),
            "llm_model": "gemini-2.5-pro",
            "version": "1.0_merged",
            "sources": [Path(f).name for f in formats_files]
        },
        "generated_formats": merged_formats
    }
    
    # Save
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Merged formats saved to: {output_file}")
    print(f"   Total formats: {len(merged_formats)}")
    
    # Print summary by substandard
    substandard_counts = {}
    for fmt in merged_formats:
        sid = fmt['substandard_id']
        substandard_counts[sid] = substandard_counts.get(sid, 0) + 1
    
    print(f"\n📊 Formats per substandard:")
    for sid in sorted(substandard_counts.keys()):
        print(f"      {sid}: {substandard_counts[sid]} format(s)")
    
    return output_data

def main():
    """Main execution function."""
    
    print("="*80)
    print("SEQUENCES AND FORMATS MERGER")
    print("="*80)
    
    script_dir = Path(__file__).parent
    outputs_dir = script_dir.parent / "outputs"
    
    # Define input files
    original_sequences = outputs_dir / "generated_sequences_20251030_113708.json"
    regenerated_sequences = outputs_dir / "regenerated_sequences_for_validation_20251031.json"
    
    formats_files = [
        outputs_dir / "generated_formats_new_sequences_20251030_153007.json",
        outputs_dir / "generated_formats_regenerated_sequences_20251031_131410.json"
    ]
    
    # Define output files
    merged_sequences_output = outputs_dir / "sequences.json"
    merged_formats_output = outputs_dir / "formats.json"
    
    # Merge sequences first
    merged_sequences_data = merge_sequences(
        str(original_sequences),
        str(regenerated_sequences),
        str(merged_sequences_output)
    )
    
    # Merge formats using the merged sequences as reference
    merged_formats_data = merge_formats(
        [str(f) for f in formats_files],
        merged_sequences_data,
        str(merged_formats_output)
    )
    
    # Final summary
    print("\n" + "="*80)
    print("MERGE COMPLETE")
    print("="*80)
    print(f"\n📄 sequences.json: {merged_sequences_data['metadata']['total_substandards']} substandards")
    print(f"📄 formats.json: {merged_formats_data['metadata']['total_formats']} formats")
    print(f"\n✅ All files merged successfully!")

if __name__ == "__main__":
    main()


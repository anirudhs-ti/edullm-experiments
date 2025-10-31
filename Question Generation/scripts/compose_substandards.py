#!/usr/bin/env python3
"""
Compose substandards with sequences and formats
Based on FINAL_COMPOSITION_STRATEGY.md

Filter: Keep only EXCELLENT and FAIR quality sequences
"""

import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# File paths
MAPPINGS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/Experiment - Find existing mappings/outputs/substandard_to_sequence_mappings.v3.json"
SEQUENCES_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/Experiment - Generate mappings/outputs/results/sequences.json"
FORMATS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/Experiment - Generate mappings/outputs/results/formats.json"
GEN_FORMATS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/Experiment - Generate mappings/outputs/generated_formats_20251030_125804.json"

OUTPUT_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/Question Generation/composed_substandards.json"


def load_json(filepath):
    """Load JSON file"""
    print(f"Loading: {Path(filepath).name}")
    with open(filepath, 'r') as f:
        return json.load(f)


def build_path_a_indexes(sequences_data, formats_data):
    """Build indexes for Path A (sequences.json → formats.json)"""
    sequences_by_id = {}
    for entry in sequences_data.get('generated_sequences', []):
        sub_id = entry.get('substandard_id')
        sequences_by_id[sub_id] = entry
    
    formats_by_key = {}
    for fmt in formats_data.get('generated_formats', []):
        key = (fmt.get('substandard_id'), fmt.get('sequence_number'))
        formats_by_key[key] = fmt
    
    return sequences_by_id, formats_by_key


def build_path_b_indexes(mappings_data, gen_formats_data):
    """Build indexes for Path B (mappings.v3.json → generated_formats)"""
    mappings_by_id = {}
    for entry in mappings_data.get('mappings', []):
        sub_id = entry.get('substandard_id')
        mappings_by_id[sub_id] = entry
    
    gen_formats_by_key = {}
    for fmt in gen_formats_data.get('generated_formats', []):
        key = (fmt.get('skill'), fmt.get('grade'), fmt.get('sequence_number'))
        gen_formats_by_key[key] = fmt
    
    return mappings_by_id, gen_formats_by_key


def get_substandard_metadata(substandard_id, path_a_sequences, path_b_mappings):
    """Get metadata for a substandard (Step 1)"""
    # Try Path A first (preferred)
    if substandard_id in path_a_sequences:
        entry = path_a_sequences[substandard_id]
        return {
            'substandard_id': substandard_id,
            'substandard_description': entry.get('substandard_description'),
            'assessment_boundary': entry.get('assessment_boundary'),
            'grade': entry.get('grade')
        }
    
    # Fall back to Path B
    elif substandard_id in path_b_mappings:
        entry = path_b_mappings[substandard_id]
        return {
            'substandard_id': substandard_id,
            'substandard_description': entry.get('substandard_description'),
            'assessment_boundary': entry.get('assessment_boundary'),
            'grade': entry.get('grade')
        }
    
    return None


def get_path_a_sequences(substandard_id, path_a_sequences, path_a_formats):
    """Get sequences from Path A (Step 2a)"""
    if substandard_id not in path_a_sequences:
        return []
    
    entry = path_a_sequences[substandard_id]
    sequences = []
    
    for seq in entry.get('generated_sequences', []):
        # Get format for this sequence (Step 3a)
        key = (substandard_id, seq.get('sequence_number'))
        format_entry = path_a_formats.get(key)
        
        sequence_data = {
            'source': 'Path A',
            'sequence_number': seq.get('sequence_number'),
            'problem_type': seq.get('problem_type'),
            'example_questions': seq.get('example_questions', []),
            'visual_aids': seq.get('visual_aids', []),
            'format': format_entry.get('generated_format') if format_entry else None
        }
        
        # Add generation_reasoning if available
        if format_entry:
            sequence_data['generation_reasoning'] = format_entry.get('generation_reasoning')
        
        sequences.append(sequence_data)
    
    return sequences


def get_path_b_sequences(substandard_id, path_b_mappings, path_b_formats):
    """Get sequences from Path B (Step 2b)"""
    if substandard_id not in path_b_mappings:
        return []
    
    mapping = path_b_mappings[substandard_id]
    matches = mapping.get('final_excellent_matches', [])
    
    # Filter: Keep only EXCELLENT and FAIR
    filtered_matches = [m for m in matches if m.get('quality') in ['EXCELLENT', 'FAIR']]
    
    if not filtered_matches:
        return []
    
    # Separate matches with and without formats
    matches_with_formats = []
    matches_without_formats = []
    
    for match in filtered_matches:
        key = (match.get('skill'), match.get('grade'), match.get('sequence_number'))
        format_entry = path_b_formats.get(key)
        
        match_data = {
            'source': 'Path B',
            'skill': match.get('skill'),
            'grade': match.get('grade'),
            'sequence_number': match.get('sequence_number'),
            'quality': match.get('quality'),
            'alignment_score': match.get('alignment_score'),
            'format': format_entry.get('generated_format') if format_entry else None
        }
        
        # Add generation_reasoning if available
        if format_entry:
            match_data['generation_reasoning'] = format_entry.get('generation_reasoning')
        
        if format_entry:
            matches_with_formats.append(match_data)
        else:
            matches_without_formats.append(match_data)
    
    # If we have formats, keep ALL matches with formats
    if matches_with_formats:
        # Sort by alignment_score (highest first)
        return sorted(matches_with_formats, 
                     key=lambda m: m.get('alignment_score', 0),
                     reverse=True)
    
    # If no formats, keep top 2-3 by alignment score
    else:
        sorted_matches = sorted(matches_without_formats,
                               key=lambda m: m.get('alignment_score', 0),
                               reverse=True)
        return sorted_matches[:3]


def compose_all_substandards():
    """Main composition function"""
    print("="*80)
    print("COMPOSING SUBSTANDARDS")
    print("="*80)
    print()
    
    # Load all data
    print("Loading data files...")
    sequences_data = load_json(SEQUENCES_FILE)
    formats_data = load_json(FORMATS_FILE)
    mappings_data = load_json(MAPPINGS_FILE)
    gen_formats_data = load_json(GEN_FORMATS_FILE)
    print()
    
    # Build indexes
    print("Building indexes...")
    path_a_sequences, path_a_formats = build_path_a_indexes(sequences_data, formats_data)
    path_b_mappings, path_b_formats = build_path_b_indexes(mappings_data, gen_formats_data)
    print(f"  Path A: {len(path_a_sequences)} substandards, {len(path_a_formats)} formats")
    print(f"  Path B: {len(path_b_mappings)} substandards, {len(path_b_formats)} formats")
    print()
    
    # Collect all unique substandard IDs
    all_substandard_ids = set()
    all_substandard_ids.update(path_a_sequences.keys())
    all_substandard_ids.update(path_b_mappings.keys())
    
    print(f"Total unique substandard IDs: {len(all_substandard_ids)}")
    print()
    
    # Statistics
    stats = {
        'total_substandards': len(all_substandard_ids),
        'path_a_substandards': 0,
        'path_b_substandards': 0,
        'total_sequences': 0,
        'sequences_with_formats': 0,
        'sequences_without_formats': 0,
        'filtered_poor_quality': 0
    }
    
    # Process each substandard
    result = {
        'metadata': {
            'composition_date': datetime.now().isoformat(),
            'composition_version': '1.0',
            'filter': 'EXCELLENT and FAIR only (exclude POOR)',
            'source_files': {
                'path_a_sequences': 'sequences.json',
                'path_a_formats': 'formats.json',
                'path_b_mappings': 'substandard_to_sequence_mappings.v3.json',
                'path_b_formats': 'generated_formats_20251030_125804.json'
            }
        },
        'substandards': []
    }
    
    print("Processing substandards...")
    for i, substandard_id in enumerate(sorted(all_substandard_ids), 1):
        if i % 10 == 0:
            print(f"  Processed {i}/{len(all_substandard_ids)}...")
        
        # Step 1: Get metadata
        metadata = get_substandard_metadata(substandard_id, path_a_sequences, path_b_mappings)
        
        if not metadata:
            continue
        
        # Step 2: Get sequences
        sequences = []
        
        # Try Path A first
        path_a_seqs = get_path_a_sequences(substandard_id, path_a_sequences, path_a_formats)
        if path_a_seqs:
            sequences = path_a_seqs
            stats['path_a_substandards'] += 1
        
        # Fall back to Path B
        elif substandard_id in path_b_mappings:
            path_b_seqs = get_path_b_sequences(substandard_id, path_b_mappings, path_b_formats)
            sequences = path_b_seqs
            if sequences:
                stats['path_b_substandards'] += 1
        
        # Count sequences
        stats['total_sequences'] += len(sequences)
        for seq in sequences:
            if seq.get('format'):
                stats['sequences_with_formats'] += 1
            else:
                stats['sequences_without_formats'] += 1
        
        # Add to result
        if sequences:
            result['substandards'].append({
                **metadata,
                'sequences': sequences
            })
    
    print(f"  Processed {len(all_substandard_ids)}/{len(all_substandard_ids)}")
    print()
    
    # Update metadata with statistics
    result['metadata']['statistics'] = stats
    
    # Print summary
    print("="*80)
    print("COMPOSITION SUMMARY")
    print("="*80)
    print(f"Total substandards processed: {stats['total_substandards']}")
    print(f"  - Path A (sequences.json): {stats['path_a_substandards']}")
    print(f"  - Path B (mappings.v3.json): {stats['path_b_substandards']}")
    print(f"Total sequences: {stats['total_sequences']}")
    print(f"  - With formats: {stats['sequences_with_formats']}")
    print(f"  - Without formats: {stats['sequences_without_formats']}")
    print()
    
    return result


def save_result(result):
    """Save composed result to JSON file"""
    print(f"Saving to: {OUTPUT_FILE}")
    
    # Ensure directory exists
    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(result, f, indent=2)
    
    # Get file size
    file_size = Path(OUTPUT_FILE).stat().st_size
    file_size_mb = file_size / (1024 * 1024)
    
    print(f"Saved successfully!")
    print(f"File size: {file_size_mb:.2f} MB")
    print()


def main():
    """Main entry point"""
    print()
    print("="*80)
    print("SUBSTANDARD COMPOSITION TOOL")
    print("="*80)
    print()
    
    # Compose
    result = compose_all_substandards()
    
    # Save
    save_result(result)
    
    print("="*80)
    print("DONE!")
    print("="*80)
    print()


if __name__ == "__main__":
    main()

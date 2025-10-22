#!/usr/bin/env python3
"""
Augment substandard_to_sequence_mappings.json with format information from di_formats_with_mappings.json
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


def load_json(filepath: Path) -> Dict:
    """Load JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: Dict, filepath: Path):
    """Save JSON file with pretty formatting"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_format_lookup(di_formats_data: Dict) -> Dict[tuple, List[Dict]]:
    """
    Build a lookup dictionary from (skill_name, grade, sequence_number) -> list of formats
    
    Returns a dict where keys are tuples of (skill_name, grade, sequence_number)
    and values are lists of format dictionaries
    """
    lookup = {}
    
    for skill_name, skill_data in di_formats_data['skills'].items():
        if 'formats' not in skill_data:
            continue
            
        for format_info in skill_data['formats']:
            grade = format_info.get('grade')
            sequence_numbers = format_info.get('sequence_numbers', [])
            
            # Extract relevant format details
            format_details = {
                'format_number': format_info.get('format_number'),
                'format_title': format_info.get('title'),
                'grade': grade,
                'sequence_numbers': sequence_numbers,
                'parts': format_info.get('parts', [])
            }
            
            # Add to lookup for each sequence number this format covers
            for seq_num in sequence_numbers:
                key = (skill_name, grade, seq_num)
                if key not in lookup:
                    lookup[key] = []
                lookup[key].append(format_details)
    
    return lookup


def augment_substandard_mappings(
    substandard_data: Dict,
    format_lookup: Dict[tuple, List[Dict]]
) -> Dict:
    """
    Augment substandard mappings with format information
    """
    augmented_data = substandard_data.copy()
    
    # Add augmentation metadata
    augmented_data['metadata']['format_augmentation'] = {
        'augmented_at': datetime.now().isoformat(),
        'source_di_formats': 'data/di_formats_with_mappings.json',
        'total_formats_added': 0
    }
    
    formats_added_count = 0
    
    # Process each mapping
    for mapping in augmented_data['mappings']:
        # Process phase2_results
        if 'phase2_results' in mapping:
            for result in mapping['phase2_results']:
                skill_name = result['skill_name']
                grade = result.get('grade')
                
                # Process all_ratings
                if 'all_ratings' in result:
                    for rating in result['all_ratings']:
                        sequence_number = rating.get('sequence_number')
                        
                        # Look up format
                        key = (skill_name, grade, sequence_number)
                        formats = format_lookup.get(key, [])
                        
                        if formats:
                            # Add format information to this rating
                            rating['related_formats'] = formats
                            formats_added_count += len(formats)
                        else:
                            rating['related_formats'] = []
                
                # Also augment excellent_sequences info if present
                if 'excellent_sequences' in result and result['excellent_sequences']:
                    result['excellent_sequences_with_formats'] = []
                    for seq_num in result['excellent_sequences']:
                        key = (skill_name, grade, seq_num)
                        formats = format_lookup.get(key, [])
                        result['excellent_sequences_with_formats'].append({
                            'sequence_number': seq_num,
                            'formats': formats
                        })
        
        # Also augment final_excellent_matches
        if 'final_excellent_matches' in mapping and mapping['final_excellent_matches']:
            for match in mapping['final_excellent_matches']:
                skill_name = match['skill']
                grade = match['grade']
                sequence_number = match['sequence_number']
                
                key = (skill_name, grade, sequence_number)
                formats = format_lookup.get(key, [])
                match['related_formats'] = formats
    
    augmented_data['metadata']['format_augmentation']['total_formats_added'] = formats_added_count
    
    return augmented_data


def main():
    # Paths
    workspace_path = Path('/workspaces/github-com-anirudhs-ti-edullm-experiments')
    di_formats_path = workspace_path / 'data' / 'di_formats_with_mappings.json'
    substandard_mappings_path = workspace_path / 'output' / 'substandard_to_sequence_mappings.json'
    output_path = workspace_path / 'output' / 'substandard_to_sequence_mappings_with_formats.json'
    
    print("Loading data files...")
    di_formats_data = load_json(di_formats_path)
    substandard_data = load_json(substandard_mappings_path)
    
    print("Building format lookup...")
    format_lookup = build_format_lookup(di_formats_data)
    print(f"  Found {len(format_lookup)} unique (skill, grade, sequence) combinations with formats")
    
    print("Augmenting substandard mappings with format information...")
    augmented_data = augment_substandard_mappings(substandard_data, format_lookup)
    
    print(f"Saving augmented data to {output_path}...")
    save_json(augmented_data, output_path)
    
    total_formats = augmented_data['metadata']['format_augmentation']['total_formats_added']
    print(f"\n✓ Successfully augmented mappings!")
    print(f"  Total formats added: {total_formats}")
    print(f"  Output file: {output_path}")


if __name__ == '__main__':
    main()


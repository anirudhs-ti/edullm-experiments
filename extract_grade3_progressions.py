#!/usr/bin/env python3
"""
Script to extract complete grade 3 progressions for each skill from di_formats.json.
This will help verify that the progression data is being extracted correctly.
"""

import json
import csv
from typing import Dict, List, Any

def load_di_formats():
    """Load the di_formats.json file"""
    with open('di_formats.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def format_sequence_content(sequence: Dict[str, Any]) -> str:
    """Format a single sequence into a readable string"""
    parts = []
    
    # Add sequence number and problem type
    seq_num = sequence.get('sequence_number', 'N/A')
    problem_type = sequence.get('problem_type', 'No description')
    parts.append(f"Sequence {seq_num}: {problem_type}")
    
    # Add example questions
    if 'example_questions' in sequence and sequence['example_questions']:
        examples = "; ".join(sequence['example_questions'])
        parts.append(f"Examples: {examples}")
    
    # Add visual aids
    if 'visual_aids' in sequence and sequence['visual_aids']:
        visual_aids = "; ".join(sequence['visual_aids'])
        parts.append(f"Visual Aids: {visual_aids}")
    
    return " | ".join(parts)

def extract_grade3_progressions(di_formats_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all grade 3 progressions from the di_formats data"""
    progressions = []
    
    if 'skills' not in di_formats_data:
        print("No 'skills' key found in di_formats.json")
        return progressions
    
    for skill_name, skill_data in di_formats_data['skills'].items():
        print(f"Processing skill: {skill_name}")
        
        if 'progression' not in skill_data:
            print(f"  No progression data found for {skill_name}")
            continue
        
        # Find grade 3 progressions
        for progression_item in skill_data['progression']:
            if progression_item.get('grade') == 3:
                print(f"  Found grade 3 progression for {skill_name}")
                
                # Check if this progression has sequence data
                if 'sequence' in progression_item and progression_item['sequence']:
                    # Format all sequences
                    formatted_sequences = []
                    for sequence in progression_item['sequence']:
                        formatted_seq = format_sequence_content(sequence)
                        formatted_sequences.append(formatted_seq)
                    
                    # Join all sequences
                    complete_progression = " | ".join(formatted_sequences)
                    
                    progressions.append({
                        'skill': skill_name,
                        'grade': 3,
                        'sequence_count': len(progression_item['sequence']),
                        'complete_progression': complete_progression,
                        'raw_sequence_data': progression_item['sequence']
                    })
                    
                    print(f"    Extracted {len(progression_item['sequence'])} sequences")
                else:
                    print(f"    No sequence data found in progression")
    
    return progressions

def save_to_csv(progressions: List[Dict[str, Any]], output_file: str):
    """Save the progressions to a CSV file"""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['skill', 'grade', 'sequence_count', 'complete_progression']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for progression in progressions:
            writer.writerow({
                'skill': progression['skill'],
                'grade': progression['grade'],
                'sequence_count': progression['sequence_count'],
                'complete_progression': progression['complete_progression']
            })

def main():
    """Main function to extract grade 3 progressions"""
    print("Loading di_formats.json...")
    di_formats_data = load_di_formats()
    
    print("Extracting grade 3 progressions...")
    progressions = extract_grade3_progressions(di_formats_data)
    
    print(f"\nFound {len(progressions)} grade 3 progressions")
    
    # Save to CSV
    output_file = 'grade3_progressions_extracted.csv'
    save_to_csv(progressions, output_file)
    
    print(f"Results saved to {output_file}")
    
    # Print summary
    print("\nSummary:")
    for progression in progressions:
        print(f"  {progression['skill']}: {progression['sequence_count']} sequences")
        print(f"    Preview: {progression['complete_progression'][:100]}...")
        print()

if __name__ == "__main__":
    main()

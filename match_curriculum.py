#!/usr/bin/env python3
"""
Script to match curriculum.csv entries with direct instruction formats from di_formats.json
and create cursor-extracted-instructions.csv with additional columns.
"""

import json
import csv
import re
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher

def load_data():
    """Load curriculum.csv and di_formats.json"""
    curriculum_data = []
    with open('curriculum.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        curriculum_data = list(reader)
    
    with open('di_formats.json', 'r', encoding='utf-8') as f:
        di_formats = json.load(f)
    
    return curriculum_data, di_formats

def extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from text for matching"""
    if not text:
        return []
    
    # Convert to lowercase and remove common words
    text = text.lower()
    
    # Remove common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'must', 'shall'}
    
    # Extract words (letters and numbers only)
    words = re.findall(r'\b[a-z0-9]+\b', text)
    
    # Filter out stop words and short words
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    
    return keywords

def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts using multiple methods"""
    if not text1 or not text2:
        return 0.0
    
    # Method 1: Sequence matcher
    seq_similarity = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    # Method 2: Keyword overlap
    keywords1 = set(extract_keywords(text1))
    keywords2 = set(extract_keywords(text2))
    
    if not keywords1 or not keywords2:
        keyword_similarity = 0.0
    else:
        intersection = keywords1.intersection(keywords2)
        union = keywords1.union(keywords2)
        keyword_similarity = len(intersection) / len(union) if union else 0.0
    
    # Method 3: Substring matching
    text1_lower = text1.lower()
    text2_lower = text2.lower()
    
    # Check if one text contains the other
    substring_score = 0.0
    if text1_lower in text2_lower or text2_lower in text1_lower:
        substring_score = 0.8
    else:
        # Check for significant word overlap
        words1 = set(text1_lower.split())
        words2 = set(text2_lower.split())
        if words1 and words2:
            word_overlap = len(words1.intersection(words2)) / max(len(words1), len(words2))
            substring_score = word_overlap * 0.6
    
    # Weighted combination
    final_score = (seq_similarity * 0.4 + keyword_similarity * 0.4 + substring_score * 0.2)
    return min(final_score, 1.0)

def find_best_match(curriculum_entry: Dict, di_formats: Dict) -> Tuple[Optional[Dict], float]:
    """Find the best matching direct instruction format for a curriculum entry"""
    grade = int(curriculum_entry['grade'])
    description = curriculum_entry['substandard_description']
    substandard_id = curriculum_entry['substandard_id']
    
    best_match = None
    best_score = 0.0
    
    # Iterate through all skills
    for skill_name, skill_data in di_formats['skills'].items():
        if 'progression' not in skill_data:
            continue
            
        for progression in skill_data['progression']:
            if progression.get('grade') != grade:
                continue
                
            # Check sequence items
            if 'sequence' in progression:
                for seq_item in progression['sequence']:
                    problem_type = seq_item.get('problem_type', '')
                    
                    # Calculate similarity with description
                    similarity = calculate_similarity(description, problem_type)
                    
                    if similarity > best_score:
                        best_score = similarity
                        best_match = {
                            'skill_name': skill_name,
                            'problem_type': problem_type,
                            'sequence_number': seq_item.get('sequence_number', ''),
                            'example_questions': seq_item.get('example_questions', []),
                            'visual_aids': seq_item.get('visual_aids', []),
                            'format_number': progression.get('format_number', ''),
                            'title': progression.get('title', '')
                        }
            
            # Check if there's a direct match with format title
            title = progression.get('title', '')
            if title:
                title_similarity = calculate_similarity(description, title)
                if title_similarity > best_score:
                    best_score = title_similarity
                    best_match = {
                        'skill_name': skill_name,
                        'problem_type': title,
                        'sequence_number': '',
                        'example_questions': [],
                        'visual_aids': [],
                        'format_number': progression.get('format_number', ''),
                        'title': title
                    }
    
    return best_match, best_score

def determine_confidence(score: float, match: Optional[Dict]) -> str:
    """Determine confidence level based on similarity score"""
    if not match or score < 0.1:
        return "Very Low"
    elif score < 0.3:
        return "Low"
    elif score < 0.5:
        return "Medium"
    elif score < 0.7:
        return "High"
    else:
        return "Very High"

def format_direct_instruction(match: Optional[Dict]) -> str:
    """Format the direct instruction information"""
    if not match:
        return ""
    
    parts = []
    
    if match.get('skill_name'):
        parts.append(f"Skill: {match['skill_name']}")
    
    if match.get('title'):
        parts.append(f"Title: {match['title']}")
    
    if match.get('problem_type'):
        parts.append(f"Problem Type: {match['problem_type']}")
    
    if match.get('format_number'):
        parts.append(f"Format: {match['format_number']}")
    
    if match.get('sequence_number'):
        parts.append(f"Sequence: {match['sequence_number']}")
    
    if match.get('example_questions'):
        examples = match['example_questions'][:3]  # Limit to first 3 examples
        parts.append(f"Examples: {'; '.join(examples)}")
    
    return " | ".join(parts)

def main():
    """Main function to process curriculum and create output CSV"""
    print("Loading data...")
    curriculum_data, di_formats = load_data()
    
    print(f"Processing {len(curriculum_data)} curriculum entries...")
    
    output_data = []
    
    for i, entry in enumerate(curriculum_data):
        print(f"Processing entry {i+1}/{len(curriculum_data)}: {entry['substandard_description'][:50]}...")
        
        best_match, score = find_best_match(entry, di_formats)
        confidence = determine_confidence(score, best_match)
        direct_instruction = format_direct_instruction(best_match)
        
        output_entry = {
            'grade': entry['grade'],
            'substandard_description': entry['substandard_description'],
            'substandard_id': entry['substandard_id'],
            'direct_instructions': direct_instruction,
            'match_confidence': confidence
        }
        
        output_data.append(output_entry)
    
    # Write output CSV
    output_file = 'cursor-extracted-instructions.csv'
    fieldnames = ['grade', 'substandard_description', 'substandard_id', 'direct_instructions', 'match_confidence']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_data)
    
    print(f"\nCompleted! Output written to {output_file}")
    
    # Print summary statistics
    confidence_counts = {}
    for entry in output_data:
        conf = entry['match_confidence']
        confidence_counts[conf] = confidence_counts.get(conf, 0) + 1
    
    print("\nConfidence Distribution:")
    for conf, count in sorted(confidence_counts.items()):
        print(f"  {conf}: {count} entries")

if __name__ == "__main__":
    main()




#!/usr/bin/env python3
"""
Script to re-match curriculum standards with Very Low confidence matches using pure LLM approach.
This script focuses only on substandards from hybrid-extracted-instructions-grade3.csv that have "Very Low" confidence.
"""

import json
import csv
import os
import time
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv
import google.generativeai as genai

def load_environment():
    """Load environment variables from .env file"""
    load_dotenv()
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    return api_key

def initialize_gemini(api_key: str):
    """Initialize Gemini API"""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.0-flash-lite')

def load_data():
    """Load curriculum.csv, di_formats.json, and hybrid-extracted-instructions-grade3.csv"""
    curriculum_data = []
    with open('curriculum.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        curriculum_data = list(reader)
    
    with open('di_formats.json', 'r', encoding='utf-8') as f:
        di_formats_raw = json.load(f)
    
    # Extract instruction formats from the nested structure
    di_formats = []
    if 'skills' in di_formats_raw:
        for skill_name, skill_data in di_formats_raw['skills'].items():
            if 'progression' in skill_data:
                for progression_item in skill_data['progression']:
                    if progression_item.get('grade') == 3:  # Focus on grade 3
                        # Convert to the expected format
                        instruction_format = {
                            'skill': skill_name,
                            'grade': 3,
                            'direct_instructions': format_direct_instructions(progression_item['sequence'])
                        }
                        di_formats.append(instruction_format)
    
    # Load hybrid results to identify Very Low confidence matches
    very_low_matches = []
    with open('hybrid-extracted-instructions-grade3.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['match_confidence'] == 'Very Low':
                very_low_matches.append(row)
    
    return curriculum_data, di_formats, very_low_matches

def format_direct_instructions(sequence_data):
    """Format sequence data into a readable instruction format"""
    if not sequence_data:
        return ""
    
    formatted_parts = []
    for i, sequence in enumerate(sequence_data, 1):
        # Use problem_type instead of description
        sequence_text = f"Sequence {i}: {sequence.get('problem_type', '')}"
        
        # Use example_questions instead of examples
        if 'example_questions' in sequence and sequence['example_questions']:
            examples_text = " | Examples: " + "; ".join(sequence['example_questions'])
            sequence_text += examples_text
        
        if 'visual_aids' in sequence and sequence['visual_aids']:
            visual_aids_text = " | Visual Aids: " + "; ".join(sequence['visual_aids'])
            sequence_text += visual_aids_text
        
        formatted_parts.append(sequence_text)
    
    return " | ".join(formatted_parts)

def create_llm_matching_prompt(curriculum_description: str, instruction_format: str) -> str:
    """Create a comprehensive prompt for LLM to find the best match"""
    return f"""
You are an expert in educational curriculum alignment and direct instruction design. Your task is to find the BEST possible match between a curriculum standard and direct instruction formats.

CURRICULUM STANDARD:
{curriculum_description}

DIRECT INSTRUCTION FORMAT:
{instruction_format}

ANALYSIS REQUIREMENTS:
1. Examine the curriculum standard's core learning objective
2. Analyze the direct instruction format's skill focus, sequences, and examples
3. Determine how well the instruction format addresses the curriculum standard
4. Consider the appropriateness of examples and visual aids for the grade level
5. Evaluate the progression of difficulty in the sequences

MATCHING CRITERIA:
- Skill alignment: Does the instruction format teach the exact skill described in the standard?
- Grade appropriateness: Are the examples and complexity suitable for grade 3?
- Sequence logic: Does the instruction progression build toward the standard's objective?
- Example relevance: Do the examples directly support the learning objective?
- Visual aid support: Do visual aids enhance understanding of the concept?

SCORING GUIDELINES:
- 0.9-1.0: Perfect match - instruction format directly teaches the curriculum standard
- 0.7-0.89: Strong match - instruction format addresses the core objective with minor gaps
- 0.5-0.69: Moderate match - instruction format partially addresses the standard
- 0.3-0.49: Weak match - instruction format has some relevance but significant gaps
- 0.0-0.29: Poor match - instruction format doesn't meaningfully address the standard

Please provide:
1. A similarity score (0.0 to 1.0)
2. A detailed explanation of why this is or isn't a good match
3. Specific examples of how the instruction format addresses (or fails to address) the curriculum standard

Format your response as:
SCORE: [score]
EXPLANATION: [detailed explanation]
"""

def find_best_match_for_standard(model, curriculum_standard: Dict, di_formats: List[Dict]) -> Tuple[Dict, float, str]:
    """Find the best matching instruction format for a curriculum standard using LLM"""
    best_match = None
    best_score = 0.0
    best_explanation = ""
    
    print(f"Finding best match for: {curriculum_standard['substandard_description']}")
    print(f"Comparing against {len(di_formats)} instruction formats...")
    
    for i, instruction_format in enumerate(di_formats, 1):
        try:
            print(f"  LLM call {i}/{len(di_formats)} for '{curriculum_standard['substandard_description'][:50]}...' and '{instruction_format['skill']}'")
            
            prompt = create_llm_matching_prompt(
                curriculum_standard['substandard_description'],
                instruction_format['direct_instructions']
            )
            
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Parse the response
            score = 0.0
            explanation = ""
            
            lines = response_text.split('\n')
            for line in lines:
                if line.startswith('SCORE:'):
                    try:
                        score = float(line.split('SCORE:')[1].strip())
                    except (ValueError, IndexError):
                        continue
                elif line.startswith('EXPLANATION:'):
                    explanation = line.split('EXPLANATION:')[1].strip()
            
            # If parsing failed, try to extract score from the text
            if score == 0.0:
                import re
                score_match = re.search(r'(\d+\.?\d*)', response_text)
                if score_match:
                    try:
                        score = float(score_match.group(1))
                        if score > 1.0:  # If score is > 1, it might be a percentage
                            score = score / 100.0
                    except ValueError:
                        score = 0.0
            
            if explanation == "":
                explanation = response_text[:500] + "..." if len(response_text) > 500 else response_text
            
            print(f"  Score: {score:.3f} - {instruction_format['skill']}")
            
            if score > best_score:
                best_score = score
                best_match = instruction_format
                best_explanation = explanation
                
        except Exception as e:
            print(f"  Error processing instruction format: {e}")
            continue
        
        # Add small delay to avoid rate limiting
        time.sleep(0.1)
    
    return best_match, best_score, best_explanation

def determine_confidence_level(score: float) -> str:
    """Determine confidence level based on similarity score"""
    if score >= 0.8:
        return "Very High"
    elif score >= 0.6:
        return "High"
    elif score >= 0.4:
        return "Medium"
    elif score >= 0.2:
        return "Low"
    else:
        return "Very Low"

def main():
    """Main function to process Very Low confidence matches"""
    print("Loading environment and initializing Gemini...")
    api_key = load_environment()
    model = initialize_gemini(api_key)
    
    print("Loading data...")
    curriculum_data, di_formats, very_low_matches = load_data()
    
    print(f"Found {len(very_low_matches)} Very Low confidence matches to re-process")
    
    # Create output file
    output_file = 'llm-improved-very-low-matches.csv'
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'grade', 'substandard_description', 'substandard_id', 
            'direct_instructions', 'match_confidence', 'similarity_score', 'llm_explanation'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for i, very_low_match in enumerate(very_low_matches, 1):
            print(f"\nProcessing substandard {i}/{len(very_low_matches)}: {very_low_match['substandard_description']}")
            print(f"Substandard ID: {very_low_match['substandard_id']}")
            
            # Find the corresponding curriculum standard
            curriculum_standard = None
            for std in curriculum_data:
                if std['substandard_id'] == very_low_match['substandard_id']:
                    curriculum_standard = std
                    break
            
            if not curriculum_standard:
                print(f"  Warning: Could not find curriculum standard for {very_low_match['substandard_id']}")
                continue
            
            # Find best match using LLM
            best_match, best_score, best_explanation = find_best_match_for_standard(
                model, curriculum_standard, di_formats
            )
            
            if best_match:
                confidence_level = determine_confidence_level(best_score)
                
                # Write improved result
                writer.writerow({
                    'grade': curriculum_standard['grade'],
                    'substandard_description': curriculum_standard['substandard_description'],
                    'substandard_id': curriculum_standard['substandard_id'],
                    'direct_instructions': best_match['direct_instructions'],
                    'match_confidence': confidence_level,
                    'similarity_score': best_score,
                    'llm_explanation': best_explanation
                })
                
                print(f"  Improved match found: {confidence_level} confidence ({best_score:.3f})")
                print(f"  Skill: {best_match['skill']}")
            else:
                print(f"  No suitable match found")
                
                # Write original result with note
                writer.writerow({
                    'grade': curriculum_standard['grade'],
                    'substandard_description': curriculum_standard['substandard_description'],
                    'substandard_id': curriculum_standard['substandard_id'],
                    'direct_instructions': very_low_match['direct_instructions'],
                    'match_confidence': 'Very Low',
                    'similarity_score': 0.0,
                    'llm_explanation': 'No suitable match found by LLM analysis'
                })
    
    print(f"\nCompleted! Results saved to {output_file}")
    print(f"Processed {len(very_low_matches)} Very Low confidence matches")

if __name__ == "__main__":
    main()

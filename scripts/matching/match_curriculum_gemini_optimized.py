#!/usr/bin/env python3
"""
Optimized script to match curriculum.csv entries with direct instruction formats from di_formats.json
using Gemini LLM for similarity scoring and create gemini-extracted-instructions.csv.
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
    return genai.GenerativeModel('gemini-2.5-flash')

def load_data():
    """Load curriculum.csv and di_formats.json"""
    curriculum_data = []
    with open('curriculum.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        curriculum_data = list(reader)
    
    with open('di_formats.json', 'r', encoding='utf-8') as f:
        di_formats = json.load(f)
    
    return curriculum_data, di_formats

def create_similarity_prompt(curriculum_description: str, instruction_format: str) -> str:
    """Create a prompt for Gemini to assess similarity"""
    return f"""
You are an expert in educational curriculum alignment. Your task is to assess how well a direct instruction format matches a curriculum standard.

CURRICULUM STANDARD:
{curriculum_description}

DIRECT INSTRUCTION FORMAT:
{instruction_format}

Please evaluate the similarity between these two educational components on a scale of 0.0 to 1.0, where:
- 1.0 = Perfect match (exactly the same concept/skill)
- 0.8-0.9 = Very high similarity (same core concept with minor differences)
- 0.6-0.7 = High similarity (related concepts, same mathematical domain)
- 0.4-0.5 = Medium similarity (some overlap in skills/concepts)
- 0.2-0.3 = Low similarity (minimal overlap)
- 0.0-0.1 = No similarity (completely different concepts)

Consider:
1. Mathematical domain (arithmetic, algebra, geometry, etc.)
2. Specific skills being taught
3. Problem types and formats
4. Grade level appropriateness
5. Learning objectives alignment

Respond with ONLY a decimal number between 0.0 and 1.0, followed by a brief explanation of your reasoning.
"""

def get_llm_similarity(model, curriculum_description: str, instruction_format: str) -> Tuple[float, str]:
    """Get similarity score from Gemini LLM"""
    try:
        prompt = create_similarity_prompt(curriculum_description, instruction_format)
        response = model.generate_content(prompt)
        
        # Extract the numeric score from the response
        response_text = response.text.strip()
        
        # Look for a decimal number at the start of the response
        import re
        score_match = re.search(r'^(\d+\.?\d*)', response_text)
        if score_match:
            score = float(score_match.group(1))
            # Ensure score is between 0 and 1
            score = max(0.0, min(1.0, score))
            explanation = response_text[len(score_match.group(0)):].strip()
        else:
            # Fallback: look for any decimal number in the response
            score_match = re.search(r'(\d+\.?\d*)', response_text)
            if score_match:
                score = float(score_match.group(1))
                score = max(0.0, min(1.0, score))
                explanation = response_text
            else:
                score = 0.0
                explanation = "Could not parse score from response"
        
        return score, explanation
        
    except Exception as e:
        print(f"Error getting LLM similarity: {e}")
        return 0.0, f"Error: {str(e)}"

def format_instruction_for_comparison(progression: Dict, seq_item: Optional[Dict] = None) -> str:
    """Format instruction data for LLM comparison"""
    parts = []
    
    if progression.get('title'):
        parts.append(f"Title: {progression['title']}")
    
    if progression.get('format_number'):
        parts.append(f"Format: {progression['format_number']}")
    
    if seq_item:
        if seq_item.get('problem_type'):
            parts.append(f"Problem Type: {seq_item['problem_type']}")
        
        if seq_item.get('example_questions'):
            examples = seq_item['example_questions'][:3]  # Limit to first 3
            parts.append(f"Examples: {'; '.join(examples)}")
    
    return " | ".join(parts)

def find_best_match_gemini_optimized(curriculum_entry: Dict, di_formats: Dict, model) -> Tuple[Optional[Dict], float, str]:
    """Find the best matching direct instruction format using Gemini LLM with optimizations"""
    grade = int(curriculum_entry['grade'])
    description = curriculum_entry['substandard_description']
    substandard_id = curriculum_entry['substandard_id']
    
    best_match = None
    best_score = 0.0
    best_explanation = ""
    api_calls_made = 0
    
    # Pre-filter progressions by grade to reduce iterations
    grade_progressions = []
    for skill_name, skill_data in di_formats['skills'].items():
        if 'progression' not in skill_data:
            continue
        for progression in skill_data['progression']:
            if progression.get('grade') == grade:
                grade_progressions.append((skill_name, progression))
    
    print(f"  Processing {len(grade_progressions)} grade-{grade} progressions...")
    
    # Iterate through grade-filtered progressions
    for skill_name, progression in grade_progressions:
        # Early termination if we have a very high score
        if best_score >= 0.9:
            print(f"  Early termination: Found excellent match (score: {best_score:.3f})")
            break
            
        # Check sequence items first (usually more specific)
        if 'sequence' in progression:
            for seq_item in progression['sequence']:
                instruction_format = format_instruction_for_comparison(progression, seq_item)
                
                # Get LLM similarity score
                score, explanation = get_llm_similarity(model, description, instruction_format)
                api_calls_made += 1
                
                if score > best_score:
                    best_score = score
                    best_explanation = explanation
                    best_match = {
                        'skill_name': skill_name,
                        'problem_type': seq_item.get('problem_type', ''),
                        'sequence_number': seq_item.get('sequence_number', ''),
                        'example_questions': seq_item.get('example_questions', []),
                        'visual_aids': seq_item.get('visual_aids', []),
                        'format_number': progression.get('format_number', ''),
                        'title': progression.get('title', ''),
                        'llm_explanation': explanation
                    }
                
                # Early termination for very high scores
                if best_score >= 0.9:
                    break
            
            # Early termination after sequence items if we have a good score
            if best_score >= 0.9:
                break
        
        # Only check progression title if we don't have a good sequence match
        if best_score < 0.7:
            title = progression.get('title', '')
            if title:
                instruction_format = format_instruction_for_comparison(progression)
                score, explanation = get_llm_similarity(model, description, instruction_format)
                api_calls_made += 1
                
                if score > best_score:
                    best_score = score
                    best_explanation = explanation
                    best_match = {
                        'skill_name': skill_name,
                        'problem_type': title,
                        'sequence_number': '',
                        'example_questions': [],
                        'visual_aids': [],
                        'format_number': progression.get('format_number', ''),
                        'title': title,
                        'llm_explanation': explanation
                    }
    
    print(f"  Made {api_calls_made} API calls, best score: {best_score:.3f}")
    return best_match, best_score, best_explanation

def determine_confidence_llm(score: float) -> str:
    """Determine confidence level based on LLM similarity score"""
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

def format_direct_instruction_llm(match: Optional[Dict]) -> str:
    """Format the direct instruction information with LLM explanation"""
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
    
    if match.get('llm_explanation'):
        parts.append(f"LLM Reasoning: {match['llm_explanation']}")
    
    return " | ".join(parts)

def main():
    """Main function to process curriculum and create output CSV using optimized Gemini approach"""
    print("Loading environment and initializing Gemini...")
    api_key = load_environment()
    model = initialize_gemini(api_key)
    
    print("Loading data...")
    curriculum_data, di_formats = load_data()
    
    print(f"Processing {len(curriculum_data)} curriculum entries with optimized Gemini LLM...")
    
    output_data = []
    total_api_calls = 0
    
    for i, entry in enumerate(curriculum_data):
        print(f"\nProcessing entry {i+1}/{len(curriculum_data)}: {entry['substandard_description'][:50]}...")
        
        best_match, score, explanation = find_best_match_gemini_optimized(entry, di_formats, model)
        confidence = determine_confidence_llm(score)
        direct_instruction = format_direct_instruction_llm(best_match)
        
        output_entry = {
            'grade': entry['grade'],
            'substandard_description': entry['substandard_description'],
            'substandard_id': entry['substandard_id'],
            'direct_instructions': direct_instruction,
            'match_confidence': confidence,
            'similarity_score': round(score, 3),
            'llm_explanation': explanation
        }
        
        output_data.append(output_entry)
        
        # Add a small delay to avoid rate limiting
        time.sleep(0.1)
        
        # Save progress every 10 entries (more frequent updates)
        if (i + 1) % 10 == 0:
            print(f"Progress: {i+1}/{len(curriculum_data)} entries processed")
            
            # Write intermediate results
            output_file = 'gemini-extracted-instructions-partial.csv'
            fieldnames = ['grade', 'substandard_description', 'substandard_id', 'direct_instructions', 'match_confidence', 'similarity_score', 'llm_explanation']
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(output_data)
            
            print(f"  Intermediate results saved to {output_file}")
    
    # Write final output CSV
    output_file = 'gemini-extracted-instructions.csv'
    fieldnames = ['grade', 'substandard_description', 'substandard_id', 'direct_instructions', 'match_confidence', 'similarity_score', 'llm_explanation']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_data)
    
    print(f"\nCompleted! Output written to {output_file}")
    
    # Print summary statistics
    confidence_counts = {}
    total_score = 0
    for entry in output_data:
        conf = entry['match_confidence']
        confidence_counts[conf] = confidence_counts.get(conf, 0) + 1
        total_score += entry['similarity_score']
    
    avg_score = total_score / len(output_data) if output_data else 0
    
    print("\nConfidence Distribution:")
    for conf, count in sorted(confidence_counts.items()):
        print(f"  {conf}: {count} entries")
    
    print(f"\nAverage Similarity Score: {avg_score:.3f}")

if __name__ == "__main__":
    main()






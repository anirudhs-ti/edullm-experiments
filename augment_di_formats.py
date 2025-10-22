#!/usr/bin/env python3
"""
Script to augment di_formats.json with:
A. Format mappings for each sequence based on existing format-to-sequence mappings
B. Grade-based skill summaries generated using Gemini-2.5-flash
"""

import json
import pandas as pd
import google.generativeai as genai
import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_gemini(api_key: str):
    """Initialize Gemini model"""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.5-flash')

def load_di_formats(filepath: str) -> Dict:
    """Load the di_formats.json file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Loaded di_formats.json with {len(data['skills'])} skills")
        return data
    except Exception as e:
        logger.error(f"Error loading di_formats.json: {e}")
        return {}

def load_format_mappings(filepath: str) -> pd.DataFrame:
    """Load format mappings from enhanced_llm_instructions.csv"""
    try:
        df = pd.read_csv(filepath)
        logger.info(f"Loaded format mappings: {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Error loading format mappings: {e}")
        return pd.DataFrame()

def extract_format_number(direct_instructions: str) -> Optional[str]:
    """Extract format number from direct instructions"""
    import re
    match = re.search(r'Format (\d+\.\d+)', direct_instructions)
    return match.group(1) if match else None

def create_format_mapping(df: pd.DataFrame) -> Dict[str, str]:
    """Create mapping from substandard_id to format number"""
    format_mapping = {}
    
    for _, row in df.iterrows():
        substandard_id = row['substandard_id']
        direct_instructions = str(row['direct_instructions'])
        format_num = extract_format_number(direct_instructions)
        
        if format_num:
            format_mapping[substandard_id] = format_num
            logger.debug(f"Mapped {substandard_id} -> Format {format_num}")
    
    logger.info(f"Created format mapping for {len(format_mapping)} substandards")
    return format_mapping

def augment_sequences_with_formats(data: Dict, format_mapping: Dict[str, str]) -> Dict:
    """Augment sequences with format references based on existing format-to-sequence mappings"""
    augmented_data = data.copy()
    
    total_skills = len(augmented_data['skills'])
    skill_count = 0
    total_mappings_created = 0
    
    for skill_name, skill_data in augmented_data['skills'].items():
        skill_count += 1
        logger.info(f"Processing skill {skill_count}/{total_skills}: {skill_name}")
        
        # Step 1: Initialize all sequences with empty related_formats list
        # Remove old format_number and format_title fields if they exist
        for progression in skill_data.get('progression', []):
            for sequence_item in progression['sequence']:
                # Remove old singular fields if they exist
                sequence_item.pop('format_number', None)
                sequence_item.pop('format_title', None)
                # Initialize new list field
                sequence_item['related_formats'] = []
        
        # Step 2: Iterate through formats and populate sequences
        formats_list = skill_data.get('formats', [])
        logger.debug(f"  Found {len(formats_list)} formats for {skill_name}")
        
        for format_item in formats_list:
            format_number = format_item.get('format_number')
            format_title = format_item.get('title')
            format_grade = format_item.get('grade')
            sequence_numbers = format_item.get('sequence_numbers', [])
            
            if not format_number or format_grade is None or not sequence_numbers:
                logger.debug(f"  Skipping incomplete format: {format_number}")
                continue
            
            # For each sequence number referenced by this format
            for seq_num in sequence_numbers:
                # Find the matching sequence in progression
                for progression in skill_data.get('progression', []):
                    if progression['grade'] == format_grade:
                        for sequence_item in progression['sequence']:
                            if sequence_item['sequence_number'] == seq_num:
                                # Append format info to this sequence's related_formats list
                                format_ref = {
                                    "format_number": format_number,
                                    "format_title": format_title
                                }
                                sequence_item['related_formats'].append(format_ref)
                                total_mappings_created += 1
                                logger.debug(f"    Mapped Format {format_number} to Grade {format_grade}, Seq {seq_num}")
        
        # Count how many sequences got formats
        sequences_with_formats = 0
        sequences_without_formats = 0
        for progression in skill_data.get('progression', []):
            for sequence_item in progression['sequence']:
                if sequence_item['related_formats']:
                    sequences_with_formats += 1
                else:
                    sequences_without_formats += 1
        
        logger.info(f"  Completed {skill_name}: {sequences_with_formats} sequences mapped, {sequences_without_formats} unmapped")
    
    logger.info(f"Format augmentation complete: {total_mappings_created} format-to-sequence mappings created")
    return augmented_data

def create_skill_summary_prompt(skill_name: str, skill_data: Dict, grades_list: List[int]) -> str:
    """Create prompt for generating grade-based skill summary"""
    
    # Collect all progressions and their sequences
    progressions_text = ""
    for progression in skill_data['progression']:
        grade = progression['grade']
        sequences_text = ""
        
        for seq in progression['sequence']:
            sequences_text += f"  - Sequence {seq['sequence_number']}: {seq['problem_type']}\n"
            if seq.get('example_questions'):
                sequences_text += f"    Examples: {', '.join(seq['example_questions'][:2])}\n"
        
        progressions_text += f"Grade {grade}:\n{sequences_text}\n"
    
    # Create expected grade keys for the output
    expected_keys = ", ".join([f'"grade_{g}"' for g in grades_list])
    
    prompt = f"""
You are an expert educational content specialist. Create a separate summary for the skill "{skill_name}" FOR EACH GRADE.

For each grade, explain:
1. The specific types of tasks/progressions covered in that grade
2. The instructional formats used at that grade level
3. What students are learning and how it relates to the overall skill

SKILL DATA:
{progressions_text}

IMPORTANT: You must provide a summary for EACH grade present in the data. Return a JSON object with the structure:
{{
  "grade_summaries": {{
    "grade_0": "Summary for grade 0...",
    "grade_1": "Summary for grade 1...",
    ...
  }}
}}

The keys must be: {expected_keys}

Each summary should be 2-4 sentences that clearly describe what students learn about "{skill_name}" in that specific grade.
"""
    
    return prompt

def generate_skill_summary(model, skill_name: str, skill_data: Dict) -> Optional[Dict[str, str]]:
    """Generate grade-based skill summary using Gemini with JSON output"""
    try:
        # Get list of grades for this skill
        grades_list = [progression['grade'] for progression in skill_data['progression']]
        
        prompt = create_skill_summary_prompt(skill_name, skill_data, grades_list)
        
        # Use JSON mode without strict schema enforcement (since Dict keys are dynamic)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        
        if response.text:
            # Parse the JSON response
            parsed_response = json.loads(response.text)
            grade_summaries = parsed_response.get('grade_summaries', {})
            
            # Validate that we got summaries for all expected grades
            expected_keys = {f"grade_{g}" for g in grades_list}
            actual_keys = set(grade_summaries.keys())
            
            if expected_keys != actual_keys:
                logger.warning(f"Expected grades {expected_keys} but got {actual_keys} for {skill_name}")
            
            logger.info(f"Generated summaries for {len(grade_summaries)} grades for skill: {skill_name}")
            return grade_summaries
        else:
            logger.warning(f"No response generated for skill: {skill_name}")
            return None
            
    except Exception as e:
        logger.error(f"Error generating summary for {skill_name}: {e}")
        return None

def add_skill_summaries(data: Dict, model) -> Dict:
    """Add grade-based skill summaries to the data"""
    augmented_data = data.copy()
    
    total_skills = len(augmented_data['skills'])
    skill_count = 0
    successful_summaries = 0
    
    for skill_name, skill_data in augmented_data['skills'].items():
        skill_count += 1
        logger.info(f"Generating summary {skill_count}/{total_skills} for skill: {skill_name}")
        
        grade_summaries = generate_skill_summary(model, skill_name, skill_data)
        
        if grade_summaries:
            # Store as dictionary with grade keys
            skill_data['grade_based_summary'] = grade_summaries
            successful_summaries += 1
            logger.info(f"  ✓ Successfully added summaries for {len(grade_summaries)} grades for {skill_name}")
        else:
            skill_data['grade_based_summary'] = {}
            logger.warning(f"  ✗ Failed to generate summary for {skill_name}")
    
    logger.info(f"Skill summary generation complete: {successful_summaries}/{total_skills} successful")
    return augmented_data

def save_augmented_data(data: Dict, output_filepath: str):
    """Save the augmented data to a new file"""
    try:
        # Update metadata
        existing_version = data['metadata'].get('augmentation_version', '0.0.0')
        data['metadata']['last_updated'] = datetime.now().isoformat()
        data['metadata']['augmentation_version'] = "2.0.0"  # Increment for format mapping update
        
        # Preserve existing augmentation summary and add format mapping info
        if 'augmentation_summary' not in data['metadata']:
            data['metadata']['augmentation_summary'] = {}
        
        data['metadata']['augmentation_summary']['format_mappings_added'] = True
        data['metadata']['augmentation_summary']['total_skills_processed'] = len(data['skills'])
        data['metadata']['augmentation_summary']['previous_version'] = existing_version
        
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved augmented data to {output_filepath}")
        
    except Exception as e:
        logger.error(f"Error saving augmented data: {e}")

def main():
    """Main function to run the format mapping process"""
    
    # Configuration
    DI_FORMATS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/data/di_formats_augmented.json"
    OUTPUT_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/data/di_formats_with_mappings.json"
    
    logger.info("=" * 60)
    logger.info("Starting Format-to-Sequence Mapping Process")
    logger.info("=" * 60)
    
    # Load data
    logger.info("Loading data...")
    di_formats_data = load_di_formats(DI_FORMATS_FILE)
    if not di_formats_data:
        logger.error("Failed to load di_formats_augmented.json")
        return
    
    # Note: We're using internal format-to-sequence mappings from the formats array
    # The format_mappings_df and CSV file are not needed for this process
    logger.info("Using internal format-to-sequence mappings from formats array")
    
    # Augment data with format mappings
    logger.info("Augmenting sequences with format references...")
    augmented_data = augment_sequences_with_formats(di_formats_data, {})
    
    # Save results
    logger.info("Saving augmented data...")
    save_augmented_data(augmented_data, OUTPUT_FILE)
    
    logger.info("=" * 60)
    logger.info("Format mapping complete!")
    logger.info(f"Output saved to: {OUTPUT_FILE}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()

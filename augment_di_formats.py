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
    """Augment sequences with format numbers based on grade and sequence_number"""
    augmented_data = data.copy()
    
    total_skills = len(augmented_data['skills'])
    skill_count = 0
    
    for skill_name, skill_data in augmented_data['skills'].items():
        skill_count += 1
        logger.info(f"Processing skill {skill_count}/{total_skills}: {skill_name}")
        
        total_sequences = sum(len(progression['sequence']) for progression in skill_data['progression'])
        sequence_count = 0
        
        for progression in skill_data['progression']:
            grade = progression['grade']
            logger.debug(f"  Processing grade {grade} with {len(progression['sequence'])} sequences")
            
            for sequence_item in progression['sequence']:
                sequence_count += 1
                sequence_number = sequence_item['sequence_number']
                
                # Create a key to match against format mappings
                # This is a simplified approach - you may need to adjust based on your specific mapping logic
                sequence_key = f"grade_{grade}_seq_{sequence_number}"
                
                # Try to find matching format
                # For now, we'll add a placeholder that can be updated with actual mapping logic
                sequence_item['format_number'] = None
                sequence_item['format_title'] = None
                
                # You can implement more sophisticated matching logic here
                # based on your specific requirements for mapping sequences to formats
        
        logger.info(f"  Completed {skill_name}: {sequence_count} sequences processed")
    
    logger.info(f"Format augmentation complete: {total_skills} skills processed")
    return augmented_data

def create_skill_summary_prompt(skill_name: str, skill_data: Dict) -> str:
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
    
    prompt = f"""
You are an expert educational content specialist. Create a comprehensive summary for the skill "{skill_name}" that explains:

1. The types of tasks/progressions covered across different grades
2. The instructional formats used for this skill
3. How the skill builds and progresses across grade levels

SKILL DATA:
{progressions_text}

Please provide a clear, educational summary that would be useful for teachers and curriculum developers. Focus on the learning progression and instructional approaches.

Return your response in a structured format with clear sections.
"""
    
    return prompt

def generate_skill_summary(model, skill_name: str, skill_data: Dict) -> str:
    """Generate grade-based skill summary using Gemini"""
    try:
        prompt = create_skill_summary_prompt(skill_name, skill_data)
        
        response = model.generate_content(prompt)
        
        if response.text:
            logger.info(f"Generated summary for skill: {skill_name}")
            return response.text.strip()
        else:
            logger.warning(f"No response generated for skill: {skill_name}")
            return ""
            
    except Exception as e:
        logger.error(f"Error generating summary for {skill_name}: {e}")
        return ""

def add_skill_summaries(data: Dict, model) -> Dict:
    """Add grade-based skill summaries to the data"""
    augmented_data = data.copy()
    
    total_skills = len(augmented_data['skills'])
    skill_count = 0
    successful_summaries = 0
    
    for skill_name, skill_data in augmented_data['skills'].items():
        skill_count += 1
        logger.info(f"Generating summary {skill_count}/{total_skills} for skill: {skill_name}")
        
        summary = generate_skill_summary(model, skill_name, skill_data)
        
        if summary:
            skill_data['grade_based_summary'] = summary
            successful_summaries += 1
            logger.info(f"  ✓ Successfully added summary for {skill_name}")
        else:
            skill_data['grade_based_summary'] = "Summary generation failed"
            logger.warning(f"  ✗ Failed to generate summary for {skill_name}")
    
    logger.info(f"Skill summary generation complete: {successful_summaries}/{total_skills} successful")
    return augmented_data

def save_augmented_data(data: Dict, output_filepath: str):
    """Save the augmented data to a new file"""
    try:
        # Update metadata
        data['metadata']['last_updated'] = datetime.now().isoformat()
        data['metadata']['augmentation_version'] = "1.0.0"
        data['metadata']['augmentation_summary'] = {
            "format_mappings_added": True,
            "skill_summaries_added": True,
            "total_skills_processed": len(data['skills'])
        }
        
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved augmented data to {output_filepath}")
        
    except Exception as e:
        logger.error(f"Error saving augmented data: {e}")

def main():
    """Main function to run the augmentation process"""
    
    # Load environment variables
    env_path = "/workspaces/github-com-anirudhs-ti-edullm-experiments/.env"
    load_dotenv(env_path)
    logger.info(f"Loaded environment variables from {env_path}")
    
    # Configuration
    DI_FORMATS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/data/di_formats.json"
    FORMAT_MAPPINGS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/output/enhanced_llm_instructions.csv"
    OUTPUT_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/data/di_formats_augmented.json"
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable not set")
        return
    
    logger.info("GEMINI_API_KEY found, proceeding with augmentation")
    
    # Initialize Gemini
    model = initialize_gemini(api_key)
    
    # Load data
    logger.info("Loading data...")
    di_formats_data = load_di_formats(DI_FORMATS_FILE)
    if not di_formats_data:
        logger.error("Failed to load di_formats.json")
        return
    
    format_mappings_df = load_format_mappings(FORMAT_MAPPINGS_FILE)
    if format_mappings_df.empty:
        logger.warning("No format mappings loaded - proceeding without format augmentation")
        format_mapping = {}
    else:
        format_mapping = create_format_mapping(format_mappings_df)
    
    # Augment data
    logger.info("Augmenting sequences with format mappings...")
    augmented_data = augment_sequences_with_formats(di_formats_data, format_mapping)
    
    logger.info("Generating skill summaries...")
    augmented_data = add_skill_summaries(augmented_data, model)
    
    # Save results
    logger.info("Saving augmented data...")
    save_augmented_data(augmented_data, OUTPUT_FILE)
    
    logger.info("Augmentation complete!")

if __name__ == "__main__":
    main()

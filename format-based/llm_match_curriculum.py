#!/usr/bin/env python3
"""
LLM-based matching between curriculum.csv and all_formats_extracted.csv using Gemini 2.0 Flash Lite
Generates a report similar to tfidf-extracted-instructions.csv format but with LLM-based scaffolding assessment
"""

import pandas as pd
import numpy as np
import google.generativeai as genai
import os
import concurrent.futures
import time
import json
from typing import List, Tuple, Dict, Optional, Literal
import logging
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('llm_matching.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Pydantic models for schema validation
class FormatRanking(BaseModel):
    """Schema for individual format ranking"""
    format_number: int = Field(..., ge=1, le=30, description="Format number in the batch (1-30)")
    title: str = Field(..., min_length=1, description="Title of the instruction format")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score between 0.0 and 1.0")
    explanation: str = Field(..., min_length=10, description="Brief explanation of the match quality")

class BestMatch(BaseModel):
    """Schema for the best match result"""
    format_number: int = Field(..., ge=1, le=30, description="Format number in the batch (1-30)")
    title: str = Field(..., min_length=1, description="Title of the instruction format")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score between 0.0 and 1.0")
    explanation: str = Field(..., min_length=20, description="Detailed explanation of why this instruction would be good scaffolding")

class LLMBatchResponse(BaseModel):
    """Schema for the complete LLM batch response"""
    best_match: BestMatch = Field(..., description="The best matching format")
    rankings: List[FormatRanking] = Field(..., min_length=1, max_length=30, description="Ranked list of all formats in the batch")
    
    class Config:
        """Pydantic configuration"""
        validate_assignment = True
        use_enum_values = True

# ---------------- Skill selection schemas ----------------
class SkillChoice(BaseModel):
    """Schema for a top skill choice"""
    skill: str = Field(..., min_length=1, description="Skill name exactly as provided")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Score 0.0-1.0 for skill match strength")
    explanation: str = Field(..., min_length=10, description="Why this skill matches the substandard")

class SkillSelectionResponse(BaseModel):
    """Schema for LLM skill selection output"""
    top_skills: List[SkillChoice] = Field(..., min_length=1, max_length=2, description="Top 1-2 skills")

    class Config:
        validate_assignment = True
        use_enum_values = True

def score_to_confidence(score: float) -> str:
    """Convert numeric score to confidence level deterministically"""
    if score >= 0.8:
        return "High"
    elif score >= 0.6:
        return "Medium-High"
    elif score >= 0.4:
        return "Medium"
    elif score >= 0.2:
        return "Medium-Low"
    elif score >= 0.1:
        return "Low"
    else:
        return "Very Low"

def initialize_gemini(api_key: str):
    """Initialize Gemini model"""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.5-flash')

def load_curriculum_data(filepath: str) -> pd.DataFrame:
    """Load curriculum data from CSV and filter for 3rd grade"""
    try:
        df = pd.read_csv(filepath)
        # Filter for 3rd grade only
        df_grade3 = df[df['grade'] == 3].reset_index(drop=True)
        logger.info(f"Loaded curriculum data: {len(df)} total rows, {len(df_grade3)} grade 3 rows")
        return df_grade3
    except Exception as e:
        logger.error(f"Error loading curriculum data: {e}")
        return pd.DataFrame()

def load_formats_data(filepath: str) -> pd.DataFrame:
    """Load formats data from CSV"""
    try:
        df = pd.read_csv(filepath)
        logger.info(f"Loaded formats data: {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Error loading formats data: {e}")
        return pd.DataFrame()

def create_skill_selection_prompt(substandard_description: str, available_skills: List[str]) -> str:
    """Create prompt to select top 1-2 skills for the substandard"""
    skills_text = "\n".join(f"- {s}" for s in available_skills)
    prompt = f"""
You are an expert educational assessment specialist. Select the top 1-2 skills that best match the given substandard.

SUBSTANDARD:
{substandard_description}

AVAILABLE SKILLS (choose only from this list):
{skills_text}

Return ONLY valid JSON with no prose before or after, in exactly this structure:
{{
  "top_skills": [
    {{ "skill": "Skill Name", "similarity_score": 0.0-1.0, "explanation": "why this skill" }}
  ]
}}

Rules:
- skill must be exactly one of the provided names
- provide 1 or 2 skills max
- scores 0.0-1.0 only
"""
    return prompt

def select_top_skills(model, substandard_description: str, formats_df: pd.DataFrame) -> List[str]:
    """Use LLM to select top 1-2 skills that match the substandard."""
    # Collect available skills from formats
    if 'skill' not in formats_df.columns:
        logger.warning("Formats data has no 'skill' column; skipping skill selection")
        return []
    available_skills = sorted(list({s for s in formats_df['skill'].dropna().unique()}))
    if not available_skills:
        return []

    prompt = create_skill_selection_prompt(substandard_description, available_skills)
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        if '```json' in response_text:
            js = response_text.split('```json',1)[1].split('```',1)[0].strip()
        elif '{' in response_text and '}' in response_text:
            js = response_text[response_text.find('{'):response_text.rfind('}')+1]
        else:
            js = response_text
        raw = json.loads(js)
        validated = SkillSelectionResponse(**raw)
        # Log the LLM-selected skills with scores and brief explanations
        for choice in validated.top_skills:
            logger.info(
                f"  Skill candidate: {choice.skill} (score: {choice.similarity_score})\n"
                f"    Reason: {choice.explanation[:180]}..."
            )
        chosen_skills = []
        for choice in validated.top_skills:
            if choice.skill in available_skills:
                chosen_skills.append(choice.skill)
        # Ensure uniqueness and at most 2
        return list(dict.fromkeys(chosen_skills))[:2]
    except Exception as e:
        logger.warning(f"Skill selection failed, using heuristic fallback: {e}")
        # Heuristic: pick skills with highest term overlap with substandard
        sub_l = substandard_description.lower()
        def skill_score(skill: str) -> int:
            tokens = [t for t in skill.lower().replace('-', ' ').split() if len(t) > 2]
            return sum(1 for t in tokens if t in sub_l)
        scored = sorted(available_skills, key=skill_score, reverse=True)
        fallback_selected = scored[:2]
        logger.info(f"  Fallback selected skills: {', '.join(fallback_selected)}")
        return fallback_selected

def create_batch_scaffolding_prompt(substandard_description: str, format_batch: List[Dict]) -> str:
    """Create prompt for assessing scaffolding quality of multiple formats at once"""
    
    # Format the batch of instructions
    format_descriptions = []
    for i, format_item in enumerate(format_batch, 1):
        format_descriptions.append(f"""
FORMAT {i}: {format_item['title']}
Content: {format_item['flattened_content'][:500]}...
""")
    
    formats_text = "\n".join(format_descriptions)
    
    prompt = f"""
You are an expert educational assessment specialist. Your task is to evaluate which of the provided direct instruction formats would serve as the BEST scaffolding for a specific curriculum substandard.

CURRICULUM SUBSTANDARD:
{substandard_description}

AVAILABLE INSTRUCTION FORMATS:
{formats_text}

Please assess each format's scaffolding quality by considering:
1. Conceptual alignment: Does the instruction address the same mathematical concepts?
2. Skill progression: Does the instruction build appropriate prerequisite skills?
3. Cognitive load: Is the instruction appropriately challenging for 3rd grade students?
4. Instructional approach: Does the teaching method support learning the substandard?
5. Content relevance: How directly does the instruction relate to the substandard?

Return ONLY valid JSON with no prose before or after, in exactly this structure:
{{
    "best_match": {{
        "format_number": 1,
        "title": "Format Title",
        "similarity_score": 0.0-1.0,
        "explanation": "Detailed explanation of why this instruction would be good scaffolding for the substandard"
    }},
    "rankings": [
        {{
            "format_number": 1,
            "title": "Format Title",
            "similarity_score": 0.0-1.0,
            "explanation": "Brief explanation of the match quality"
        }}
    ]
}}

IMPORTANT: Provide similarity scores as decimal numbers between 0.0 and 1.0, where:
- 0.9-1.0 = Excellent match
- 0.7-0.8 = Very good match
- 0.5-0.6 = Good match
- 0.3-0.4 = Fair match
- 0.1-0.2 = Poor match
- 0.0-0.1 = Very poor match
"""
    return prompt

def assess_batch_scaffolding_with_llm(model, substandard_description: str, format_batch: List[Dict]) -> LLMBatchResponse:
    """Use LLM to assess scaffolding quality of multiple formats at once with schema validation"""
    try:
        prompt = create_batch_scaffolding_prompt(substandard_description, format_batch)
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Parse JSON response
        response_text = response.text.strip()
        
        # Try to extract JSON from response
        if '```json' in response_text:
            json_start = response_text.find('```json') + 7
            json_end = response_text.find('```', json_start)
            json_text = response_text[json_start:json_end].strip()
        elif '{' in response_text and '}' in response_text:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_text = response_text[json_start:json_end]
        else:
            json_text = response_text
        
        try:
            # Parse JSON and validate with Pydantic schema
            raw_result = json.loads(json_text)
            validated_result = LLMBatchResponse(**raw_result)
            
            logger.debug(f"Successfully validated LLM response schema")
            return validated_result
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {response_text[:200]}...")
            logger.warning(f"JSON decode error: {e}")
            
        except ValidationError as e:
            logger.warning(f"Schema validation failed: {e}")
            logger.warning(f"Raw response: {response_text[:200]}...")
            
        # Fallback response with schema validation
        fallback_data = {
            "best_match": {
                "format_number": 1,
                "title": format_batch[0]['title'],
                "similarity_score": 0.3,
                "explanation": "Failed to parse LLM response - using fallback"
            },
            "rankings": [
                {
                    "format_number": 1,
                    "title": format_batch[0]['title'],
                    "similarity_score": 0.3,
                    "explanation": "Fallback ranking due to parsing error"
                }
            ]
        }
        
        try:
            return LLMBatchResponse(**fallback_data)
        except ValidationError as e:
            logger.error(f"Even fallback response failed validation: {e}")
            raise
            
    except Exception as e:
        logger.error(f"Error in LLM batch assessment: {e}")
        
        # Create a minimal valid response
        minimal_data = {
            "best_match": {
                "format_number": 1,
                "title": format_batch[0]['title'] if format_batch else "Unknown Format",
                "similarity_score": 0.1,
                "explanation": f"Error during assessment: {str(e)}"
            },
            "rankings": [
                {
                    "format_number": 1,
                    "title": format_batch[0]['title'] if format_batch else "Unknown Format",
                    "similarity_score": 0.1,
                    "explanation": "Assessment failed due to error"
                }
            ]
        }
        
        try:
            return LLMBatchResponse(**minimal_data)
        except ValidationError as validation_error:
            logger.error(f"Minimal response also failed validation: {validation_error}")
            raise RuntimeError(f"Unable to create valid response: {validation_error}")

def find_best_match_for_substandard(model, substandard_row: pd.Series, formats_df: pd.DataFrame) -> Dict:
    """Find the best matching format for a single substandard using batched comparisons.
    Supports limited parallelization via MAX_PARALLEL_BATCHES env var (default: 1)."""
    substandard_description = substandard_row['substandard_description']
    substandard_id = substandard_row['substandard_id']
    
    logger.info(f"Processing substandard: {substandard_id}")
    logger.info(f"Description: {substandard_description[:100]}...")
    
    best_match = None
    best_score = 0.0
    best_assessment = None
    
    # Process formats in batches of 30
    batch_size = 30
    # If possible, restrict formats to LLM-selected skills
    total_formats = len(formats_df)
    # Optional skill pre-filtering
    try:
        selected_skills = select_top_skills(model, substandard_description, formats_df)
        if selected_skills:
            logger.info(f"  Selected skills: {', '.join(selected_skills)}")
            filtered_df = formats_df[formats_df['skill'].isin(selected_skills)]
            if not filtered_df.empty:
                formats_df = filtered_df.reset_index(drop=True)
                total_formats = len(formats_df)
                # Log per skill format counts for transparency
                per_skill_counts = formats_df['skill'].value_counts().to_dict()
                counts_str = ", ".join([f"{k}: {v}" for k, v in per_skill_counts.items()])
                logger.info(f"  Filtered formats to selected skills: {total_formats} remaining ({counts_str})")
    except Exception as e:
        logger.warning(f"  Skill filtering skipped due to error: {e}")

    num_batches = (total_formats + batch_size - 1) // batch_size
    
    logger.info(f"  Processing {total_formats} formats in {num_batches} batches of {batch_size}")
    
    # Parallelization settings (disabled per request)
    max_parallel = 1
    
    def process_one_batch(batch_num: int):
        start_idx_local = batch_num * batch_size
        end_idx_local = min(start_idx_local + batch_size, total_formats)
        batch_formats_local = formats_df.iloc[start_idx_local:end_idx_local]
        logger.info(f"  Batch {batch_num+1}/{num_batches}: formats {start_idx_local+1}-{end_idx_local}")
        format_batch_local = []
        for _, format_row_local in batch_formats_local.iterrows():
            format_batch_local.append({
                'title': format_row_local['title'],
                'flattened_content': format_row_local['flattened_content']
            })
        assessment = assess_batch_scaffolding_with_llm(model, substandard_description, format_batch_local)
        best_local = assessment.best_match
        global_index = start_idx_local + best_local.format_number - 1
        return {
            'batch_num': batch_num,
            'best_title': best_local.title,
            'best_score': best_local.similarity_score,
            'best_index': global_index,
            'assessment': best_local,
            'rankings_count': len(assessment.rankings)
        }

    # Execute batches with limited parallelism
    batch_indices = list(range(num_batches))
    if max_parallel == 1:
        for b in batch_indices:
            result_local = process_one_batch(b)
            logger.info(f"    Best in batch: {result_local['best_title']} (confidence: {score_to_confidence(result_local['best_score'])}, score: {result_local['best_score']})")
            if result_local['best_score'] > best_score:
                best_score = result_local['best_score']
                best_match = formats_df.iloc[result_local['best_index']]
                best_assessment = result_local['assessment']
            logger.info(f"    Batch rankings: {result_local['rankings_count']} formats ranked")
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
            for result_local in executor.map(process_one_batch, batch_indices):
                logger.info(f"    Best in batch: {result_local['best_title']} (confidence: {score_to_confidence(result_local['best_score'])}, score: {result_local['best_score']})")
                if result_local['best_score'] > best_score:
                    best_score = result_local['best_score']
                    best_match = formats_df.iloc[result_local['best_index']]
                    best_assessment = result_local['assessment']
                logger.info(f"    Batch rankings: {result_local['rankings_count']} formats ranked")
    
    # Create result entry
    if best_match is not None:
        final_confidence = score_to_confidence(best_assessment.similarity_score)
        result = {
            'grade': substandard_row['grade'],
            'substandard_description': substandard_description,
            'substandard_id': substandard_id,
            'direct_instructions': best_match['flattened_content'],
            'match_confidence': final_confidence,
            'similarity_score': round(best_assessment.similarity_score, 3),
            'llm_explanation': best_assessment.explanation
        }
        
        logger.info(f"  🎯 Overall best match: {best_match['title']} (confidence: {final_confidence}, score: {best_score:.3f})")
        return result
    else:
        logger.warning(f"  No suitable match found for substandard {substandard_id}")
        return None

def save_progress(results: List[Dict], output_file: str, current_index: int, total_count: int):
    """Save current progress to file"""
    try:
        # Create DataFrame from current results
        results_df = pd.DataFrame(results)
        
        # Save to CSV
        results_df.to_csv(output_file, index=False)
        
        logger.info(f"Progress saved: {len(results)}/{total_count} substandards completed")
        logger.info(f"Results saved to: {output_file}")
        
    except Exception as e:
        logger.error(f"Error saving progress: {e}")

def main():
    """Main function to run LLM-based matching"""
    
    # Load environment variables from .env file
    load_dotenv()
    
    # File paths
    curriculum_file = "/workspace/edullm-experiments/curriculum.csv"
    formats_file = "/workspace/edullm-experiments/all_formats_extracted.csv"
    output_file = "/workspace/edullm-experiments/llm-extracted-instructions.csv"
    
    # Get API key from environment
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable not set")
        return
    
    logger.info("Starting LLM-based matching process...")
    logger.info(f"Timestamp: {datetime.now()}")
    
    # Initialize Gemini model
    try:
        model = initialize_gemini(api_key)
        logger.info("Gemini model initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {e}")
        return
    
    # Load data
    curriculum_df = load_curriculum_data(curriculum_file)
    formats_df = load_formats_data(formats_file)
    
    if curriculum_df.empty or formats_df.empty:
        logger.error("Error: Could not load required data files")
        return
    
    logger.info(f"Processing {len(curriculum_df)} grade 3 substandards against {len(formats_df)} instruction formats")
    
    # Process each substandard
    results = []
    total_count = len(curriculum_df)
    
    for index, substandard_row in curriculum_df.iterrows():
        logger.info(f"\n{'='*80}")
        logger.info(f"PROCESSING SUBSTANDARD {index+1}/{total_count}")
        logger.info(f"{'='*80}")
        
        try:
            # Find best match for this substandard
            result = find_best_match_for_substandard(model, substandard_row, formats_df)
            
            if result:
                results.append(result)
                logger.info(f"✓ Successfully processed substandard {index+1}")
            else:
                logger.warning(f"✗ Failed to find match for substandard {index+1}")
            
            # Save progress after every 10 substandards
            if (index + 1) % 10 == 0:
                save_progress(results, output_file, index, total_count)

            # No delay between calls (user-requested)
            time.sleep(0)
            
        except Exception as e:
            logger.error(f"Error processing substandard {index+1}: {e}")
            continue
    
    # Final save
    if results:
        results_df = pd.DataFrame(results)
        results_df.to_csv(output_file, index=False)
        
        logger.info(f"\n{'='*80}")
        logger.info("LLM MATCHING COMPLETED!")
        logger.info(f"{'='*80}")
        logger.info(f"Total matches found: {len(results_df)}")
        logger.info(f"Results saved to: {output_file}")
        
        # Print summary statistics
        confidence_counts = results_df['match_confidence'].value_counts()
        logger.info("\nConfidence distribution:")
        for confidence, count in confidence_counts.items():
            logger.info(f"  {confidence}: {count}")
        
        logger.info(f"\nAverage similarity score: {results_df['similarity_score'].mean():.3f}")
        logger.info(f"Max similarity score: {results_df['similarity_score'].max():.3f}")
        logger.info(f"Min similarity score: {results_df['similarity_score'].min():.3f}")
        
    else:
        logger.error("No results generated")

if __name__ == "__main__":
    main()

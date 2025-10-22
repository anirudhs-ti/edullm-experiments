#!/usr/bin/env python3
"""
Map curriculum substandards to DI format sequences using LLM-based matching.
Two-phase approach:
  Phase 1: Select top 1-2 skills that match the substandard
  Phase 2: For each skill, rate sequences as EXCELLENT/FAIR/POOR/NON-EXISTENT
Only EXCELLENT matches are kept in the final output.
"""

import pandas as pd
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Optional
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from pydantic import BaseModel, Field, ValidationError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('curriculum_sequence_mapping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Schemas
# ============================================================================

class SkillMatch(BaseModel):
    """Schema for a skill match in Phase 1"""
    skill_name: str = Field(..., min_length=1, description="Name of the skill")
    match_score: float = Field(..., ge=0.0, le=1.0, description="Match score 0.0-1.0")
    reasoning: str = Field(..., min_length=10, description="Why this skill matches")

class Phase1Response(BaseModel):
    """Schema for Phase 1: Skill Selection"""
    selected_skills: List[SkillMatch] = Field(..., min_length=0, max_length=2, description="Top 1-2 skills")
    overall_reasoning: str = Field(..., min_length=10, description="Overall selection reasoning")

    class Config:
        validate_assignment = True

class SequenceRating(BaseModel):
    """Schema for rating a single sequence"""
    sequence_number: int = Field(..., ge=1, description="Sequence number")
    problem_type: str = Field(..., min_length=1, description="Problem type description")
    match_quality: str = Field(..., description="EXCELLENT, FAIR, POOR, or NON-EXISTENT")
    explanation: str = Field(..., min_length=20, description="Detailed explanation of the rating")

    class Config:
        validate_assignment = True

class Phase2Response(BaseModel):
    """Schema for Phase 2: Sequence Rating"""
    sequence_ratings: List[SequenceRating] = Field(..., description="Ratings for all sequences")
    excellent_sequences: List[int] = Field(..., description="List of EXCELLENT sequence numbers")
    no_excellent_explanation: Optional[str] = Field(None, description="Explanation if no EXCELLENT matches found")

    class Config:
        validate_assignment = True

# ============================================================================
# Helper Functions
# ============================================================================

def initialize_gemini(api_key: str):
    """Initialize Gemini 2.5 Flash model"""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.5-flash')

def load_curriculum_csv(filepath: str, grade: int = 3) -> pd.DataFrame:
    """Load curriculum CSV and filter by grade"""
    try:
        df = pd.read_csv(filepath)
        df_filtered = df[df['grade'] == grade].reset_index(drop=True)
        logger.info(f"Loaded curriculum: {len(df)} total rows, {len(df_filtered)} grade {grade} rows")
        return df_filtered
    except Exception as e:
        logger.error(f"Error loading curriculum CSV: {e}")
        return pd.DataFrame()

def load_di_formats_json(filepath: str) -> Dict:
    """Load DI formats JSON"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        num_skills = len(data.get('skills', {}))
        logger.info(f"Loaded DI formats JSON: {num_skills} skills")
        return data
    except Exception as e:
        logger.error(f"Error loading DI formats JSON: {e}")
        return {}

def create_output_directory(output_dir: str):
    """Create output directory if it doesn't exist"""
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Output directory ready: {output_dir}")

def load_progress(progress_file: str) -> Dict:
    """Load progress from previous run"""
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r') as f:
                progress = json.load(f)
            logger.info(f"Loaded progress: {len(progress.get('completed', []))} substandards completed")
            return progress
        except Exception as e:
            logger.warning(f"Could not load progress file: {e}")
    return {'completed': [], 'results': []}

def save_progress(progress: Dict, progress_file: str):
    """Save current progress"""
    try:
        with open(progress_file, 'w') as f:
            json.dump(progress, f, indent=2)
        logger.info(f"Progress saved: {len(progress['completed'])} substandards completed")
    except Exception as e:
        logger.error(f"Error saving progress: {e}")

# ============================================================================
# Phase 1: Skill Selection
# ============================================================================

def create_phase1_prompt(grade: int, substandard_desc: str, assessment_boundary: str, 
                         skills_with_summaries: Dict[str, str]) -> str:
    """Create prompt for Phase 1: Skill Selection"""
    
    skills_text = ""
    for i, (skill_name, summary) in enumerate(skills_with_summaries.items(), 1):
        skills_text += f"\n{i}. Skill: \"{skill_name}\"\n"
        skills_text += f"   Grade {grade} Summary: {summary[:400]}...\n"
    
    prompt = f"""You are an expert educational content specialist. Your task is to identify which Direct Instruction math skills best match a curriculum substandard.

CURRICULUM SUBSTANDARD:
Grade: {grade}
Description: {substandard_desc}
Assessment Boundary: {assessment_boundary}

AVAILABLE SKILLS AND THEIR GRADE {grade} SUMMARIES:
{skills_text}

TASK:
Identify the TOP 1 or 2 skills (preferably 1) that best encompass this substandard and assessment boundary.

Return ONLY valid JSON with no prose before or after, in exactly this structure:
{{
  "selected_skills": [
    {{
      "skill_name": "Exact skill name from list above",
      "match_score": 0.0-1.0,
      "reasoning": "Why this skill matches the substandard"
    }}
  ],
  "overall_reasoning": "Brief explanation of the selection strategy"
}}

Rules:
- skill_name must EXACTLY match one of the provided skill names
- Provide 1 or 2 skills maximum (prefer 1 if one is clearly best)
- match_score must be between 0.0 and 1.0
- Consider both the conceptual alignment and assessment boundary constraints
"""
    return prompt

def phase1_select_skills(model, grade: int, substandard_desc: str, assessment_boundary: str,
                         di_data: Dict) -> List[str]:
    """Phase 1: Use LLM to select top 1-2 skills"""
    
    # Build skills with grade-based summaries
    skills_with_summaries = {}
    target_grade_key = f"grade_{grade}"
    
    for skill_name, skill_data in di_data['skills'].items():
        if 'grade_based_summary' in skill_data and target_grade_key in skill_data['grade_based_summary']:
            summary = skill_data['grade_based_summary'][target_grade_key]
            skills_with_summaries[skill_name] = summary
    
    if not skills_with_summaries:
        logger.warning(f"No skills found with grade {grade} summaries")
        return []
    
    logger.info(f"Phase 1: Evaluating {len(skills_with_summaries)} skills for grade {grade}")
    
    prompt = create_phase1_prompt(grade, substandard_desc, assessment_boundary, skills_with_summaries)
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Extract JSON
        if '```json' in response_text:
            json_text = response_text.split('```json', 1)[1].split('```', 1)[0].strip()
        elif '{' in response_text and '}' in response_text:
            json_text = response_text[response_text.find('{'):response_text.rfind('}')+1]
        else:
            json_text = response_text
        
        # Parse and validate
        raw_data = json.loads(json_text)
        validated = Phase1Response(**raw_data)
        
        # Log results
        logger.info(f"  Phase 1 Results: {len(validated.selected_skills)} skills selected")
        for skill_match in validated.selected_skills:
            logger.info(f"    ✓ {skill_match.skill_name} (score: {skill_match.match_score:.2f})")
            logger.info(f"      Reasoning: {skill_match.reasoning[:150]}...")
        
        # Return skill names
        selected_names = [s.skill_name for s in validated.selected_skills]
        return selected_names
        
    except Exception as e:
        logger.error(f"Phase 1 failed: {e}")
        logger.error(f"Response text: {response_text[:500]}...")
        return []

# ============================================================================
# Phase 2: Sequence Rating
# ============================================================================

def create_phase2_prompt(grade: int, substandard_desc: str, assessment_boundary: str,
                         skill_name: str, sequences: List[Dict]) -> str:
    """Create prompt for Phase 2: Sequence Rating"""
    
    sequences_text = ""
    for seq in sequences:
        sequences_text += f"\nSequence #{seq['sequence_number']}:\n"
        sequences_text += f"  Problem Type: {seq['problem_type']}\n"
        sequences_text += f"  Example Questions: {seq['example_questions']}\n"
        if seq.get('visual_aids'):
            sequences_text += f"  Visual Aids: {seq['visual_aids']}\n"
    
    prompt = f"""You are an expert educational content specialist. Your task is to rate how well each Direct Instruction sequence matches a curriculum substandard.

CURRICULUM SUBSTANDARD:
Grade: {grade}
Description: {substandard_desc}
Assessment Boundary: {assessment_boundary}

SELECTED SKILL: "{skill_name}"

AVAILABLE SEQUENCES FOR GRADE {grade}:
{sequences_text}

TASK:
Rate each sequence using these quality levels:
- EXCELLENT: Perfect match - directly addresses the substandard and respects all assessment boundary constraints
- FAIR: Partial match - addresses some aspects but may miss key elements or violate some constraints
- POOR: Weak match - tangentially related but not suitable for this specific substandard
- NON-EXISTENT: No meaningful connection to the substandard

Return ONLY valid JSON with no prose before or after, in exactly this structure:
{{
  "sequence_ratings": [
    {{
      "sequence_number": 1,
      "problem_type": "Problem type description",
      "match_quality": "EXCELLENT",
      "explanation": "Detailed explanation of why this rating was given, considering both conceptual alignment and assessment boundary constraints"
    }}
  ],
  "excellent_sequences": [1, 2],
  "no_excellent_explanation": "Only include this field if excellent_sequences is empty - explain why no sequences earned EXCELLENT rating"
}}

IMPORTANT:
- Rate ALL sequences
- Only include sequence numbers in excellent_sequences if they received "EXCELLENT" rating
- If no sequences are EXCELLENT, provide no_excellent_explanation
- Consider assessment boundary constraints carefully (e.g., factor limits, no fractions, no word problems, etc.)
"""
    return prompt

def phase2_rate_sequences(model, grade: int, substandard_desc: str, assessment_boundary: str,
                          skill_name: str, skill_data: Dict) -> Dict:
    """Phase 2: Rate all sequences for a skill"""
    
    # Find sequences for this grade
    sequences = []
    for progression in skill_data.get('progression', []):
        if progression['grade'] == grade:
            sequences = progression['sequence']
            break
    
    if not sequences:
        logger.warning(f"  No sequences found for skill '{skill_name}' at grade {grade}")
        return {
            'skill_name': skill_name,
            'grade': grade,
            'excellent_sequences': [],
            'all_ratings': [],
            'no_excellent_explanation': f"No sequences available for grade {grade}"
        }
    
    logger.info(f"  Phase 2: Rating {len(sequences)} sequences for skill '{skill_name}'")
    
    prompt = create_phase2_prompt(grade, substandard_desc, assessment_boundary, skill_name, sequences)
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Extract JSON
        if '```json' in response_text:
            json_text = response_text.split('```json', 1)[1].split('```', 1)[0].strip()
        elif '{' in response_text and '}' in response_text:
            json_text = response_text[response_text.find('{'):response_text.rfind('}')+1]
        else:
            json_text = response_text
        
        # Parse and validate
        raw_data = json.loads(json_text)
        validated = Phase2Response(**raw_data)
        
        # Log results
        excellent_count = len(validated.excellent_sequences)
        logger.info(f"    Phase 2 Results: {excellent_count} EXCELLENT sequences found")
        
        for rating in validated.sequence_ratings:
            if rating.match_quality == "EXCELLENT":
                logger.info(f"      ✓ Sequence #{rating.sequence_number}: {rating.problem_type}")
                logger.info(f"        Explanation: {rating.explanation[:150]}...")
        
        if excellent_count == 0 and validated.no_excellent_explanation:
            logger.info(f"    No EXCELLENT matches: {validated.no_excellent_explanation[:200]}...")
        
        return {
            'skill_name': skill_name,
            'grade': grade,
            'excellent_sequences': validated.excellent_sequences,
            'all_ratings': [r.dict() for r in validated.sequence_ratings],
            'no_excellent_explanation': validated.no_excellent_explanation
        }
        
    except Exception as e:
        logger.error(f"  Phase 2 failed for skill '{skill_name}': {e}")
        logger.error(f"  Response text: {response_text[:500]}...")
        return {
            'skill_name': skill_name,
            'grade': grade,
            'excellent_sequences': [],
            'all_ratings': [],
            'no_excellent_explanation': f"Error during rating: {str(e)}"
        }

# ============================================================================
# Main Processing
# ============================================================================

def process_substandard(model, row: pd.Series, di_data: Dict) -> Dict:
    """Process a single substandard through both phases"""
    
    substandard_id = row['substandard_id']
    grade = row['grade']
    substandard_desc = row['substandard_description']
    assessment_boundary = row.get('assessment_boundary', 'No specific boundaries provided')
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Processing: {substandard_id}")
    logger.info(f"Grade: {grade}")
    logger.info(f"Description: {substandard_desc[:100]}...")
    logger.info(f"{'='*80}")
    
    result = {
        'substandard_id': substandard_id,
        'grade': grade,
        'substandard_description': substandard_desc,
        'assessment_boundary': assessment_boundary,
        'phase1_selected_skills': [],
        'phase2_results': [],
        'final_excellent_matches': [],
        'processing_timestamp': datetime.now().isoformat()
    }
    
    # Phase 1: Select skills
    selected_skills = phase1_select_skills(model, grade, substandard_desc, assessment_boundary, di_data)
    result['phase1_selected_skills'] = selected_skills
    
    if not selected_skills:
        logger.warning("  Phase 1 returned no skills - skipping Phase 2")
        return result
    
    # Phase 2: Rate sequences for each selected skill
    for skill_name in selected_skills:
        if skill_name not in di_data['skills']:
            logger.warning(f"  Skill '{skill_name}' not found in DI data - skipping")
            continue
        
        skill_data = di_data['skills'][skill_name]
        phase2_result = phase2_rate_sequences(model, grade, substandard_desc, assessment_boundary,
                                              skill_name, skill_data)
        result['phase2_results'].append(phase2_result)
        
        # Collect excellent matches
        for seq_num in phase2_result['excellent_sequences']:
            result['final_excellent_matches'].append({
                'skill': skill_name,
                'grade': grade,
                'sequence_number': seq_num
            })
    
    # Summary
    total_excellent = len(result['final_excellent_matches'])
    logger.info(f"\n  📊 FINAL SUMMARY:")
    logger.info(f"    Skills evaluated: {len(selected_skills)}")
    logger.info(f"    Total EXCELLENT matches: {total_excellent}")
    
    if total_excellent == 0:
        logger.info(f"    ⚠️  No EXCELLENT matches found for this substandard")
    else:
        for match in result['final_excellent_matches']:
            logger.info(f"      • {match['skill']} - Sequence #{match['sequence_number']}")
    
    return result

def main():
    """Main execution function"""
    
    # Load environment variables
    load_dotenv()
    
    # Configuration
    CURRICULUM_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/data/curricululm_with_assesment_boundary.csv"
    DI_FORMATS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/data/di_formats_with_mappings.json"
    OUTPUT_DIR = "/workspaces/github-com-anirudhs-ti-edullm-experiments/output"
    OUTPUT_FILE = os.path.join(OUTPUT_DIR, "substandard_to_sequence_mappings.json")
    PROGRESS_FILE = os.path.join(OUTPUT_DIR, "mapping_progress.json")
    TARGET_GRADE = 3
    
    # Initialize
    logger.info("="*80)
    logger.info("CURRICULUM TO SEQUENCE MAPPING - GRADE 3 POC")
    logger.info(f"Started: {datetime.now()}")
    logger.info("="*80)
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment")
        return
    
    # Initialize Gemini
    try:
        model = initialize_gemini(api_key)
        logger.info("✓ Gemini 2.0 Flash initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini: {e}")
        return
    
    # Load data
    curriculum_df = load_curriculum_csv(CURRICULUM_FILE, TARGET_GRADE)
    di_data = load_di_formats_json(DI_FORMATS_FILE)
    
    if curriculum_df.empty or not di_data:
        logger.error("Failed to load required data files")
        return
    
    # Create output directory
    create_output_directory(OUTPUT_DIR)
    
    # Load progress (resume mode)
    progress = load_progress(PROGRESS_FILE)
    completed_ids = set(progress.get('completed', []))
    results = progress.get('results', [])
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Processing {len(curriculum_df)} grade {TARGET_GRADE} substandards")
    logger.info(f"Already completed: {len(completed_ids)} substandards")
    logger.info(f"Remaining: {len(curriculum_df) - len(completed_ids)} substandards")
    logger.info(f"{'='*80}\n")
    
    # Process each substandard
    total = len(curriculum_df)
    for idx, row in curriculum_df.iterrows():
        substandard_id = row['substandard_id']
        
        # Skip if already completed (resume mode)
        if substandard_id in completed_ids:
            logger.info(f"[{idx+1}/{total}] Skipping {substandard_id} (already completed)")
            continue
        
        logger.info(f"\n[{idx+1}/{total}] Processing {substandard_id}")
        
        try:
            # Process this substandard
            result = process_substandard(model, row, di_data)
            
            # Save result
            results.append(result)
            completed_ids.add(substandard_id)
            
            # Update progress
            progress['completed'] = list(completed_ids)
            progress['results'] = results
            
            # Save progress every 5 substandards
            if len(completed_ids) % 5 == 0:
                save_progress(progress, PROGRESS_FILE)
                
                # Also save final output
                with open(OUTPUT_FILE, 'w') as f:
                    json.dump({
                        'metadata': {
                            'source_csv': CURRICULUM_FILE,
                            'source_json': DI_FORMATS_FILE,
                            'target_grade': TARGET_GRADE,
                            'total_substandards': total,
                            'processed_substandards': len(completed_ids),
                            'processing_date': datetime.now().isoformat(),
                            'llm_model': 'gemini-2.0-flash-exp'
                        },
                        'mappings': results
                    }, f, indent=2)
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error processing {substandard_id}: {e}")
            continue
    
    # Final save
    save_progress(progress, PROGRESS_FILE)
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump({
            'metadata': {
                'source_csv': CURRICULUM_FILE,
                'source_json': DI_FORMATS_FILE,
                'target_grade': TARGET_GRADE,
                'total_substandards': total,
                'processed_substandards': len(completed_ids),
                'processing_date': datetime.now().isoformat(),
                'llm_model': 'gemini-2.0-flash-exp',
                'completion_status': 'complete' if len(completed_ids) == total else 'partial'
            },
            'mappings': results
        }, f, indent=2)
    
    # Summary statistics
    logger.info(f"\n{'='*80}")
    logger.info("PROCESSING COMPLETE!")
    logger.info(f"{'='*80}")
    logger.info(f"Total substandards processed: {len(results)}")
    logger.info(f"Output saved to: {OUTPUT_FILE}")
    logger.info(f"Progress saved to: {PROGRESS_FILE}")
    
    # Count statistics
    total_excellent = sum(len(r['final_excellent_matches']) for r in results)
    substandards_with_matches = sum(1 for r in results if len(r['final_excellent_matches']) > 0)
    substandards_without_matches = len(results) - substandards_with_matches
    
    logger.info(f"\n📊 STATISTICS:")
    logger.info(f"  Substandards with EXCELLENT matches: {substandards_with_matches}")
    logger.info(f"  Substandards without EXCELLENT matches: {substandards_without_matches}")
    logger.info(f"  Total EXCELLENT sequence matches: {total_excellent}")
    logger.info(f"  Average matches per substandard: {total_excellent/len(results):.2f}")
    
    logger.info(f"\n✅ All done! Check {OUTPUT_FILE} for results.")

if __name__ == "__main__":
    main()


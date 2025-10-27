#!/usr/bin/env python3
"""
Generate new substandard-to-sequence mappings using brute-force validation.
Fills gaps for substandards with no EXCELLENT/FAIR matches by rating all sequences.
"""

import json
import os
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from pydantic import BaseModel, Field

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('generate_new_mappings.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Schemas
# ============================================================================

class SequenceRating(BaseModel):
    """Schema for rating a single sequence with scoring metrics"""
    skill_name: str = Field(..., description="Skill name for context")
    sequence_number: int = Field(..., ge=1, description="Sequence number")
    problem_type: str = Field(..., min_length=1, description="Problem type description")
    match_quality: str = Field(..., description="EXCELLENT, FAIR, POOR, or NON-EXISTENT")
    boundary_classification: str = Field(..., description="COMPLIANT, MINOR_VIOLATION, or MAJOR_VIOLATION")
    grade_alignment: str = Field(..., description="ON_GRADE, SLIGHTLY_OFF, or OFF_GRADE")
    extraneous_skill_load: str = Field(..., description="LOW, MODERATE, or HIGH")
    alignment_score: int = Field(..., ge=0, le=100, description="Alignment strength 0-100")
    explanation: str = Field(..., min_length=20, description="Detailed explanation")

    class Config:
        validate_assignment = True

class BatchRatingResponse(BaseModel):
    """Schema for batch rating response"""
    sequence_ratings: List[SequenceRating] = Field(..., description="Ratings for all sequences")
    excellent_sequences: List[int] = Field(..., description="List of EXCELLENT sequence numbers")

    class Config:
        validate_assignment = True

# ============================================================================
# Helper Functions
# ============================================================================

def initialize_gemini(api_key: str):
    """Initialize Gemini 2.0 Flash model"""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.0-flash-exp')

def load_json(filepath: str) -> Dict:
    """Load JSON file"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded JSON: {filepath}")
        return data
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return {}

def find_substandards_without_good_matches(mappings: List[Dict]) -> List[Dict]:
    """Find substandards with no FAIR or EXCELLENT matches"""
    no_good_matches = []
    
    for mapping in mappings:
        has_good_match = False
        
        # Check final_excellent_matches
        if mapping.get('final_excellent_matches') and len(mapping['final_excellent_matches']) > 0:
            has_good_match = True
            continue
        
        # Check all ratings for FAIR/EXCELLENT
        for phase2_result in mapping.get('phase2_results', []):
            for rating in phase2_result.get('all_ratings', []):
                if rating.get('match_quality') in ['FAIR', 'EXCELLENT']:
                    has_good_match = True
                    break
            if has_good_match:
                break
        
        if not has_good_match:
            no_good_matches.append(mapping)
    
    return no_good_matches

def extract_all_sequences_for_grade(di_data: Dict, grade: int) -> List[Dict]:
    """Extract all sequences from DI data for a specific grade"""
    all_sequences = []
    
    for skill_name, skill_data in di_data.get('skills', {}).items():
        for progression in skill_data.get('progression', []):
            if progression.get('grade') == grade:
                for seq in progression.get('sequence', []):
                    sequence_obj = {
                        'skill_name': skill_name,
                        'grade': grade,
                        'sequence_number': seq.get('sequence_number'),
                        'problem_type': seq.get('problem_type', ''),
                        'example_questions': seq.get('example_questions'),
                        'visual_aids': seq.get('visual_aids'),
                        'related_formats': seq.get('related_formats', [])
                    }
                    all_sequences.append(sequence_obj)
    
    logger.info(f"Extracted {len(all_sequences)} sequences for grade {grade}")
    return all_sequences

def create_batch_rating_prompt(grade: int, substandard_desc: str, assessment_boundary: str,
                                sequences: List[Dict]) -> str:
    """Create batch rating prompt with scoring metrics"""
    
    # Build sequences array
    sequences_json = []
    for seq in sequences:
        seq_obj = {
            "skill_name": seq['skill_name'],
            "sequence_number": seq['sequence_number'],
            "problem_type": seq['problem_type'],
            "example_questions": seq['example_questions'],
            "visual_aids": seq['visual_aids']
        }
        sequences_json.append(seq_obj)
    
    sequences_text = json.dumps(sequences_json, indent=2)
    
    prompt = f"""You are an impartial expert evaluator validating whether Grade {grade} math substandards align with problem sequences. Judge alignment ONLY using the substandard text, its assessment boundary, and the grade. For each sequence, independently assign one of: EXCELLENT, FAIR, POOR, or NON-EXISTENT, and provide structured rationale.

RUBRIC
- EXCELLENT: Direct and complete coverage of the substandard's intent at the given grade; tasks primarily require the target skill; steps/representations/terminology and difficulty match the assessment boundary; minimal extraneous skills.
- FAIR: Meaningful partial coverage; supports a key component but misses some aspects (scope, representation, boundary) or needs minor adaptation.
- POOR: Weak or indirect alignment; touches topic but the main work does not address the substandard as written, or grade/rigor is off; would need substantial changes.
- NON-EXISTENT: No real alignment; different topic or skill.

CLASSIFICATIONS (deterministic)
- boundary_classification: 
  * COMPLIANT - Fully respects all assessment boundary constraints
  * MINOR_VIOLATION - Violates 1 minor constraint or partially violates a key constraint
  * MAJOR_VIOLATION - Violates multiple constraints or severely violates a key constraint
- grade_alignment:
  * ON_GRADE - Appropriate difficulty and complexity for Grade {grade}
  * SLIGHTLY_OFF - Mostly appropriate but slightly too easy/hard
  * OFF_GRADE - Clearly wrong grade level
- extraneous_skill_load:
  * LOW - Minimal skills beyond the substandard required
  * MODERATE - Some additional skills needed but manageable
  * HIGH - Substantial prerequisite or parallel skills required

SCORING
- alignment_score: integer 0–100 reflecting strength of alignment given the substandard, boundary, and grade. Typical bands:
  * EXCELLENT: 85–100
  * FAIR: 60–84
  * POOR: 25–59
  * NON-EXISTENT: 0–24
- Ensure bands and labels are consistent (e.g., do not assign EXCELLENT with alignment_score 70).

RULES
- Rate EACH sequence independently; do not compare sequences to each other.
- Consider skill_name only as optional context; prioritize what the sequence actually demands.
- Cite the assessment boundary when it affects your judgment.
- Be deterministic; no randomness.
- Output MUST strictly follow the JSON schema with no extra fields or text.

SUBSTANDARD (Grade {grade})
{substandard_desc}

ASSESSMENT BOUNDARY
{assessment_boundary}

SEQUENCES TO RATE (evaluate every item exactly once)
{sequences_text}

Return ONLY valid JSON with no prose before or after, in exactly this structure:
{{
  "sequence_ratings": [
    {{
      "skill_name": "<string from input>",
      "sequence_number": <int>,
      "problem_type": "<string from input>",
      "match_quality": "EXCELLENT|FAIR|POOR|NON-EXISTENT",
      "boundary_classification": "COMPLIANT|MINOR_VIOLATION|MAJOR_VIOLATION",
      "grade_alignment": "ON_GRADE|SLIGHTLY_OFF|OFF_GRADE",
      "extraneous_skill_load": "LOW|MODERATE|HIGH",
      "alignment_score": <int 0-100>,
      "explanation": "<>= 20 words citing concrete elements and boundary considerations>"
    }}
  ],
  "excellent_sequences": [<list of sequence_number values rated EXCELLENT>]
}}

IMPORTANT:
- sequence_ratings must contain one entry per input sequence
- excellent_sequences must list ONLY the sequence_number values rated EXCELLENT
- Each explanation must be >= 20 words and cite specific elements
- alignment_score must be consistent with match_quality band
"""
    return prompt

def rate_sequences_in_batches(model, grade: int, substandard_desc: str, assessment_boundary: str,
                               all_sequences: List[Dict], batch_size: int = 15) -> Dict:
    """Rate all sequences in batches"""
    
    all_ratings = []
    
    total_batches = (len(all_sequences) + batch_size - 1) // batch_size
    
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(all_sequences))
        batch = all_sequences[start_idx:end_idx]
        
        logger.info(f"  Processing batch {batch_idx + 1}/{total_batches} ({len(batch)} sequences)")
        
        prompt = create_batch_rating_prompt(grade, substandard_desc, assessment_boundary, batch)
        
        max_retries = 3
        for attempt in range(max_retries):
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
                validated = BatchRatingResponse(**raw_data)
                
                # Collect ratings
                for rating in validated.sequence_ratings:
                    all_ratings.append(rating.dict())
                
                # Success - break retry loop
                break
                
            except Exception as e:
                logger.warning(f"    Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"    Batch {batch_idx + 1} failed after {max_retries} attempts")
                    # Add placeholder ratings for this batch
                    for seq in batch:
                        all_ratings.append({
                            'skill_name': seq['skill_name'],
                            'sequence_number': seq['sequence_number'],
                            'problem_type': seq['problem_type'],
                            'match_quality': 'NON-EXISTENT',
                            'boundary_classification': 'MAJOR_VIOLATION',
                            'grade_alignment': 'OFF_GRADE',
                            'extraneous_skill_load': 'HIGH',
                            'alignment_score': 0,
                            'explanation': f'Error during evaluation: {str(e)}'
                        })
        
        # Small delay between batches
        time.sleep(0.5)
    
    return {
        'all_ratings': all_ratings,
        'total_sequences_evaluated': len(all_ratings)
    }

def select_top_5_sequences(ratings: List[Dict]) -> List[Dict]:
    """Select top 5 sequences using deterministic scoring and tie-breaking"""
    
    # Filter eligible sequences
    eligible = []
    for rating in ratings:
        # Only EXCELLENT or FAIR
        if rating['match_quality'] not in ['EXCELLENT', 'FAIR']:
            continue
        # Exclude MAJOR_VIOLATION
        if rating['boundary_classification'] == 'MAJOR_VIOLATION':
            continue
        # Exclude OFF_GRADE (prefer ON_GRADE and SLIGHTLY_OFF)
        if rating['grade_alignment'] == 'OFF_GRADE':
            continue
        eligible.append(rating)
    
    if not eligible:
        logger.warning("  No eligible sequences found")
        return []
    
    # Calculate final scores
    for rating in eligible:
        # Base weight
        base_weight = 1.0 if rating['match_quality'] == 'EXCELLENT' else 0.75
        
        # Penalties
        penalties = 0.0
        if rating['boundary_classification'] == 'MINOR_VIOLATION':
            penalties += 0.10
        if rating['grade_alignment'] == 'SLIGHTLY_OFF':
            penalties += 0.10
        if rating['extraneous_skill_load'] == 'MODERATE':
            penalties += 0.05
        elif rating['extraneous_skill_load'] == 'HIGH':
            penalties += 0.15
        
        # Final score
        rating['final_score'] = base_weight * (rating['alignment_score'] / 100.0) - penalties
    
    # Sort with tie-breakers
    def sort_key(r):
        return (
            1 if r['match_quality'] == 'EXCELLENT' else 0,  # EXCELLENT first
            r['final_score'],  # Higher score better
            0 if r['boundary_classification'] == 'COMPLIANT' else 1,  # COMPLIANT first
            {'LOW': 0, 'MODERATE': 1, 'HIGH': 2}[r['extraneous_skill_load']],  # LOW first
            0 if r['grade_alignment'] == 'ON_GRADE' else 1,  # ON_GRADE first
            r['sequence_number']  # Deterministic tie-break
        )
    
    eligible.sort(key=sort_key, reverse=True)
    
    # Take top 5
    top_5 = eligible[:5]
    
    logger.info(f"  Selected {len(top_5)} sequences from {len(eligible)} eligible")
    for i, rating in enumerate(top_5, 1):
        logger.info(f"    {i}. Seq #{rating['sequence_number']} ({rating['skill_name']}): "
                   f"{rating['match_quality']} | score={rating['final_score']:.2f} | "
                   f"align={rating['alignment_score']}")
    
    return top_5

def generate_final_matches_list(top_5: List[Dict], grade: int) -> List[Dict]:
    """Generate final_excellent_matches list with augmented fields"""
    final_matches = []
    for rating in top_5:
        match_obj = {
            'skill': rating['skill_name'],
            'grade': grade,
            'sequence_number': rating['sequence_number'],
            'quality': rating['match_quality'],
            'alignment_score': rating['alignment_score']
        }
        final_matches.append(match_obj)
    return final_matches

def main():
    """Main execution function"""
    
    # Configuration
    BATCH_SIZE = 15
    
    MAPPINGS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/output/substandard_to_sequence_mappings.json"
    DI_FORMATS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/data/di_formats_with_mappings.json"
    OUTPUT_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/output/substandard_to_sequence_mappings.v2.json"
    REPORT_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/output/bruteforce_remap_report.md"
    
    # Load environment
    load_dotenv()
    
    logger.info("="*80)
    logger.info("GENERATE NEW MAPPINGS USING BRUTE-FORCE VALIDATION")
    logger.info(f"Started: {datetime.now()}")
    logger.info("="*80)
    
    # Initialize Gemini
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment")
        return
    
    try:
        model = initialize_gemini(api_key)
        logger.info("✓ Gemini 2.0 Flash initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini: {e}")
        return
    
    # Load data
    mappings_data = load_json(MAPPINGS_FILE)
    di_data = load_json(DI_FORMATS_FILE)
    
    if not mappings_data or not di_data:
        logger.error("Failed to load required data files")
        return
    
    # Find substandards without good matches
    mappings = mappings_data.get('mappings', [])
    no_good_matches = find_substandards_without_good_matches(mappings)
    
    logger.info(f"\n📊 Found {len(no_good_matches)} substandards with no FAIR/EXCELLENT matches")
    
    if len(no_good_matches) == 0:
        logger.info("✅ All substandards have at least FAIR matches - no work needed!")
        return
    
    # Process each substandard
    updated_mappings = []
    flipped_count = 0
    report_entries = []
    
    for idx, substandard in enumerate(no_good_matches, 1):
        substandard_id = substandard['substandard_id']
        grade = substandard['grade']
        substandard_desc = substandard['substandard_description']
        assessment_boundary = substandard.get('assessment_boundary', 'No specific boundaries provided')
        
        logger.info(f"\n{'='*80}")
        logger.info(f"[{idx}/{len(no_good_matches)}] Processing: {substandard_id}")
        logger.info(f"Grade: {grade}")
        logger.info(f"Description: {substandard_desc[:100]}...")
        logger.info(f"{'='*80}")
        
        # Get ALL sequences for this grade
        all_grade_sequences = extract_all_sequences_for_grade(di_data, grade)
        all_grade_sequences.sort(key=lambda x: (x['skill_name'], x['sequence_number']))
        
        logger.info(f"Evaluating {len(all_grade_sequences)} total sequences across all skills")
        
        # Rate all sequences in batches
        batch_results = rate_sequences_in_batches(
            model, grade, substandard_desc, assessment_boundary,
            all_grade_sequences, batch_size=BATCH_SIZE
        )
        
        # Select top 5
        top_5 = select_top_5_sequences(batch_results['all_ratings'])
        
        # Generate final matches
        final_matches = generate_final_matches_list(top_5, grade)
        
        # Update the mapping
        updated_mapping = substandard.copy()
        updated_mapping['final_excellent_matches'] = final_matches
        updated_mapping['bruteforce_metadata'] = {
            'total_sequences_evaluated': batch_results['total_sequences_evaluated'],
            'top_5_count': len(top_5),
            'processing_timestamp': datetime.now().isoformat()
        }
        updated_mappings.append(updated_mapping)
        
        # Track flips
        if len(final_matches) > 0:
            flipped_count += 1
            report_entries.append({
                'substandard_id': substandard_id,
                'description': substandard_desc,
                'matches': final_matches
            })
        
        logger.info(f"\n  📊 RESULT for {substandard_id}:")
        logger.info(f"    Sequences evaluated: {batch_results['total_sequences_evaluated']}")
        logger.info(f"    Top 5 selected: {len(final_matches)}")
        if len(final_matches) > 0:
            logger.info(f"    ✅ FLIPPED: Now has {len(final_matches)} matches!")
        else:
            logger.info(f"    ⚠️  Still no matches found")
    
    # Merge with original mappings
    logger.info(f"\n{'='*80}")
    logger.info("MERGING WITH ORIGINAL MAPPINGS")
    logger.info(f"{'='*80}")
    
    # Create lookup
    updated_lookup = {m['substandard_id']: m for m in updated_mappings}
    
    # Build final mappings list
    final_mappings = []
    for original in mappings:
        if original['substandard_id'] in updated_lookup:
            final_mappings.append(updated_lookup[original['substandard_id']])
        else:
            final_mappings.append(original)
    
    # Build output
    output_data = {
        'metadata': {
            'source_csv': mappings_data['metadata']['source_csv'],
            'source_json': mappings_data['metadata']['source_json'],
            'target_grade': mappings_data['metadata']['target_grade'],
            'total_substandards': mappings_data['metadata']['total_substandards'],
            'processed_substandards': mappings_data['metadata']['processed_substandards'],
            'original_processing_date': mappings_data['metadata']['processing_date'],
            'bruteforce_remap_date': datetime.now().isoformat(),
            'bruteforce_remapped_count': len(updated_mappings),
            'llm_model': 'gemini-2.0-flash-exp',
            'completion_status': 'complete'
        },
        'mappings': final_mappings
    }
    
    # Write output
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output_data, f, indent=2)
    logger.info(f"✓ Wrote new mappings to: {OUTPUT_FILE}")
    
    # Generate report
    with open(REPORT_FILE, 'w') as f:
        f.write("# Brute-Force Remap Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Summary\n\n")
        f.write(f"- **Total substandards remapped:** {len(updated_mappings)}\n")
        f.write(f"- **Flipped to having matches:** {flipped_count}\n")
        f.write(f"- **Still no matches:** {len(updated_mappings) - flipped_count}\n\n")
        
        if report_entries:
            f.write("## ✅ Substandards with New Matches\n\n")
            for entry in report_entries:
                f.write(f"### {entry['substandard_id']}\n\n")
                f.write(f"**Description:** {entry['description']}\n\n")
                f.write(f"**New matches ({len(entry['matches'])}):**\n")
                for match in entry['matches']:
                    f.write(f"- Seq #{match['sequence_number']} ({match['skill']}): "
                           f"{match['quality']} | score={match['alignment_score']}\n")
                f.write("\n---\n\n")
    
    logger.info(f"✓ Wrote report to: {REPORT_FILE}")
    
    # Final summary
    logger.info(f"\n{'='*80}")
    logger.info("BRUTE-FORCE REMAP COMPLETE!")
    logger.info(f"{'='*80}")
    logger.info(f"Substandards processed: {len(updated_mappings)}")
    logger.info(f"Flipped to having matches: {flipped_count}")
    logger.info(f"Still no matches: {len(updated_mappings) - flipped_count}")
    logger.info(f"\n📁 Outputs:")
    logger.info(f"  - New mappings: {OUTPUT_FILE}")
    logger.info(f"  - Report: {REPORT_FILE}")

if __name__ == "__main__":
    main()


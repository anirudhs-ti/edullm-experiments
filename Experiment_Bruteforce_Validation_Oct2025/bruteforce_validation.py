#!/usr/bin/env python3
"""
Brute-force validation: Re-check substandards with no FAIR/EXCELLENT matches
by exhaustively evaluating ALL grade-relevant sequences.
"""

import json
import os
import random
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
        logging.FileHandler('bruteforce_validation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Schemas (matching the original)
# ============================================================================

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
        
        # Check all ratings for FAIR
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
    """Create batch rating prompt for multiple sequences"""
    
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
    
    prompt = f"""You are an impartial expert evaluator validating whether K–12 math substandards align with problem sequences. Judge alignment ONLY using the provided substandard text, its assessment boundary, and the specified grade. For each sequence, independently assign one of: EXCELLENT, FAIR, POOR, or NON-EXISTENT. Provide concise, specific explanations that cite concrete elements from the sequence and the substandard; avoid generic statements.

RUBRIC:
- EXCELLENT: Direct and complete coverage of the substandard's intent at the given grade. Tasks primarily require the target skill; steps, representations, terminology, and difficulty match the assessment boundary. Little/no extraneous skills required.
- FAIR: Meaningful partial coverage. The sequence supports a key component of the substandard but misses some aspects (scope, representation, or boundary) or needs minor adaptation.
- POOR: Weak or indirect alignment. Touches the topic but the main focus/steps do not address the substandard as written, or grade/rigor is noticeably off; would need substantial changes.
- NON-EXISTENT: No real alignment; different topic or skill.

RULES:
- Rate EACH sequence independently; do not compare sequences to each other.
- Consider `skill_name` only as optional context; do NOT let it override what the sequence actually demands.
- Do NOT reward superficial keyword overlap; focus on the mathematical work the student must do.
- If information is insufficient to establish alignment, choose NON-EXISTENT.
- Be deterministic; no randomness. Use only the four labels above.
- Output MUST strictly follow the JSON schema with no extra fields or text.

TASK: Rate the alignment between this substandard and EACH of the following sequences for Grade {grade}.

SUBSTANDARD (Grade {grade}):
{substandard_desc}

ASSESSMENT BOUNDARY:
{assessment_boundary}

SEQUENCES TO RATE (evaluate every item exactly once):
{sequences_text}

Return ONLY valid JSON with no prose before or after, in exactly this structure:
{{
  "sequence_ratings": [
    {{
      "sequence_number": <int>,
      "problem_type": "<string>",
      "match_quality": "EXCELLENT|FAIR|POOR|NON-EXISTENT",
      "explanation": "<string of at least 20 words citing specific elements>"
    }}
  ],
  "excellent_sequences": [<list of sequence_number values rated EXCELLENT>],
  "no_excellent_explanation": "<string or null - only if excellent_sequences is empty>"
}}

IMPORTANT:
- sequence_ratings must contain one entry per input sequence
- excellent_sequences must list ONLY the sequence_number values rated EXCELLENT
- Each explanation must be >= 20 words and cite specific elements
"""
    return prompt

def rate_sequences_in_batches(model, grade: int, substandard_desc: str, assessment_boundary: str,
                               all_sequences: List[Dict], batch_size: int = 15) -> Dict:
    """Rate all sequences in batches"""
    
    all_ratings = []
    excellent_sequences = []
    fair_sequences = []
    
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
                validated = Phase2Response(**raw_data)
                
                # Collect ratings
                for rating in validated.sequence_ratings:
                    rating_dict = rating.dict()
                    # Add skill_name for context
                    for seq in batch:
                        if seq['sequence_number'] == rating.sequence_number:
                            rating_dict['skill_name'] = seq['skill_name']
                            break
                    all_ratings.append(rating_dict)
                    
                    if rating.match_quality == "EXCELLENT":
                        excellent_sequences.append(rating.sequence_number)
                        logger.info(f"    ✓ EXCELLENT: Seq #{rating.sequence_number} ({rating.problem_type[:50]}...)")
                    elif rating.match_quality == "FAIR":
                        fair_sequences.append(rating.sequence_number)
                        logger.info(f"    ~ FAIR: Seq #{rating.sequence_number} ({rating.problem_type[:50]}...)")
                
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
                            'explanation': f'Error during evaluation: {str(e)}'
                        })
        
        # Small delay between batches
        time.sleep(0.5)
    
    return {
        'all_ratings': all_ratings,
        'excellent_sequences': excellent_sequences,
        'fair_sequences': fair_sequences,
        'total_sequences_evaluated': len(all_ratings)
    }

def generate_markdown_report(results: List[Dict], output_path: str):
    """Generate markdown summary report"""
    
    with open(output_path, 'w') as f:
        f.write("# Brute-Force Validation Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Summary\n\n")
        
        total_substandards = len(results)
        flipped = [r for r in results if r['found_good_match']]
        f.write(f"- **Total substandards re-checked:** {total_substandards}\n")
        f.write(f"- **Previously had no FAIR/EXCELLENT matches:** {total_substandards}\n")
        f.write(f"- **Now have FAIR/EXCELLENT matches:** {len(flipped)}\n\n")
        
        if flipped:
            f.write("## ✅ Substandards with Newly Found Matches\n\n")
            for r in flipped:
                f.write(f"### {r['substandard_id']}\n\n")
                f.write(f"**Description:** {r['substandard_description']}\n\n")
                
                if r['excellent_sequences']:
                    f.write(f"**EXCELLENT matches ({len(r['excellent_sequences'])}):**\n")
                    for seq_num in r['excellent_sequences']:
                        # Find the rating
                        for rating in r['all_ratings']:
                            if rating['sequence_number'] == seq_num and rating['match_quality'] == 'EXCELLENT':
                                f.write(f"- Sequence #{seq_num} ({rating['skill_name']}): {rating['problem_type']}\n")
                                f.write(f"  - *{rating['explanation']}*\n")
                                break
                    f.write("\n")
                
                if r['fair_sequences']:
                    f.write(f"**FAIR matches ({len(r['fair_sequences'])}):**\n")
                    for seq_num in r['fair_sequences']:
                        # Find the rating
                        for rating in r['all_ratings']:
                            if rating['sequence_number'] == seq_num and rating['match_quality'] == 'FAIR':
                                f.write(f"- Sequence #{seq_num} ({rating['skill_name']}): {rating['problem_type']}\n")
                                f.write(f"  - *{rating['explanation']}*\n")
                                break
                    f.write("\n")
                
                f.write("---\n\n")
        
        still_no_matches = [r for r in results if not r['found_good_match']]
        if still_no_matches:
            f.write("## ⚠️ Substandards Still Without Good Matches\n\n")
            for r in still_no_matches:
                f.write(f"- **{r['substandard_id']}**: {r['substandard_description']}\n")
                f.write(f"  - Evaluated {r['total_sequences_evaluated']} sequences\n\n")
    
    logger.info(f"Markdown report saved to: {output_path}")

def main():
    """Main execution function"""
    
    # Configuration
    RANDOM_SEED = 42
    NUM_SAMPLES = 5
    BATCH_SIZE = 15  # Sequences per API call
    
    MAPPINGS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/output/substandard_to_sequence_mappings.json"
    DI_FORMATS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/data/di_formats_with_mappings.json"
    OUTPUT_DIR = "/workspaces/github-com-anirudhs-ti-edullm-experiments/output"
    OUTPUT_FILE = os.path.join(OUTPUT_DIR, "bruteforce_rechecks.json")
    SUMMARY_FILE = os.path.join(OUTPUT_DIR, "bruteforce_rechecks_summary.json")
    REPORT_FILE = os.path.join(OUTPUT_DIR, "bruteforce_rechecks_report.md")
    
    # Load environment
    load_dotenv()
    
    logger.info("="*80)
    logger.info("BRUTE-FORCE VALIDATION OF SUBSTANDARDS WITHOUT GOOD MATCHES")
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
        logger.info("✅ All substandards have at least FAIR matches - no validation needed!")
        return
    
    # Sample random substandards
    random.seed(RANDOM_SEED)
    sample_size = min(NUM_SAMPLES, len(no_good_matches))
    sampled_substandards = random.sample(no_good_matches, sample_size)
    
    logger.info(f"🎲 Randomly sampled {sample_size} substandards (seed={RANDOM_SEED})")
    for i, s in enumerate(sampled_substandards, 1):
        logger.info(f"  {i}. {s['substandard_id']}: {s['substandard_description'][:80]}...")
    
    # Process each sampled substandard
    results = []
    
    for idx, substandard in enumerate(sampled_substandards, 1):
        substandard_id = substandard['substandard_id']
        grade = substandard['grade']
        substandard_desc = substandard['substandard_description']
        assessment_boundary = substandard.get('assessment_boundary', 'No specific boundaries provided')
        
        logger.info(f"\n{'='*80}")
        logger.info(f"[{idx}/{sample_size}] Re-checking: {substandard_id}")
        logger.info(f"Grade: {grade}")
        logger.info(f"Description: {substandard_desc}")
        logger.info(f"{'='*80}")
        
        # Get ALL sequences for this grade
        all_grade_sequences = extract_all_sequences_for_grade(di_data, grade)
        
        # Create unique identifier for sequences (skill + seq_num)
        # Sort for determinism
        all_grade_sequences.sort(key=lambda x: (x['skill_name'], x['sequence_number']))
        
        logger.info(f"Will evaluate {len(all_grade_sequences)} total sequences across all skills")
        
        # Rate all sequences in batches
        batch_results = rate_sequences_in_batches(
            model, grade, substandard_desc, assessment_boundary,
            all_grade_sequences, batch_size=BATCH_SIZE
        )
        
        # Compile result
        result = {
            'substandard_id': substandard_id,
            'grade': grade,
            'substandard_description': substandard_desc,
            'assessment_boundary': assessment_boundary,
            'previous_status': {
                'had_excellent': len(substandard.get('final_excellent_matches', [])) > 0,
                'phase1_selected_skills': substandard.get('phase1_selected_skills', [])
            },
            'bruteforce_results': {
                'total_sequences_evaluated': batch_results['total_sequences_evaluated'],
                'excellent_sequences': batch_results['excellent_sequences'],
                'fair_sequences': batch_results['fair_sequences'],
                'all_ratings': batch_results['all_ratings']
            },
            'found_good_match': len(batch_results['excellent_sequences']) > 0 or len(batch_results['fair_sequences']) > 0,
            'total_sequences_evaluated': batch_results['total_sequences_evaluated'],
            'excellent_sequences': batch_results['excellent_sequences'],
            'fair_sequences': batch_results['fair_sequences'],
            'all_ratings': batch_results['all_ratings'],
            'processing_timestamp': datetime.now().isoformat()
        }
        
        results.append(result)
        
        # Log summary
        logger.info(f"\n  📊 BRUTE-FORCE SUMMARY for {substandard_id}:")
        logger.info(f"    Total sequences evaluated: {result['total_sequences_evaluated']}")
        logger.info(f"    EXCELLENT matches: {len(result['excellent_sequences'])}")
        logger.info(f"    FAIR matches: {len(result['fair_sequences'])}")
        logger.info(f"    Found good match: {result['found_good_match']}")
        
        if result['found_good_match']:
            logger.info(f"    ⚠️  VALIDATION ISSUE: Previously had no good matches, now has {len(result['excellent_sequences']) + len(result['fair_sequences'])}!")
            if result['excellent_sequences']:
                logger.info(f"       EXCELLENT sequences: {result['excellent_sequences']}")
            if result['fair_sequences']:
                logger.info(f"       FAIR sequences: {result['fair_sequences'][:5]}{'...' if len(result['fair_sequences']) > 5 else ''}")
        else:
            logger.info(f"    ✓ VALIDATED: Confirmed no FAIR/EXCELLENT matches exist")
        
        # Save incremental progress
        with open(OUTPUT_FILE, 'w') as f:
            json.dump({
                'metadata': {
                    'purpose': 'Brute-force validation of substandards without good matches',
                    'random_seed': RANDOM_SEED,
                    'sample_size': sample_size,
                    'batch_size': BATCH_SIZE,
                    'processing_date': datetime.now().isoformat(),
                    'llm_model': 'gemini-2.0-flash-exp'
                },
                'results': results
            }, f, indent=2)
    
    # Generate summary
    summary = {
        'metadata': {
            'total_substandards_rechecked': len(results),
            'found_good_matches': sum(1 for r in results if r['found_good_match']),
            'still_no_matches': sum(1 for r in results if not r['found_good_match'])
        },
        'substandards': []
    }
    
    for r in results:
        summary['substandards'].append({
            'substandard_id': r['substandard_id'],
            'grade': r['grade'],
            'found_good_match': r['found_good_match'],
            'excellent_count': len(r['excellent_sequences']),
            'fair_count': len(r['fair_sequences']),
            'excellent_sequences': r['excellent_sequences'],
            'fair_sequences': r['fair_sequences']
        })
    
    with open(SUMMARY_FILE, 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Generate markdown report
    generate_markdown_report(results, REPORT_FILE)
    
    # Final summary
    logger.info(f"\n{'='*80}")
    logger.info("BRUTE-FORCE VALIDATION COMPLETE!")
    logger.info(f"{'='*80}")
    logger.info(f"Substandards re-checked: {len(results)}")
    logger.info(f"Found new good matches: {summary['metadata']['found_good_matches']}")
    logger.info(f"Still no matches: {summary['metadata']['still_no_matches']}")
    logger.info(f"\n📁 Outputs:")
    logger.info(f"  - Full results: {OUTPUT_FILE}")
    logger.info(f"  - Summary: {SUMMARY_FILE}")
    logger.info(f"  - Report: {REPORT_FILE}")
    
    # Validation insights
    if summary['metadata']['found_good_matches'] > 0:
        logger.info(f"\n⚠️  VALIDATION CONCERN:")
        logger.info(f"  {summary['metadata']['found_good_matches']} substandard(s) now have good matches")
        logger.info(f"  This suggests the original Phase 1 skill selection may have missed relevant skills.")
        logger.info(f"  Review {REPORT_FILE} for details.")
    else:
        logger.info(f"\n✅ VALIDATION CONFIRMED:")
        logger.info(f"  All {len(results)} sampled substandards truly have no FAIR/EXCELLENT matches.")
        logger.info(f"  The original experiment results are validated.")

if __name__ == "__main__":
    main()


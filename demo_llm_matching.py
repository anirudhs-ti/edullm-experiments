#!/usr/bin/env python3
"""
Demo script to show LLM matching functionality with a small subset
This runs on just 3 substandards to demonstrate the process
"""

import pandas as pd
import numpy as np
import google.generativeai as genai
import os
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
        logging.FileHandler('demo_llm_matching.log'),
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

def load_demo_data():
    """Load a small subset of data for demo"""
    try:
        # Load curriculum and filter for first 3 grade 3 entries
        df = pd.read_csv("/workspace/edullm-experiments/curriculum.csv")
        df_grade3 = df[df['grade'] == 3].head(3).reset_index(drop=True)
        
        # Load formats
        df_formats = pd.read_csv("/workspace/edullm-experiments/all_formats_extracted.csv")
        
        logger.info(f"Demo data loaded: {len(df_grade3)} substandards, {len(df_formats)} formats")
        return df_grade3, df_formats
        
    except Exception as e:
        logger.error(f"Error loading demo data: {e}")
        return pd.DataFrame(), pd.DataFrame()

def create_batch_scaffolding_prompt(substandard_description: str, format_batch: List[Dict]) -> str:
    """Create prompt for assessing scaffolding quality of multiple formats at once"""
    
    # Format the batch of instructions
    format_descriptions = []
    for i, format_item in enumerate(format_batch, 1):
        format_descriptions.append(f"""
FORMAT {i}: {format_item['title']}
Content: {format_item['flattened_content'][:300]}...
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

Rank all formats from best to worst match and provide your assessment in the following JSON format:
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
        }},
        ...
    ]
}}

IMPORTANT: Provide similarity scores as decimal numbers between 0.0 and 1.0, where:
- 0.9-1.0 = Excellent match
- 0.7-0.8 = Very good match  
- 0.5-0.6 = Good match
- 0.3-0.4 = Fair match
- 0.1-0.2 = Poor match
- 0.0-0.1 = Very poor match

Be thorough in your analysis and provide specific reasoning for your rankings. Focus on finding the format that would provide the best scaffolding for students to achieve the substandard.
"""
    return prompt

def assess_batch_scaffolding_with_llm(model, substandard_description: str, format_batch: List[Dict]) -> LLMBatchResponse:
    """Use LLM to assess scaffolding quality of multiple formats at once"""
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

def demo_matching():
    """Run demo matching on small subset"""
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Check for API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable not set")
        logger.info("To run this demo, set your API key:")
        logger.info("export GEMINI_API_KEY='your_api_key_here'")
        return
    
    # Initialize model
    try:
        model = initialize_gemini(api_key)
        logger.info("✓ Gemini model initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {e}")
        return
    
    # Load demo data
    curriculum_df, formats_df = load_demo_data()
    if curriculum_df.empty or formats_df.empty:
        logger.error("Failed to load demo data")
        return
    
    logger.info(f"Running demo on {len(curriculum_df)} substandards against {len(formats_df)} formats")
    
    results = []
    
    for index, substandard_row in curriculum_df.iterrows():
        logger.info(f"\n{'='*60}")
        logger.info(f"DEMO: Processing substandard {index+1}/{len(curriculum_df)}")
        logger.info(f"{'='*60}")
        
        substandard_description = substandard_row['substandard_description']
        substandard_id = substandard_row['substandard_id']
        
        logger.info(f"Substandard: {substandard_id}")
        logger.info(f"Description: {substandard_description}")
        
        best_match = None
        best_score = 0.0
        best_assessment = None
        
        # Use first 30 formats for demo (one batch)
        demo_formats = formats_df.head(30)
        
        logger.info(f"\n  Processing {len(demo_formats)} formats in 1 batch")
        
        # Convert to batch format
        format_batch = []
        for idx, format_row in demo_formats.iterrows():
            format_batch.append({
                'title': format_row['title'],
                'flattened_content': format_row['flattened_content']
            })
        
        # Get LLM assessment for the batch
        batch_assessment = assess_batch_scaffolding_with_llm(model, substandard_description, format_batch)
        
        # Extract best match from batch (now using Pydantic model)
        best_in_batch = batch_assessment.best_match
        best_match_idx = best_in_batch.format_number - 1
        best_match = demo_formats.iloc[best_match_idx]
        best_assessment = best_in_batch
        
        confidence = score_to_confidence(best_in_batch.similarity_score)
        logger.info(f"  ✓ Best match: {best_in_batch.title}")
        logger.info(f"  Confidence: {confidence}, Score: {best_in_batch.similarity_score}")
        logger.info(f"  Explanation: {best_in_batch.explanation[:150]}...")
        
        # Show rankings
        logger.info(f"  Rankings: {len(batch_assessment.rankings)} formats ranked")
        for i, ranking in enumerate(batch_assessment.rankings[:3]):  # Show top 3
            rank_confidence = score_to_confidence(ranking.similarity_score)
            logger.info(f"    {i+1}. {ranking.title} ({rank_confidence}, {ranking.similarity_score})")
        
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
            
            results.append(result)
            logger.info(f"\n  🎯 Best match: {best_match['title']}")
            logger.info(f"  Confidence: {final_confidence}")
            logger.info(f"  Score: {best_assessment.similarity_score:.3f}")
        
        # No delay for speed testing
        time.sleep(0)
    
    # Save demo results
    if results:
        results_df = pd.DataFrame(results)
        output_file = "/workspace/edullm-experiments/demo_llm_results.csv"
        results_df.to_csv(output_file, index=False)
        
        logger.info(f"\n{'='*60}")
        logger.info("DEMO COMPLETED!")
        logger.info(f"{'='*60}")
        logger.info(f"Results saved to: {output_file}")
        
        # Show summary
        for i, result in enumerate(results):
            logger.info(f"\nResult {i+1}:")
            logger.info(f"  Substandard: {result['substandard_id']}")
            logger.info(f"  Confidence: {result['match_confidence']}")
            logger.info(f"  Score: {result['similarity_score']}")
            logger.info(f"  Explanation: {result['llm_explanation'][:200]}...")

def main():
    """Run demo"""
    logger.info("Starting LLM Matching Demo")
    logger.info(f"Timestamp: {datetime.now()}")
    
    demo_matching()

if __name__ == "__main__":
    main()

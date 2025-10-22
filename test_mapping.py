#!/usr/bin/env python3
"""
Test script to verify the mapping pipeline works on a single substandard.
This is a dry-run before processing all 112 grade 3 substandards.
"""

import sys
import os
sys.path.insert(0, '/workspaces/github-com-anirudhs-ti-edullm-experiments')

from map_curriculum_to_sequences import *
import logging

# Configure logging for test
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_single_substandard():
    """Test the mapping process on a single substandard"""
    
    logger.info("="*80)
    logger.info("TEST RUN - Processing 1 Grade 3 Substandard")
    logger.info("="*80)
    
    # Load environment
    load_dotenv()
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        logger.error("GEMINI_API_KEY not found in .env file")
        return False
    
    logger.info("✓ API key found")
    
    # Initialize model
    try:
        model = initialize_gemini(api_key)
        logger.info("✓ Gemini 2.0 Flash initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini: {e}")
        return False
    
    # Load data
    CURRICULUM_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/data/curricululm_with_assesment_boundary.csv"
    DI_FORMATS_FILE = "/workspaces/github-com-anirudhs-ti-edullm-experiments/data/di_formats_with_mappings.json"
    
    curriculum_df = load_curriculum_csv(CURRICULUM_FILE, grade=3)
    di_data = load_di_formats_json(DI_FORMATS_FILE)
    
    if curriculum_df.empty:
        logger.error("Failed to load curriculum data")
        return False
    
    if not di_data:
        logger.error("Failed to load DI formats data")
        return False
    
    logger.info(f"✓ Loaded {len(curriculum_df)} grade 3 substandards")
    logger.info(f"✓ Loaded {len(di_data['skills'])} skills")
    
    # Process first substandard
    logger.info("\nProcessing first substandard as test...")
    
    test_row = curriculum_df.iloc[0]
    
    try:
        result = process_substandard(model, test_row, di_data)
        
        logger.info("\n" + "="*80)
        logger.info("TEST COMPLETED SUCCESSFULLY!")
        logger.info("="*80)
        logger.info("\nResult summary:")
        logger.info(f"  Substandard ID: {result['substandard_id']}")
        logger.info(f"  Phase 1 selected skills: {result['phase1_selected_skills']}")
        logger.info(f"  Total EXCELLENT matches: {len(result['final_excellent_matches'])}")
        
        if result['final_excellent_matches']:
            logger.info("\n  EXCELLENT matches:")
            for match in result['final_excellent_matches']:
                logger.info(f"    • {match['skill']} - Sequence #{match['sequence_number']}")
        else:
            logger.info("\n  ⚠️  No EXCELLENT matches found")
            for phase2_result in result['phase2_results']:
                if phase2_result.get('no_excellent_explanation'):
                    logger.info(f"    Reason: {phase2_result['no_excellent_explanation']}")
        
        logger.info("\n✅ Pipeline is working correctly!")
        logger.info("   You can now run the full script: python3 map_curriculum_to_sequences.py")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_single_substandard()
    sys.exit(0 if success else 1)


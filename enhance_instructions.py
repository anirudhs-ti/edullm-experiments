#!/usr/bin/env python3
"""
Script to enhance LLM-extracted instructions CSV with assessment boundaries and format numbers.

This script:
1. Reads the llm-extracted-instructions.csv file
2. Matches records with curriculum_with_assessment_boundary.csv using substandard_id
3. Adds assessment_boundary column
4. Extracts format numbers from direct_instructions column
5. Outputs enhanced CSV file
"""

import pandas as pd
import re
import sys
from pathlib import Path

def extract_format_number(direct_instructions):
    """
    Extract format number from direct_instructions text.
    Looks for patterns like "Format 9.1", "Format 12", etc.
    """
    if pd.isna(direct_instructions) or not direct_instructions:
        return None
    
    # Look for patterns like "Format 9.1", "Format 12", etc.
    pattern = r'Format\s+(\d+(?:\.\d+)?)'
    match = re.search(pattern, str(direct_instructions))
    
    if match:
        return match.group(1)
    return None

def main():
    # File paths
    instructions_file = "/workspaces/github-com-anirudhs-ti-edullm-experiments/output/llm-extracted-instructions.csv"
    curriculum_file = "/workspaces/github-com-anirudhs-ti-edullm-experiments/data/curricululm_with_assesment_boundary.csv"
    output_file = "/workspaces/github-com-anirudhs-ti-edullm-experiments/output/enhanced_llm_instructions.csv"
    
    print("Loading data files...")
    
    # Load the CSV files
    try:
        instructions_df = pd.read_csv(instructions_file)
        curriculum_df = pd.read_csv(curriculum_file)
    except FileNotFoundError as e:
        print(f"Error: Could not find file - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading CSV files: {e}")
        sys.exit(1)
    
    print(f"Loaded {len(instructions_df)} instruction records")
    print(f"Loaded {len(curriculum_df)} curriculum records")
    
    # Display column names for debugging
    print("\nInstructions CSV columns:", instructions_df.columns.tolist())
    print("Curriculum CSV columns:", curriculum_df.columns.tolist())
    
    # Merge the dataframes on substandard_id
    print("\nMerging data on substandard_id...")
    merged_df = instructions_df.merge(
        curriculum_df[['substandard_id', 'assessment_boundary']], 
        on='substandard_id', 
        how='left'
    )
    
    print(f"Merged dataset has {len(merged_df)} records")
    
    # Extract format numbers
    print("Extracting format numbers...")
    merged_df['format_number'] = merged_df['direct_instructions'].apply(extract_format_number)
    
    # Count successful extractions
    format_extracted = merged_df['format_number'].notna().sum()
    assessment_boundary_added = merged_df['assessment_boundary'].notna().sum()
    
    print(f"Successfully extracted format numbers for {format_extracted} records")
    print(f"Successfully added assessment boundaries for {assessment_boundary_added} records")
    
    # Display sample of enhanced data
    print("\nSample of enhanced data:")
    sample_cols = ['grade', 'substandard_id', 'substandard_description', 'format_number', 'assessment_boundary']
    print(merged_df[sample_cols].head())
    
    # Save the enhanced dataset
    print(f"\nSaving enhanced dataset to {output_file}...")
    merged_df.to_csv(output_file, index=False)
    
    print("Script completed successfully!")
    print(f"Enhanced CSV saved as: {output_file}")
    
    # Summary statistics
    print("\nSummary:")
    print(f"- Total records: {len(merged_df)}")
    print(f"- Records with format numbers: {format_extracted}")
    print(f"- Records with assessment boundaries: {assessment_boundary_added}")
    print(f"- Records with both: {len(merged_df[(merged_df['format_number'].notna()) & (merged_df['assessment_boundary'].notna())])}")

if __name__ == "__main__":
    main()

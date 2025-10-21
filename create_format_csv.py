#!/usr/bin/env python3
"""
Script to create a separate CSV file with format numbers extracted from the enhanced instructions.
"""

import pandas as pd

def main():
    # Read the enhanced CSV
    enhanced_file = "/workspaces/github-com-anirudhs-ti-edullm-experiments/output/enhanced_llm_instructions.csv"
    format_output_file = "/workspaces/github-com-anirudhs-ti-edullm-experiments/output/format_numbers.csv"
    
    print("Loading enhanced instructions...")
    df = pd.read_csv(enhanced_file)
    
    # Create a simplified CSV with just the key columns and format number
    format_df = df[['grade', 'substandard_id', 'substandard_description', 'format_number']].copy()
    
    # Sort by format number for better organization
    format_df = format_df.sort_values('format_number')
    
    # Save the format numbers CSV
    print(f"Saving format numbers to {format_output_file}...")
    format_df.to_csv(format_output_file, index=False)
    
    print("Format numbers CSV created successfully!")
    print(f"Total records: {len(format_df)}")
    print(f"Unique format numbers: {format_df['format_number'].nunique()}")
    
    # Show sample
    print("\nSample of format numbers:")
    print(format_df.head(10))

if __name__ == "__main__":
    main()

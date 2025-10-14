#!/usr/bin/env python3
"""
Test script to verify LLM setup and data loading
"""

import pandas as pd
import os
import google.generativeai as genai
from dotenv import load_dotenv

def test_data_loading():
    """Test if data files can be loaded correctly"""
    print("Testing data loading...")
    
    # Test curriculum loading
    curriculum_file = "/workspace/edullm-experiments/curriculum.csv"
    try:
        df = pd.read_csv(curriculum_file)
        df_grade3 = df[df['grade'] == 3]
        print(f"✓ Curriculum loaded: {len(df)} total rows, {len(df_grade3)} grade 3 rows")
        
        # Show first few grade 3 entries
        print("First 3 grade 3 substandards:")
        for i, row in df_grade3.head(3).iterrows():
            print(f"  {row['substandard_id']}: {row['substandard_description'][:60]}...")
            
    except Exception as e:
        print(f"✗ Error loading curriculum: {e}")
        return False
    
    # Test formats loading
    formats_file = "/workspace/edullm-experiments/all_formats_extracted.csv"
    try:
        df_formats = pd.read_csv(formats_file)
        print(f"✓ Formats loaded: {len(df_formats)} formats")
        
        # Show first few formats
        print("First 3 formats:")
        for i, row in df_formats.head(3).iterrows():
            print(f"  {row['title']}: {row['flattened_content'][:60]}...")
            
    except Exception as e:
        print(f"✗ Error loading formats: {e}")
        return False
    
    return True

def test_gemini_setup():
    """Test if Gemini API is properly configured"""
    print("\nTesting Gemini setup...")
    
    # Load environment variables from .env file
    load_dotenv()
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("✗ GEMINI_API_KEY environment variable not set")
        return False
    
    print(f"✓ API key found: {api_key[:10]}...")
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        
        # Test with a simple prompt
        response = model.generate_content("Hello, can you respond with 'Test successful'?")
        print(f"✓ Gemini test successful: {response.text.strip()}")
        
    except Exception as e:
        print(f"✗ Error testing Gemini: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("="*60)
    print("LLM MATCHING SETUP TEST")
    print("="*60)
    
    data_ok = test_data_loading()
    gemini_ok = test_gemini_setup()
    
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)
    
    if data_ok and gemini_ok:
        print("✓ All tests passed! Ready to run LLM matching.")
        print("\nTo run the full matching process:")
        print("python llm_match_curriculum.py")
    else:
        print("✗ Some tests failed. Please fix issues before running.")
        if not data_ok:
            print("  - Data loading issues")
        if not gemini_ok:
            print("  - Gemini API issues")

if __name__ == "__main__":
    main()

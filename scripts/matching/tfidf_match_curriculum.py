#!/usr/bin/env python3
"""
TF-IDF based matching between curriculum.csv and all_formats_extracted.csv
Generates a report similar to hybrid-extracted-instructions-grade3.csv format
"""

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from typing import List, Tuple, Dict
import os

def preprocess_text(text: str) -> str:
    """Clean and preprocess text for TF-IDF analysis"""
    if pd.isna(text) or text is None:
        return ""
    
    # Convert to lowercase
    text = str(text).lower()
    
    # Remove special characters and extra whitespace
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def load_curriculum_data(filepath: str) -> pd.DataFrame:
    """Load curriculum data from CSV"""
    try:
        df = pd.read_csv(filepath)
        print(f"Loaded curriculum data: {len(df)} rows")
        return df
    except Exception as e:
        print(f"Error loading curriculum data: {e}")
        return pd.DataFrame()

def load_formats_data(filepath: str) -> pd.DataFrame:
    """Load formats data from CSV"""
    try:
        df = pd.read_csv(filepath)
        print(f"Loaded formats data: {len(df)} rows")
        return df
    except Exception as e:
        print(f"Error loading formats data: {e}")
        return pd.DataFrame()

def create_tfidf_matrices(curriculum_texts: List[str], format_texts: List[str]) -> Tuple[np.ndarray, np.ndarray, TfidfVectorizer]:
    """Create TF-IDF matrices for both datasets"""
    
    # Combine all texts for vocabulary building
    all_texts = curriculum_texts + format_texts
    
    # Initialize TF-IDF vectorizer
    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words='english',
        ngram_range=(1, 2),  # Use unigrams and bigrams
        min_df=2,  # Ignore terms that appear in less than 2 documents
        max_df=0.95  # Ignore terms that appear in more than 95% of documents
    )
    
    # Fit and transform all texts
    tfidf_matrix = vectorizer.fit_transform(all_texts)
    
    # Split back into curriculum and format matrices
    curriculum_matrix = tfidf_matrix[:len(curriculum_texts)]
    format_matrix = tfidf_matrix[len(curriculum_texts):]
    
    print(f"TF-IDF matrix shape - Curriculum: {curriculum_matrix.shape}, Formats: {format_matrix.shape}")
    
    return curriculum_matrix, format_matrix, vectorizer

def calculate_similarity_scores(curriculum_matrix: np.ndarray, format_matrix: np.ndarray) -> np.ndarray:
    """Calculate cosine similarity between curriculum and format texts"""
    similarity_matrix = cosine_similarity(curriculum_matrix, format_matrix)
    return similarity_matrix

def get_top_matches(similarity_matrix: np.ndarray, curriculum_df: pd.DataFrame, 
                   format_df: pd.DataFrame, top_k: int = 1) -> List[Dict]:
    """Get top matches for each curriculum item"""
    
    results = []
    
    for i, curriculum_row in curriculum_df.iterrows():
        # Get similarity scores for this curriculum item
        similarities = similarity_matrix[i]
        
        # Get top K matches
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        for j, idx in enumerate(top_indices):
            format_row = format_df.iloc[idx]
            similarity_score = similarities[idx]
            
            # Determine confidence level based on similarity score
            if similarity_score >= 0.5:
                confidence = "High"
            elif similarity_score >= 0.3:
                confidence = "Medium"
            elif similarity_score >= 0.15:
                confidence = "Low"
            else:
                confidence = "Very Low"
            
            # Create result entry
            result = {
                'grade': curriculum_row['grade'],
                'substandard_description': curriculum_row['substandard_description'],
                'substandard_id': curriculum_row['substandard_id'],
                'direct_instructions': format_row['flattened_content'],
                'match_confidence': confidence,
                'similarity_score': round(similarity_score, 3),
                'llm_explanation': ""  # Empty for TF-IDF matching
            }
            
            results.append(result)
    
    return results

def main():
    """Main function to run TF-IDF matching"""
    
    # File paths
    curriculum_file = "/Users/trilogy/Documents/EduLLM/curriculum.csv"
    formats_file = "/Users/trilogy/Documents/EduLLM/format-based/all_formats_extracted.csv"
    output_file = "/Users/trilogy/Documents/EduLLM/tfidf-extracted-instructions.csv"
    
    print("Starting TF-IDF matching process...")
    
    # Load data
    curriculum_df = load_curriculum_data(curriculum_file)
    formats_df = load_formats_data(formats_file)
    
    if curriculum_df.empty or formats_df.empty:
        print("Error: Could not load required data files")
        return
    
    # Preprocess text data
    print("Preprocessing text data...")
    curriculum_texts = [preprocess_text(text) for text in curriculum_df['substandard_description']]
    format_texts = [preprocess_text(text) for text in formats_df['flattened_content']]
    
    # Remove empty texts
    valid_curriculum_indices = [i for i, text in enumerate(curriculum_texts) if text]
    valid_format_indices = [i for i, text in enumerate(format_texts) if text]
    
    curriculum_texts = [curriculum_texts[i] for i in valid_curriculum_indices]
    format_texts = [format_texts[i] for i in valid_format_indices]
    
    curriculum_df_filtered = curriculum_df.iloc[valid_curriculum_indices].reset_index(drop=True)
    formats_df_filtered = formats_df.iloc[valid_format_indices].reset_index(drop=True)
    
    print(f"Valid curriculum texts: {len(curriculum_texts)}")
    print(f"Valid format texts: {len(format_texts)}")
    
    # Create TF-IDF matrices
    print("Creating TF-IDF matrices...")
    curriculum_matrix, format_matrix, vectorizer = create_tfidf_matrices(curriculum_texts, format_texts)
    
    # Calculate similarity scores
    print("Calculating similarity scores...")
    similarity_matrix = calculate_similarity_scores(curriculum_matrix, format_matrix)
    
    # Get top matches
    print("Finding top matches...")
    results = get_top_matches(similarity_matrix, curriculum_df_filtered, formats_df_filtered, top_k=1)
    
    # Create results DataFrame
    results_df = pd.DataFrame(results)
    
    # Save results
    print(f"Saving results to {output_file}...")
    results_df.to_csv(output_file, index=False)
    
    print(f"TF-IDF matching completed! Results saved to {output_file}")
    print(f"Total matches found: {len(results_df)}")
    
    # Print summary statistics
    confidence_counts = results_df['match_confidence'].value_counts()
    print("\nConfidence distribution:")
    for confidence, count in confidence_counts.items():
        print(f"  {confidence}: {count}")
    
    print(f"\nAverage similarity score: {results_df['similarity_score'].mean():.3f}")
    print(f"Max similarity score: {results_df['similarity_score'].max():.3f}")
    print(f"Min similarity score: {results_df['similarity_score'].min():.3f}")

if __name__ == "__main__":
    main()

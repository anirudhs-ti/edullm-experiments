#!/usr/bin/env python3
"""
Transform regenerated sequences to match the format expected by validate_generated_sequences.py
"""

import json
from datetime import datetime
from pathlib import Path

def transform_regenerated_sequences(input_file: str, output_file: str):
    """
    Extract regenerated sequences and format them to match the original structure.
    
    Args:
        input_file: Path to regenerated_sequences JSON file
        output_file: Path to save transformed sequences
    """
    # Load regenerated sequences
    with open(input_file, 'r', encoding='utf-8') as f:
        regenerated_data = json.load(f)
    
    # Create new structure matching the original format
    transformed_data = {
        "metadata": {
            "generation_timestamp": datetime.now().isoformat(),
            "total_substandards_processed": regenerated_data["metadata"]["total_lessons_regenerated"],
            "llm_model": regenerated_data["metadata"]["llm_model"],
            "generation_version": regenerated_data["metadata"]["generation_version"],
            "source": f"Transformed from {Path(input_file).name}"
        },
        "generated_sequences": []
    }
    
    # Transform each lesson's regenerated sequences
    for lesson in regenerated_data["regenerated_sequences"]:
        transformed_lesson = {
            "substandard_id": lesson["substandard_id"],
            "grade": float(lesson["grade"]),  # Ensure it's a float
            "substandard_description": lesson["substandard_description"],
            "assessment_boundary": lesson["assessment_boundary"],
            "generated_sequences": lesson["regenerated_sequences"]  # Extract just the new sequences
        }
        transformed_data["generated_sequences"].append(transformed_lesson)
    
    # Save transformed data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(transformed_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Transformed {len(transformed_data['generated_sequences'])} lessons")
    print(f"📄 Saved to: {output_file}")

if __name__ == "__main__":
    # Paths
    script_dir = Path(__file__).parent
    outputs_dir = script_dir.parent / "outputs"
    
    input_file = outputs_dir / "regenerated_sequences_20251031_123237.json"
    output_file = outputs_dir / "regenerated_sequences_for_validation_20251031.json"
    
    transform_regenerated_sequences(str(input_file), str(output_file))


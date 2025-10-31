#!/usr/bin/env python3
"""
Question Generation System - Main Script
Generates MCQ questions for Grade 3 mathematics from composed substandards.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict

# Import utilities
from utils import (
    load_substandards,
    load_misconceptions,
    convert_format_to_scaffolding,
    generate_plan,
    generate_question,
    load_prompt,
    LANGFUSE_AVAILABLE
)

# Import Langfuse decorator and client
from utils import LANGFUSE_AVAILABLE, langfuse_client, observe

if LANGFUSE_AVAILABLE:
    print("✅ Langfuse tracing enabled")
else:
    print("⚠️  Langfuse not available - tracing disabled")


class QuestionGenerator:
    """Main question generator orchestrator."""
    
    def __init__(
        self,
        composed_json_path: str,
        misconceptions_csv_path: str,
        num_substandards: int = 30,
        random_seed: int = None,
        model: str = "gemini/gemini-2.5-flash"
    ):
        self.num_substandards = num_substandards
        self.model = model
        
        print("=" * 80)
        print("QUESTION GENERATION SYSTEM")
        print("=" * 80)
        
        # Load data
        print("\n1. Loading data...")
        self.substandards = load_substandards(composed_json_path, num_substandards, random_seed)
        self.misconceptions_map = load_misconceptions(misconceptions_csv_path)
        
        # Load prompts
        self.plan_template = load_prompt("system_a_plan_generation.txt")
        self.question_template = load_prompt("system_b_question_generation.txt")
        
        # Results
        self.results = {
            "generated_questions": [],
            "stats": {"total_attempted": 0, "successful": 0, "failed": 0, "skipped": 0},
            "errors": []
        }
    
    @observe(name="generate_question_for_substandard")
    def _generate_single_question(self, data, question_num: int) -> Dict:
        """Generate one question for a substandard."""
        # Get misconceptions
        misconceptions = self.misconceptions_map.get(data.substandard_id, [])
        print(f"   Misconceptions: {len(misconceptions)} found")
        
        # Step 1: Convert format to scaffolding
        print(f"   Step 1: Converting format to scaffolding...")
        scaffolding = convert_format_to_scaffolding(data.format_data, self.model)
        
        # Step 2: Generate plan (System A)
        print(f"   Step 2: Generating plan with System A...")
        plan = generate_plan(data, misconceptions, self.plan_template, self.model)
        
        # Step 3: Generate question (System B)
        print(f"   Step 3: Generating question with System B...")
        question_id = f"q{question_num}"
        question = generate_question(
            plan, scaffolding, data, question_id, 
            self.question_template, self.model
        )
        
        return question
    
    def run(self) -> Dict:
        """Run question generation for all substandards."""
        print(f"\n2. Generating questions...")
        print("-" * 80)
        
        for i, data in enumerate(self.substandards, 1):
            print(f"\n[{i}/{len(self.substandards)}] Processing: {data.substandard_id}")
            
            try:
                question = self._generate_single_question(data, i)
                self.results["generated_questions"].append(question)
                self.results["stats"]["successful"] += 1
                print(f"✅ Successfully generated question {question['id']}")
                
            except Exception as e:
                self.results["stats"]["failed"] += 1
                self.results["errors"].append({
                    "substandard_id": data.substandard_id,
                    "error": str(e)
                })
                print(f"❌ Failed: {e}")
            
            self.results["stats"]["total_attempted"] += 1
        
        # Flush Langfuse if available
        if LANGFUSE_AVAILABLE and langfuse_client:
            print("\n3. Flushing Langfuse traces...")
            langfuse_client.flush()
        
        return self.results
    
    def save_results(self, output_path: str, grade: int = 3):
        """Save results to JSON file."""
        output = {
            "subject": "math",
            "grade": str(grade),
            "type": "mcq",
            "generated_questions": self.results["generated_questions"],
            "verbose": True,
            "metadata": {
                "generation_timestamp": datetime.now().isoformat(),
                "model": self.model,
                "num_substandards_requested": self.num_substandards,
                "stats": self.results["stats"]
            }
        }
        
        if self.results["errors"]:
            output["errors"] = self.results["errors"]
        
        # Save file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(output, indent=2, fp=f)
        
        print(f"\n4. Results saved to: {output_path}")
        print("\nGeneration Statistics:")
        print(f"   Total attempted: {self.results['stats']['total_attempted']}")
        print(f"   Successful: {self.results['stats']['successful']}")
        print(f"   Failed: {self.results['stats']['failed']}")
        print(f"   Skipped: {self.results['stats']['skipped']}")


def main(num_substandards: int = 30, seed: int = 42):
    """Main entry point."""
    # Paths
    base_path = Path("/workspaces/github-com-anirudhs-ti-edullm-experiments")
    composed_json = base_path / "Question Generation" / "data" / "composed_substandards.json"
    misconceptions_csv = base_path / "Experiment - Generate mappings" / "data" / "Copy of MATH DATA MODEL - 3rd Grade.csv"
    output_json = base_path / "Question Generation" / "outputs" / f"generated_questions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Configuration
    MODEL = "gemini/gemini-2.5-flash"
    GRADE = 3
    
    # Generate
    generator = QuestionGenerator(
        composed_json_path=str(composed_json),
        misconceptions_csv_path=str(misconceptions_csv),
        num_substandards=num_substandards,
        random_seed=seed,
        model=MODEL
    )
    
    generator.run()
    generator.save_results(str(output_json), grade=GRADE)
    
    print("\n" + "=" * 80)
    print("GENERATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    import sys
    
    # Parse arguments
    num = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    
    main(num_substandards=num, seed=seed)


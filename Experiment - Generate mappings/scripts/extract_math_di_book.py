
import os
import sys
import json
import PyPDF2
import pdfplumber
import tiktoken
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel
# from src.llms import produce_structured_response_gemini
from google import genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import sys
import copy

from dotenv import load_dotenv

load_dotenv()

llm= ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)
    

# Global mapping of skills to their chapter pages
skills_chapter_pages = {
        "Counting": {
            "chapter_start_page": 42,
            "chapter_end_page": 55,
            "instructional_sequence_pages": (43,43)
        },
        "Symbol Identification and Place Value": {
            "chapter_start_page": 56,
            "chapter_end_page": 84,
            "instructional_sequence_pages": (57,58)
        },
        "Basic Facts": {
            "chapter_start_page": 85,
            "chapter_end_page": 104,
            "instructional_sequence_pages": (85,85)
        },
        "Addition": {
            "chapter_start_page": 105,
            "chapter_end_page": 131,
            "instructional_sequence_pages": (106,106)
        },
        "Subtraction": {
            "chapter_start_page": 132,
            "chapter_end_page": 153,
            "instructional_sequence_pages": (133,133)
        },
        "Multiplication": {
            "chapter_start_page": 154,
            "instructional_sequence_pages": (156,156),
            "chapter_end_page": 180
        },
        "Division": {
            "chapter_start_page": 181,
            "instructional_sequence_pages": (182,182),
            "chapter_end_page": 217
        },
        "Problem Solving": {
            "chapter_start_page": 218,
            "instructional_sequence_pages": (219,220),
            "chapter_end_page": 217
        },
        "Measurement": {
            "chapter_start_page": 262,
            "instructional_sequence_pages": (263,265),
            "chapter_end_page": 300
        },
        "Fractions": {
            "chapter_start_page": 301,
            "instructional_sequence_pages": (305,309),
            "chapter_end_page": 375
        },
        "Decimals": {
            "chapter_start_page": 376,
            "instructional_sequence_pages": (377,379),
            "chapter_end_page": 407
        },
        "Percent, Ratio, Probability": {
            "chapter_start_page": 408,
            "instructional_sequence_pages": (409,409),
            "chapter_end_page": 434
        },
        "Data Analysis": {
            "chapter_start_page": 435,
            "instructional_sequence_pages": (436,437),
            "chapter_end_page": 459
        },
        "Geometry": {
            "chapter_start_page": 460,
            "instructional_sequence_pages": (461,467),
            "chapter_end_page": 494
        },
        "Pre-Algebra": {
            "chapter_start_page": 495,
            "instructional_sequence_pages": (496,498),
            "chapter_end_page": 529
        }
    }


def produce_structured_response_gemini(
    prompt: str,
    structure_model: Type[BaseModel],
    llm_model: str = "gemini-2.5-pro",
) -> Any:
    """Gemini structured response implementation."""
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": structure_model,
            },
        )
        # Parse JSON response into the Pydantic model
        json_text = response.candidates[0].content.parts[0].text
        return structure_model.model_validate_json(json_text)
    except Exception as e:
        logger.error(f"Gemini structured response generation failed: {e}")
        raise

def read_math_di_book():
    """Main function to process the Direct Instruction Mathematics book."""
    # Correct the path to go up one directory from scripts to project root, then into data
    project_root = os.path.dirname(os.path.dirname(__file__))
    pdf_path = os.path.join(project_root, "data", "Direct_Instruction_Mathematics.pdf")
    
    print(f"Processing PDF: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return

    # Initialize JSON file
    json_output_path = initialize_json_file()
    if not json_output_path:
        print("Failed to initialize JSON file. Exiting.")
        return None
    
    # Read pages using pdfplumber
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"Total pages in PDF: {len(pdf.pages)}")
            
            for skill, pages in skills_chapter_pages.items():
                print(f"\n{'='*60}")
                print(f"Processing skill: {skill}")
                print(f"{'='*60}")
                
                # Run both sequence and format processing in parallel using ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=2) as executor:
                    # Submit both tasks to run in parallel - each opens its own PDF instance
                    sequence_future = executor.submit(process_skill_sequence, pdf_path, skill, pages, json_output_path)
                    format_future = executor.submit(process_formats, pdf_path, skill, pages, json_output_path)
                    
                    # Wait for both to complete and handle results
                    futures = [sequence_future, format_future]
                    task_names = ["Sequence", "Format"]
                    
                    for future, task_name in zip(futures, task_names):
                        try:
                            future.result()  # This will raise an exception if the task failed
                            print(f"[{skill}] ✅ {task_name} processing completed successfully")
                        except Exception as e:
                            print(f"[{skill}] ❌ {task_name} processing failed: {e}")
                
                print(f"[{skill}] 🏁 Parallel processing completed")

            
            
            # Finalize the JSON file
            finalize_json_file(json_output_path)
            print(f"\n✅ All skills processed and saved to: {json_output_path}")
            return json_output_path
            
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None


class SequenceItem(BaseModel):
    """Individual sequence item within a grade progression."""
    sequence_number: int
    problem_type: str
    example_questions: Optional[List[str]] = []
    visual_aids: Optional[List[str]] = []

class GradeProgression(BaseModel):
    """Grade-level progression containing sequence items."""
    grade: int
    sequence: List[SequenceItem]

class SkillResponse(BaseModel):
    """Response for a single skill with multiple grade progressions."""
    name: str
    progression: List[GradeProgression]

class FormatStep(BaseModel):
    """Individual step in a format with teacher and student components."""
    step_number: int
    teacher_action: str
    student_response: Optional[str] = None
    notes: Optional[str] = None

class FormatPart(BaseModel):
    """A part within a format (e.g., Part A, Part B)."""
    part_name: str
    description: Optional[str] = None
    steps: List[FormatStep]

class Format(BaseModel):
    """Individual format within a skill/chapter."""
    format_number: str  # e.g., "7.1"
    title: str  # e.g., "EQUALITY INTRODUCTION"
    parts: List[FormatPart]

class ChapterFormatsResponse(BaseModel):
    """Response containing all formats for a chapter/skill."""
    skill_name: str
    chapter_pages: str
    formats: List[Format]

class PitfallsResponse(BaseModel):
    """Response containing pitfalls."""
    pitfalls: List[str]

def process_formats(pdf_path, skill, pages, json_output_path):
    """Process formats for a single skill from the PDF.
    
    Args:
        pdf_path: Path to the PDF file
        skill: The skill name
        pages: Dictionary containing page information for the skill
        json_output_path: Path to the JSON output file
    
    Returns:
        None (writes results directly to JSON file)
    """
    # Get chapter page range (entire chapter, not just instructional sequence)
    chapter_start_page = pages.get("chapter_start_page")
    chapter_end_page = pages.get("chapter_end_page")
    
    if not chapter_start_page or not chapter_end_page:
        print(f"[{skill}] ⚠️  No chapter page range defined, skipping format processing")
        return
    
    print(f"\n[{skill}] Extracting formats from chapter pages {chapter_start_page} to {chapter_end_page}")

    # Open PDF for this thread
    with pdfplumber.open(pdf_path) as pdf:
        # Validate page numbers (pdfplumber uses 0-based indexing)
        if chapter_start_page < 1 or chapter_end_page > len(pdf.pages):
            print(f"Error: Chapter page range {chapter_start_page}-{chapter_end_page} is out of bounds (1-{len(pdf.pages)}) for skill {skill}")
            
            # Write error to JSON
            format_data = {
                "skill_name": skill,
                "chapter_pages": f"{chapter_start_page}-{chapter_end_page}",
                "formats": [],
                "error": f"Chapter page range {chapter_start_page}-{chapter_end_page} is out of bounds",
                "processed_at": datetime.now().isoformat()
            }
            update_json_with_formats(json_output_path, skill, format_data)
            return

        # Extract text from entire chapter
        chapter_text = ""
        for page_num in range(chapter_start_page - 1, chapter_end_page):
            try:
                page = pdf.pages[page_num]
                text = page.extract_text()
                if text:
                    chapter_text += f"\n--- Page {page_num + 1} ---\n"
                    chapter_text += text + "\n"
            except Exception as e:
                print(f"[{skill}] ⚠️  Error extracting text from page {page_num + 1}: {e}")
                # Try alternative extraction method
                try:
                    # Use a more robust extraction method
                    text = page.extract_text(x_tolerance=3, y_tolerance=3)
                    if text:
                        chapter_text += f"\n--- Page {page_num + 1} ---\n"
                        chapter_text += text + "\n"
                        print(f"[{skill}] ✓ Alternative extraction succeeded for page {page_num + 1}")
                except Exception as e2:
                    print(f"[{skill}] ❌ Alternative extraction also failed for page {page_num + 1}: {e2}")
                    # Last resort: try PyPDF2 for this page
                    try:
                        print(f"[{skill}] 🔄 Trying PyPDF2 as last resort for page {page_num + 1}")
                        # Note: This would require opening the PDF with PyPDF2 separately
                        # For now, just mark the error
                        chapter_text += f"\n--- Page {page_num + 1} ---\n"
                        chapter_text += f"[ERROR: Could not extract text from page {page_num + 1}: {e2}]\n"
                    except:
                        chapter_text += f"\n--- Page {page_num + 1} ---\n"
                        chapter_text += f"[ERROR: Could not extract text from page {page_num + 1}]\n"
        
        print(f"[{skill}] Extracted {len(chapter_text)} characters from chapter")
        
        # Process with AI to extract formats and pitfalls
        try:
            print(f"[{skill}] Processing formats with Gemini...")
            formats_response = extract_chapter_formats(chapter_text, skill)
            
            print(f"[{skill}] Processing pitfalls with Gemini...")
            pitfalls_response = extract_pitfalls(chapter_text, skill)
            
            format_data = {
                "skill_name": formats_response.skill_name if formats_response else skill,
                "chapter_pages": f"{chapter_start_page}-{chapter_end_page}",
                "formats": [format_item.model_dump() for format_item in formats_response.formats] if formats_response else [],
                "pitfalls": pitfalls_response.pitfalls if pitfalls_response else [],
                "raw_text": chapter_text,
                "processed_at": datetime.now().isoformat()
            }
            print(f"[{skill}] ✓ Successfully extracted {len(format_data['formats'])} formats and {len(format_data['pitfalls'])} pitfalls")

        except Exception as e:
            print(f"[{skill}] ❌ Error extracting formats/pitfalls: {e}")
            format_data = {
                "skill_name": skill,
                "chapter_pages": f"{chapter_start_page}-{chapter_end_page}",
                "formats": [],
                "pitfalls": [],
                "raw_text": chapter_text,
                "error": str(e),
                "processed_at": datetime.now().isoformat()
            }

        # Write formats to JSON immediately
        update_json_with_formats(json_output_path, skill, format_data)
        print(f"[{skill}] 💾 Saved formats to JSON file")


def process_skill_sequence(pdf_path, skill, pages, json_output_path):
    """Process a single skill's instructional sequence from the PDF.
    
    Args:
        pdf_path: Path to the PDF file
        skill: The skill name
        pages: Dictionary containing page information for the skill
        json_output_path: Path to the JSON output file
    
    Returns:
        None (writes results directly to JSON file)
    """
    instructional_sequence_pages = pages["instructional_sequence_pages"]
    start_page, end_page = instructional_sequence_pages

    print(f"\n[{skill}] Extracting text from pages {start_page} to {end_page}")

    # Open PDF for this thread
    with pdfplumber.open(pdf_path) as pdf:
        # Validate page numbers (pdfplumber uses 0-based indexing)
        if start_page < 1 or end_page > len(pdf.pages):
            print(f"Error: Page range {start_page}-{end_page} is out of bounds (1-{len(pdf.pages)}) for skill {skill}")
            
            # Still write the error to JSON
            skill_data = {
                "name": skill,
                "instruction_sequence_pages": f"{start_page}-{end_page}",
                "raw_text": "",
                "progression": None,
                "error": f"Page range {start_page}-{end_page} is out of bounds"
            }
            update_json_with_skill(json_output_path, skill, skill_data)
            return

        # Extract text from pages
        instructional_sequence_text = ""
        for page_num in range(start_page - 1, end_page):
            try:
                page = pdf.pages[page_num]
                text = page.extract_text()
                if text:
                    instructional_sequence_text += text + "\n"
            except Exception as e:
                print(f"[{skill}] ⚠️  PDF PARSING ERROR on page {page_num + 1}: {e}")
                print(f"[{skill}] 🔍 Error type: {type(e).__name__}")
                print(f"[{skill}] 📄 This is a PDF reading issue, not an LLM issue")
                # Try alternative extraction method
                try:
                    # Use a more robust extraction method
                    text = page.extract_text(x_tolerance=3, y_tolerance=3)
                    if text:
                        instructional_sequence_text += text + "\n"
                        print(f"[{skill}] ✓ Alternative extraction succeeded for page {page_num + 1}")
                except Exception as e2:
                    print(f"[{skill}] ❌ Alternative extraction also failed for page {page_num + 1}: {e2}")
                    # Last resort: try PyPDF2 for this page
                    try:
                        print(f"[{skill}] 🔄 Trying PyPDF2 as last resort for page {page_num + 1}")
                        # Note: This would require opening the PDF with PyPDF2 separately
                        # For now, just mark the error
                        instructional_sequence_text += f"[ERROR: Could not extract text from page {page_num + 1}: {e2}]\n"
                    except:
                        instructional_sequence_text += f"[ERROR: Could not extract text from page {page_num + 1}]\n"
        
        print(f"[{skill}] Extracted {len(instructional_sequence_text)} characters of text")
        
        # Process with AI
        try:
            print(f"[{skill}] Processing with Gemini...")
            sequence = extract_instructional_sequence(instructional_sequence_text, skill)
            
            skill_data = {
                "name": sequence.name if sequence else skill,
                "instruction_sequence_pages": f"{start_page}-{end_page}",
                "raw_text": instructional_sequence_text,
                "progression": [grade_prog.model_dump() for grade_prog in sequence.progression] if sequence else None,
                "processed_at": datetime.now().isoformat()
            }
            print(f"[{skill}] ✓ Successfully processed")

        except Exception as e:
            print(f"[{skill}] ❌ Error extracting instructional sequence: {e}")
            skill_data = {
                "name": skill,
                "instruction_sequence_pages": f"{start_page}-{end_page}",
                "raw_text": instructional_sequence_text,
                "progression": None,
                "error": str(e),
                "processed_at": datetime.now().isoformat()
            }

        # Write this skill to JSON immediately
        update_json_with_skill(json_output_path, skill, skill_data)
        print(f"[{skill}] 💾 Saved to JSON file")


def extract_pitfalls(text, skill_name):
    """Extract pitfalls/don'ts from a chapter's text."""
    prompt = f"""
    Extract up to 10 concise pitfalls (don'ts, mistakes to avoid, common errors) from the chapter text for the skill "{skill_name}".
    
    Look for:
    - Statements about what NOT to do
    - Common mistakes students make
    - Things to avoid when teaching
    - Incorrect approaches
    - Warning statements
    - "Don't" statements
    - "Avoid" statements
    - "Never" statements
    
    Text: {text}
    
    Instructions:
    - Extract only the most important pitfalls/don'ts
    - Keep each pitfall concise (1-2 short sentences max)
    - Focus on actionable don'ts that would be useful for teachers
    - Don't include obvious or trivial warnings
    - If no clear pitfalls are found, return an empty list
    - Maximum 10 pitfalls
    
    Critical:
    - These are instructions meant for an online application, so don't include any classroom specific interaction such as "point to", or "say", or "ask", into an online equivalent, where the teacher is an application, and not a humanoid 
    - Example: Don't write "Teacher says 'here are 10 apples...'", just write "Display 'here are 10 apples...'"
    - Only extract what is explicitly mentioned in the text
    - Don't make up pitfalls that aren't clearly stated
    - Focus on educational/instructional pitfalls, not general safety warnings
    """

    response = produce_structured_response_gemini(prompt, PitfallsResponse)
    return response


def extract_chapter_formats(text, skill_name):
    """Extract all formats from a chapter's text."""
    prompt = f"""
    Extract all teaching formats from the chapter text for the skill "{skill_name}".
    
    Look for sections that start with "Format X.Y" followed by a title (e.g., "Format 7.1 EQUALITY INTRODUCTION").
    
    Each format typically contains:
    - A format number and title
    - Multiple parts (Part A, Part B, etc.)
    - Each part contains numbered steps with teacher actions and student responses
    - Teacher actions are in the left column, student responses in the right column
    
    Text: {text}

    Instructions:
    - Extract all formats found in the text
    - For each format, capture the format number (e.g., "7.1") and title
    - Identify all parts within each format (Part A, Part B, etc.)
    - For each part, extract all numbered steps
    - For each step, capture:
      - The step number
      - Teacher action (left column content)
      - Student response (right column content, if present)
      - Any parenthetical notes or instructions
    - Convert classroom-specific language to online application equivalents:
      - "Point to" → "Highlight" or "Display"
      - "Write on board" → "Display"
      - "Say" → "Present" or "Show"
      - Remove references to physical classroom interactions
    - Only extract what is explicitly present in the text
    - Maintain the sequential order of formats and steps as they appear

    Critical:
    - DON'T make up content that isn't in the text
    - Follow the schema exactly
    - Capture all formats in the chapter, not just the first one
    """

    response = produce_structured_response_gemini(prompt, ChapterFormatsResponse)
    return response


def extract_instructional_sequence(text, skill_name):
    """Extract the instructional sequence from the text."""
    prompt = f"""
    Extract the instructional sequence for the skill "{skill_name}" from the text.
    
    The text contains a table with columns: Grade Level, Problem Type, Performance Indicator
    
    Grade Level mappings:
    - K = Kindergarten = grade 0
    - 1 = First grade = grade 1  
    - 2 = Second grade = grade 2
    - 3 = Third grade = grade 3
    - etc.
    
    Text: {text}

    Instructions:
    - Group sequence items by grade level into separate GradeProgression objects
    - For each grade level (K, 1, 2, etc.), create a separate GradeProgression
    - Within each GradeProgression, sequence_number should start from 1 for that grade
    - Extract the problem types in the order they appear in the text
    - For each problem type, look at the Grade Level column to determine which GradeProgression it belongs to
    - Include example questions from the Performance Indicator column
    - Note any visual aids or materials mentioned in the Performance Indicator
    - The name field should be the skill name
    - Return all grade progressions in the progression array, ordered by grade level
    - For visual aids, describe the visual aid simply and succinctly

    Critical:
    - DON'T make up stuff that is not in the text - only extract what is explicitly mentioned in the text
    - Strictly follow the schema
    - Make sure there are no duplicate example questions or visual aids for the same problem type
    - We are extracting data for an online application, so don't include any classroom specific interaction such as "point to", or "say", or "ask", into an online equivalent, where the teacher is an application, and not a humanoid 
    - Example: Don't write "Teacher points to a row of 10 apples...", just write "Display a row of 10 apples..."
    """

    response = produce_structured_response_gemini(prompt, SkillResponse)
    
    return response

def initialize_json_file(output_filename: str = None) -> str:
    """Initialize or verify the JSON file with metadata, preserving existing data."""
    if output_filename is None:
        output_filename = f"di_math_instructional_sequences.json"
    
    # Get the project root directory and create the output path
    project_root = os.path.dirname(os.path.dirname(__file__))
    output_path = os.path.join(project_root, "data", output_filename)
    
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        # Check if file already exists
        if os.path.exists(output_path):
            # Read existing data
            with open(output_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # Update metadata but preserve existing skills
            existing_data["metadata"]["last_updated"] = datetime.now().isoformat()
            existing_data["metadata"]["status"] = "in_progress"
            
            # Write back the updated existing data
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Updated existing JSON file: {output_path}")
            print(f"  - Existing skills preserved: {len(existing_data.get('skills', {}))}")
            return output_path
        else:
            # Create new file with empty data structure
            initial_data = {
                "metadata": {
                    "extraction_timestamp": datetime.now().isoformat(),
                    "source_document": "Direct_Instruction_Mathematics.pdf",
                    "total_skills_processed": 0,
                    "extractor_version": "1.0",
                    "status": "in_progress"
                },
                "skills": {}
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Created new JSON file: {output_path}")
            return output_path
        
    except Exception as e:
        print(f"Error initializing JSON file: {e}")
        return None

def update_json_with_formats(output_path: str, skill_name: str, format_data: Dict) -> bool:
    """Update the JSON file by adding format data to an existing skill's data."""
    try:
        # Read existing data
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if the skill already exists in the skills section
        if "skills" not in data:
            data["skills"] = {}
        
        if skill_name not in data["skills"]:
            print(f"Warning: Skill '{skill_name}' not found in existing data. Creating new entry.")
            data["skills"][skill_name] = {"name": skill_name}
        
        # Add format data to the existing skill object
        data["skills"][skill_name]["formats"] = format_data["formats"]
        data["skills"][skill_name]["pitfalls"] = format_data["pitfalls"]
        data["skills"][skill_name]["chapter_pages"] = format_data["chapter_pages"]
        data["skills"][skill_name]["formats_processed_at"] = format_data["processed_at"]
        
        # Add error if present
        if "error" in format_data:
            data["skills"][skill_name]["formats_error"] = format_data["error"]
        # Update metadata
        data["metadata"]["last_updated"] = datetime.now().isoformat()
        
        # Write back to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Added formats to existing skill data: {skill_name}")
        return True
        
    except Exception as e:
        print(f"Error updating JSON file with formats for {skill_name}: {e}")
        return False


def update_json_with_skill(output_path: str, skill_name: str, skill_data: Dict) -> bool:
    """Update the JSON file by adding sequence data to an existing skill's data."""
    try:
        # Read existing data
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if the skill already exists in the skills section
        if "skills" not in data:
            data["skills"] = {}
        
        if skill_name not in data["skills"]:
            # Create new skill entry
            data["skills"][skill_name] = {"name": skill_name}
        
        # Add sequence data to the existing skill object
        data["skills"][skill_name]["name"] = skill_data["name"]
        data["skills"][skill_name]["instruction_sequence_pages"] = skill_data["instruction_sequence_pages"]
        data["skills"][skill_name]["progression"] = skill_data["progression"]
        data["skills"][skill_name]["processed_at"] = skill_data["processed_at"]
        
        # Add error if present
        if "error" in skill_data:
            data["skills"][skill_name]["sequence_error"] = skill_data["error"]
        
        # Optionally store raw sequence text (commented out to save space)
        # data["skills"][skill_name]["sequence_raw_text"] = skill_data["raw_text"]
        
        # Update metadata
        data["metadata"]["total_skills_processed"] = len(data["skills"])
        data["metadata"]["last_updated"] = datetime.now().isoformat()
        
        # Write back to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Added sequence to skill data: {skill_name}")
        return True
        
    except Exception as e:
        print(f"Error updating JSON file with {skill_name}: {e}")
        return False

def finalize_json_file(output_path: str) -> bool:
    """Mark the JSON file as completed."""
    try:
        # Read existing data
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Update metadata to mark as completed
        data["metadata"]["status"] = "completed"
        data["metadata"]["completion_timestamp"] = datetime.now().isoformat()
        
        # Calculate summary statistics
        successful_extractions = sum(1 for skill_data in data["skills"].values() 
                                   if skill_data.get('progression') is not None)
        failed_extractions = len(data["skills"]) - successful_extractions
        
        data["metadata"]["summary"] = {
            "successful_extractions": successful_extractions,
            "failed_extractions": failed_extractions,
            "success_rate": f"{(successful_extractions / len(data['skills']) * 100):.1f}%" if data["skills"] else "0%"
        }
        
        # Write back to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Finalized JSON file: {output_path}")
        print(f"  - Total skills: {len(data['skills'])}")
        print(f"  - File size: {os.path.getsize(output_path)} bytes")
        return True
        
    except Exception as e:
        print(f"Error finalizing JSON file: {e}")
        return False

def assign_grades_to_formats():
    """
    Assign grades and sequence numbers to each format based on the skill's progression.
    Updates the existing JSON file with grade and sequence_number fields for each format.
    """
    print("\n" + "="*80)
    print("🎯 Starting Grade Assignment to Formats")
    print("="*80)
    
    # Get the project root directory and read the JSON file
    project_root = os.path.dirname(os.path.dirname(__file__))
    json_path = os.path.join(project_root, "data", "di_math_instructional_sequences.json")
    
    if not os.path.exists(json_path):
        print(f"❌ JSON file not found: {json_path}")
        return None
    
    try:
        # Read existing data
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        skills_data = data.get("skills", {})
        updated_count = 0
        
        # Process each skill
        for skill_name, skill_data in skills_data.items():
            print(f"\n{'='*60}")
            print(f"Processing: {skill_name}")
            print(f"{'='*60}")
            
            progression = skill_data.get("progression", [])
            formats = skill_data.get("formats", [])
            
            if not formats:
                print(f"⚠️  No formats found for {skill_name}, skipping...")
                continue
            
            if not progression:
                print(f"⚠️  No progression found for {skill_name}, skipping...")
                continue
            
            # Process formats with LLM to assign grades
            try:
                updated_formats = assign_grades_with_llm(skill_name, progression, formats)
                
                if updated_formats:
                    # Update the formats in the data structure
                    data["skills"][skill_name]["formats"] = updated_formats
                    updated_count += 1
                    
                    # Debug: Verify the grades are in the data before saving
                    formats_with_grades = [f for f in data["skills"][skill_name]["formats"] if "assigned_grade" in f]
                    print(f"✅ Updated {len(updated_formats)} formats for {skill_name}")
                    print(f"   📊 Formats with assigned_grade in data: {len(formats_with_grades)}/{len(updated_formats)}")
                    
                    # SAVE IMMEDIATELY AFTER EACH SKILL
                    data["metadata"]["last_updated"] = datetime.now().isoformat()
                    data["metadata"]["grades_assigned_at"] = datetime.now().isoformat()
                    
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"   💾 Saved {skill_name} to JSON")
                    
                else:
                    print(f"⚠️  No updates made for {skill_name}")
                    
            except Exception as e:
                print(f"❌ Error processing {skill_name}: {e}")
                continue
        
        # Write back to file
        print(f"\n🔍 DEBUG: About to save. updated_count = {updated_count}")
        if updated_count > 0:
            print(f"📝 DEBUG: Preparing to write to {json_path}")
            data["metadata"]["last_updated"] = datetime.now().isoformat()
            data["metadata"]["grades_assigned_at"] = datetime.now().isoformat()
            
            print(f"💾 DEBUG: Opening file for writing...")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ DEBUG: File write completed")
            print(f"\n✅ Successfully updated {updated_count} skills with grade assignments")
            print(f"💾 Saved to: {json_path}")
            return json_path
        else:
            print("\n⚠️  No updates were made to any skills")
            return None
            
    except Exception as e:
        print(f"❌ Error reading/writing JSON file: {e}")
        return None


class GradeAssignment(BaseModel):
    """Grade assignment for a format."""
    format_number: str
    assigned_grade: int
    sequence_numbers: List[int]
    reasoning: str

class GradeAssignmentResponse(BaseModel):
    """Response containing grade assignments for all formats."""
    assignments: List[GradeAssignment]


def assign_grades_with_llm(skill_name: str, progression: List[Dict], formats: List[Dict]) -> List[Dict]:
    """
    Use LLM to assign grades and sequence numbers to formats based on progression.
    
    Args:
        skill_name: Name of the skill
        progression: List of grade progressions for the skill
        formats: List of formats for the skill
    
    Returns:
        Updated list of formats with grade and sequence_numbers fields added
    """
    prompt = f"""
    Analyze the teaching formats for the skill "{skill_name}" and assign appropriate grades based on the instructional sequence progression.
    
    INSTRUCTIONAL SEQUENCE PROGRESSION:
    {json.dumps(progression, indent=2)}
    
    TEACHING FORMATS TO ANALYZE:
    {json.dumps(formats, indent=2)}
    
    INSTRUCTIONS:
    1. For each format, determine which grade level it best aligns with based on:
       - The grade of the most relevant item in the sequence progression
    
    2. Assign sequence_numbers that map the format to relevant sequence items in the progression:
       - A format can map to multiple sequence numbers if it covers multiple problem types
       - Use the actual sequence numbers from the grade's progression
    
    3. Provide reasoning for each assignment explaining:
       - Why this format belongs to the assigned grade
       - Which specific problem types from the progression it addresses
    
    4. If a format appears to span multiple grades, assign it to the earliest appropriate grade
        
    CRITICAL:
    - Only use grade levels that exist in the progression
    - Sequence numbers must match actual numbers from the progression
    - Every format must be assigned a grade and at least one sequence number
    - Follow the schema exactly
    """
    
    # print(prompt)

    try:
        response = produce_structured_response_gemini(prompt, GradeAssignmentResponse)
        
        # Update formats with the assignments
        updated_formats = copy.deepcopy(formats)
        
        for assignment in response.assignments:
            # Find the matching format
            for i, format_item in enumerate(updated_formats):
                if format_item.get("format_number") == assignment.format_number:
                    # Add grade and sequence_numbers fields
                    updated_formats[i]["assigned_grade"] = assignment.assigned_grade
                    updated_formats[i]["sequence_numbers"] = assignment.sequence_numbers
                    updated_formats[i]["grade_assignment_reasoning"] = assignment.reasoning
                    print(f"  ✓ Format {assignment.format_number}: Grade {assignment.assigned_grade}, Sequences {assignment.sequence_numbers}")
                    
                    # Debug: Verify the field was actually added
                    if "assigned_grade" in updated_formats[i]:
                        print(f"    ✓ Verified: assigned_grade field added to format {assignment.format_number}")
                    else:
                        print(f"    ❌ ERROR: assigned_grade field NOT added to format {assignment.format_number}")
                    break
        
        # Debug: Check if any formats have the new fields
        formats_with_grades = [f for f in updated_formats if "assigned_grade" in f]
        print(f"  📊 Total formats with grades assigned: {len(formats_with_grades)}/{len(updated_formats)}")
        
        return updated_formats
        
    except Exception as e:
        print(f"  ❌ LLM processing error: {e}")
        raise


def run_pitfalls_extraction_only():
    """Run only pitfalls extraction on existing data, writing after each skill."""
    json_output_path = initialize_json_file()
    if not json_output_path:
        print("Failed to initialize JSON file. Exiting.")
        return
    
    # Load existing data
    try:
        with open(json_output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {json_output_path} not found. Run the full script first.")
        return
    
    print(f"Processing pitfalls extraction for {len(data['skills'])} skills...")
    
    # Get PDF path same way as read_math_di_book function
    project_root = os.path.dirname(os.path.dirname(__file__))
    pdf_path = os.path.join(project_root, "data", "Direct_Instruction_Mathematics.pdf")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for skill_name, skill_data in data['skills'].items():
                print(f"\n{'='*60}")
                print(f"Extracting pitfalls for skill: {skill_name}")
                print(f"{'='*60}")
                
                # Get pages for this skill
                if skill_name not in skills_chapter_pages:
                    print(f"Warning: No page mapping for skill {skill_name}")
                    continue
                
                skill_pages = skills_chapter_pages[skill_name]
                start_page = skill_pages["chapter_start_page"]
                end_page = skill_pages["chapter_end_page"]
                
                # Extract text from all chapter pages for this skill
                chapter_text = []
                for page_num in range(start_page, end_page + 1):
                    if page_num <= len(pdf.pages):
                        page = pdf.pages[page_num - 1]  # pdfplumber uses 0-based indexing
                        text = page.extract_text()
                        if text:
                            chapter_text.append(text)
                
                full_chapter_text = '\n\n'.join(chapter_text)
                
                # Extract pitfalls using LLM
                try:
                    pitfalls_response = extract_pitfalls(full_chapter_text, skill_name)
                    skill_data['pitfalls'] = pitfalls_response.pitfalls
                    print(f"[{skill_name}] ✅ Extracted {len(pitfalls_response.pitfalls)} pitfalls")
                    
                    # Save immediately after each skill
                    with open(json_output_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"[{skill_name}] 💾 Saved to JSON")
                    
                except Exception as e:
                    print(f"[{skill_name}] ❌ Pitfalls extraction failed: {e}")
                    skill_data['pitfalls'] = []
    
    except Exception as e:
        print(f"Error processing pitfalls: {e}")
        return
    
    print(f"\n🎉 Pitfalls extraction complete! Updated: {json_output_path}")


if __name__ == "__main__":
    
    
    # Check if we should run pitfalls extraction only
    if len(sys.argv) > 1 and sys.argv[1] == "--pitfalls":
        print("🚨 Running Pitfalls Extraction Only...")
        run_pitfalls_extraction_only()
    # Check if we should run grade assignment
    elif len(sys.argv) > 1 and sys.argv[1] == "--assign-grades":
        print("🎓 Running Grade Assignment Process...")
        result = assign_grades_to_formats()
        if result:
            print(f"\n✅ Grade assignment completed successfully!")
        else:
            print(f"\n❌ Grade assignment failed")
    else:
        print("🚀 Starting Direct Instruction Mathematics processing...")
        print("📝 Each skill will be processed and saved incrementally to JSON file")
        
        # Process all skills and write incrementally to JSON
        output_file = read_math_di_book()
        
        if output_file:
            print(f"\n🎉 Processing completed successfully!")
            print(f"📁 Final results saved to: {output_file}")
            
            # Read the final file to show summary
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    final_data = json.load(f)
            
                metadata = final_data.get("metadata", {})
                skills = final_data.get("skills", {})
                summary = metadata.get("summary", {})
            
                print(f"\n📊 Final Summary:")
                print(f"  📚 Total skills processed: {len(skills)}")
                print(f"  ✅ Successful extractions: {summary.get('successful_extractions', 0)}")
                print(f"  ❌ Failed extractions: {summary.get('failed_extractions', 0)}")
                print(f"  📈 Success rate: {summary.get('success_rate', '0%')}")
                
                # Show which skills had errors
                failed_skills = [skill for skill, data in skills.items() 
                               if data.get('progression') is None]
                
                if failed_skills:
                    print(f"\n⚠️  Skills with extraction errors:")
                    for skill in failed_skills:
                        error_msg = skills[skill].get('error', 'Unknown error')
                        print(f"    - {skill}: {error_msg}")
                else:
                    print(f"\n🎯 All skills processed successfully!")
                    
            except Exception as e:
                print(f"Error reading final summary: {e}")
        else:
            print("❌ Processing failed - no output file created.")


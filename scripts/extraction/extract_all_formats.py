#!/usr/bin/env python3
"""
Script to extract all formats from di_formats.json into a flattened CSV.
Each format will be represented as a single row with all its content flattened into one cell.
"""

import json
import csv
from typing import Dict, List, Any

def load_di_formats():
    """Load the di_formats.json file"""
    with open('di_formats.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def format_step_content(step: Dict[str, Any]) -> str:
    """Format a single step into a readable string"""
    parts = []
    
    step_num = step.get('step_number', 'N/A')
    parts.append(f"Step {step_num}")
    
    teacher_action = step.get('teacher_action', '')
    if teacher_action:
        parts.append(f"Teacher: {teacher_action}")
    
    student_response = step.get('student_response', '')
    if student_response:
        parts.append(f"Student: {student_response}")
    
    notes = step.get('notes', '')
    if notes:
        parts.append(f"Notes: {notes}")
    
    return " | ".join(parts)

def format_part_content(part: Dict[str, Any]) -> str:
    """Format a single part into a readable string"""
    parts = []
    
    part_name = part.get('part_name', '')
    if part_name:
        parts.append(f"Part: {part_name}")
    
    description = part.get('description', '')
    if description:
        parts.append(f"Description: {description}")
    
    # Format all steps
    if 'steps' in part and part['steps']:
        step_contents = []
        for step in part['steps']:
            step_content = format_step_content(step)
            step_contents.append(step_content)
        parts.append("Steps: " + " || ".join(step_contents))
    
    return " | ".join(parts)

def format_format_content(format_data: Dict[str, Any]) -> str:
    """Format a complete format into a flattened string"""
    parts = []
    
    # Add format metadata
    format_number = format_data.get('format_number', '')
    if format_number:
        parts.append(f"Format {format_number}")
    
    title = format_data.get('title', '')
    if title:
        parts.append(f"Title: {title}")
    
    # Add grade if present
    grade = format_data.get('grade', '')
    if grade:
        parts.append(f"Grade: {grade}")
    
    # Format all parts
    if 'parts' in format_data and format_data['parts']:
        part_contents = []
        for part in format_data['parts']:
            part_content = format_part_content(part)
            part_contents.append(part_content)
        parts.append("Parts: " + " || ".join(part_contents))
    
    return " | ".join(parts)

def extract_all_formats(di_formats_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all formats from the di_formats data"""
    formats = []
    
    if 'skills' not in di_formats_data:
        print("No 'skills' key found in di_formats.json")
        return formats
    
    for skill_name, skill_data in di_formats_data['skills'].items():
        print(f"Processing skill: {skill_name}")
        
        if 'formats' not in skill_data:
            print(f"  No formats found for {skill_name}")
            continue
        
        # Process all formats for this skill
        for format_data in skill_data['formats']:
            print(f"  Found format: {format_data.get('format_number', 'Unknown')} - {format_data.get('title', 'No title')}")
            
            # Flatten the format content
            flattened_content = format_format_content(format_data)
            
            formats.append({
                'skill': skill_name,
                'format_number': format_data.get('format_number', ''),
                'title': format_data.get('title', ''),
                'grade': format_data.get('grade', ''),
                'flattened_content': flattened_content,
                'raw_format_data': format_data
            })
    
    return formats

def save_to_csv(formats: List[Dict[str, Any]], output_file: str):
    """Save the formats to a CSV file"""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['skill', 'format_number', 'title', 'grade', 'flattened_content']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for format_item in formats:
            writer.writerow({
                'skill': format_item['skill'],
                'format_number': format_item['format_number'],
                'title': format_item['title'],
                'grade': format_item['grade'],
                'flattened_content': format_item['flattened_content']
            })

def main():
    """Main function to extract all formats"""
    print("Loading di_formats.json...")
    di_formats_data = load_di_formats()
    
    print("Extracting all formats...")
    formats = extract_all_formats(di_formats_data)
    
    print(f"\nFound {len(formats)} formats")
    
    # Save to CSV
    output_file = 'all_formats_extracted.csv'
    save_to_csv(formats, output_file)
    
    print(f"Results saved to {output_file}")
    
    # Print summary
    print("\nSummary:")
    for format_item in formats[:5]:  # Show first 5 as examples
        print(f"  {format_item['skill']} - {format_item['format_number']}: {format_item['title']}")
        print(f"    Preview: {format_item['flattened_content'][:150]}...")
        print()
    
    if len(formats) > 5:
        print(f"  ... and {len(formats) - 5} more formats")

if __name__ == "__main__":
    main()

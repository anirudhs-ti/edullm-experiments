import os
import re
import json
import argparse
import random
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import pdfplumber
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv


class ChapterPick(BaseModel):
    chapter_title: str
    start_page: Optional[int] = None
    confidence: float
    reasoning: Optional[str] = None


def extract_pages_text(pdf_path: str, start_page: int, end_page: int) -> str:
    parts: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        start = max(1, start_page)
        end = min(len(pdf.pages), end_page)
        for idx in range(start - 1, end):
            page_num = idx + 1
            page = pdf.pages[idx]
            text = page.extract_text() or ""
            if not text:
                try:
                    text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                except Exception:
                    text = ""
            parts.append(f"\n--- Page {page_num} ---\n{text}")
    return "\n".join(parts)


def parse_toc_entries(toc_text: str) -> List[Dict]:
    entries: List[Dict] = []
    # Heuristic: lines that end with a page number (1-4 digits)
    line_re = re.compile(r"^(?P<title>.*?\S)\s+\.?\s*(?P<page>\d{1,4})\s*$")
    raw_entries: List[Dict] = []
    for raw_line in toc_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = line_re.match(line)
        if not m:
            continue
        title = m.group("title")
        try:
            page = int(m.group("page"))
        except ValueError:
            continue
        if len(title) < 3:
            continue
        raw_entries.append({"title": title, "start_page": page})

    # Sort and dedupe
    seen = set()
    raw_entries.sort(key=lambda x: x["start_page"])
    filtered: List[Dict] = []
    for e in raw_entries:
        key = (e["title"], e["start_page"]) 
        if key in seen:
            continue
        seen.add(key)
        filtered.append(e)

    # Group subtopics under nearest preceding Chapter/Appendix
    def is_chapter_title(t: str) -> bool:
        t_norm = t.lower()
        return (
            t_norm.startswith("chapter ") or
            t_norm.startswith("appendix ") or
            t_norm in {"glossary", "references", "index"}
        )

    grouped: List[Dict] = []
    current: Optional[Dict] = None
    for e in filtered:
        title = e["title"]
        if is_chapter_title(title):
            # Start a new chapter bucket
            if current is not None:
                grouped.append(current)
            current = {
                "chapter_title": title,
                "start_page": e["start_page"],
                "subtopics": []
            }
        else:
            # Subtopic: attach to current if exists
            if current is None:
                # If ToC starts mid-section, create a generic bucket
                current = {
                    "chapter_title": "(Unlabeled Section)",
                    "start_page": e["start_page"],
                    "subtopics": []
                }
            current["subtopics"].append({
                "title": title,
                "start_page": e["start_page"]
            })

    if current is not None:
        grouped.append(current)

    return grouped


def llm_pick_chapter(format_item: Dict, toc_entries: List[Dict], toc_text: str) -> ChapterPick:
    # Prepare grouped list of chapters with subtopics
    def chapter_line(e: Dict) -> str:
        subs = e.get("subtopics", [])
        subs_txt = "; ".join([st["title"] for st in subs[:8]]) if subs else ""
        return (
            f"- {e['chapter_title']} (starts p. {e['start_page']})" +
            (f" — topics: {subs_txt}" if subs_txt else "")
        )

    chapters_list = "\n".join([chapter_line(e) for e in toc_entries[:50]])

    format_title = format_item.get("generated_format", {}).get("title") or format_item.get("problem_type")
    skill = format_item.get("skill")
    problem_type = format_item.get("problem_type")

    prompt = f"""
You are given:
1) A list of chapter or section entries (with starting pages) extracted from the book's table of contents.
2) A generated instructional format (skill + problem_type + title).

Task:
- Pick the single most relevant chapter/section title from the list that best matches the format.
- If possible, include the starting page number from the list.
- Return JSON matching the schema exactly.

Table of contents (subset):
{chapters_list}

Full ToC text (for nuance; prefer choosing from the list above):
"""
    prompt += toc_text[:12000]  # safety cap
    prompt += f"""

Format summary:
- Skill: {skill}
- Problem Type: {problem_type}
- Title: {format_title}

Respond with:
{{"chapter_title": string, "start_page": number|null, "confidence": number, "reasoning": string}}
Confidence should be between 0 and 1.
"""

    # Ensure API key is configured (support both env var names)
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        # Let the client try environment-based auth, but provide a clearer error if missing
        try:
            client = genai.Client()
        except Exception as e:
            raise RuntimeError("Google GenAI API key not found. Set GEMINI_API_KEY or GOOGLE_API_KEY in .env") from e
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": ChapterPick,
        },
    )
    try:
        json_text = response.candidates[0].content.parts[0].text
        return ChapterPick.model_validate_json(json_text)
    except Exception as e:
        # Fallback: try reading full text
        try:
            raw = getattr(response, "text", None) or str(response)
            return ChapterPick.model_validate_json(raw)
        except Exception:
            raise


def main():
    parser = argparse.ArgumentParser(description="Stage 1: Map up to N formats to likely chapters using ToC + LLM")
    parser.add_argument("--generated", required=True, help="Path to generated_formats_*.json")
    parser.add_argument("--pdf", required=True, help="Path to Direct_Instruction_Mathematics.pdf")
    parser.add_argument("--toc_start", type=int, default=10, help="ToC start page (1-based)")
    parser.add_argument("--toc_end", type=int, default=14, help="ToC end page (1-based, inclusive)")
    parser.add_argument("--num", type=int, default=6, help="Max number of random formats to map")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--out", required=False, help="Output prefix (without extension)")
    args = parser.parse_args()

    with open(args.generated, "r", encoding="utf-8") as f:
        gen_data = json.load(f)
    formats: List[Dict] = gen_data.get("generated_formats", [])
    if not formats:
        raise RuntimeError("No generated_formats found in input JSON")

    random.seed(args.seed)
    sample = random.sample(formats, k=min(args.num, len(formats)))

    toc_text = extract_pages_text(args.pdf, args.toc_start, args.toc_end)
    toc_entries = parse_toc_entries(toc_text)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_prefix = os.path.join(os.path.dirname(args.generated), f"stage1_chapter_mapping_{ts}")
    out_prefix = args.out or default_prefix
    os.makedirs(os.path.dirname(out_prefix), exist_ok=True)

    results: List[Dict] = []
    for item in sample:
        try:
            pick = llm_pick_chapter(item, toc_entries, toc_text)
            results.append({
                "skill": item.get("skill"),
                "problem_type": item.get("problem_type"),
                "format_title": item.get("generated_format", {}).get("title"),
                "pick": pick.model_dump(),
            })
        except Exception as e:
            results.append({
                "skill": item.get("skill"),
                "problem_type": item.get("problem_type"),
                "format_title": item.get("generated_format", {}).get("title"),
                "error": str(e),
            })

    out_json = f"{out_prefix}.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "generated_formats_path": args.generated,
                "pdf_path": args.pdf,
                "validated_at": datetime.now().isoformat(),
                "toc_pages": f"{args.toc_start}-{args.toc_end}",
                "num_items": len(results),
            },
            "toc_entries": toc_entries,
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    print(f"Stage 1 complete. Output: {out_json}")


if __name__ == "__main__":
    main()



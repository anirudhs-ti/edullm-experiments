import os
import re
import json
import argparse
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import pdfplumber
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv


class SupportJudgment(BaseModel):
    is_supported: bool
    confidence: float
    evidence_pages: List[int]
    reasoning: str


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def find_chapter_range(toc_entries: List[Dict], pick_title: str, pick_start: int) -> Tuple[int, int, Dict, int]:
    # Resolve the pick to a ToC entry by best match on title (substring both ways) and/or start_page
    pick_title_norm = normalize(pick_title)
    candidates = []
    for idx, e in enumerate(toc_entries):
        title_norm = normalize(e.get("chapter_title"))
        start_page = e.get("start_page")
        score = 0
        if pick_start and start_page == pick_start:
            score += 3
        if pick_title_norm and (pick_title_norm in title_norm or title_norm in pick_title_norm):
            score += 2
        if score > 0:
            candidates.append((score, idx, e))
    if not candidates:
        # fallback: choose closest start_page
        if pick_start:
            closest = min(
                [(abs(e.get("start_page", 10**9) - pick_start), idx, e) for idx, e in enumerate(toc_entries)],
                key=lambda x: x[0]
            )
            _, idx, e = closest
        else:
            idx, e = 0, toc_entries[0]
    else:
        candidates.sort(key=lambda x: (-x[0], x[1]))
        _, idx, e = candidates[0]

    start_page = e.get("start_page")
    # end_page = next chapter start - 1, else big number
    if idx + 1 < len(toc_entries):
        end_page = max(start_page, toc_entries[idx + 1].get("start_page") - 1)
    else:
        end_page = start_page + 40  # reasonable cap

    return start_page, end_page, e, idx


def extract_text_range(pdf_path: str, start_page: int, end_page: int) -> Tuple[str, Dict[int, str]]:
    pages: Dict[int, str] = {}
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
            pages[page_num] = text
            parts.append(f"\n--- Page {page_num} ---\n{text}")
    return "\n".join(parts), pages


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _find_actual_start(pdf: pdfplumber.PDF, guess_start: int, title: str, window: int = 60) -> Optional[int]:
    # Try to find the page within [guess_start - window, guess_start + window] that contains the chapter title
    query = _norm(title)
    total_pages = len(pdf.pages)
    start = max(1, guess_start - window)
    end = min(total_pages, guess_start + window)
    for page_num in range(start, end + 1):
        page = pdf.pages[page_num - 1]
        text = page.extract_text() or ""
        if not text:
            try:
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            except Exception:
                text = ""
        if not text:
            continue
        norm_text = _norm(text)
        if query and query in norm_text:
            return page_num
        # Fallback: try matching without the "Chapter X" prefix if present
        m = re.match(r"chapter\s+\d+\s+(.*)$", query)
        if m:
            tail = m.group(1)
            if tail and tail in norm_text:
                return page_num
    return None


def calibrate_page_offset(pdf_path: str, toc_entries: List[Dict]) -> int:
    # Use several chapter entries to compute the most likely global offset between ToC numbers and PDF indices
    candidates: List[int] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for e in toc_entries:
                title = e.get("chapter_title") or ""
                if not title.lower().startswith("chapter "):
                    continue
                toc_start = e.get("start_page")
                if not isinstance(toc_start, int):
                    continue
                found = _find_actual_start(pdf, toc_start, title, window=80)
                if found is not None:
                    candidates.append(found - toc_start)
                if len(candidates) >= 6:
                    break
    except Exception:
        return 0

    if not candidates:
        return 0
    # Choose the median offset for robustness
    candidates.sort()
    mid = len(candidates) // 2
    if len(candidates) % 2 == 1:
        return candidates[mid]
    return (candidates[mid - 1] + candidates[mid]) // 2


def llm_judge_support(format_item: Dict, chapter_text: str) -> SupportJudgment:
    # Prepare a concise description of the format
    skill = format_item.get("skill")
    problem_type = format_item.get("problem_type")
    title = format_item.get("generated_format", {}).get("title")

    prompt = f"""
You will receive a generated instructional format summary and the full text of a chapter from Direct Instruction Mathematics.
Decide whether the chapter explicitly supports teaching the given skill/problem type.
Return a JSON object with fields: is_supported (boolean), confidence (0..1), evidence_pages (array of up to 5 page numbers), reasoning (short explanation).

Format summary:
- Skill: {skill}
- Problem Type: {problem_type}
- Title: {title}

Chapter text:
{chapter_text[:24000]}

Respond ONLY in JSON per the schema.
"""

    # Initialize client
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        try:
            client = genai.Client()
        except Exception as e:
            raise RuntimeError("Google GenAI API key not found. Set GEMINI_API_KEY or GOOGLE_API_KEY in .env") from e

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": SupportJudgment,
        },
    )

    try:
        json_text = response.candidates[0].content.parts[0].text
        return SupportJudgment.model_validate_json(json_text)
    except Exception:
        raw = getattr(response, "text", None) or str(response)
        return SupportJudgment.model_validate_json(raw)


def main():
    parser = argparse.ArgumentParser(description="Stage 2: Validate formats against chapter content picked in Stage 1")
    parser.add_argument("--stage1", required=True, help="Path to stage1_chapter_mapping_*.json")
    parser.add_argument("--generated", required=True, help="Path to generated_formats_*.json")
    parser.add_argument("--pdf", required=True, help="Path to Direct_Instruction_Mathematics.pdf")
    parser.add_argument("--book_to_pdf_offset", type=int, default=17, help="PDF page = book page + offset (default 17)")
    parser.add_argument("--out", required=False, help="Output prefix (without extension)")
    args = parser.parse_args()

    with open(args.stage1, "r", encoding="utf-8") as f:
        s1 = json.load(f)
    toc_entries = s1.get("toc_entries", [])
    s1_results = s1.get("results", [])

    with open(args.generated, "r", encoding="utf-8") as f:
        gen_data = json.load(f)
    gen_formats: List[Dict] = gen_data.get("generated_formats", [])

    # Build quick index by (skill, problem_type, format_title)
    def key_of(it: Dict) -> Tuple[str, str, str]:
        return (
            normalize(it.get("skill")),
            normalize(it.get("problem_type")),
            normalize(it.get("generated_format", {}).get("title"))
        )

    idx_map: Dict[Tuple[str, str, str], Dict] = {}
    for it in gen_formats:
        idx_map[key_of(it)] = it

    # Use fixed offset
    page_offset = args.book_to_pdf_offset

    results_out: List[Dict] = []

    for pick in s1_results:
        s = normalize(pick.get("skill"))
        p = normalize(pick.get("problem_type"))
        t = normalize(pick.get("format_title"))
        fmt = idx_map.get((s, p, t))
        if fmt is None:
            # fallback: match by skill + problem_type
            fmt = next((it for it in gen_formats if normalize(it.get("skill")) == s and normalize(it.get("problem_type")) == p), None)
        if fmt is None:
            results_out.append({
                "skill": pick.get("skill"),
                "problem_type": pick.get("problem_type"),
                "format_title": pick.get("format_title"),
                "error": "Format not found in generated_formats",
            })
            continue

        pick_title = pick.get("pick", {}).get("chapter_title")
        pick_start = pick.get("pick", {}).get("start_page")
        if not pick_title or not pick_start:
            results_out.append({
                "skill": pick.get("skill"),
                "problem_type": pick.get("problem_type"),
                "format_title": pick.get("format_title"),
                "error": "Missing chapter title/start_page in stage1 pick",
            })
            continue

        start_page, end_page, resolved_toc, idx = find_chapter_range(toc_entries, pick_title, pick_start)
        start_page_real = start_page + page_offset
        if idx + 1 < len(toc_entries):
            next_start_real = toc_entries[idx + 1]["start_page"] + page_offset
            end_page_real = max(start_page_real, next_start_real - 1)
        else:
            end_page_real = start_page_real + 40

        chapter_text, page_texts = extract_text_range(args.pdf, start_page_real, end_page_real)

        # Extract first 50-100 words from start page for verification
        book_content_preview = ""
        if start_page_real in page_texts:
            words = page_texts[start_page_real].split()[:100]
            book_content_preview = " ".join(words)

        try:
            judgment = llm_judge_support(fmt, chapter_text)
            results_out.append({
                "skill": pick.get("skill"),
                "problem_type": pick.get("problem_type"),
                "format_title": pick.get("format_title"),
                "chapter": {
                    "title": resolved_toc.get("chapter_title"),
                    "start_page": start_page_real,
                    "end_page": end_page_real,
                    "page_offset": page_offset,
                    "book_content_preview": book_content_preview,
                },
                "judgment": judgment.model_dump(),
            })
        except Exception as e:
            results_out.append({
                "skill": pick.get("skill"),
                "problem_type": pick.get("problem_type"),
                "format_title": pick.get("format_title"),
                "chapter": {
                    "title": resolved_toc.get("chapter_title"),
                    "start_page": start_page_real,
                    "end_page": end_page_real,
                    "page_offset": page_offset,
                    "book_content_preview": book_content_preview,
                },
                "error": str(e),
            })

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_prefix = os.path.join(os.path.dirname(args.stage1), f"stage2_validation_{ts}")
    out_prefix = args.out or default_prefix
    os.makedirs(os.path.dirname(out_prefix), exist_ok=True)

    out_json = f"{out_prefix}.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "stage1_path": args.stage1,
                "generated_formats_path": args.generated,
                "pdf_path": args.pdf,
                "validated_at": datetime.now().isoformat(),
                "total_items": len(results_out),
            },
            "results": results_out,
        }, f, indent=2, ensure_ascii=False)

    print(f"Stage 2 complete. Output: {out_json}")


if __name__ == "__main__":
    main()

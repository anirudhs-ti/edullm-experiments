#!/usr/bin/env python3
"""
Grade-3-only hybrid matcher with per-row console updates.
- Local TF-IDF retrieval
- Escalate to Gemini only for 0.40 <= sim < 0.60
Writes: hybrid-extracted-instructions-grade3.csv
"""

import csv
import json
import math
import os
import re
import time
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional

from dotenv import load_dotenv
import google.generativeai as genai


def tokenize(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()
    tokens = [t for t in tokens if len(t) > 1 or t.isdigit()]
    return tokens


def build_tfidf(texts: List[List[str]]) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
    df: Counter = Counter()
    for toks in texts:
        for term in set(toks):
            df[term] += 1
    n_docs = len(texts)
    idf: Dict[str, float] = {}
    for term, d in df.items():
        idf[term] = math.log((n_docs + 1) / (d + 0.5)) + 1.0

    vectors: List[Dict[str, float]] = []
    for toks in texts:
        tf = Counter(toks)
        vec: Dict[str, float] = {}
        for term, c in tf.items():
            vec[term] = (c / (len(toks) or 1)) * idf.get(term, 0.0)
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        for k in list(vec.keys()):
            vec[k] /= norm
        vectors.append(vec)
    return vectors, idf


def cosine_sparse(a: Dict[str, float], b: Dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    s = 0.0
    for t, va in a.items():
        vb = b.get(t)
        if vb is not None:
            s += va * vb
    return s


def format_candidate(skill_name: str, progression: Dict, seq_item: Optional[Dict] = None) -> str:
    parts: List[str] = []
    if skill_name:
        parts.append(f"Skill: {skill_name}")
    grade = progression.get("grade")
    if grade is not None:
        parts.append(f"Grade: {grade}")
    title = progression.get("title")
    if title:
        parts.append(f"Title: {title}")
    fmt = progression.get("format_number")
    if fmt:
        parts.append(f"Format: {fmt}")
    for k in ("instruction_sequence_pages", "chapter_pages"):
        v = progression.get(k)
        if v:
            pretty = k.replace("_", " ").title()
            parts.append(f"{pretty}: {v}")
    
    if seq_item:
        # Single sequence item formatting
        seq_no = seq_item.get("sequence_number")
        if seq_no is not None:
            parts.append(f"Sequence: {seq_no}")
        pt = seq_item.get("problem_type")
        if pt:
            parts.append(f"Problem Type: {pt}")
        examples = seq_item.get("example_questions") or []
        if examples:
            parts.append("Examples: " + "; ".join(str(e) for e in examples[:5]))
        visuals = seq_item.get("visual_aids") or []
        if visuals:
            parts.append("Visual Aids: " + "; ".join(str(v) for v in visuals[:5]))
        for key, val in seq_item.items():
            if key in ("sequence_number", "problem_type", "example_questions", "visual_aids"):
                continue
            if val is None or val == "":
                continue
            pretty = key.replace("_", " ").title()
            parts.append(f"{pretty}: {val}")
    else:
        # Aggregate all sequences in the progression
        sequences = progression.get("sequence", []) or []
        for seq_item in sequences:
            seq_no = seq_item.get("sequence_number")
            if seq_no is not None:
                parts.append(f"Sequence {seq_no}: {seq_item.get('problem_type', '')}")
                examples = seq_item.get("example_questions") or []
                if examples:
                    parts.append(f"Examples: {'; '.join(str(e) for e in examples[:5])}")
                visuals = seq_item.get("visual_aids") or []
                if visuals:
                    parts.append(f"Visual Aids: {'; '.join(str(v) for v in visuals[:5])}")
    
    return " | ".join(parts)


def flatten_candidates(di: Dict, target_grade: str) -> List[Dict[str, str]]:
    candidates: List[Dict[str, str]] = []
    for skill_name, skill in di.get("skills", {}).items():
        for progression in skill.get("progression", []):
            grade = str(progression.get("grade"))
            if grade != target_grade:
                continue
            
            # Aggregate all sequences into one comprehensive candidate
            text = format_candidate(skill_name, progression, None)
            if text:
                candidates.append({
                    "grade": grade,
                    "skill_name": skill_name,
                    "format_number": str(progression.get("format_number", "")),
                    "title": progression.get("title", ""),
                    "sequence_number": "",
                    "problem_type": progression.get("title", ""),
                    "text": text,
                })
    return candidates


def load_environment() -> str:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    return api_key


def initialize_gemini(api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")


def create_similarity_prompt(curriculum_description: str, instruction_format: str) -> str:
    return f"""
You are an expert in educational curriculum alignment. Your task is to assess how well a direct instruction format matches a curriculum standard.

CURRICULUM STANDARD:
{curriculum_description}

DIRECT INSTRUCTION FORMAT:
{instruction_format}

Please evaluate the similarity between these two educational components on a scale of 0.0 to 1.0 and respond with ONLY a decimal number between 0.0 and 1.0 followed by a brief explanation.
"""


def get_llm_similarity(model, curriculum_description: str, instruction_format: str) -> Tuple[float, str]:
    try:
        prompt = create_similarity_prompt(curriculum_description, instruction_format)
        response = model.generate_content(prompt)
        response_text = (response.text or "").strip()
        import re as _re
        m = _re.search(r"^(\d+\.?\d*)", response_text)
        if m:
            score = float(m.group(1))
            score = max(0.0, min(1.0, score))
            explanation = response_text[len(m.group(0)):].strip()
            return score, explanation
        m = _re.search(r"(\d+\.?\d*)", response_text)
        if m:
            score = float(m.group(1))
            score = max(0.0, min(1.0, score))
            return score, response_text
        return 0.0, "Could not parse score"
    except Exception as e:
        print(f"Error getting LLM similarity: {e}")
        return 0.0, f"Error: {e}"


def confidence_from_score(score: float) -> str:
    if score >= 0.8: return "Very High"
    if score >= 0.6: return "High"
    if score >= 0.4: return "Medium"
    if score >= 0.2: return "Low"
    return "Very Low"


def main():
    target_grade = os.getenv("TARGET_GRADE_OVERRIDE", "3")
    with open("curriculum.csv", "r", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))
    rows = [r for r in all_rows if str(r.get("grade")) == target_grade]

    with open("di_formats.json", "r", encoding="utf-8") as f:
        di = json.load(f)
    candidates = flatten_candidates(di, target_grade)

    cand_tokens: List[List[str]] = [tokenize(c["text"]) for c in candidates]
    cand_vecs, cand_idf = build_tfidf(cand_tokens)

    # Initialize Gemini if available; otherwise proceed without escalation
    model = None
    try:
        api_key = load_environment()
        model = initialize_gemini(api_key)
    except Exception:
        model = None

    out_rows: List[Dict[str, str]] = []
    for i, row in enumerate(rows):
        description = row.get("substandard_description", "")
        # Build query vector in candidate IDF space
        q_tokens = tokenize(description)
        tf = Counter(q_tokens)
        q_vec: Dict[str, float] = {}
        for term, c in tf.items():
            idf_val = cand_idf.get(term, 0.0)
            q_vec[term] = (c / (len(q_tokens) or 1)) * idf_val
        norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
        for k in list(q_vec.keys()):
            q_vec[k] /= norm

        # Retrieve
        best_j = None
        best_sim = -1.0
        for j in range(len(candidates)):
            s = cosine_sparse(q_vec, cand_vecs[j])
            if s > best_sim:
                best_sim = s
                best_j = j

        direct = ""
        llm_explanation = ""
        final_score = max(0.0, best_sim)

        if best_j is not None:
            c = candidates[best_j]
            # Use full candidate text for CSV to maximize context
            direct = c.get("text", "")

            # Escalate borderline
            if model is not None and 0.4 <= best_sim < 0.6:
                score, explanation = get_llm_similarity(model, description, c["text"])
                final_score = score
                llm_explanation = explanation
                time.sleep(0.15)

        print(f"Row {i+1}/{len(rows)} | sim={best_sim:.3f} -> score={final_score:.3f} | {row.get('substandard_id','')}")

        out_rows.append({
            "grade": target_grade,
            "substandard_description": description,
            "substandard_id": row.get("substandard_id", ""),
            "direct_instructions": direct,
            "match_confidence": confidence_from_score(final_score),
            "similarity_score": f"{final_score:.3f}",
            "llm_explanation": llm_explanation,
        })

    out_path = f"hybrid-extracted-instructions-grade{target_grade}.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "grade",
            "substandard_description",
            "substandard_id",
            "direct_instructions",
            "match_confidence",
            "similarity_score",
            "llm_explanation",
        ])
        w.writeheader()
        w.writerows(out_rows)
    print(f"Completed! Output written to {out_path}")


if __name__ == "__main__":
    main()



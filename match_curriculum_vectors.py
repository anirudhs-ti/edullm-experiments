#!/usr/bin/env python3
"""
Vector-based matcher (no external API calls).
Builds a simple TF-IDF-like representation using Python stdlib only.
Generates vector-extracted-instructions.csv with top-1 match per row.
"""

import csv
import json
import math
import os
import re
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional


def tokenize(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()
    # remove single-char non-digits
    tokens = [t for t in tokens if len(t) > 1 or t.isdigit()]
    return tokens


def load_curriculum(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_di(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_candidate(progression: Dict, seq_item: Optional[Dict] = None) -> str:
    parts: List[str] = []
    title = progression.get("title")
    if title:
        parts.append(f"title: {title}")
    fmt = progression.get("format_number")
    if fmt:
        parts.append(f"format: {fmt}")
    if seq_item:
        pt = seq_item.get("problem_type")
        if pt:
            parts.append(f"problem: {pt}")
        examples = seq_item.get("example_questions") or []
        if examples:
            parts.append("examples: " + "; ".join(examples[:3]))
    return " | ".join(parts)


def flatten_candidates(di: Dict) -> List[Dict[str, str]]:
    candidates: List[Dict[str, str]] = []
    for skill_name, skill in di.get("skills", {}).items():
        for progression in skill.get("progression", []):
            grade = progression.get("grade")
            # sequence items
            for seq_item in progression.get("sequence", []) or []:
                text = format_candidate(progression, seq_item)
                candidates.append({
                    "grade": str(grade),
                    "skill_name": skill_name,
                    "format_number": str(progression.get("format_number", "")),
                    "title": progression.get("title", ""),
                    "sequence_number": str(seq_item.get("sequence_number", "")),
                    "problem_type": seq_item.get("problem_type", ""),
                    "text": text,
                })
            # progression-only as fallback
            text = format_candidate(progression, None)
            if text:
                candidates.append({
                    "grade": str(grade),
                    "skill_name": skill_name,
                    "format_number": str(progression.get("format_number", "")),
                    "title": progression.get("title", ""),
                    "sequence_number": "",
                    "problem_type": progression.get("title", ""),
                    "text": text,
                })
    return candidates


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
            vec[term] = (c / len(toks)) * idf.get(term, 0.0)
        # L2 normalize
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


def main():
    curriculum = load_curriculum("curriculum.csv")
    di = load_di("di_formats.json")
    candidates = flatten_candidates(di)

    # Build per-grade candidate indices
    grade_to_indices: Dict[str, List[int]] = defaultdict(list)
    candidate_tokens: List[List[str]] = []
    for idx, c in enumerate(candidates):
        grade_to_indices[str(c.get("grade"))].append(idx)
        candidate_tokens.append(tokenize(c["text"]))

    cand_vectors, idf = build_tfidf(candidate_tokens)

    out_rows: List[Dict[str, str]] = []
    total = len(curriculum)
    for i, row in enumerate(curriculum):
        if (i + 1) % 25 == 0:
            print(f"Progress: {i+1}/{total}")

        grade = str(row.get("grade"))
        description = row.get("substandard_description", "")
        q_tokens = tokenize(description)
        q_vecs, _ = build_tfidf([q_tokens])
        q_vec = q_vecs[0]

        best_j = None
        best_score = -1.0
        for j in grade_to_indices.get(grade, []):
            score = cosine_sparse(q_vec, cand_vectors[j])
            if score > best_score:
                best_score = score
                best_j = j

        direct = ""
        if best_j is not None:
            c = candidates[best_j]
            parts: List[str] = []
            if c.get("skill_name"):
                parts.append(f"Skill: {c['skill_name']}")
            if c.get("title"):
                parts.append(f"Title: {c['title']}")
            if c.get("problem_type"):
                parts.append(f"Problem Type: {c['problem_type']}")
            if c.get("format_number"):
                parts.append(f"Format: {c['format_number']}")
            if c.get("sequence_number"):
                parts.append(f"Sequence: {c['sequence_number']}")
            direct = " | ".join(parts)

        def bucket(s: float) -> str:
            if s >= 0.8: return "Very High"
            if s >= 0.6: return "High"
            if s >= 0.4: return "Medium"
            if s >= 0.2: return "Low"
            return "Very Low"

        out_rows.append({
            "grade": str(row.get("grade", "")),
            "substandard_description": description,
            "substandard_id": row.get("substandard_id", ""),
            "direct_instructions": direct,
            "match_confidence": bucket(best_score if best_score >= 0 else 0.0),
            "similarity_score": f"{best_score:.3f}" if best_score >= 0 else "0.000",
            "llm_explanation": ""
        })

    out_path = "vector-extracted-instructions.csv"
    fieldnames = [
        "grade",
        "substandard_description",
        "substandard_id",
        "direct_instructions",
        "match_confidence",
        "similarity_score",
        "llm_explanation",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)
    print(f"Completed! Output written to {out_path}")


if __name__ == "__main__":
    main()





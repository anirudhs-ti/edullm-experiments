import argparse
import os
from pathlib import Path
from datetime import datetime, timezone
import importlib
from typing import List, Tuple

import sys

# Load environment variables from Rules/.env if present (for Gemini and Langfuse keys)
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None

_ENV_LOADED = False
def _load_env_if_present() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if load_dotenv is not None and env_path.exists():
        load_dotenv(env_path)  # type: ignore
    _ENV_LOADED = True


def _require(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        print(
            f"Missing dependency: {module_name}. Install with: pip install {module_name}",
            file=sys.stderr,
        )
        raise


def extract_pdf_text_with_pages(pdf_path: Path) -> List[Tuple[int, str]]:
    pypdf = _require("pypdf")
    pages: List[Tuple[int, str]] = []
    with open(pdf_path, "rb") as f:
        reader = pypdf.PdfReader(f)
        for i, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            pages.append((i, text))
    return pages


def build_page_annotated_text(pages: List[Tuple[int, str]]) -> str:
    parts: List[str] = []
    for page_num, text in pages:
        header = f"[Page {page_num}]\n"
        parts.append(header + text.strip() + "\n\n")
    return "".join(parts)


def call_llm(model: str, system_prompt: str, user_content: str) -> str:
    _load_env_if_present()
    genai = _require("google.generativeai")
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY or GOOGLE_API_KEY for Gemini client")
    genai.configure(api_key=api_key)

    # Optional Langfuse trace
    lf_client = None
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        try:
            from langfuse import Langfuse  # type: ignore
            lf_client = Langfuse()
        except Exception:
            lf_client = None

    trace = None
    if lf_client is not None:
        try:
            trace = lf_client.trace(
                name="analyze_pdf_sequence",
                input={"model": model, "system": system_prompt, "user": user_content},
                metadata={"provider": "gemini"},
            )
        except Exception:
            trace = None

    try:
        g_model = genai.GenerativeModel(model_name=model, system_instruction=system_prompt)
        resp = g_model.generate_content(
            user_content,
            generation_config={"temperature": 0},
        )
        text = getattr(resp, "text", None) or ""
        if trace is not None:
            try:
                trace.update(output={"text": text})
            except Exception:
                pass
        return text
    except Exception as e:
        if trace is not None:
            try:
                trace.update(output={"error": str(e)})
            except Exception:
                pass
        raise RuntimeError(f"LLM call failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze one or all PDFs for evidence-backed descriptions of 'sequence' and "
            "'instructional format', then consolidate into a final answer."
        )
    )

    book_dir_default = Path(__file__).resolve().parent.parent / "book"
    parser.add_argument("--pdf", type=Path, default=None, help="Analyze a single PDF path")
    parser.add_argument(
        "--book-dir",
        type=Path,
        default=book_dir_default,
        help="Directory containing book PDFs (used when --pdf is not set)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.environ.get("GEMINI_MODEL", "gemini-2.5-pro"),
        help="Gemini model name (uses GEMINI_MODEL env or gemini-2.5-pro)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs",
        help="Directory to write outputs",
    )
    _load_env_if_present()
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    def analyze_one(pdf_path: Path) -> str:
        pages = extract_pdf_text_with_pages(pdf_path)
        annotated = build_page_annotated_text(pages)
        source = pdf_path.name
        system_prompt = (
            "You are an assistant that must ONLY use the provided PDF content. "
            "Task: derive detailed, evidence-backed explanations of two concepts: 'sequence' and 'instructional format'.\n"
            "Rules:\n"
            "- Only make claims that are explicitly supported by the text.\n"
            "- For EVERY claim, include page citations like [" + source + ", p. 20] based on provided [Page X] markers.\n"
            "- No outside knowledge, no speculation, no unsourced claims.\n"
            "Output strictly as Markdown with two top-level sections: 'Sequence' and 'Instructional Format'."
        )
        user_content = (
            "SOURCE: " + source + "\n\n" +
            "FULL PDF CONTENT BELOW (with [Page X] markers). From ONLY this content, produce detailed, "
            "evidence-backed explanations of 'sequence' and 'instructional format'. Every claim must "
            "include page citations like [" + source + ", p. X].\n\n" + annotated
        )
        findings = call_llm(args.model, system_prompt, user_content)
        out_file = args.out_dir / (
            f"findings_sequence_instructional_format_{source.replace(' ', '_').replace('/', '_')}_{timestamp}.md"
        )
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(f"Model: {args.model}\n")
            f.write(f"Source PDF: {source}\n")
            f.write(f"Generated UTC: {timestamp}\n\n")
            f.write(findings or "")
        print(f"Saved findings to: {out_file}")
        return findings or ""

    findings_by_pdf: List[Tuple[str, str]] = []
    if args.pdf is not None:
        findings_by_pdf.append((args.pdf.name, analyze_one(args.pdf)))
    else:
        pdfs = sorted([p for p in args.book_dir.iterdir() if p.suffix.lower() == ".pdf"])
        for pdf in pdfs:
            findings_by_pdf.append((pdf.name, analyze_one(pdf)))

    # Consolidate across PDFs
    consolidate_system = (
        "Consolidate the sources into a single coherent answer to these questions.\n"
        "Questions to answer (as top-level headings):\n"
        "1) What is a 'good' sequence? How to check it? What rules must be followed while creating a sequence? Are there specifics on what types of questions must be there?\n"
        "2) What is a 'good' format? How to check it? What rules must be followed while creating a format? What language should be used?\n"
        "Rules:\n"
        "- Use ONLY claims that appear in the provided sources.\n"
        "- EVERY claim must include a citation like [<filename>, p. X].\n"
        "- Merge duplicates, keep it concise but complete. No new claims."
    )
    sources_blob_parts: List[str] = []
    for name, txt in findings_by_pdf:
        sources_blob_parts.append("SOURCE: " + name + "\n\n" + (txt or "") + "\n\n")
    consolidate_user = (
        "Sources (each begins with 'SOURCE: <filename>'):\n\n" + "\n\n".join(sources_blob_parts)
    )
    consolidated = call_llm(args.model, consolidate_system, consolidate_user)
    final_out = args.out_dir / f"book_consolidated_sequence_format_{timestamp}.md"
    with open(final_out, "w", encoding="utf-8") as f:
        f.write(f"Model: {args.model}\n")
        f.write(f"Generated UTC: {timestamp}\n\n")
        f.write(consolidated or "")
    print(f"Saved consolidated findings to: {final_out}")


if __name__ == "__main__":
    main()



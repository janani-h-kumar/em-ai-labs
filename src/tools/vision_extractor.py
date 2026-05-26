# ============================================================
# vision_extractor.py — Receipt & Bank Statement Extractor
# Place at: C:\Workspace\em-ai-labs\src\tools\vision_extractor.py
#
# Dependencies:
#   pip install pymupdf pillow
#
# This tool is MODEL-AGNOSTIC.
# It does NOT import or instantiate any LLM client.
# The caller (orchestrator or agent) injects an llm_caller function.
#
# Contract for llm_caller:
#   A callable with signature:
#     llm_caller(prompt: str, image_b64: str | None, media_type: str | None) -> str
#   - prompt     : the full text prompt to send
#   - image_b64  : base64-encoded image string, or None for text-only calls
#   - media_type : e.g. "image/png", or None for text-only calls
#   Returns      : raw string response from the LLM
#
# Usage:
#   from src.tools.vision_extractor import extract_transactions
#
#   def my_llm(prompt, image_b64, media_type):
#       ...  # your LLM call here
#       return response_text
#
#   results = extract_transactions("receipt.jpg",        llm_caller=my_llm)
#   results = extract_transactions("statements/",        llm_caller=my_llm)
#   results = extract_transactions("bank_april.pdf",     llm_caller=my_llm)
# ============================================================

import base64
import json
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

import fitz  # PyMuPDF

# ============================================================
# Load config (language-agnostic JSON)
# ============================================================

_CONFIG_PATH = Path(__file__).parent.parent.parent / "configs" / "vision_config.json"

with open(_CONFIG_PATH, encoding="utf-8") as _f:
    _CONFIG = json.load(_f)

_CATEGORIES: list[str] = _CONFIG["categories"]
_DEFAULT_CURRENCY: str = _CONFIG["default_currency"]
_SUPPORTED_EXTENSIONS: set[str] = set(_CONFIG["supported_image_extensions"])

# Type alias for clarity
LLMCaller = Callable[[str, str | None, str | None], str]

logger = logging.getLogger(__name__)

# ============================================================
# PUBLIC ENTRY POINT
# ============================================================


def extract_transactions(
    input_path: str | Path,
    llm_caller: LLMCaller,
) -> list[dict]:
    """
    Extract structured transactions from a receipt or bank statement.

    Args:
        input_path : path to a single image, a directory of images, or a PDF
        llm_caller : injected LLM callable — see module docstring for contract

    Returns:
        List of transaction dicts with fields:
          date, merchant, amount, currency, type (credit|debit|unknown),
          category, category_source (fixed_list|inferred), description,
          confidence (high|medium|low), notes, source_file
    """
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Path not found: {input_path}")

    if input_path.is_dir():
        return _process_directory(input_path, llm_caller)
    elif input_path.suffix.lower() == ".pdf":
        return _process_pdf(input_path, llm_caller)
    elif input_path.suffix.lower() in _SUPPORTED_EXTENSIONS:
        return _process_single_image(input_path, llm_caller)
    else:
        raise ValueError(
            f"Unsupported file type: '{input_path.suffix}'. "
            f"Supported types: pdf, {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
        )


# ============================================================
# INTERNAL — Input handlers
# ============================================================


def _process_directory(dir_path: Path, llm_caller: LLMCaller) -> list[dict]:
    all_files = sorted(
        [
            f
            for f in dir_path.iterdir()
            if f.suffix.lower() in _SUPPORTED_EXTENSIONS or f.suffix.lower() == ".pdf"
        ]
    )

    if not all_files:
        raise ValueError(
            f"No supported files found in: {dir_path}. "
            f"Supported types: pdf, {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
        )

    images = [f for f in all_files if f.suffix.lower() in _SUPPORTED_EXTENSIONS]
    pdfs = [f for f in all_files if f.suffix.lower() == ".pdf"]

    # FIXED G004: Swapped out f-string for standard log parameterization
    logger.info(
        "[vision_extractor] '%s/' — %s image(s), %s PDF(s)", dir_path.name, len(images), len(pdfs)
    )

    all_transactions = []
    for f in all_files:
        # FIXED G004: Swapped out f-string for standard log parameterization
        logger.info("   -> %s", f.name)
        if f.suffix.lower() == ".pdf":
            all_transactions.extend(_process_pdf(f, llm_caller))
        else:
            all_transactions.extend(_process_single_image(f, llm_caller))

    return all_transactions


def _process_single_image(image_path: Path, llm_caller: LLMCaller) -> list[dict]:
    image_b64 = _encode_image(image_path)
    media_type = _get_media_type(image_path)
    prompt = _build_prompt()
    raw = llm_caller(prompt, image_b64, media_type)
    return _parse_response(raw, source_file=image_path.name)


def _process_pdf(pdf_path: Path, llm_caller: LLMCaller) -> list[dict]:
    """
    Per-page strategy:
      - Pages with extractable text  -> text prompt (cheaper, faster)
      - Pages with little/no text    -> rasterized image prompt (handles scans)
    Covers digital statements, scanned receipts, and mixed PDFs.
    """
    doc = fitz.open(str(pdf_path))
    all_transactions = []

    # FIXED G004: Swapped out f-string for standard log parameterization
    logger.info("[vision_extractor] PDF '%s' — %s page(s)", pdf_path.name, len(doc))

    prompt = _build_prompt()

    for page_num, page in enumerate(doc, start=1):
        source_label = f"{pdf_path.name} — page {page_num}"
        text = page.get_text("text").strip()

        if len(text) > 100:
            # FIXED G004: Swapped out f-string for standard log parameterization
            logger.info("   -> Page %s: text mode", page_num)
            prompt = _build_prompt(extracted_text=text)
            raw = llm_caller(prompt, None, None)
        else:
            # FIXED G004: Swapped out f-string for standard log parameterization
            logger.info("   -> Page %s: vision mode (scanned or image-only)", page_num)
            pix = page.get_pixmap(dpi=150)
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
            os.close(tmp_fd)
            try:
                pix.save(tmp_path)
                image_b64 = _encode_image(Path(tmp_path))
                raw = llm_caller(prompt, image_b64, "image/png")
            finally:
                os.unlink(tmp_path)

        all_transactions.extend(_parse_response(raw, source_file=source_label))

    doc.close()
    return all_transactions


# ============================================================
# INTERNAL — Prompt builder
# ============================================================


def _build_prompt(extracted_text: str | None = None) -> str:
    """
    Builds the extraction prompt.
    If extracted_text is provided, it is appended (text mode).
    Otherwise the prompt assumes an image will accompany it (vision mode).
    """
    categories_str = "\n".join(f"  - {c}" for c in _CATEGORIES)
    mode_instruction = (
        "The bank statement text is provided at the end of this prompt."
        if extracted_text
        else "The receipt or bank statement is provided as an image."
    )

    prompt = f"""You are a financial data extraction assistant.

{mode_instruction}

Extract ALL transactions visible in the document.
For each transaction return a JSON object with exactly these fields:

  date             : "YYYY-MM-DD" if parseable, otherwise the raw date string, or null
  merchant         : merchant, payee, or payer name (string or null)
  amount           : numeric value as a float, always positive (null if unreadable)
  currency         : currency code e.g. "INR", "USD" — default to "{_DEFAULT_CURRENCY}" if not shown
  type             : "credit" if money came IN, "debit" if money went OUT, "unknown" if unclear
  category         : best match from the fixed list below; if no confident match, infer a short label
  category_source  : "fixed_list" if matched from the list, "inferred" if you made it up
  description      : raw narration or label from the document (string or null)
  confidence       : "high", "medium", or "low" — how clearly readable this transaction is
  notes            : any ambiguity, assumption, or partial visibility (string or null)

Fixed category list — prefer these:
{categories_str}

Rules:
  - Return ONLY a valid JSON array. No explanation, no markdown, no code fences.
  - If the document has no transactions (e.g. a cover page), return an empty array: []
  - Do NOT invent transactions. Only extract what is explicitly present.
  - For bank statements: each row is one transaction.
  - For receipts: the total/grand total is the transaction. Line items are NOT separate transactions.
  - Credits: salary, refunds, cashbacks, transfers received.
  - Debits: purchases, EMI payments, fees, transfers sent.
"""

    if extracted_text:
        prompt += f"\n\nDocument text:\n\n{extracted_text}"

    return prompt


# ============================================================
# INTERNAL — Response parser
# ============================================================


def _parse_response(raw: str, source_file: str) -> list[dict]:
    """Parse LLM JSON response. Attaches source_file and applies field defaults."""
    cleaned = raw.strip()

    # Strip accidental markdown fences if any
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        transactions = json.loads(cleaned)
    except json.JSONDecodeError as e:
        # FIXED G004: Swapped out f-strings for standard log parameterization
        logger.warning("   [WARNING] JSON parse failed for '%s': %s", source_file, e)
        logger.info("   Response preview: %s", raw[:300])
        return []

    if not isinstance(transactions, list):
        # FIXED G004: Swapped out f-strings for standard log parameterization
        logger.warning(
            "   [WARNING] Expected list, got %s for '%s'", type(transactions).__name__, source_file
        )
        return []

    for txn in transactions:
        txn["source_file"] = source_file
        txn.setdefault("currency", _DEFAULT_CURRENCY)
        txn.setdefault("type", "unknown")
        txn.setdefault("confidence", "medium")
        txn.setdefault("category_source", "inferred")
        txn.setdefault("notes", None)

    return transactions


# ============================================================
# INTERNAL — Helpers
# ============================================================


def _encode_image(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def _get_media_type(image_path: Path) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
    }.get(image_path.suffix.lower(), "image/jpeg")

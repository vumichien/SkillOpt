"""MCQA evaluation: extract the chosen option letter and exact-match vs gold.

Dataset-agnostic. The "answer" is a single option label (e.g. ``C``). Extraction
is robust to several response shapes, in priority order:

  1. ``<answer>X</answer>`` tag (preferred — the rollout prompt requests it)
  2. an explicit "answer is X" / "answer: X" / "answer (X)" phrase
  3. the first standalone valid label token anywhere in the text

Only labels present in ``valid_labels`` are accepted, so reasoning prose that
mentions other capital letters does not produce a false extraction.
"""
from __future__ import annotations

import re

_DEFAULT_LABELS = ("A", "B", "C", "D", "E")


def _norm_labels(valid_labels: list[str] | tuple[str, ...] | None) -> list[str]:
    labels = [str(l).strip().upper() for l in (valid_labels or _DEFAULT_LABELS) if str(l).strip()]
    return labels or list(_DEFAULT_LABELS)


def _first_valid_letter(segment: str, valid: list[str]) -> str:
    """Return the first standalone single-letter token in *segment* that is valid.

    Used only on already-trusted segments (e.g. inside <answer> tags), where a
    bare letter is an intended choice rather than stray prose.
    """
    if not segment:
        return ""
    for token in re.findall(r"[A-Za-z]+", segment):
        upper = token.upper()
        if len(upper) == 1 and upper in valid:
            return upper
    return ""


def _option_formatted_letter(text: str, valid: list[str]) -> str:
    """First valid label written in option form: ``C.`` / ``C)`` / ``(C)`` / ``C:``."""
    for m in re.finditer(r"\b([A-Za-z])\s*[.):]", text):
        upper = m.group(1).upper()
        if upper in valid:
            return upper
    return ""


def _last_letter_token(text: str, valid: list[str]) -> str:
    """Valid label only if the response's last *word* is that single letter.

    Captures untagged endings like "... so I choose C" without grabbing a
    leading English article ("A dog ...") from arbitrary prose.
    """
    words = text.split()
    if not words:
        return ""
    last = words[-1].strip("().,;:!?<>\"'").upper()
    if last in valid:
        return last
    return ""


def extract_letter(
    text: str,
    valid_labels: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Extract the chosen option label from a target response. ``""`` if none."""
    valid = _norm_labels(valid_labels)
    if not text:
        return ""

    # 1. <answer>...</answer> (use the last tag if several)
    tagged = re.findall(r"<answer>(.*?)</answer>", text, re.DOTALL | re.IGNORECASE)
    if tagged:
        letter = _first_valid_letter(tagged[-1], valid)
        if letter:
            return letter

    # 2. whole (stripped) response is exactly one valid label
    stripped = text.strip().upper()
    if stripped in valid:
        return stripped

    # 3. explicit intent phrase: "answer/option/choice is|:|= X"
    phrase = re.search(
        r"\b(?:answer|option|choice)\b\s*(?:is|:|=|->)?\s*\(?\s*([A-Za-z])\b",
        text,
        re.IGNORECASE,
    )
    if phrase:
        upper = phrase.group(1).upper()
        if upper in valid:
            return upper

    # 4. a letter written in option form anywhere ("C." / "(C)" / "C)")
    letter = _option_formatted_letter(text, valid)
    if letter:
        return letter

    # 5. last standalone token is a valid label (untagged conclusions);
    #    deliberately NOT a first/any bare-letter scan, to avoid reading a
    #    leading article ("A ...") as label A.
    return _last_letter_token(text, valid)


def evaluate(
    prediction_text: str,
    gold_letters: list[str],
    valid_labels: list[str] | tuple[str, ...] | None = None,
) -> dict:
    """Evaluate one MC prediction. Returns em / predicted_answer / gold."""
    gold = [str(g).strip().upper() for g in (gold_letters or []) if str(g).strip()]
    predicted = extract_letter(prediction_text, valid_labels)
    em = 1.0 if predicted and predicted in gold else 0.0
    return {
        "em": em,
        "predicted_answer": predicted,
        "gold": gold,
    }

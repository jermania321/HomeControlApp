"""Classify a subject by its priority keywords."""


def classify_priority(subject):
    """Return HIGH, MEDIUM, or LOW based on keywords in ``subject``.

    A missing or empty subject is classified as LOW. HIGH keywords take
    precedence over MEDIUM keywords when both are present.
    """
    text = (subject or "").casefold()
    if "urgent" in text or "asap" in text:
        return "HIGH"
    if "meeting" in text or "reminder" in text:
        return "MEDIUM"
    return "LOW"

"""Classify a subject by its priority keywords."""


DEFAULT_RULES = {"high": ["urgent", "asap"], "medium": ["meeting", "reminder"]}

PRIORITY_COLORS = {"HIGH": "#a61b1b", "MEDIUM": "#8a6500", "LOW": "#247a3b"}
PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def priority_color(priority):
    """Return the inbox background color for a priority label."""
    return PRIORITY_COLORS.get(str(priority).upper(), "#404040")


def priority_rank(priority):
    """Return an ascending sort rank: HIGH, then MEDIUM, then LOW."""
    return PRIORITY_ORDER.get(str(priority).upper(), len(PRIORITY_ORDER))


def classify_priority(subject, rules=None):
    """Return HIGH, MEDIUM, or LOW based on keywords in ``subject``.

    A missing or empty subject is classified as LOW. HIGH keywords take
    precedence over MEDIUM keywords when both are present.
    """
    text = (subject or "").casefold()
    rules = rules or DEFAULT_RULES
    if any(str(word).casefold() in text for word in rules.get("high", []) if word):
        return "HIGH"
    if any(str(word).casefold() in text for word in rules.get("medium", []) if word):
        return "MEDIUM"
    return "LOW"

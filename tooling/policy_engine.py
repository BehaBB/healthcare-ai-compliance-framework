import re

def no_phi_rule(text: str) -> bool:
    if not text:
        return True

    patterns = [
        r"\bssn\b",
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN формат
        r"\bmedical record\b",
        r"\bpatient\b",
        r"\b\d{3}-\d{3}-\d{4}\b",  # phone
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",  # email
    ]

    text_lower = text.lower()

    for pattern in patterns:
        if re.search(pattern, text_lower):
            return False

    return True

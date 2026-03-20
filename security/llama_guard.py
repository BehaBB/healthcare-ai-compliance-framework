def is_safe(text: str) -> bool:
    # временная заглушка
    banned = ["ssn", "credit card", "medical record"]

    for word in banned:
        if word in text.lower():
            return False

    return True

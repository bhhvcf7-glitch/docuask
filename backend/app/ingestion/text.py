import re

DIACRITICS = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
CHAR_MAP = str.maketrans({
    "ـ": "", "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي",
    **{chr(0x0660 + n): str(n) for n in range(10)},
    **{chr(0x06F0 + n): str(n) for n in range(10)},
})


def normalize_arabic(text: str) -> str:
    return DIACRITICS.sub("", text.translate(CHAR_MAP))

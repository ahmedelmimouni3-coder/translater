from functions.gemini_ai import translate_with_gemini

CHUNK_CHARS = 6000


def _split_paragraphs(text, limit=CHUNK_CHARS):
    """Splits text into parts of at most `limit` characters, preferring line boundaries."""
    chunks, current = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if current and len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def translate_text(text, target_lang_name, target_lang_code=""):
    """Translates the whole text with Gemini and returns it, raising a clear error on failure."""
    if not text or not text.strip():
        raise ValueError("لا يوجد نص لترجمته")
    results = [translate_with_gemini(chunk, target_lang_name, target_lang_code) for chunk in _split_paragraphs(text)]
    return "\n".join(results)

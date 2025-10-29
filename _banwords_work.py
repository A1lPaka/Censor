import re, random
from PySide6.QtCore import QRegularExpression

opts = (QRegularExpression.CaseInsensitiveOption |
                QRegularExpression.UseUnicodePropertiesOption)

censor = ("#%!&", "&$!#%", "#$!@", "@$!#%", "!@#$", "%$!#", "$#&%!", "@#$%!")

def _make_search_regex(root: str):
    safe = re.escape(root)
    # pattern = rf"\b{safe}\b"
    rx_root = QRegularExpression(safe, QRegularExpression.UseUnicodePropertiesOption)
    return rx_root

def _build_search_spans(text_block, search_text):
    regex = _make_search_regex(search_text)
    text = text_block.toPlainText()
    it = regex.globalMatch(text)
    ranges = []
    while it.hasNext():
        match = it.next()
        start = match.capturedStart()
        length = match.capturedLength()
        if length > 0:
            ranges.append((start, length))

    return ranges

def _replace_pattern(ban_words, var):
    ban_words = [word for word in ban_words if word]

    if not ban_words:
        return r"(?!)"
    if var == 1:
        return r"\b[\p{L}\p{N}]*(?:" + "|".join(re.escape(root) + r"[\p{L}\p{N}]*" for root in ban_words) + r")\b"
    elif var == 2:
        return r"\b(?:" + "|".join(re.escape(word) for word in ban_words) + r")\b"

def _make_regex(roots, words, exc_roots, exc_words):

    roots_pattern = _replace_pattern(roots, 1)
    words_pattern = _replace_pattern(words, 2)
    exc_roots_pattern = _replace_pattern(exc_roots, 1)
    exc_words_pattern = _replace_pattern(exc_words, 2)

    rx_ban_roots = QRegularExpression(roots_pattern, opts)
    rx_ban_words = QRegularExpression(words_pattern, opts)
    rx_exceptions_roots = QRegularExpression(exc_roots_pattern, opts)
    rx_exceptions_words = QRegularExpression(exc_words_pattern, opts)

    return rx_ban_roots, rx_ban_words, rx_exceptions_roots, rx_exceptions_words

def _build_spans(text_block, rx_ban_roots=None, rx_ban_words=None, rx_exc_roots=None, rx_exc_words=None):
    text = text_block.toPlainText()

    seen = set()
    spans = []

    def add_span(start, end):
        if start < end and (start, end) not in seen:
            seen.add((start, end))
            cursor1 = text_block.textCursor()
            cursor1.setPosition(start)
            cursor2 = text_block.textCursor()
            cursor2.setPosition(end)
            spans.append((cursor1, cursor2))

    exceptions_starts_ends = []
    for rx in (rx_exc_roots, rx_exc_words): 
        it = rx.globalMatch(text)
        while it.hasNext(): 
            match = it.next() 
            start = match.capturedStart()
            length = match.capturedLength()
            end = start + length
            exceptions_starts_ends.append((start, end))

    for rx in (rx_ban_roots, rx_ban_words): 
        it = rx.globalMatch(text)
        while it.hasNext(): 
            match = it.next() 
            start = match.capturedStart()
            length = match.capturedLength()
            end = start + length
            if any(not (end <= exc_start or start >= exc_end) for exc_start, exc_end in exceptions_starts_ends):
                continue
            add_span(start, end)

    return spans

def mask(text: str, var: int) -> str:
    if var == 1:
        len_word = len(text)
        if len_word <= 2:
            return '*' * len_word
        return text[0] + '*' * (len_word - 2) + text[-1]
    if var == 2:
        return random.choice(censor)
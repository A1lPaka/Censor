from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
import unicodedata

class BanWordHighlighter(QSyntaxHighlighter):
    def __init__(self, document, spans):
        super().__init__(document)
        self.spans = spans or []
        self.spans_by_block = {}
        self.format_ban_word = QTextCharFormat() 
        self.format_ban_word.setBackground(QColor("#C42B1C"))

        self._reindex_spans_by_block()

    def _reindex_spans_by_block(self):
        spans_by_block = {}
        for start_cursor, end_cursor in self.spans:
            block_number = start_cursor.blockNumber()
            spans_by_block.setdefault(block_number, []).append((start_cursor, end_cursor))
        self.spans_by_block = spans_by_block

    def set_spans(self, spans):
        self.spans = spans or []
        self._reindex_spans_by_block()
        self.rehighlight()

    def clear_spans(self):
        self.spans = []
        self.spans_by_block = {}
        self.rehighlight()

    def highlightBlock(self, text: str):
        if not self.spans:
            return
        
        block = self.currentBlock()
        block_pos = block.position()
        block_len = block.length()
        block_num = block.blockNumber()

        for start_cursor, end_cursor in self.spans_by_block.get(block_num, []):
            start = start_cursor.position() - block_pos
            length = max(0, min(end_cursor.position(), block_pos + block_len) - (start_cursor.position()))

            if length > 0:
                segment = text[start:start+length]
                cut = -1
                for i, ch in enumerate(segment):
                    if ch.isspace() or unicodedata.category(ch).startswith('P'):
                        cut = i
                        break
                if cut != -1:
                    length = cut
            if length > 0:
                self.setFormat(start, length, self.format_ban_word)

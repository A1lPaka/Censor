from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTextEdit, QMenu, QGraphicsDropShadowEffect, QLineEdit
from PySide6.QtGui import QKeySequence, QShortcut, QFontInfo, QAction, QColor, QGuiApplication

class ZoomableTextEdit(QTextEdit):
    zoomChanged = Signal(float)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        font_size = self.font()
        font_size.setPointSize(12)
        self.setFont(font_size)
        self._base_point_size = QFontInfo(self.font()).pointSizeF()
        self._intended_percent = 100
        # ========== Задаем горячие клавиши ==========
        # Zoom In
        QShortcut(QKeySequence("Ctrl+="), self, activated=self.zoom_in_safe)   # Ctrl и «=»
        QShortcut(QKeySequence("Ctrl++"), self, activated=self.zoom_in_safe)   # Ctrl и «+» (значит Ctrl+Shift+=")

        # Zoom Out
        QShortcut(QKeySequence("Ctrl+-"), self, activated=self.zoom_out_safe)  # Ctrl и «-»
        QShortcut(QKeySequence("Ctrl+_"), self, activated=self.zoom_out_safe)  # Ctrl и «_» (Ctrl+Shift+"-")

        # Reset
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.reset_zoom)
        
    def wheelEvent(self, event):
        mods = event.modifiers()
        if mods & Qt.ControlModifier:
            dy = event.angleDelta().y()
            if dy > 0: 
                self.zoom_in_safe()
            elif dy < 0:
                self.zoom_out_safe()
            event.accept()
            return
        super().wheelEvent(event)

    def _apply_zoom(self, target: float):
        current_font = self.font()
        current_font.setPointSizeF(target)
        self.setFont(current_font)

    def zoom_in_safe(self):
        self.set_zoom_percent(min(self.zoom_percent() + 10, 500))

    def zoom_out_safe(self):
        self.set_zoom_percent(max(self.zoom_percent() - 10, 10))

    def reset_zoom(self):
        self.set_zoom_percent(100)

    def set_zoom_percent(self, percent: float):
        percent = max(10, min(500, percent))
        self._intended_percent = percent
        target = self._base_point_size * (percent / 100.0)
        self._apply_zoom(target)
        self.zoomChanged.emit(round(self._intended_percent))

    def zoom_percent(self) -> float:
        return round(getattr(self, "_intended_percent", 100))
    
    def contextMenuEvent(self, event):
        menu = RBCMenu(self)
        menu.show_for_text_edit(self, event.pos())
    
class RBCMenu(QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("rbc_menu")
        self.setWindowFlags(self.windowFlags() | Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(4, 4)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        self.undo_action = QAction(self.tr("  Отменить"), self, shortcut=QKeySequence.Undo)
        self.undo_action.setObjectName("rbc_menu_action")
        self.addAction(self.undo_action)
        self.redo_action = QAction(self.tr("  Повторить"), self, shortcut=QKeySequence.Redo)
        self.redo_action.setObjectName("rbc_menu_action")
        self.addAction(self.redo_action)
        self.addSeparator()
        self.cut_action = QAction(self.tr("  Вырезать"), self, shortcut=QKeySequence.Cut)
        self.cut_action.setObjectName("rbc_menu_action")
        self.addAction(self.cut_action)
        self.copy_action = QAction(self.tr("  Копировать"), self, shortcut=QKeySequence.Copy)
        self.copy_action.setObjectName("rbc_menu_action")
        self.addAction(self.copy_action)
        self.paste_action = QAction(self.tr("  Вставить"), self, shortcut=QKeySequence.Paste)
        self.paste_action.setObjectName("rbc_menu_action")
        self.addAction(self.paste_action)
        self.delete_action = QAction(self.tr("  Удалить"), self, shortcut=QKeySequence.Delete)
        self.delete_action.setObjectName("rbc_menu_action")
        self.addAction(self.delete_action)
        self.addSeparator()
        self.select_all_action = QAction(self.tr("  Выделить всё"), self, shortcut=QKeySequence.SelectAll)
        self.select_all_action.setObjectName("rbc_menu_action")
        self.addAction(self.select_all_action)

    def show_for_text_edit(self, text_edit: QTextEdit, pos):
        self.undo_action.triggered.connect(text_edit.undo)
        self.redo_action.triggered.connect(text_edit.redo)
        self.cut_action.triggered.connect(text_edit.cut)
        self.copy_action.triggered.connect(text_edit.copy)
        self.paste_action.triggered.connect(text_edit.paste)
        self.delete_action.triggered.connect(lambda: self._delete_action_triggered_text_edit(text_edit))
        self.select_all_action.triggered.connect(text_edit.selectAll)

        self.undo_action.setEnabled(text_edit.document().isUndoAvailable())
        self.redo_action.setEnabled(text_edit.document().isRedoAvailable())

        has_selection = text_edit.textCursor().hasSelection()
        self.cut_action.setEnabled(has_selection)
        self.copy_action.setEnabled(has_selection)
        self.delete_action.setEnabled(has_selection and not text_edit.isReadOnly())
        self.paste_action.setEnabled(text_edit.canPaste())

        self.move(text_edit.mapToGlobal(pos))
        self.show()

    def show_for_line_edit(self, line_edit: QLineEdit, pos):
        self.undo_action.triggered.connect(line_edit.undo)
        self.redo_action.triggered.connect(line_edit.redo)
        self.cut_action.triggered.connect(line_edit.cut)
        self.copy_action.triggered.connect(line_edit.copy)
        self.paste_action.triggered.connect(line_edit.paste)
        self.delete_action.triggered.connect(lambda: self._delete_action_triggered_line_edit(line_edit))
        self.select_all_action.triggered.connect(line_edit.selectAll)

        self.undo_action.setEnabled(line_edit.isUndoAvailable())
        self.redo_action.setEnabled(line_edit.isRedoAvailable())

        has_selection = bool(line_edit.selectedText())
        has_paste = QGuiApplication.clipboard().mimeData().hasText()
        self.cut_action.setEnabled(has_selection)
        self.copy_action.setEnabled(has_selection)
        self.delete_action.setEnabled(has_selection)
        self.paste_action.setEnabled(has_paste)

        self.move(line_edit.mapToGlobal(pos))
        self.show()

    def _delete_action_triggered_text_edit(self, editor: QTextEdit):
        cursor = editor.textCursor()
        if cursor.hasSelection() and not editor.isReadOnly():
            cursor.removeSelectedText()
        return

    def _delete_action_triggered_line_edit(self, editor: QLineEdit):
        cursor_pos = editor.cursorPosition()
        selected_text = editor.selectedText()
        if selected_text:
            start = cursor_pos - len(selected_text)
            editor.setSelection(start, len(selected_text))
            editor.insert("")

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtWidgets import QApplication, QFrame, QToolButton, QWidget, QHBoxLayout, QVBoxLayout, QSpinBox, QAbstractSpinBox, QLineEdit, QLabel
from PySide6.QtGui import QFont, QFontInfo
from CensorTextBlock import RBCMenu

class PopupSpinBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        if parent is not None and self.parentWidget() is None:
            self.setParent(parent)
        self.hide()  # Скрыт по умолчанию
        self._previous_focus = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.zoom_box = QSpinBox(self)

        self.zoom_box.setFrame(False)
        self.zoom_box.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.zoom_box.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.zoom_box.lineEdit().setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.zoom_box.setRange(10, 500)
        self.zoom_box.setSingleStep(5)
        self.zoom_box.setSuffix("%")
        self.zoom_box.setValue(100)
        self.zoom_box.setKeyboardTracking(False)
        self.zoom_box.setAlignment(Qt.AlignCenter)
        self.zoom_box.setFocusPolicy(Qt.ClickFocus)
        metrics = self.zoom_box.fontMetrics()
        self.zoom_box.setFixedWidth(metrics.horizontalAdvance("0100%0") + 16)
        layout.addWidget(self.zoom_box)

    def open_at(self, anchor_button: QToolButton):
        parent = self.parentWidget()
        button_center = anchor_button.mapTo(parent, anchor_button.rect().center())
        button_top_left = anchor_button.mapTo(parent, anchor_button.rect().topLeft())

        self.adjustSize()
        popup_width = self.sizeHint().width()
        popup_height = self.sizeHint().height()

        px = int(button_center.x() - popup_width / 2)
        py = button_top_left.y() - popup_height - 4

        self.move(px, py)

        self._previous_focus = QApplication.focusWidget()
        self.show()
        self.raise_()
        self.setFocus()
        self.zoom_box.setFocus()

        self._host_widget = self.window()
        self._host_window = self._host_widget.windowHandle()

        QTimer.singleShot(0, lambda: QApplication.instance().installEventFilter(self))

    def eventFilter(self, obj, event):
        event_type = event.type()

        if obj is self:
            return False
        
        if isinstance(obj, QWidget):
            if self.isAncestorOf(obj):
                return False
        
        if event_type in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
            global_pos = event.globalPosition().toPoint()
            global_rect = self.rect().translated(self.mapToGlobal(self.rect().topLeft()))
            if not global_rect.contains(global_pos):
                self.close()
            return False
            
        if event_type in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd):
            touch_points = event.points()
            for point in touch_points:
                global_pos = point.globalPosition().toPoint()
                global_rect = self.rect().translated(self.mapToGlobal(self.rect().topLeft()))
                if not global_rect.contains(global_pos):
                    self.close()
                    break
            return False
        
        if event_type == QEvent.Wheel:
            global_pos = event.globalPosition().toPoint()
            global_rect = self.rect().translated(self.mapToGlobal(self.rect().topLeft()))
            if not global_rect.contains(global_pos):
                self.close()
            return False
        
        if event_type == QEvent.ApplicationDeactivate:
            self.close()
            return False

        if event_type in (QEvent.Move, QEvent.Resize):
            if obj is getattr(self, "_host_widget", None) or obj is getattr(self, "_host_window", None):
                self.close()
            return False
        
        return False
    
    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        self._host_widget = None
        self._host_window = None
        if self._previous_focus is not None:
            self._previous_focus.setFocus()
            self._previous_focus = None
        super().closeEvent(event)

class ButtonPopup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        if parent is not None and self.parentWidget() is None:
            self.setParent(parent)
        self.hide()  # Скрыт по умолчанию
        self._previous_focus = None
        
        self.root_layout = QHBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.chrome = QFrame(self)
        self.chrome.setObjectName("chrome")
        self.chrome.setFrameShape(QFrame.NoFrame)
        self.root_layout.addWidget(self.chrome)

        self.layout_buttons = QVBoxLayout(self.chrome)
        self.layout_buttons.setContentsMargins(0, 0, 0, 0)
        self.layout_buttons.setSpacing(0)

    def add_option(self, text, slot):
        button = QToolButton(self)
        button.setObjectName("popup_button")
        button.setAutoRaise(True)
        button.setText(text)
        button.clicked.connect(lambda checked=False: (slot(), self.close()))
        self.layout_buttons.addWidget(button)

    def clear_options(self):
        while self.layout_buttons.count():
            item = self.layout_buttons.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def open_at(self, anchor_button: QToolButton):
        parent = self.parentWidget()
        button_center = anchor_button.mapTo(parent, anchor_button.rect().center())
        button_top_left = anchor_button.mapTo(parent, anchor_button.rect().topLeft())

        self.adjustSize()
        popup_width = self.sizeHint().width()
        popup_height = self.sizeHint().height()

        px = int(button_center.x() - popup_width / 2)
        py = button_top_left.y() - popup_height - 4

        self.move(px, py)

        self._previous_focus = QApplication.focusWidget()
        self.show()
        self.raise_()
        self.setFocus()

        self._host_widget = self.window()
        self._host_window = self._host_widget.windowHandle()

        QTimer.singleShot(0, lambda: QApplication.instance().installEventFilter(self))

    def size_setting(self, text: str):
        metrics = self.fontMetrics() # для вычисления ширины кнопки
        width = metrics.horizontalAdvance(text) + 25
        for i in range(self.layout_buttons.count()):
            widget = self.layout_buttons.itemAt(i).widget()
            if isinstance(widget, QToolButton):
                widget.setFixedWidth(width)

    def eventFilter(self, obj, event):
        event_type = event.type()

        if obj is self:
            return False
        
        if isinstance(obj, QWidget):
            if self.isAncestorOf(obj):
                return False
        
        if event_type in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
            global_pos = event.globalPosition().toPoint()
            global_rect = self.rect().translated(self.mapToGlobal(self.rect().topLeft()))
            if not global_rect.contains(global_pos):
                self.close()
            return False
            
        if event_type in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd):
            touch_points = event.points()
            for point in touch_points:
                global_pos = point.globalPosition().toPoint()
                global_rect = self.rect().translated(self.mapToGlobal(self.rect().topLeft()))
                if not global_rect.contains(global_pos):
                    self.close()
                    break
            return False

        if event_type == QEvent.Wheel:
            global_pos = event.globalPosition().toPoint()
            global_rect = self.rect().translated(self.mapToGlobal(self.rect().topLeft()))
            if not global_rect.contains(global_pos):
                self.close()
            return False

        if event_type == QEvent.ApplicationDeactivate:
            self.close()
            return False

        if event_type in (QEvent.Move, QEvent.Resize):
            if obj is getattr(self, "_host_widget", None) or obj is getattr(self, "_host_window", None):
                self.close()
            return False
        
        return False
    
    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        self._host_widget = None
        self._host_window = None
        if self._previous_focus is not None:
            self._previous_focus.setFocus()
            self._previous_focus = None
        super().closeEvent(event)

class SearchPopup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        if parent is not None and self.parentWidget() is None:
            self.setParent(parent)
        self.hide()  # Скрыт по умолчанию
        self._previous_focus = None
        self._current_button = None

        self.icon_font = QFont()
        for fam in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            self.icon_font.setFamily(fam)
            if QFontInfo(self.icon_font).family() == fam:
                break

        self.root_layout = QHBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.chrome = QFrame(self)
        self.chrome.setObjectName("chrome")
        self.chrome.setFrameShape(QFrame.NoFrame)
        self.root_layout.addWidget(self.chrome)

        self.layout_contents = QVBoxLayout(self.chrome)
        self.layout_contents.setContentsMargins(0, 0, 0, 0)
        self.layout_contents.setSpacing(0)

        self.search_edit_holder = QWidget(self)
        self.search_edit_holder.setObjectName("search_edit_holder")

        self.search_edit_layout = QHBoxLayout(self.search_edit_holder)
        self.search_edit_layout.setContentsMargins(3, 3, 4, 0)
        self.search_edit_layout.setSpacing(4)

        self.search_change_button = QToolButton(self)
        self.search_change_button.setObjectName("search_change_button")
        self.search_change_button.setText("\ue70d")
        self.search_change_button.setFont(self.icon_font)
        self.search_change_button.setToolTip(self.tr("Открыть параметры замены"))
        metrics = self.search_change_button.fontMetrics() # для вычисления ширины кнопки
        width = metrics.horizontalAdvance("✕") + 9
        self.search_change_button.setFixedWidth(width)
        self.search_change_button.setFixedHeight(width)
        self.search_change_button.clicked.connect(lambda: self.change_mode())

        self.search_edit = QLineEdit(self)
        self.search_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.search_edit.installEventFilter(self)
        self.search_edit.setObjectName("search_edit")
        self.search_edit.setPlaceholderText(self.tr("Поиск..."))
        self.search_edit.setClearButtonEnabled(False) # Кнопка очистки текста
        self.search_edit.setFocusPolicy(Qt.ClickFocus)
        self.search_edit.setFixedWidth(250)
        self.search_edit.setFixedHeight(24)

        self.search_label = QLabel(self)
        self.search_label.setObjectName("search_label")
        self.search_label.setText("0 из 0")

        self.search_prev_button = QToolButton(self)
        self.search_prev_button.setObjectName("search_prev_button")
        self.search_prev_button.setText("🡡")
        self.search_prev_button.setToolTip(self.tr("Предыдущее совпадение"))
        metrics = self.search_prev_button.fontMetrics() # для вычисления ширины кнопки
        width = metrics.horizontalAdvance("✕") + 9
        self.search_prev_button.setFixedWidth(width)
        self.search_prev_button.setFixedHeight(width)

        self.search_next_button = QToolButton(self)
        self.search_next_button.setObjectName("search_next_button")
        self.search_next_button.setText("🡣")
        self.search_next_button.setToolTip(self.tr("Следующее совпадение"))
        metrics = self.search_next_button.fontMetrics() # для вычисления ширины кнопки
        width = metrics.horizontalAdvance("✕") + 9
        self.search_next_button.setFixedWidth(width)
        self.search_next_button.setFixedHeight(width)

        self.search_close_button = QToolButton(self)
        self.search_close_button.setObjectName("search_close_button")
        self.search_close_button.setText("✕")
        self.search_close_button.setShortcut("Esc")
        self.search_close_button.setToolTip(self.tr("Закрыть поиск"))
        metrics = self.search_close_button.fontMetrics() # для вычисления ширины кнопки
        width = metrics.horizontalAdvance("✕") + 9
        self.search_close_button.setFixedWidth(width)
        self.search_close_button.setFixedHeight(width)
        self.search_close_button.clicked.connect(lambda: self.search_close())

        self.search_edit_layout.addWidget(self.search_change_button)
        self.search_edit_layout.addWidget(self.search_edit)
        self.search_edit_layout.addWidget(self.search_label)
        self.search_edit_layout.addStretch(1)
        self.search_edit_layout.addWidget(self.search_prev_button)
        self.search_edit_layout.addWidget(self.search_next_button)
        self.search_edit_layout.addWidget(self.search_close_button)

        self.search_edit_layout.setAlignment(Qt.AlignTop)

        self.long_separator = QFrame(self)
        self.long_separator.setObjectName("long_separator")
        self.long_separator.setFrameShape(QFrame.HLine)
        self.long_separator.setFrameShadow(QFrame.Sunken)
        self.long_separator.setLineWidth(1)
        self.long_separator.setFixedHeight(1)
        self.long_separator.setFixedWidth(460)
        self.long_separator.hide()  # Скрыт по умолчанию

        self.change_edit_holder = QWidget(self)
        self.change_edit_holder.setObjectName("change_edit_holder")
        self.change_edit_holder.hide()  # Скрыт по умолчанию

        self.change_edit_layout = QHBoxLayout(self.change_edit_holder)
        self.change_edit_layout.setContentsMargins(3, 3, 4, 0)
        self.change_edit_layout.setSpacing(4)

        self.change_spacer_button = QToolButton(self)
        self.change_spacer_button.setObjectName("search_change_button")
        metrics = self.change_spacer_button.fontMetrics() # для вычисления ширины кнопки
        width = metrics.horizontalAdvance("✕") + 9
        self.change_spacer_button.setFixedWidth(width)
        self.change_spacer_button.setFixedHeight(width)
        self.change_spacer_button.setEnabled(False)

        self.change_edit = QLineEdit(self)
        self.change_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.change_edit.installEventFilter(self)
        self.change_edit.setObjectName("change_edit")
        self.change_edit.setPlaceholderText(self.tr("Заменить на..."))
        self.change_edit.setClearButtonEnabled(False) # Кнопка очистки текста
        self.change_edit.setFocusPolicy(Qt.ClickFocus)
        self.change_edit.setFixedWidth(250)
        self.change_edit.setFixedHeight(24)

        self.change_one_button = QToolButton(self)
        self.change_one_button.setObjectName("change_one_button")
        self.change_one_button.setText(self.tr("Заменить"))
        self.change_one_button.setToolTip(self.tr("Заменить текущее совпадение"))

        self.change_all_button = QToolButton(self)
        self.change_all_button.setObjectName("change_all_button")
        self.change_all_button.setText(self.tr("Заменить всё"))
        self.change_all_button.setToolTip(self.tr("Заменить все совпадения"))

        self.change_edit_layout.addWidget(self.change_spacer_button)
        self.change_edit_layout.addWidget(self.change_edit)
        self.change_edit_layout.addWidget(self.change_one_button)
        self.change_edit_layout.addWidget(self.change_all_button)

        self.change_edit_layout.setAlignment(Qt.AlignTop)

        self.layout_contents.addWidget(self.search_edit_holder)
        self.layout_contents.addWidget(self.long_separator)
        self.layout_contents.addWidget(self.change_edit_holder)

        self.layout_contents.setAlignment(self.long_separator, Qt.AlignHCenter)

        self.chrome.setMinimumWidth(480)
        self.chrome.setMinimumHeight(32)

    def change_mode(self):
        if self.chrome.minimumHeight() == 32:
            self.chrome.setMinimumHeight(65) 
            self.search_change_button.setText("\ue70e")
            self.search_change_button.setToolTip(self.tr("Закрыть параметры замены"))
            self.long_separator.show()
            self.change_edit_holder.show()
            self.adjustSize()
            self.updateGeometry()
        else:
            self.chrome.setMinimumHeight(32)
            self.search_change_button.setText("\ue70d")
            self.search_change_button.setToolTip(self.tr("Открыть параметры замены"))
            self.long_separator.hide()
            self.change_edit_holder.hide()
            self.adjustSize()
            self.updateGeometry()

    def search_close(self):
        self.change_mode() if self.chrome.minimumHeight() != 32 else None
        self.close()

    def open_at(self, anchor_button: QToolButton):
        self._current_button = anchor_button
        parent = self.parentWidget()
        button_bottom_right = anchor_button.mapTo(parent, anchor_button.rect().bottomRight())

        self.adjustSize()
        popup_width = self.sizeHint().width()

        px = button_bottom_right.x() - popup_width + 2
        py = button_bottom_right.y() + 3

        self.move(px, py)

        self._previous_focus = QApplication.focusWidget()
        self.show()
        self.raise_()
        self.setFocus()

        self._host_widget = self.window()
        self._host_window = self._host_widget.windowHandle()

        QTimer.singleShot(0, lambda: QApplication.instance().installEventFilter(self))

    def size_setting(self, text: str):
        metrics = self.fontMetrics() # для вычисления ширины кнопки
        width = metrics.horizontalAdvance(text) + 25
        for i in range(self.search_edit_layout.count()):
            widget = self.search_edit_layout.itemAt(i).widget()
            if isinstance(widget, QToolButton):
                widget.setFixedWidth(width)
    
    def eventFilter(self, obj, event) -> bool:
        et = event.type()

        search_edit = getattr(self, "search_edit", None)
        change_edit = getattr(self, "change_edit", None)
        if obj is search_edit and et == QEvent.ContextMenu:
            menu = RBCMenu(self)
            menu.show_for_line_edit(search_edit, event.pos())
            return True
        if obj is change_edit and et == QEvent.ContextMenu:
            menu = RBCMenu(self)
            menu.show_for_line_edit(change_edit, event.pos())
            return True

        if obj is self:
            return False
        
        if isinstance(obj, QWidget) and self.isAncestorOf(obj):
            return False

        if et == QEvent.ApplicationDeactivate:
            self.close()
            return False

        if et in (QEvent.Move, QEvent.Resize):
            if obj is getattr(self, "_host_widget", None) or obj is getattr(self, "_host_window", None):
                self.open_at(self._current_button)
            return False

        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        self._host_widget = None
        self._host_window = None
        if self._previous_focus is not None:
            self._previous_focus.setFocus()
            self._previous_focus = None
        super().closeEvent(event)

    def _retranslate_ui(self):
        self.search_edit.setPlaceholderText(self.tr("Поиск...")), self.search_change_button.setToolTip(self.tr("Открыть параметры замены")), self.change_one_button.setToolTip(self.tr("Заменить текущее совпадение"))
        self.change_edit.setPlaceholderText(self.tr("Заменить на...")), self.search_prev_button.setToolTip(self.tr("Предыдущее совпадение")), self.change_all_button.setToolTip(self.tr("Заменить все совпадения"))
        self.change_one_button.setText(self.tr("Заменить")), self.search_next_button.setToolTip(self.tr("Следующее совпадение")), self.search_change_button.setToolTip(self.tr("Закрыть параметры замены"))
        self.change_all_button.setText(self.tr("Заменить всё")), self.search_close_button.setToolTip(self.tr("Закрыть поиск")), self.search_change_button.setToolTip(self.tr("Открыть параметры замены"))
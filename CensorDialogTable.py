import locale
from typing import Literal
import os
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import QFrame, QPushButton, QWidget, QHBoxLayout, QVBoxLayout, QSizePolicy, QStyle, QMenuBar, QStatusBar, QDialog, QTableView, QHeaderView, QStyledItemDelegate, QStyleOptionViewItem, QMessageBox
from PySide6.QtGui import QAction, QColor, QPen, QIcon, QKeySequence
from CensorTextBlock import RBCMenu
from _utils import  res_path

os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false"
locale.setlocale(locale.LC_COLLATE, '')

class CensorTable(QAbstractTableModel):
    def __init__(self, rows = None, parent = None):
        super().__init__(parent)
        self._header = [self.tr("Запрещенные корни"), self.tr("Запрещенные слова"), self.tr("Исключаемые корни"), self.tr("Исключаемые слова")]
        self._empty_row = ["", "", "", ""]
        self._rows = rows or [self._empty_row.copy() for i in range(31)]
        self.sort_direction = None  # None, "a-z", "z-a"
        self._was_edited = False  # Флаг, указывающий, было ли редактирование таблицы
        self._header_tips = [
            self.tr("Список нецензурных корней.<br><i>Пример: *гром* - \"по*гром*\", \"*гром*ить\", \"про*гром*ыхать</i>.<br>Все слова, содержащие эти корни,<br>будут считаться нарушением."),
            self.tr("Список нецензурных слов.<br><i>Пример: *гром* - \"*гром*\", <b>не</b> \"*гром*ить\".<br>Только точные совпадения с этими словами,<br>будут считаться нарушением."),
            self.tr("Список корней-исключений.<br><i>Пример: *громк* — «*громк*ий», \"бес*громк*ий\"</i>.<br>Слова, содержащие эти корни,<br><b>не</b> будут считаться нарушением."),
            self.tr("Список слов-исключений.<br><i>Пример: *громкий* — только слово \"*громкий*\"</i>.<br>Точные совпадения из этого списка<br><b>не</b> будут считаться нарушением.")
        ]

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self._rows[0]) if self._rows else 0
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return self._rows[index.row()][index.column()]
        return None
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._header[section]
            if role == Qt.ToolTipRole:
                return self._header_tips[section] if 0 <= section < len(self._header_tips) else None

        # Вертикальный заголовок (номера строк)
        if orientation == Qt.Vertical:
            if role == Qt.DisplayRole:
                return str(section + 1)
            if role == Qt.ToolTipRole:
                return self.tr("Строка %1").replace("%1", str(section + 1))

        return None
    
    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
    
    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        if role == Qt.EditRole:
            row = index.row()
            col = index.column()
            self._rows[row][col] = str(value)
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])

            # Автоматически добавляем пустую строку, если редактируется последняя строка
            if row == self.rowCount() - 1:
                last = self._rows[-1]
                if any((cell.strip() != "") for cell in last):
                    self.insertRows(self.rowCount(), 1)
            return True
        return False
    
    def insertRows(self, row, count=1, parent=QModelIndex()):
        self.beginInsertRows(QModelIndex(), row, row + count - 1)
        for _ in range(count):
            self._rows.insert(row, self._empty_row.copy())
        self.endInsertRows()
        return True
    
    def fill_table(self, ban_roots, ban_words, exception_roots, exception_words):
        combined = []  # [ban_roots, ban_words, exception_roots, exception_words]
        max_length = max(len(ban_roots), len(ban_words), len(exception_roots), len(exception_words))
        for i in range(max_length):
            row = [
                ban_roots[i] if i < len(ban_roots) else "",
                ban_words[i] if i < len(ban_words) else "",
                exception_roots[i] if i < len(exception_roots) else "",
                exception_words[i] if i < len(exception_words) else ""
            ]
            combined.append(row)

        if len(combined) < 30:
            for _ in range(30 - len(combined)):
                combined.append(["", "", "", ""])

        combined.append(["", "", "", ""])  # Добавляем пустую строку в конец

        self.beginResetModel()
        self._rows = combined
        self.endResetModel()
    
    def get_new_listes(self):
        ban_roots = []
        ban_words = []
        exception_roots = []
        exception_words = []
        for row in self._rows:
            if row[0].strip() != "":
                ban_roots.append(row[0].strip().lower())
            if row[1].strip() != "":
                ban_words.append(row[1].strip().lower())
            if row[2].strip() != "":
                exception_roots.append(row[2].strip().lower())
            if row[3].strip() != "":
                exception_words.append(row[3].strip().lower())
        return ban_roots, ban_words, exception_roots, exception_words

    def full_sort(self, var: Literal["a-z", "z-a"]):
        ban_roots, ban_words, exception_roots, exception_words = self.get_new_listes()
        if var == "a-z":
            ban_roots.sort(key=locale.strxfrm)
            ban_words.sort(key=locale.strxfrm)
            exception_roots.sort(key=locale.strxfrm)
            exception_words.sort(key=locale.strxfrm)
            self.sort_direction = var
        elif var == "z-a":
            ban_roots.sort(key=locale.strxfrm, reverse=True)
            ban_words.sort(key=locale.strxfrm, reverse=True)
            exception_roots.sort(key=locale.strxfrm, reverse=True)
            exception_words.sort(key=locale.strxfrm, reverse=True)
            self.sort_direction = var

        self.fill_table(ban_roots, ban_words, exception_roots, exception_words)

    def get_sort_direction(self):
        return self.sort_direction
    
    def clear_table(self):
        self.beginResetModel()
        self._rows = [self._empty_row.copy() for i in range(31)]
        self.endResetModel()

class CensorDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, color=QColor("#343C70"), width=2):
        super().__init__(parent)
        self.color = color
        self.width = width

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)

        has_focus = bool(option.state & QStyle.State_HasFocus)

        opt.state &= ~QStyle.State_HasFocus

        super().paint(painter, opt, index)

        if has_focus:
            painter.save()
            pen = QPen(self.color, self.width)
            pen.setCosmetic(True)
            painter.setPen(pen)

            rect = option.rect.adjusted(1, 1, -4, -2)
            painter.drawRect(rect)
            painter.restore()

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        editor.setContextMenuPolicy(Qt.CustomContextMenu)
        editor.customContextMenuRequested.connect(lambda pos, ed=editor: RBCMenu(ed).show_for_line_edit(ed, pos))
        return editor

class WarningMessage(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(QMessageBox.Warning)
        self.setWindowTitle(self.tr("Предупреждение!"))
        self.setText(self.tr("Вы уверенны в вашем действии?\nИзменения будут потеряны."))
        self.ok_button = self.addButton(self.tr("ОК"), QMessageBox.AcceptRole)
        self.cancel_button = self.addButton(self.tr("Отмена"), QMessageBox.RejectRole)
        self.setDefaultButton(self.cancel_button)

    def setNewWindowTitle(self, new_title: str):
        self.setWindowTitle(new_title)

    def setNewText(self, new_text: str):
        self.setText(new_text)

class CensorSetting(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Настройки цензуры"))
        self.setWindowIcon(QIcon(res_path("assets/censorico64x64.png")))
        self.setModal(True) # Блокируем взаимодействие с главным окном, пока открыто это
        self.setMinimumSize(590, 362) # Минимальный размер окна
        self.resize(750, 420) # Начальный размер окна
# =========================================================================
        self.standart_ban_roots = []
        self.standart_ban_words = []
        self.standart_exceptions_roots = []
        self.standart_exceptions_words = []
        self._was_imp = False
# =========================================================================
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.setSpacing(0)

        menu_bar = QMenuBar(self)
        menu_bar.setObjectName("table_menu_bar")
        menu_bar.setNativeMenuBar(False) # Чтобы меню отображалось в окне, а не вверху экрана на macOS

        self.import_action = QAction(self.tr("Импортировать список"), self)
        self.import_action.setShortcut(QKeySequence.Open)
        menu_bar.addAction(self.import_action)

        self.export_action = QAction(self.tr("Экспортировать список"), self)
        self.export_action.setShortcut(QKeySequence.Save)
        menu_bar.addAction(self.export_action)

        self.sort_action = QAction(self.tr("Сортировать (а-я)"), self)
        menu_bar.addAction(self.sort_action)

        self.clear_action = QAction(self.tr("Очистить списки"), self)
        menu_bar.addAction(self.clear_action)

        table_holder = QWidget(self)
        table_holder_layout = QHBoxLayout(table_holder)
        table_holder_layout.setContentsMargins(0, 0, 0, 0)
        table_holder_layout.setSpacing(0)

        table_box = QFrame(table_holder)
        table_box.setObjectName("table_box")
        table_box_layout = QVBoxLayout(table_box)
        table_box_layout.setContentsMargins(0, 0, 0, 0)
        table_box_layout.setSpacing(0)
        table_box.setMinimumWidth(620)
        table_box.setMaximumWidth(1100)

        table_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.table = QTableView(table_box)
        self.model = CensorTable()
        self.table.setModel(self.model)

        self.table.verticalHeader().setVisible(False) # Скрыть вертикальный заголовок 
        self.table.setShowGrid(False) # Скрыть сетку
        self.table.verticalHeader().setDefaultSectionSize(29) # Высота строк
        self.table.setVerticalScrollMode(QTableView.ScrollPerPixel) # Плавный скролл
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # Растягиваем колонки по ширине окна
        horizontal_header = self.table.horizontalHeader() 
        horizontal_header.setSectionsClickable(False) # Отключаем сортировку по клику на заголовок
        horizontal_header.setHighlightSections(False) # Отключаем выделение заголовка при клике
        # table.setFocusPolicy(Qt.NoFocus) # Отключаем пунктирную рамку вокруг ячейки при клике
        self.table.setSelectionMode(QTableView.SingleSelection) # Разрешаем выделение только одной ячейки
        self.table.setSelectionBehavior(QTableView.SelectItems) # Разрешаем выделение только ячеек, а не строк или столбцов целиком
        
        self._change_color(0)

        table_box_layout.addWidget(self.table)

        table_holder_layout.addWidget(table_box)
        table_holder_layout.setAlignment(Qt.AlignCenter)

        # ===== Подключение дейсвий к кнопкам =====
        self.sort_action.triggered.connect(lambda: self.sort_table())
        self.clear_action.triggered.connect(lambda: self.clear_table())
        # =========================================

        status_bar = QStatusBar(self)
        status_bar.setObjectName("table_status_bar")

        status_bar.setContentsMargins(10, 0, 0, 0)

        button_holder = QWidget(status_bar)
        button_holder_layout = QHBoxLayout(button_holder)
        button_holder_layout.setContentsMargins(0, 0, 0, 0)
        button_holder_layout.setSpacing(0)

        self.return_start_list_button = QPushButton(button_holder)
        self.return_start_list_button.setText(self.tr("Стандартный список"))
        self.return_start_list_button.clicked.connect(lambda: self.return_start_list())
        # self.return_start_list_button.setObjectName("return_start_list_button")

        self.save_button = QPushButton(button_holder)
        self.save_button.setText(self.tr("Сохранить"))
        self.save_button.setFocus() # Фокус на эту кнопку, чтобы срабатывал Enter
        self.save_button.clicked.connect(lambda: self.save_opt())

        self.cancel_button = QPushButton(button_holder)
        self.cancel_button.setText(self.tr("Отмена"))
        self.cancel_button.clicked.connect(lambda: self.cancel_opt())
        # self.cancel_button.setObjectName("cancel_button")

        button_holder_layout.addWidget(self.return_start_list_button)
        button_holder_layout.addWidget(self.save_button)
        button_holder_layout.addWidget(self.cancel_button)

        status_bar.addPermanentWidget(button_holder)

        dialog_layout.addWidget(menu_bar)
        dialog_layout.addWidget(table_holder)
        dialog_layout.addWidget(status_bar)

    def sort_table(self):
        current_sort = self.model.get_sort_direction()
        if current_sort == "a-z":
            new_sort = "z-a"
            self.sort_action.setText(self.tr("Сортировать (а-я)"))
        else:
            new_sort = "a-z"
            self.sort_action.setText(self.tr("Сортировать (я-а)"))
        self.model.full_sort(new_sort)

    def clear_table(self):
        reply = WarningMessage(self)
        reply.setNewWindowTitle(self.tr("Очистить списки?"))
        reply.setNewText(self.tr("Вы уверены, что хотите очистить все списки?\nВсе изменения будут потеряны."))
        reply.exec()
        if reply.clickedButton() == reply.ok_button:
            self.model.clear_table()
        
    def return_start_list(self):
        reply = WarningMessage(self)
        reply.setNewWindowTitle(self.tr("Вернуть стандартный список?"))
        reply.setNewText(self.tr("Вы уверены, что хотите вернуть стандартный список?\nВсе изменения будут потеряны."))
        reply.exec()
        if reply.clickedButton() == reply.ok_button:
            self.model.fill_table(self.standart_ban_roots, self.standart_ban_words, self.standart_exceptions_roots, self.standart_exceptions_words)
        
    def cancel_opt(self):
        reply = WarningMessage(self)
        reply.setTextFormat(Qt.RichText)
        reply.setNewWindowTitle(self.tr("Отменить изменения?"))
        reply.setNewText(self.tr("<span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Все изменения будут потеряны.&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Продолжить?</span>"))
        reply.exec()
        if reply.clickedButton() == reply.ok_button:
            self.reject()
            self.close()

    def closeEvent(self, event):
        if not self._was_imp:
            reply = WarningMessage(self)
            reply.setTextFormat(Qt.RichText)
            reply.setNewWindowTitle(self.tr("Отменить изменения?"))
            reply.setNewText(self.tr("<span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Все изменения будут потеряны.&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Продолжить?</span>"))
            reply.exec()
            if reply.clickedButton() == reply.ok_button:
                self.reject()
                self.close()
            else:
                event.ignore()
        else:
            self._was_imp = False

    def _was_import(self, flag):
        self._was_imp = flag

    def save_opt(self):
        self.accept()
        self.close()

    def _change_color(self, var = 0):
        self.table.setItemDelegate(CensorDelegate(self.table, QColor("#343C70") if var == 0 else QColor("#E888D1")))

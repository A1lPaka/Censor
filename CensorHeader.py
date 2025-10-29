from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtWidgets import QToolButton, QWidget, QHBoxLayout, QLabel, QSizePolicy, QTabBar, QSpacerItem
from PySide6.QtGui import QFontInfo, QFont, QPixmap, QCursor
import sys
from _utils import res_path

if sys.platform.startswith("win"):
    import win32api, win32con, win32gui

class EncodingDetectionError(Exception):
    pass

class HeaderBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("header_bar")
        self.setFixedHeight(29)
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WA_StyledBackground, True)

        # ===== контент =====
        # ===== Контейнер лейблов в хедербаре =====
        header_label_container = QWidget(self)
        header_label_container.setAttribute(Qt.WA_TransparentForMouseEvents, True) # Чтобы клики проходили сквозь контейнер
        header_label_container_layout = QHBoxLayout(header_label_container)
        header_label_container_layout.setContentsMargins(0, 0, 0, 0)
        header_label_container_layout.setSpacing(0)

        icon_label = QLabel(self)
        icon_pixmap = QPixmap(res_path("assets/censorico32x32.png"))
        drp = self.devicePixelRatioF() or 1.0
        scaled = icon_pixmap.scaled(int(23*drp), int(23*drp), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        scaled.setDevicePixelRatio(drp)
        icon_label.setPixmap(scaled)
        icon_label.setAttribute(Qt.WA_TransparentForMouseEvents, True) # Чтобы клики проходили сквозь лейбл
        icon_label.setContentsMargins(12, 0, 7, 0)

        title = QLabel("Censor", self)
        title.setObjectName("header_title")
    
        title.setContentsMargins(0, 0, 12, 0)
        title.setAttribute(Qt.WA_TransparentForMouseEvents, True) # Чтобы клики проходили сквозь лейбл
        title.setTextInteractionFlags(Qt.NoTextInteraction)

        header_label_container_layout.setAlignment(Qt.AlignLeft)
        header_label_container_layout.addWidget(icon_label)
        header_label_container_layout.addWidget(title)
        header_label_container_layout.addStretch(1)

        label_cont_fix_width = header_label_container.sizeHint().width()
        header_label_container.setFixedWidth(label_cont_fix_width) # Фиксированная ширина контейнера лейблов, чтобы не скакала при смене текста
        header_label_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # ===== Вкладки =====
        self.tab_bar = QTabBar(self)
        self.tab_bar.setObjectName("header_tab_bar")
        self.tab_bar.setMovable(False) 
        self.tab_bar.setExpanding(False) # Вкладки не растягиваются на всю ширину
        self.tab_bar.setDrawBase(False) # Не рисовать базу (линию под вкладками)

        self.tab_bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # ===== Кнопки управления окном =====
        self.sys_button_holder = QWidget(self)
        self.sys_button_holder.setObjectName("sys_button_holder")

        sys_button_holder_layout = QHBoxLayout(self.sys_button_holder)
        sys_button_holder_layout.setContentsMargins(0, 0, 0, 0)
        sys_button_holder_layout.setSpacing(0)

        icon_font = QFont()
        for fam in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            icon_font.setFamily(fam)
            if QFontInfo(icon_font).family() == fam:
                break

        icon_font.setPointSize(8)

        self.button_min = QToolButton(self)
        self.button_min.setFont(icon_font)
        self.button_min.setText("\ue921")
        self.button_min.setObjectName("minimize_button")
        self.button_min.clicked.connect(lambda: self.window().showMinimized())

        self.button_max = QToolButton(self)
        self.button_max.setFont(icon_font)
        self.button_max.setText("\ue922")
        self.button_max.setObjectName("maximize_button")
        self.button_max.clicked.connect(lambda: (self.window()._window_maximize_restore() if hasattr(self.window(), "_window_maximize_restore") else self.window().showMaximized()))

        self.button_close = QToolButton(self)
        self.button_close.setFont(icon_font)
        self.button_close.setText("\ue8bb")
        self.button_close.setObjectName("close_button")
        self.button_close.clicked.connect(lambda: self.window().close())

        sys_button_holder_layout.addWidget(self.button_min)
        sys_button_holder_layout.addWidget(self.button_max)
        sys_button_holder_layout.addWidget(self.button_close)

        QTimer.singleShot(0, self._update_button_holder_size)


        # ===== Лэйаут =====
        header_layout = QHBoxLayout(self)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        spacer = QSpacerItem(label_cont_fix_width * 1.55, 0, QSizePolicy.Preferred, QSizePolicy.Preferred)

        header_layout.addWidget(header_label_container)
        header_layout.addSpacerItem(spacer)
        header_layout.addWidget(self.tab_bar)
        header_layout.addStretch(1)
        header_layout.addWidget(self.sys_button_holder)

        header_layout.setAlignment(self.tab_bar, Qt.AlignBottom )

        self.setMinimumWidth(0)

        # ===== drag флаги =====
        self._is_dragging = False # Флаг, указывающий, что начато перетаскивание
        self._drag_position = QPoint() # Позиция курсора при начале перетаскивания
        self._drag_candidate_pos = None # Позиция курсора для определения начала перетаскивания
        self._was_maximized = False # Флаг, указывающий, что окно было максимизировано при начале перетаскивания
        self._grab_rel_x = 0.5 # Относительная позиция курсора по X при начале перетаскивания (0.0 - слева, 1.0 - справа)
        self._grab_grip_y = 0

        self._was_dblclick = False # Флаг, указывающий, что было двойное нажатие

        # self.rbc_menu = HeaderRBCMenu(self)

    def _set_tab_bar_minimum_width(self, width: int):
        self.tab_bar.setMinimumWidth(width)

    def _update_button_holder_size(self):
        total_width = self.button_min.sizeHint().width() + self.button_max.sizeHint().width() + self.button_close.sizeHint().width()
        self.sys_button_holder.setFixedWidth(total_width)

    def _updateMaxIcon(self, is_maximized: bool):
        if is_maximized:
            self.button_max.setText("\ue923")
        else:
            self.button_max.setText("\ue922")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.childAt(event.position().toPoint()) is None:
            self._drag_candidate_pos = event.globalPosition().toPoint()
            window = self.window()
            self._was_maximized = bool(window.isMaximized()) and not bool(window.isFullScreen())
            width = max(1, self.width())
            x = float(event.position().x())
            self._grab_rel_x = 0 if x <= 0 else (1.0 if x >= width else x / width) 
            self._grab_grip_y = event.position().y()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.childAt(event.position().toPoint()) is None:
            self._was_dblclick = True
            return
            
        super().mouseDoubleClickEvent(event)            

    def mouseMoveEvent(self, event):
        if self._drag_candidate_pos is not None and not self._is_dragging:
            if (event.globalPosition().toPoint() - self._drag_candidate_pos).manhattanLength() >= 2:
                if self._was_maximized:
                    window = self.window()
                    window.showNormal()
                    def _fix_pos():
                        try:
                            cur = QCursor.pos()
                            anchor_x = int(self._grab_rel_x * max(1, window.width()))
                            anchor_y = int(self._grab_grip_y)
                            window.move(cur - QPoint(anchor_x, anchor_y))
                            self._is_dragging = True
                            wh = window.windowHandle()
                            if wh:
                                wh.startSystemMove()
                            else:
                                if sys.platform.startswith("win"):
                                    win32gui.ReleaseCapture()
                                    win32api.SendMessage(int(window.winId()), win32con.WM_SYSCOMMAND, win32con.SC_MOVE | win32con.HTCAPTION, 0)
                        finally:
                            self._updateMaxIcon(False)
                            self._was_maximized = False

                    QTimer.singleShot(0, _fix_pos)
                    return
                else:
                    self._is_dragging = True
                    try:
                        wh = self.window().windowHandle()
                        if wh:
                            wh.startSystemMove()
                        else:
                            if sys.platform.startswith("win"):
                                win32gui.ReleaseCapture()
                                win32api.SendMessage(int(self.window().winId()), win32con.WM_SYSCOMMAND, win32con.SC_MOVE | win32con.HTCAPTION, 0)
                    except Exception:
                        pass

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._was_dblclick:
            self._was_dblclick = False
            QTimer.singleShot(0, (self.window()._window_maximize_restore if hasattr(self.window(), "_window_maximize_restore") else self.window().showMaximized))
            return
        self._drag_candidate_pos = None
        self._is_dragging = False
        self._was_maximized = False
        self._grab_rel_x = 0.5
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        if self.childAt(event.pos()) is None:
            if hasattr(self.window(), "show_system_menu"):
                self.window().show_system_menu(event.globalPos())
                return
            return
        super().contextMenuEvent(event)
import sys, locale
import os, json
from PySide6.QtCore import QEvent, QTimer, QStandardPaths, QSettings, Qt, QTextBoundaryFinder, QSize, QTranslator, QLocale, QFile, QTextStream
from PySide6.QtWidgets import QApplication, QFrame, QMenu, QFileDialog, QMessageBox, QToolButton, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QInputDialog, QSizePolicy, QMenuBar, QStackedWidget, QStatusBar, QDialog, QTextEdit, QWidgetAction, QCheckBox
from PySide6.QtGui import QAction, QTextCursor, QGuiApplication, QFont, QIcon, QColor, QKeySequence, QShortcut
from winfl_anti_flicker_base import Win11FramelessMixin
from CensorHeader import HeaderBar
from CensorButtonPopup import PopupSpinBox, ButtonPopup, SearchPopup
from CensorHighlighter import BanWordHighlighter
from CensorTextBlock import ZoomableTextEdit
from CensorDialogTable import CensorSetting
from _text_work import EncodingErrorMessageBox, EncodingDetectionError, _load_file, _apply_document_margins, _path_normalize, _upload_file, _make_cens_path, _load_censorship_csv, _load_censorship_txt, _upload_censorship_txt, _upload_censorship_csv
from _banwords_work import _make_regex, _build_spans, mask
from _utils import PositionSetting, res_path
import resources_rc


if sys.platform.startswith("win"):
    ANSI_CODEC = "mbcs"  # Windows ANSI кодировка
else:
    ANSI_CODEC = locale.getpreferredencoding(False) or "utf-8"  # Локальная кодировка для Unix-подобных систем

os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false"

what_is_MainWindow = Win11FramelessMixin, QWidget if sys.platform.startswith("win") else QWidget

class MainWindow(*what_is_MainWindow):
    def __init__(self, settings: QSettings):
        super().__init__()

        self.setWindowFlag(Qt.FramelessWindowHint, True)  # Отключаем стандартный заголовок окна
        self.setAttribute(Qt.WA_TranslucentBackground, False)  # Делаем фон окна непрозрачным
        self.setAttribute(Qt.WA_StyledBackground, True)  
        self.setAutoFillBackground(True)  # Включаем авто-заполнение фона

        self.setContentsMargins(0, 0, 0, 0) # Убираем отступы вокруг окна
        self.setObjectName("main_window")

        window_layout = QVBoxLayout(self)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(0)

        # ===== 0) Окно и базовые параметры/регэкспы =====
        self.settings = settings
        self.current_language = self.settings.value("language", "auto")
        self.setWindowTitle("Censor")
        self.setWindowIcon(QIcon(res_path("assets/censorico64x64.png")))
        self.setMinimumSize(500, 362) 
        
        self.current_open_file_path = None
        self.current_cens_file_path = None
        self.encoding = "utf-8"
        self.custom_encoding = None
        self._current_encoding = None
        self.eol = "\r\n"
        self.had_bom = None

        self._hl = None
        self._spans = []
        self._spans_for_cens = []
        self._spans_count = 0
        self._was_cens_check = False

        self._active_word_index = 0
        self._search_cursors = []
        self._search_selections = []
        self._was_changed_search_text = False
        self._focus_after_replace = False

        self._word_count = 0
        self._word_count_cens = 0

        self._censsetting_is_open = False

        self.standart_banlist = {}

        with open(res_path("assets/banlist.json"), "r", encoding="utf-8") as file:
            self.standart_banlist = json.load(file)

        self.standart_ban_roots = []
        self.standart_ban_words = []
        self.standart_exceptions_roots = []
        self.standart_exceptions_words = []

        self._fill_standart_banlists()

        self.current_ban_roots = self.standart_ban_roots.copy()
        self.current_ban_words = self.standart_ban_words.copy()
        self.current_exceptions_roots = self.standart_exceptions_roots.copy()
        self.current_exceptions_words = self.standart_exceptions_words.copy()

        self.rx_ban_roots, self.rx_ban_words, self.rx_exceptions_roots, self.rx_exceptions_words = _make_regex(*self.all_standart_banlists)
        
        self._current_theme = self.settings.value("theme", "Dark")

        # Контейнер для хедербара и меню-бара
        header_container = QWidget(self)
        header_container.setObjectName("header_container")
        header_container.setAttribute(Qt.WA_StyledBackground, True)

        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        self.header_bar = HeaderBar(self)

        menu_search_holder = QWidget(self)
        menu_search_layout = QHBoxLayout(menu_search_holder)
        menu_search_layout.setContentsMargins(0, 0, 0, 0)
        menu_search_layout.setSpacing(0)

        # ===== 1) Меню-бар (сразу сверху, логически первым) =====
        menu_bar = QMenuBar(self)
        menu_bar.setNativeMenuBar(False)
        theme = self.settings.value("theme", "Dark")
        self._apply_theme(theme)

        # === Меню "Файл"
        self.menu_file = menu_bar.addMenu(self.tr("Файл"))
        self.offset_filter_menu_file = PositionSetting(dx=0, dy=2)
        self.menu_file.setProperty("_allow_position_offset", True)
        self.menu_file.installEventFilter(self.offset_filter_menu_file)

        self.action_create_message = QAction(self.tr("Создать"), self)
        self.action_create_message.setShortcut(QKeySequence.New)
        self.action_create_message.triggered.connect(self.create_message)
        self.menu_file.addAction(self.action_create_message)

        self.menu_file.addSeparator()

        self.action_open_message = QAction(self.tr("Открыть"), self)
        self.action_open_message.setShortcut(QKeySequence.Open)
        self.action_open_message.triggered.connect(self.open_message_txt)
        self.menu_file.addAction(self.action_open_message)

        self.action_save_message = QAction(self.tr("Сохранить"), self)
        self.action_save_message.setShortcut(QKeySequence.Save)
        self.action_save_message.triggered.connect(self.save_message_txt)
        self.menu_file.addAction(self.action_save_message)

        self.action_save_as_message = QAction(self.tr("Сохранить как ..."), self)
        self.action_save_as_message.setShortcut(QKeySequence.SaveAs)
        self.action_save_as_message.triggered.connect(self.save_as_message_txt)
        self.menu_file.addAction(self.action_save_as_message)

        self.action_save_all_message = QAction(self.tr("Сохранить всё"), self)
        self.action_save_all_message.setShortcut(QKeySequence("Ctrl+Alt+S"))
        self.action_save_all_message.triggered.connect(self.save_all_message_txt)
        self.menu_file.addAction(self.action_save_all_message)

        self.menu_file.addSeparator()

        self.action_import_censor = QAction(self.tr("Импортировать список цензуры"), self)
        self.menu_file.addAction(self.action_import_censor)
        self.action_import_censor.triggered.connect(self.import_ban_list)

        self.action_export_censor = QAction(self.tr("Экспортировать список цензуры"), self)
        self.menu_file.addAction(self.action_export_censor)
        self.action_export_censor.triggered.connect(self.export_ban_list)

        self.menu_file.addSeparator()

        self.action_exit = QAction(self.tr("Выход"), self)
        self.action_exit.triggered.connect(self.close)
        self.menu_file.addAction(self.action_exit)

        # === Меню "Цензура"
        self.menu_messages = menu_bar.addMenu(self.tr("Цензура"))
        self.menu_messages.setObjectName("censor_menu")
        self.offset_filter_menu_message = PositionSetting(dx=0, dy=2)
        self.menu_messages.setProperty("_allow_position_offset", True)
        self.menu_messages.installEventFilter(self.offset_filter_menu_message)
        self.menu_messages.setToolTipsVisible(True)

        self.action_check_censor = QAction(self.tr("Проверить текст на цензуру"), self)
        self.action_check_censor.triggered.connect(self._toggle_ban_word_highlight)
        self.action_check_censor.setToolTip(self.tr("Включает или отключает подсветку\nзапрещённых слов в открытом тексте"))
        self.menu_messages.addAction(self.action_check_censor)

        self.menu_apply_censor = QMenu(self.tr("Наложить цензуру на все сообщения"), self)
        self.menu_apply_censor.setObjectName("censor_menu")
        self.offset_filter_menu_apply_censor = PositionSetting(dx=4, dy=0)
        self.menu_apply_censor.setProperty("_allow_position_offset", True)
        self.menu_apply_censor.installEventFilter(self.offset_filter_menu_apply_censor)

        self.action_apply_censor_classic = QAction(self.tr("До цензуры  →  После ц*****ы"), self)
        self.action_apply_censor_classic.triggered.connect(lambda: self._make_cens(1))
        self.menu_apply_censor.addAction(self.action_apply_censor_classic)

        self.action_apply_censor_custom = QAction(self.tr("До цензуры  →  После @#$%!"), self)
        self.action_apply_censor_custom.triggered.connect(lambda: self._make_cens(2))
        self.menu_apply_censor.addAction(self.action_apply_censor_custom)

        self.menu_messages.addMenu(self.menu_apply_censor)

        self.menu_messages.addSeparator()

        self.action_open_ban_list = QAction(self.tr("Открыть список запрещенных слов"), self)
        self.menu_messages.addAction(self.action_open_ban_list)
        self.action_open_ban_list.triggered.connect(self.open_banwords_table)

        # === Меню "Настройки"
        self.menu_censor_setting = menu_bar.addMenu(self.tr("Настройки"))
        self.menu_censor_setting.setObjectName("censor_menu")
        self.menu_censor_setting.setToolTipsVisible(True)
        self.offset_filter_menu_censor_setting = PositionSetting(dx=0, dy=2)
        self.menu_censor_setting.setProperty("_allow_position_offset", True)
        self.menu_censor_setting.installEventFilter(self.offset_filter_menu_censor_setting)

        self.menu_change_app_language = QMenu(self.tr("Сменить язык приложения"), self)
        self.menu_change_app_language.setObjectName("change_language_menu")
        self.menu_censor_setting.addMenu(self.menu_change_app_language)
        self.offset_filter_menu_change_language = PositionSetting(dx=4, dy=0)
        self.menu_change_app_language.setProperty("_allow_position_offset", True)
        self.menu_change_app_language.installEventFilter(self.offset_filter_menu_change_language)

        action_en_language = QAction("🇪🇳    English", self)
        action_en_language.triggered.connect(lambda: self._change_language("en"))
        self.menu_change_app_language.addAction(action_en_language)

        action_ru_language = QAction("🇷🇺    Русский", self)
        action_ru_language.triggered.connect(lambda: self._change_language("ru"))
        self.menu_change_app_language.addAction(action_ru_language)

        action_de_language = QAction("🇩🇪    Deutsch", self)
        action_de_language.triggered.connect(lambda: self._change_language("de"))
        self.menu_change_app_language.addAction(action_de_language)
        
        self.menu_select_censor_language = QMenu(self.tr("Язык списков запрещенных слов"), self)
        self.menu_select_censor_language.setObjectName("change_language_menu")
        self.offset_filter_menu_select_censor_language = PositionSetting(dx=4, dy=0)
        self.menu_select_censor_language.setProperty("_allow_position_offset", True)
        self.menu_select_censor_language.installEventFilter(self.offset_filter_menu_select_censor_language)
        self.menu_censor_setting.addMenu(self.menu_select_censor_language)

        checkbox_widget = QWidget(self)
        checkbox_layout = QVBoxLayout(checkbox_widget)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setSpacing(0)

        en_checkbox_holder, self.en_checkbox = self._create_checkbox_with_holder(self.tr("Английский список цензуры"))
        ru_checkbox_holder, self.ru_checkbox = self._create_checkbox_with_holder(self.tr("Русский список цензуры"))
        de_checkbox_holder, self.de_checkbox = self._create_checkbox_with_holder(self.tr("Немецкий список цензуры"))

        self._activate_current_checkbox()

        self.checkboxes = {
            "en": self.en_checkbox,
            "ru": self.ru_checkbox,
            "de": self.de_checkbox
        }

        self._lang_key_map = {
            "en": "english_default",
            "ru": "russian_default",
            "de": "german_default"
        }

        self._lang_debounce = QTimer(self)
        self._lang_debounce.setSingleShot(True)
        self._lang_debounce.timeout.connect(self._toggle_censor_language)

        checkbox_layout.addWidget(en_checkbox_holder)
        checkbox_layout.addWidget(ru_checkbox_holder)
        checkbox_layout.addWidget(de_checkbox_holder)

        self.checkbox_action = QWidgetAction(self)
        self.checkbox_action.setDefaultWidget(checkbox_widget)

        self.menu_select_censor_language.aboutToShow.connect(lambda: (self.menu_select_censor_language.removeAction(self.checkbox_action), self.menu_select_censor_language.addAction(self.checkbox_action)))

        self.menu_censor_setting.addSeparator()

        self.action_switch_theme = QAction(self)
        self.action_switch_theme.setText(self.tr("Включить светлую тему") if self._current_theme == "Dark" else self.tr("Включить тёмную тему"))
        self.action_switch_theme.triggered.connect(lambda: self._toggle_theme())
        self.menu_censor_setting.addAction(self.action_switch_theme)

        self.menu_censor_setting.addSeparator()

        self.action_replace_encoding = QAction(self.tr("Открыть файл с другой кодировкой"), self)
        self.action_replace_encoding.triggered.connect(self._replace_encoding)
        self.action_replace_encoding.setToolTip(self.tr("Позволяет открыть текущий файл заново,\nи прописать вручную кодировку текста.\nПолезно, если файл отображается некорректно."))
        self.menu_censor_setting.addAction(self.action_replace_encoding)

        self.search_button = QToolButton(self)
        self.search_button.setObjectName("search_button")
        self.search_dark_icon = QIcon(res_path("assets/search_dark_icon.svg"))
        self.search_light_icon = QIcon(res_path("assets/search_light_icon.svg"))
        self.search_button.setIcon(self.search_dark_icon if self._current_theme == "Dark" else self.search_light_icon)
        self.search_button.setToolTip(self.tr("Поиск по тексту (Ctrl+F)"))
        self.search_button.setShortcut(QKeySequence.Find)
        self.search_button.setIconSize(QSize(20, 20))
        search_fix_height = menu_bar.sizeHint().height()
        self.search_button.setMinimumSize(search_fix_height, search_fix_height)

        self.search_popup = SearchPopup(self)
        self.search_popup.search_close_button.clicked.connect(self._disable_select_search_text)
        self.search_popup.search_next_button.clicked.connect(lambda: self._next_active_word_index())
        QShortcut(QKeySequence("Enter"), self.search_popup, activated=self.search_popup.search_next_button.click)  # Enter
        QShortcut(QKeySequence("Return"), self.search_popup, activated=self.search_popup.search_next_button.click)  # Enter
        self.search_popup.search_prev_button.clicked.connect(lambda: self._prev_active_word_index())
        QShortcut(QKeySequence("Shift+Enter"), self.search_popup, activated=self.search_popup.search_prev_button.click)  # Shift+Enter
        QShortcut(QKeySequence("Shift+Return"), self.search_popup, activated=self.search_popup.search_prev_button.click)  # Shift+Enter
        self.search_popup.change_one_button.clicked.connect(lambda: self._change_active_search_word())
        self.search_popup.change_all_button.clicked.connect(lambda: self._change_all_search_words())
        
        self.search_button.clicked.connect(self.open_search_popup)

        spacer_search_button = QToolButton(self)
        spacer_search_button.setObjectName("spacer_search_button")
        spacer_search_button.setMinimumHeight(search_fix_height)
        spacer_search_button.setFixedWidth(8)
        spacer_search_button.setEnabled(False)

        menu_search_layout.addWidget(menu_bar) 
        menu_search_layout.addWidget(self.search_button)
        menu_search_layout.addWidget(spacer_search_button)

        header_layout.addWidget(self.header_bar)
        header_layout.addWidget(menu_search_holder)

        # ===== 2) Центральный виджет: вкладки + оба QTextEdit =====
        # Оригинал
        self.text_edit = ZoomableTextEdit()
        self.text_edit.setFrameShape(QFrame.NoFrame)
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setTabStopDistance(4 * self.text_edit.fontMetrics().horizontalAdvance('0'))
        _apply_document_margins(self.text_edit)
        self.text_edit.document().setModified(False)

        # Цензура (read-only)
        self.cens_text_edit = ZoomableTextEdit()
        self.cens_text_edit.setFrameShape(QFrame.NoFrame)
        self.cens_text_edit.setAcceptRichText(False)
        self.cens_text_edit.setTabStopDistance(4 * self.cens_text_edit.fontMetrics().horizontalAdvance('0'))
        self.cens_text_edit.setReadOnly(True)
        _apply_document_margins(self.cens_text_edit)
        self.central_stacks = QStackedWidget()

        self.text_edit.zoomChanged.connect(lambda percent: self._mirror_zoom(self.cens_text_edit, percent))
        self.cens_text_edit.zoomChanged.connect(lambda percent: self._mirror_zoom(self.text_edit, percent))
        
        # Добавляем страницы
        self.central_stacks.addWidget(self.text_edit) 
        self.central_stacks.addWidget(self.cens_text_edit)

        self.header_bar.tab_bar.addTab(self.tr("Оригинал"))
        self.header_bar.tab_bar.addTab(self.tr("Цензура"))
        self.header_bar.tab_bar.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        tab_bar_width = self.header_bar.tab_bar.fontMetrics().horizontalAdvance("Оригинал") * 4.4
        self.header_bar._set_tab_bar_minimum_width(tab_bar_width)

        self.header_bar.tab_bar.currentChanged.connect(self.central_stacks.setCurrentIndex) # Связываем вкладки и стэк
        self.central_stacks.currentChanged.connect(self.header_bar.tab_bar.setCurrentIndex) # И наоборот

        self.header_bar.tab_bar.currentChanged.connect(lambda _:self._update_words_count_label()) # Обновляем счётчик слов при смене вкладки
        self.header_bar.tab_bar.currentChanged.connect(lambda _:self._update_cursor_position_label()) # Обновляем позицию курсора
        self.header_bar.tab_bar.currentChanged.connect(lambda _: self._update_censor_violations_label()) # Обновляем количество нарушений
        self.header_bar.tab_bar.currentChanged.connect(lambda _: self._update_modified_label()) # Обновляем статус "изменён"
        self.header_bar.tab_bar.currentChanged.connect(lambda _: self._select_search_text())
        self.central_stacks.currentChanged.connect(lambda _: self._sync_zoom_from_editor(self._active_tab().zoom_percent()))

        self.installEventFilter(self)

        # ===== 3) Статус-бар: лейблы слева, кнопки справа =====
        status_bar = QStatusBar(self)
        status_bar.setContentsMargins(10, 0, 10, 0)
        status_bar.setSizeGripEnabled(False)

        # --- Лейблы (левый контейнер)
        status_label_holder = QWidget()
        sll = QHBoxLayout(status_label_holder)
        sll.setContentsMargins(1, 0, 1, 0)
        sll.setSpacing(1)

        self.len_col_label = QLabel(self.tr("Строка 1, Столбец 1"), self)
        self.len_col_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.len_col_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.len_col_label.setObjectName("status_label")

        self.words_count_label = QLabel(self.tr("Количество слов: 0"), self)
        self.words_count_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.words_count_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.words_count_label.setObjectName("status_label")

        self.censor_violations_label = QLabel(self.tr("Нарушений: X"), self)
        self.censor_violations_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.censor_violations_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.censor_violations_label.setObjectName("status_label")

        self.modified_label = QLabel(self.tr("Сохранён"), self)
        self.modified_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.modified_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.modified_label.setObjectName("status_label")

        sll.addWidget(self._make_v_separator())
        sll.addWidget(self.len_col_label)
        sll.addWidget(self._make_v_separator())
        sll.addWidget(self.words_count_label)
        sll.addWidget(self._make_v_separator())
        sll.addWidget(self.modified_label)
        sll.addWidget(self._make_v_separator())
        sll.addWidget(self.censor_violations_label)
        sll.addWidget(self._make_v_separator())
        sll.addStretch(1)

        label_fix_width = status_label_holder.sizeHint().width()
        status_label_holder.setMinimumWidth(label_fix_width + 30)
        status_label_holder.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        status_bar.addWidget(status_label_holder)

        # --- Кнопки (правый контейнер)
        status_button_holder = QWidget()
        sbl = QHBoxLayout(status_button_holder)
        sbl.setContentsMargins(1, 0, 1, 0)
        sbl.setSpacing(1)

        # Зум
        zoom_holder = QWidget()
        zhl = QHBoxLayout(zoom_holder)
        zhl.setContentsMargins(0, 0, 0, 0)
        zhl.setSpacing(0)

        self.zoom_button_in = QToolButton()
        self.zoom_button_in.setObjectName("zoom_button_in")
        self.zoom_button_in.setAutoRaise(True)
        self.zoom_button_in.setText("+")
        self.zoom_button_in.clicked.connect(lambda: self._active_tab().zoom_in_safe())

        self.zoom_button = QToolButton()
        self.zoom_button.setObjectName("zoom_button")
        self.zoom_button.setAutoRaise(True)

        self.zoom_button_out = QToolButton()
        self.zoom_button_out.setObjectName("zoom_button_out")
        self.zoom_button_out.setAutoRaise(True)
        self.zoom_button_out.setText("-")
        self.zoom_button_out.clicked.connect(lambda: self._active_tab().zoom_out_safe())

        # Попап спинбокса зума
        self.zoom_popup = PopupSpinBox(self)
        self.offset_filter_zoom_popup = PositionSetting(dx=1, dy=-2)
        self.zoom_popup.setProperty("_allow_position_offset", True)
        self.zoom_popup.installEventFilter(self.offset_filter_zoom_popup)
        self.zoom_button.clicked.connect(lambda: self.zoom_popup.open_at(self.zoom_button))

        # Текущий процент на кнопке и связь со SpinBox
        self.text_edit.zoomChanged.connect(self._sync_zoom_from_editor)
        self.cens_text_edit.zoomChanged.connect(self._sync_zoom_from_editor)
        self.zoom_popup.zoom_box.editingFinished.connect(self._apply_zoom_from_spinbox_commit)

        self._sync_zoom_from_editor(self._active_tab().zoom_percent())

        # Подгон ширины
        metrics = self.zoom_button.fontMetrics()
        self.zoom_button.setMinimumWidth(metrics.horizontalAdvance("100%") + 26)
        metrics_in = self.zoom_button_in.fontMetrics()
        self.zoom_button_in.setFixedSize(metrics_in.horizontalAdvance("+") + 16,
                                           metrics_in.horizontalAdvance("+") + 16)
        metrics_out = self.zoom_button_out.fontMetrics()
        self.zoom_button_out.setFixedSize(metrics_out.horizontalAdvance("+") + 16,
                                            metrics_out.horizontalAdvance("+") + 16)

        zhl.addWidget(self.zoom_button_in)
        zhl.addWidget(self.zoom_button)
        zhl.addWidget(self.zoom_button_out)

        # EOL
        self.eol_button = QToolButton()
        self.eol_button.setAutoRaise(True)
        self.eol_button.setText("Windows (CRLF)")
        self.eol_button.setToolTip(self.tr("Текущий тип перевода строки в файле.\nНажмите, чтобы изменить тип при сохранении."))
        self.eol_button.clicked.connect(lambda: self.eol_popup.open_at(self.eol_button))

        self.eol_popup = ButtonPopup(self)
        self.offset_filter_eol_popup = PositionSetting(dx=1, dy=-2)
        self.eol_popup.setProperty("_allow_position_offset", True)
        self.eol_popup.installEventFilter(self.offset_filter_eol_popup)
        self.eol_popup.add_option("Unix (LF)", lambda: self._apply_eol("\n"))
        self.eol_popup.add_option("Windows (CRLF)", lambda: self._apply_eol("\r\n"))
        self.eol_popup.add_option("Mac (CR)", lambda: self._apply_eol("\r"))

        metrics_eol = self.eol_button.fontMetrics()
        self.eol_button.setMinimumWidth(metrics_eol.horizontalAdvance("Windows (CRLF)") + 36)
        self.eol_popup.size_setting("Windows (CRLF)")

        # Encoding
        self.encoding_button = QToolButton()
        self.encoding_button.setToolTip(self.tr("Текущая кодировка файла.\nНажмите, чтобы изменить кодировку при сохранении."))
        self.encoding_button.setAutoRaise(True)
        self.encoding_button.setText(self.encoding.upper())
        self.encoding_button.clicked.connect(
            lambda: self.encoding_popup.open_at(self.encoding_button))

        self.encoding_popup = ButtonPopup(self)
        self.offset_filter_encoding_popup = PositionSetting(dx=1, dy=-2)
        self.encoding_popup.setProperty("_allow_position_offset", True)
        self.encoding_popup.installEventFilter(self.offset_filter_encoding_popup)

        self.encoding_popup.add_option("UTF-8", lambda: self._apply_encoding("utf-8", had_bom=False))
        self.encoding_popup.add_option("UTF-8 BOM", lambda: self._apply_encoding("utf-8", had_bom=True))
        self.encoding_popup.add_option("UTF-16 LE", lambda: self._apply_encoding("utf-16-le", had_bom=True))
        self.encoding_popup.add_option("UTF-16 BE", lambda: self._apply_encoding("utf-16-be", had_bom=True))
        if sys.platform.startswith("win"):
            self.encoding_popup.add_option("ANSI", lambda: self._apply_encoding(ANSI_CODEC, had_bom=False))
        if self.custom_encoding:
            self.encoding_popup.add_option(self.custom_encoding, lambda: self._apply_encoding(self.custom_encoding, had_bom=False))

        metrics_enc = self.encoding_button.fontMetrics()
        self.encoding_button.setMinimumWidth(metrics_enc.horizontalAdvance("UTF-16 BOM") + 28)
        self.encoding_popup.size_setting("UTF-16 BOM")

        # Сборка правого контейнера
        sbl.addWidget(self._make_v_separator())
        sbl.addWidget(zoom_holder)
        sbl.addWidget(self._make_v_separator())
        sbl.addWidget(self.eol_button)
        sbl.addWidget(self._make_v_separator())
        sbl.addWidget(self.encoding_button)
        sbl.addWidget(self._make_v_separator())

        button_fix_width = status_button_holder.sizeHint().width()
        status_button_holder.setMinimumWidth(button_fix_width)
        status_button_holder.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        status_bar.addPermanentWidget(status_button_holder)

        status_bar.setMinimumWidth(status_bar.fontMetrics().horizontalAdvance("Количество слов: 0") * 8)

        # ===== Добавление всех основных частей в главный лэйаут окна =====
        window_layout.addWidget(header_container)
        window_layout.addWidget(self.central_stacks)
        window_layout.addWidget(status_bar)

        # ===== 4) Таймеры/сигналы, завязанные на созданные виджеты =====
        self.text_edit.cursorPositionChanged.connect(self._update_cursor_position_label)
        self.text_edit.textChanged.connect(self._update_cursor_position_label)
        self._update_cursor_position_label()

        self._words_count_timer = QTimer(self)
        self._words_count_timer.setSingleShot(True)
        self._words_count_timer.timeout.connect(self._update_words_count_label)
        self.text_edit.textChanged.connect(lambda: self._words_count_timer.start(333))
        self._update_words_count_label()

        self._search_text_timer = QTimer(self)
        self._search_text_timer.setSingleShot(True)
        self._search_text_timer.timeout.connect(self._select_search_text)
        self.text_edit.textChanged.connect(lambda: self._search_text_timer.start(150))

        self.text_edit.textChanged.connect(self._update_modified_label)
        self.cens_text_edit.textChanged.connect(self._update_modified_label)

        self._search_text_timer1 = QTimer(self)
        self._search_text_timer1.setSingleShot(True)
        self._search_text_timer1.timeout.connect(self._select_search_text)
        self.search_popup.search_edit.textChanged.connect(lambda: self._search_text_timer1.start(150))
        self.search_popup.search_edit.textChanged.connect(lambda: self._return_start_index())

        self.dialog = CensorSetting(self)
        self.dialog.import_action.triggered.connect(self.import_ban_list)
        self.dialog.export_action.triggered.connect(self.export_ban_list)

        self.text_edit.setFocus()
# =================================================== Функции для работы с приложением ===============================================
    def _create_checkbox_with_holder(self, text: str) -> QWidget:
        holder = QWidget(self)
        holder.setObjectName("checkbox_holder")
        holder.setAttribute(Qt.WA_StyledBackground, True)

        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setSpacing(0)

        checkbox = QCheckBox(text, holder)
        checkbox.setObjectName("censor_language_checkbox")
        checkbox.setTristate(False)

        checkbox.toggled.connect(lambda _state, box=checkbox: self._min_one_checked(box))
        checkbox.toggled.connect(lambda _: self._lang_debounce.start(500))

        holder_layout.addWidget(checkbox)

        def _enterEvent(event):
            holder.setProperty("hover", True)
            holder.style().unpolish(holder)
            holder.style().polish(holder)
            QWidget.enterEvent(holder, event)

        def _leaveEvent(event):
            holder.setProperty("hover", False)
            holder.style().unpolish(holder)
            holder.style().polish(holder)
            QWidget.leaveEvent(holder, event)

        holder.enterEvent = _enterEvent
        holder.leaveEvent = _leaveEvent

        def _holder_mousePressEvent(_event):
            checkbox.toggle()
        holder.mousePressEvent = _holder_mousePressEvent

        return holder, checkbox
    
    def _rebuild_encoding_popup(self):
        self.encoding_popup.clear_options()

        self.encoding_popup.add_option("UTF-8", lambda: self._apply_encoding("utf-8", had_bom=False))
        self.encoding_popup.add_option("UTF-8 BOM", lambda: self._apply_encoding("utf-8", had_bom=True))
        self.encoding_popup.add_option("UTF-16 LE", lambda: self._apply_encoding("utf-16-le", had_bom=True))
        self.encoding_popup.add_option("UTF-16 BE", lambda: self._apply_encoding("utf-16-be", had_bom=True))
        if sys.platform.startswith("win"):
            self.encoding_popup.add_option("ANSI", lambda: self._apply_encoding(ANSI_CODEC, had_bom=False))
        if self.custom_encoding:
            self._current_encoding = str(self.custom_encoding).upper()
            self.encoding_popup.add_option(self._current_encoding, lambda: self._apply_encoding(self._current_encoding, had_bom=False))

        metrics_enc = self.encoding_button.fontMetrics()
        self.encoding_button.setMinimumWidth(metrics_enc.horizontalAdvance("UTF-16 BOM") + 28)
        self.encoding_popup.size_setting("UTF-16 BOM")
    
    def _active_tab(self):
        return self.text_edit if self.central_stacks.currentIndex() == 0 else self.cens_text_edit

    def _scroll_to_active(self, editor: QTextEdit, active_cursor: QTextCursor):
        rect = editor.cursorRect(active_cursor)
        viewport = editor.viewport().rect()
        scrollbar = editor.verticalScrollBar()

        if rect.top() < 0 or rect.bottom() > viewport.height():
            scrollbar.setValue(scrollbar.value() + rect.center().y() - viewport.center().y())

    def _update_censor_violations_label(self):
        if self.central_stacks.currentIndex() == 0:  # Если активна вкладка с оригиналом
            if self._was_cens_check:
                self.censor_violations_label.setText(self.tr("Нарушений: %1").replace("%1", str(self._spans_count)))
            else:
                self.censor_violations_label.setText(self.tr("Нарушений: X"))
        elif self.central_stacks.currentIndex() == 1:  # Если активна вкладка с цензурой
            self.censor_violations_label.setText(self.tr("Нарушений: 0"))

    def open_search_popup(self):
        if self.search_popup.isVisible():
            return
        if self.search_popup.search_edit.text() == "":
            self.search_popup.search_edit.setText(self._selected_text_to_search_open())
        self.search_popup.open_at(self.search_button)
        self._select_search_text()

    def _selected_text_to_search_open(self):
        editor = self._active_tab()
        selected_text = editor.textCursor().selectedText().replace('\u2029', '\n').strip()
        if "\n" not in selected_text and selected_text:
            return selected_text
        return ""

    def _return_start_index(self):
        self._active_word_index = 0

    def _select_search_text(self):
        text = self.search_popup.search_edit.text()
        editor = self._active_tab()

        self._search_cursors = []
        self._search_selections = []

        if not text:
            editor.setExtraSelections([])
            self.search_popup.search_label.setText(self.tr("0 из 0"))
            return
        
        full_text = editor.toPlainText()
        start = 0
        selections = []

        while True:
            start = full_text.find(text, start)
            if start == -1:
                break
            cursor = editor.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(start + len(text), QTextCursor.KeepAnchor)
            self._search_cursors.append(cursor)

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            color = QColor(255, 165, 0, 100)
            selection.format.setBackground(color)
            selections.append(selection)

            start += len(text)
            
        if not selections:
            editor.setExtraSelections([])
            self.search_popup.search_label.setText(self.tr("0 из 0"))
            self._active_word_index = 0
            return

        if self._active_word_index >= len(self._search_cursors):
            self._active_word_index = 0

        if self._active_word_index < 0:
            self._active_word_index = len(self._search_cursors) - 1

        active_cursor = self._search_cursors[self._active_word_index]
        active_selection = QTextEdit.ExtraSelection()
        active_selection.cursor = active_cursor
        active_color = QColor(255, 136, 0, 250)
        active_selection.format.setBackground(active_color)
        selections.append(active_selection)

        self._search_selections = selections[:-1]
        editor.setExtraSelections(selections)

        if not self._was_changed_search_text:
            self._scroll_to_active(editor, active_cursor)
        else:
            self._was_changed_search_text = False
        self.search_popup.search_label.setText(self.tr("%1 из %2").replace("%1", str(self._active_word_index + 1)).replace("%2", str(len(self._search_cursors))))

    def _disable_select_search_text(self):
        editor = self._active_tab()
        editor.setExtraSelections([])
        self._search_cursors = []
        self._search_selections = []

    def _next_active_word_index(self):
        if not self._search_cursors:
            return
        editor = self._active_tab()
        selections = self._search_selections.copy()

        if not self._focus_after_replace:
            self._active_word_index += 1
        else:
            self._focus_after_replace = False

        if self._active_word_index >= len(self._search_cursors):
            self._active_word_index = 0

        active_cursor = self._search_cursors[self._active_word_index]
        active_selection = QTextEdit.ExtraSelection()
        active_selection.cursor = active_cursor
        active_color = QColor(255, 136, 0, 250)
        active_selection.format.setBackground(active_color)
        selections.append(active_selection)

        editor.setExtraSelections(selections)
        self._scroll_to_active(editor, active_cursor)
        self.search_popup.search_label.setText(self.tr("%1 из %2").replace("%1", str(self._active_word_index + 1)).replace("%2", str(len(self._search_cursors))))

    def _prev_active_word_index(self):
        if not self._search_cursors:
            return
        editor = self._active_tab()
        selections = self._search_selections.copy()
        
        self._active_word_index -= 1

        if self._active_word_index < 0:
            self._active_word_index = len(self._search_cursors) - 1

        active_cursor = self._search_cursors[self._active_word_index]
        active_selection = QTextEdit.ExtraSelection()
        active_selection.cursor = active_cursor
        active_color = QColor(255, 136, 0, 250)
        active_selection.format.setBackground(active_color)
        selections.append(active_selection) 

        editor.setExtraSelections(selections)
        self._scroll_to_active(editor, active_cursor)
        self.search_popup.search_label.setText(self.tr("%1 из %2").replace("%1", str(self._active_word_index + 1)).replace("%2", str(len(self._search_cursors))))

    def _change_all_search_words(self):
        if not self._search_cursors:
            return
        editor = self._active_tab()
        new_text = self.search_popup.change_edit.text()
        cursor = editor.textCursor()
        self._return_start_index()
        self._was_changed_search_text = True
        cursor.beginEditBlock()
        try:
            for search_cursor in reversed(self._search_cursors):
                search_cursor.insertText(new_text)
        finally:
            cursor.endEditBlock()

        self._disable_ban_word_highlight()
        self._update_modified_label()
        self._update_words_count_label()

    def _change_active_search_word(self):
        if not self._search_cursors:
            return
        editor = self._active_tab()
        new_text = self.search_popup.change_edit.text()
        cursor = editor.textCursor()
        active_cursor = self._search_cursors[self._active_word_index] 
        self._was_changed_search_text = True
        self._focus_after_replace = True    
        cursor.beginEditBlock()
        try:
            active_cursor.insertText(new_text)
        finally:
            cursor.endEditBlock()

        self._disable_ban_word_highlight()
        self._update_modified_label()
        self._update_words_count_label()

    def _toggle_ban_word_highlight(self):
        if self._hl is None:
            was = self.text_edit.document().isModified()
            self._spans = _build_spans(self.text_edit, *self.all_rx_banlists)
            self._was_cens_check = True
            self._spans_count = len(self._spans)
            self._update_censor_violations_label()
            if not self._spans:
                self.action_check_censor.setText(self.tr("Проверить текст на цензуру"))
                return
            self._hl = BanWordHighlighter(self.text_edit.document(), self._spans)
            self._hl.format_ban_word.setBackground(QColor("#C42B1C" if self._current_theme == "Dark" else "#FFFF25"))
            self.action_check_censor.setText(self.tr("Убрать выделение цензуры"))
            self.text_edit.document().setModified(was)
        else:
            self._disable_ban_word_highlight()

    def _make_cens(self, var): 
        document = self.text_edit.document()
        censor_document = self.cens_text_edit.document()
        censor_document.setPlainText(document.toPlainText()) # Копируем текст
        self._spans_for_cens = _build_spans(self.cens_text_edit, *self.all_rx_banlists) # Строим спаны для цензуры
        
        cursor = self.cens_text_edit.textCursor()

        positions = []
        for start_cursor, end_cursor in self._spans_for_cens:
            start_pos = start_cursor.position()
            end_pos = end_cursor.position()
            if start_pos < end_pos:
                positions.append((start_pos, end_pos))

        positions.sort(key=lambda x: x[0])

        merged_positions = [] # Объединяем пересекающиеся интервалы
        for start, end in positions:
            if not merged_positions or start > merged_positions[-1][1]:
                merged_positions.append((start, end))
            else:
                merged_positions[-1] = (merged_positions[-1][0], max(merged_positions[-1][1], end))
            
        if hasattr(document, "setUndoRedoEnabled"):
            censor_document.setUndoRedoEnabled(False)

        cursor.beginEditBlock()
        try:
            for start, end in reversed(merged_positions):
                it_cursor = self.cens_text_edit.textCursor()
                it_cursor.setPosition(start)
                it_cursor.setPosition(end, QTextCursor.KeepAnchor)
                selected_text = it_cursor.selectedText()
                it_cursor.insertText(mask(selected_text, var))
        finally:
            cursor.endEditBlock()
            if hasattr(censor_document, "setUndoRedoEnabled"):
                censor_document.setUndoRedoEnabled(True)

        _apply_document_margins(self.cens_text_edit)
        self._word_count_cens = self._word_count  # Сохраняем количество слов в цензуре
        self._update_words_count_label()
        self.header_bar.tab_bar.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.central_stacks.setCurrentIndex(1) # Переключаем на вкладку с цензурой

    def _disable_ban_word_highlight(self):
        if self._hl is not None:
            self._hl.clear_spans()
            self._hl.setDocument(None)
            self._hl = None
        self._spans = []
        self.action_check_censor.setText(self.tr("Проверить текст на цензуру"))

    def _update_modified_label(self):
        if self.central_stacks.currentIndex() == 0:  # Если активна вкладка с оригиналом
            modified = self.text_edit.document().isModified()
            self.modified_label.setText(self.tr("Изменён") if modified else self.tr("Сохранён"))
        elif self.central_stacks.currentIndex() == 1:  # Если активна вкладка с цензурой
            modified = self.cens_text_edit.document().isModified()
            self.modified_label.setText(self.tr("Не сохранён") if modified else self.tr("Сохранён"))

    def _update_words_count_label(self):
        text = self.text_edit.toPlainText()
        finder = QTextBoundaryFinder(QTextBoundaryFinder.Word, text)
        finder.toStart()
        
        count = 0

        while True:
            pos = finder.toNextBoundary()
            if pos == -1:
                break
            if (finder.boundaryReasons() & QTextBoundaryFinder.EndOfItem) and pos > 0 and text[pos - 1].isalnum():
                count += 1
        if self.central_stacks.currentIndex() == 0:  # Если активна вкладка с цензурой
            self._word_count = count
            self.words_count_label.setText(self.tr("Количество слов: %1").replace("%1", str(count)))
        elif self.central_stacks.currentIndex() == 1:  # Если активна вкладка с цензурой
            self.words_count_label.setText(self.tr("Количество слов: %1").replace("%1", str(self._word_count_cens)))

    def _update_cursor_position_label(self):
        if self.central_stacks.currentIndex() == 0:  # Если активна вкладка с оригиналом
            cursor = self.text_edit.textCursor()
            line = cursor.blockNumber() + 1
            col = cursor.positionInBlock() + 1
            self.len_col_label.setText(self.tr("Строка %1, Столбец %2").replace("%1", str(line)).replace("%2", str(col)))
        elif self.central_stacks.currentIndex() == 1:  # Если активна вкладка с цензурой
            self.len_col_label.setText(self.tr("Строка 0, Столбец 0"))

    def _apply_eol(self, eol: str):
        self.eol = eol
        self._update_eol_button_text()

    def _update_eol_button_text(self):
        if self.eol == "\n":
            self.eol_button.setText("Unix (LF)")
        elif self.eol == "\r\n":
            self.eol_button.setText("Windows (CRLF)")
        elif self.eol == "\r":
            self.eol_button.setText("Mac (CR)")

    def _apply_encoding(self, encoding: str, had_bom: bool):
        self.encoding = encoding
        self.had_bom = had_bom
        self._update_encoding_button_text()

    def _update_encoding_button_text(self):
        if self.encoding == "utf-8" and self.had_bom:
            enc = "UTF-8 BOM"
        elif self.encoding == "utf-16-le" and self.had_bom:
            enc = "UTF-16 LE"
        elif self.encoding == "utf-16-be" and self.had_bom:
            enc = "UTF-16 BE"
        elif self.encoding in ("utf-16-le", "utf-16-be") and not self.had_bom:
            enc = "UTF-16"
        elif self.encoding.lower() == ANSI_CODEC.lower() and sys.platform.startswith("win"):
            enc = "ANSI"
        else:
            enc = self.encoding.upper()
        self.encoding_button.setText(enc)

    def _sync_zoom_from_editor(self, percent: float):
        normalized_value = self._normalized_zoom_percent(percent)
        self.zoom_button.setText(f"{normalized_value}%")
        self._set_spinbox_value_safely(normalized_value)

    def _apply_zoom_from_spinbox_commit(self):
        value = self.zoom_popup.zoom_box.value()
        normalized_value = self._normalized_zoom_percent(value)
        self._set_spinbox_value_safely(normalized_value)
        self._active_tab().set_zoom_percent(normalized_value)
        self.zoom_popup.close()

    def _normalized_zoom_percent(self, value: int) -> int:
        return max(10, min(500, int(round(value / 5.0)) * 5))
    
    def _set_spinbox_value_safely(self, value: int):
        if self.zoom_popup.zoom_box.value() != value:
            was_blocked = self.zoom_popup.zoom_box.blockSignals(True)
            self.zoom_popup.zoom_box.setValue(value)
            self.zoom_popup.zoom_box.blockSignals(was_blocked)

    def _mirror_zoom(self, other_editor: ZoomableTextEdit, percent: float):
        other_editor.blockSignals(True)
        other_editor.set_zoom_percent(percent)
        other_editor.blockSignals(False)

    def _make_v_separator(self) -> QFrame:
        v_separator = QFrame()
        v_separator.setFrameShape(QFrame.VLine)
        v_separator.setFrameShadow(QFrame.Sunken)
        v_separator.setLineWidth(1)
        v_separator.setFixedWidth(1)
        v_separator.setFixedHeight(20)
        return v_separator

    def create_message(self):
        var = self._var_for_close()
        if var != 0:
            message_box = CloseFileMessageBox(self, var)
            message_box.exec()
            next_step = self._handle_warning_buttons(None, message_box, var)
            if not next_step:
                return

        self.text_edit.clear()
        _apply_document_margins(self.text_edit)
        self.current_open_file_path = None
        self.current_cens_file_path = None
        self.encoding = "utf-8"
        self.eol = "\r\n" if sys.platform.startswith("win") else "\n"
        self.had_bom = False
        self.custom_encoding = None
        self._rebuild_encoding_popup()
        self._normalization_after_open()

    def open_message_txt(self, from_replace_encoding: bool = False):
        if not from_replace_encoding:
            var = self._var_for_close()
            if var != 0:
                message_box = CloseFileMessageBox(self, var)
                message_box.exec()
                next_step = self._handle_warning_buttons(None, message_box, var)
                if not next_step:
                    return
        # ================ Начальная папка ====================================
        start_directory = self.settings.value(
            "last_open_directory",
            QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
        )
        file_path = None
        if not self.custom_encoding:
            # ================ Диалог выбора файла ================================
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                self.tr("Открыть файл"), 
                start_directory, 
                "Text Files (*.txt)"
            )
             # ================ При отмене выбора файла ============================
            if not file_path:
                return
        else:
            file_path = self.current_open_file_path

        file_path = _path_normalize(file_path)
       
        # ================ Чтение файла =======================================
        while True:
            try:
                encoding, eol, had_bom = _load_file(file_path, self.text_edit, self.custom_encoding)
                self._rebuild_encoding_popup()
                self.custom_encoding = None  # Сбрасываем пользовательскую кодировку при новом открытии файла
                break
            except EncodingDetectionError as enc_error:
                error_box = EncodingErrorMessageBox(self, enc_error, self.custom_encoding)
                error_box.exec()
                if error_box.clickedButton() is error_box.button_ok:
                    self.custom_encoding = None
                    return
                if error_box.clickedButton() is error_box.button_manual:
                    text, ok = QInputDialog.getText(
                        self, self.tr("Укажите кодировку"),
                        self.tr("Введите полное название кодировки (например: cp1251, koi8-r, utf-16-le):")
                    )
                    text = text.strip().lower()
                    if ok and text:
                        self.custom_encoding = text
                        continue
                    else:
                        return 
            except Exception as error:
                QMessageBox.critical(self, self.tr("Ошибка чтения"), self.tr("Не удалось открыть файл:\n%1").replace("%1", str(error)))
                return
        # ================ Перемещаем курсор в конец ==========================
        self.text_edit.moveCursor(QTextCursor.End)
        # ================= Запоминаем путь к открытому файлу =================
        self.settings.setValue("last_open_directory", os.path.dirname(file_path))
        self.current_open_file_path = file_path
        self.encoding = encoding
        self.eol = eol
        self.had_bom = had_bom
        self._normalization_after_open()

    def _normalization_after_open(self):
        self._disable_ban_word_highlight()
        self._update_encoding_button_text()
        self._update_eol_button_text()
        self._update_words_count_label()
        self._update_censor_violations_label()
        self._update_modified_label()
        self.header_bar.tab_bar.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.central_stacks.setCurrentIndex(0) # Переключаем на вкладку с оригиналом
        self._was_cens_check = False

    def _what_is_tab(self) -> int:
        return self.central_stacks.currentIndex()
    
    def save_message_txt(self):
        if self.central_stacks.currentIndex() == 0:
            if not self.current_open_file_path:
                self.save_as_message_txt(0)
                return
            _upload_file(self.text_edit, self.current_open_file_path, self.encoding, self.eol, self.had_bom)
            self._update_modified_label()
            return
        elif self.central_stacks.currentIndex() == 1:
            if not self.current_cens_file_path:
                self.save_as_message_txt(1)
                return
            _upload_file(self.cens_text_edit, self.current_cens_file_path, self.encoding, self.eol, self.had_bom)
            self._update_modified_label()
            return
        
    def save_all_message_txt(self):
        path_orig = _path_normalize(self.current_open_file_path)
        path_cens = _path_normalize(self.current_cens_file_path)

        if path_orig and path_cens and (path_orig == path_cens):
            path_cens = _make_cens_path(path_orig)

        if not path_orig:
            was_return = self.save_as_message_txt(0)
            if was_return:
                return
        else:
            _upload_file(self.text_edit, path_orig, self.encoding, self.eol, self.had_bom)
            self._update_modified_label()

        if not path_cens:
            was_return = self.save_as_message_txt(1)
            if was_return:
                return
        else:
            _upload_file(self.cens_text_edit, path_cens, self.encoding, self.eol, self.had_bom)
            self._update_modified_label()

    def save_as_message_txt(self, tab_for_upload: int) -> bool:
        path_orig = _path_normalize(self.current_open_file_path)
        path_cens = _path_normalize(self.current_cens_file_path)

        if path_orig and path_cens and (path_orig == path_cens):
            path_cens = _make_cens_path(path_orig)
        
        if tab_for_upload is None:
            tab_for_upload = self._what_is_tab()

        if tab_for_upload == 1:
            if not path_cens or (path_orig == path_cens):
                path_cens = _path_normalize(_make_cens_path(path_orig))
            start_directory = path_cens or self.settings.value(
                "last_open_directory",
                QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
            )
            document = self.cens_text_edit

        elif tab_for_upload == 0:
            start_directory = path_orig or self.settings.value(
                "last_open_directory",
                QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
            )
            document = self.text_edit       

        # ================ Диалог выбора файла ================================
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            self.tr("Сохранить как..."), 
            start_directory, 
            "Text Files (*.txt)"
        )
        # ================ При отмене выбора файла ============================
        if not file_path:
            return True
        # ================ При незаданном расширении ==========================
        if not os.path.splitext(file_path)[1]:
            file_path += ".txt"

        # ================ Запись файла ========================================
        _upload_file(document, file_path, self.encoding, self.eol, self.had_bom)
        self._update_modified_label()
        # ================= Запоминаем путь к открытому файлу =================
        if tab_for_upload == 1:
            self.current_cens_file_path = _path_normalize(file_path)
        elif tab_for_upload == 0:
            self.current_open_file_path = _path_normalize(file_path)

        self.settings.setValue("last_open_directory", os.path.dirname(file_path))

        return False

    def showEvent(self, event):
        super().showEvent(event)
        self.header_bar._updateMaxIcon(self.isMaximized())

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self.header_bar._updateMaxIcon(self.isMaximized())

    def import_ban_list(self):
        # ================ Начальная папка ====================================
        start_directory = self.settings.value(
            "last_open_directory",
            QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
        )
        # ================ Диалог выбора файла ================================
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            self.tr("Импортировать список цензуры"), 
            start_directory, 
            "CSV Files (*.csv);;Text Files (*.txt)"
        )
        # ================ При отмене выбора файла ============================
        if not file_path:
            return
        
        file_path = _path_normalize(file_path)

        try:
            if file_path.lower().endswith(".txt"):
                ban_roots, ban_words, exc_roots, exc_words = _load_censorship_txt(file_path)
            elif file_path.lower().endswith(".csv"):
                ban_roots, ban_words, exc_roots, exc_words = _load_censorship_csv(file_path)
        except Exception as error:
            QMessageBox.critical(self, self.tr("Ошибка чтения"), self.tr("Не удалось открыть файл:\n%1").replace("%1", str(error)))
            return

        self.current_ban_roots = ban_roots.copy()
        self.current_ban_words = ban_words.copy()
        self.current_exceptions_roots = exc_roots.copy()
        self.current_exceptions_words = exc_words.copy()

        if not self._censsetting_is_open:
            self.open_banwords_table()  # Открываем окно настроек цензуры для просмотра/редактирования
        else:
            self.dialog.model.fill_table(*self.all_current_banlists)
            self.dialog._was_import(True)

        self.all_rx_banlists = _make_regex(ban_roots, ban_words, exc_roots, exc_words)
        self._disable_ban_word_highlight()
        self._spans = []
        self._spans_count = 0
        self._spans_for_cens = []
        self._was_cens_check = False
        self.central_stacks.setCurrentIndex(0) # Переключаем на вкладку с оригиналом
        self._update_censor_violations_label()
    
    def export_ban_list(self):
        # ================ Начальная папка ====================================
        start_directory = self.settings.value(
            "last_open_directory",
            QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
        )
        # ================ Диалог выбора файла ================================
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            self.tr("Экспортировать список цензуры"), 
            start_directory, 
            "CSV Files (*.csv);;Text Files (*.txt)"
        )
        # ================ При отмене выбора файла ============================
        if not file_path:
            return
        # ================ При незаданном расширении ==========================
        if not os.path.splitext(file_path)[1]:
            file_path += ".csv"  # По умолчанию сохраняем в CSV
        
        try:
            if file_path.lower().endswith(".txt"):
                if self._censsetting_is_open:
                    br, bw, er, ew = self.dialog.model.get_new_listes()
                    self.dialog._was_import(False)
                    _upload_censorship_txt(file_path, br, bw, er, ew)
                else:
                    _upload_censorship_txt(file_path, *self.all_current_banlists)
            elif file_path.lower().endswith(".csv"):
                if self._censsetting_is_open:
                    br, bw, er, ew = self.dialog.model.get_new_listes()
                    self.dialog._was_import(False)
                    _upload_censorship_csv(file_path, br, bw, er, ew)
                else:
                    _upload_censorship_csv(file_path, *self.all_current_banlists)
        except Exception as error:
            QMessageBox.critical(self, self.tr("Ошибка записи"), self.tr("Не удалось сохранить файл:\n%1").replace("%1", str(error)))
            return
        
        self.settings.setValue("last_open_directory", os.path.dirname(file_path))

    def open_banwords_table(self):
        self._censsetting_is_open = True
        self.dialog._change_color(0 if self._current_theme == "Dark" else 1)
        self.dialog.standart_ban_roots = self.standart_ban_roots
        self.dialog.standart_ban_words = self.standart_ban_words
        self.dialog.standart_exceptions_roots = self.standart_exceptions_roots
        self.dialog.standart_exceptions_words = self.standart_exceptions_words
        self.dialog.model.fill_table(*self.all_current_banlists)

        if self.dialog.exec() == QDialog.Accepted:
            self.all_current_banlists = self.dialog.model.get_new_listes()
            self.all_rx_banlists = _make_regex(*self.all_current_banlists)
            self._disable_ban_word_highlight()
            self._spans = []
            self._spans_count = 0
            self._spans_for_cens = []
            self._was_cens_check = False
            self._update_censor_violations_label()
        self._censsetting_is_open = False

    def _replace_encoding(self):
        if not self.current_open_file_path and not self.current_cens_file_path:
            no_files_warning = QMessageBox(self)
            no_files_warning.setIcon(QMessageBox.Information)
            no_files_warning.setText(self.tr("Нет открытых файлов для изменения кодировки."))
            no_files_warning.setWindowTitle(self.tr("Информация"))
            no_files_warning.exec()
            return
        encoding_warning = QMessageBox(self)
        encoding_warning.setIcon(QMessageBox.Warning)
        encoding_warning.setText(self.tr("При смене кодировки возможна потеря данных,\nесли выбранная кодировка не поддерживает\nнекоторые символы в тексте.\n\nПродолжить?"))
        encoding_warning.setWindowTitle(self.tr("Предупреждение"))
        ok_button = encoding_warning.addButton(self.tr("ОК"), QMessageBox.AcceptRole)
        cancel_button = encoding_warning.addButton(self.tr("Отмена"), QMessageBox.RejectRole)
        encoding_warning.setDefaultButton(cancel_button)
        encoding_warning.exec()
        if encoding_warning.clickedButton() is ok_button:
            text, ok = QInputDialog.getText(
                self, self.tr("Укажите кодировку"),
                self.tr("Введите полное название кодировки (например: cp1251, koi8-r, utf-16-le):")
                )
            text = text.strip().lower()
            if ok and text:
                self.custom_encoding = text
                was_modified = self.text_edit.document().isModified()
                self.open_message_txt(True)
                if was_modified:
                    self.text_edit.document().setModified(True)
                    self._update_modified_label()
            else:
                return 
            
    def _var_for_close(self):
        var = 0
        if self.text_edit.document().isModified():
            var += 1
        if self.cens_text_edit.document().isModified() and (self._spans_for_cens != []):
            var += 2

        return var

    def closeEvent(self, event):      
         # ===== Проверяем на несохранённые изменения =====
        var = self._var_for_close()
        if var == 0:
            event.accept()
            return
        
        warning = CloseFileMessageBox(self, var)
        warning.setWindowTitle(self.tr("Подтверждение выхода"))

        warning.exec()
        self._handle_warning_buttons(event, warning, var)

    def _handle_warning_buttons(self, event, message_box, var):
        if message_box.clickedButton() is message_box.ok_button:
            if event:
                event.accept()
            return True
        elif message_box.clickedButton() is message_box.cancel_button:
            if event:
                event.ignore()
            return False
        elif message_box.clickedButton() is message_box.save_button:
            was_return = self._save_in_closeEvent(var, self.current_open_file_path, self.current_cens_file_path)
            if event:
                event.accept() if was_return else event.ignore()
            return was_return

    def _save_in_closeEvent(self, var: int, current_open_file_path: str | None, current_cens_file_path: str | None) -> bool:
        if var in (1, 3):
            if not current_open_file_path:
                was_return = self.save_as_message_txt(0)
                if was_return:
                    return False
            else:
                _upload_file(self.text_edit, current_open_file_path, self.encoding, self.eol, self.had_bom)
        if var in (2, 3):
            if not current_cens_file_path:
                was_return = self.save_as_message_txt(1)
                if was_return:
                    return False
            else:
                _upload_file(self.cens_text_edit, current_cens_file_path, self.encoding, self.eol, self.had_bom)
        return True

    def _toggle_theme(self):
        if self._current_theme == "Dark":
            self._current_theme = "Light"
            self.action_switch_theme.setText(self.tr("Включить тёмную тему"))
            self.search_button.setIcon(self.search_light_icon)
            self._disable_ban_word_highlight()
        else:
            self._current_theme = "Dark"
            self.action_switch_theme.setText(self.tr("Включить светлую тему"))
            self.search_button.setIcon(self.search_dark_icon)
            self._disable_ban_word_highlight()
        self._apply_theme(self._current_theme)

    def _apply_theme(self, theme: str = "Dark"):
        path = f":/assets/Censor{theme}Style.qss"          # ресурсный путь
        css = self._load_qss_from_resource(path)
        try:
            self.setStyleSheet(css)
            self.settings.setValue("theme", theme)
        except FileNotFoundError:
            print(f"Theme file not found: {path}")
        except Exception as err:
            print(f"Error loading theme: {err}")

    def _load_qss_from_resource(self, path: str) -> str:
        file = QFile(path)
        if not file.open(QFile.ReadOnly | QFile.Text):
            return ""
        stream = QTextStream(file)
        css = stream.readAll()
        file.close()
        return css

    def _change_language(self, lang_code: str):
        if self.current_language == lang_code:
            return
        app = QApplication.instance()
        old_translator = getattr(app, "translator", None)
        if old_translator:
            app.removeTranslator(old_translator)
        translator = QTranslator()
        app.translator = translator

        qm_path = res_path(f"translations/{lang_code}.qm")

        if not app.translator.load(qm_path):
            if lang_code != "en":
                app.translator.load(res_path("translations/en.qm"))
                lang_code = "en"

        app.installTranslator(app.translator)
        self.current_language = lang_code
        self.settings.setValue("language", lang_code)

        self._disable_ban_word_highlight()
        self._spans = []
        self._spans_count = 0
        self._spans_for_cens = []
        self._was_cens_check = False
        self.central_stacks.setCurrentIndex(0) # Переключаем на вкладку

        self.setUpdatesEnabled(False) 
        self._retranslate_ui()
        self.setUpdatesEnabled(True)
                
    def _retranslate_ui(self):
        self.menu_file.setTitle(self.tr("Файл"))
        self.action_create_message.setText(self.tr("Создать"))
        self.action_open_message.setText(self.tr("Открыть"))
        self.action_save_message.setText(self.tr("Сохранить"))
        self.action_save_all_message.setText(self.tr("Сохранить всё"))
        self.action_save_as_message.setText(self.tr("Сохранить как..."))
        self.action_import_censor.setText(self.tr("Импортировать список цензуры"))
        self.action_export_censor.setText(self.tr("Экспортировать список цензуры"))
        self.action_exit.setText(self.tr("Выход"))
        
        self.menu_messages.setTitle(self.tr("Цензура"))
        self.action_check_censor.setText(self.tr("Проверить текст на цензуру") if not self._hl else self.tr("Убрать выделение цензуры")), self.action_check_censor.setToolTip(self.tr("Включает или отключает подсветку\nзапрещённых слов в открытом тексте"))
        self.menu_apply_censor.setTitle(self.tr("Наложить цензуру на все сообщения"))
        self.action_apply_censor_classic.setText(self.tr("До цензуры  →  После ц*****ы"))
        self.action_apply_censor_custom .setText(self.tr("До цензуры  →  После @#$%!"))
        self.action_open_ban_list.setText(self.tr("Открыть список запрещенных слов"))

        self.menu_censor_setting.setTitle(self.tr("Настройки"))
        self.menu_change_app_language.setTitle(self.tr("Сменить язык приложения"))
        self.menu_select_censor_language.setTitle(self.tr("Язык списков запрещенных слов"))
        self.en_checkbox.setText(self.tr("Английский список цензуры"))
        self.ru_checkbox.setText(self.tr("Русский список цензуры"))
        self.de_checkbox.setText(self.tr("Немецкий список цензуры"))
        self.action_switch_theme.setText(self.tr("Включить светлую тему") if self._current_theme == "Dark" else self.tr("Включить тёмную тему"))
        self.action_replace_encoding.setText(self.tr("Открыть файл с другой кодировкой")), self.action_replace_encoding.setToolTip(self.tr("Позволяет открыть текущий файл заново,\nи прописать вручную кодировку текста.\nПолезно, если файл отображается некорректно."))

        self.header_bar.tab_bar.setTabText(0, self.tr("Оригинал"))
        self.header_bar.tab_bar.setTabText(1, self.tr("Цензура"))

        self.len_col_label.setText(self.tr("Строка 1, Столбец 1")), self.search_button.setToolTip(self.tr("Поиск по тексту (Ctrl+F)"))
        self.words_count_label.setText(self.tr("Количество слов: 0")), self.eol_button.setToolTip(self.tr("Текущий тип перевода строки в файле.\nНажмите, чтобы изменить тип при сохранении."))
        self.censor_violations_label.setText(self.tr("Нарушений: X")), self.encoding_button.setToolTip(self.tr("Текущая кодировка файла.\nНажмите, чтобы изменить кодировку при сохранении."))
        self.modified_label.setText(self.tr("Сохранён"))

        self.search_popup._retranslate_ui()
        if hasattr(self, "dialog") and self.dialog is not None:
            self.dialog.deleteLater()
        self.dialog = CensorSetting(self)
        self.dialog.import_action.triggered.connect(self.import_ban_list)
        self.dialog.export_action.triggered.connect(self.export_ban_list)

        self._update_encoding_button_text()
        self._update_eol_button_text()
        self._update_modified_label()
        self._update_words_count_label()
        self._update_cursor_position_label()
        self._update_censor_violations_label()

    def _toggle_censor_language(self):
        # pass
        selected_keys = []
        for code, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                selected_keys.append(self._lang_key_map[code])

        ban_roots, ban_words, exc_roots, exc_words = [], [], [], []

        for key in selected_keys:
            ban_roots.extend(self.standart_banlist[key]["ban_roots"])
            ban_words.extend(self.standart_banlist[key]["ban_words"])
            exc_roots.extend(self.standart_banlist[key]["exception_roots"])
            exc_words.extend(self.standart_banlist[key]["exception_words"])

        ban_roots = list(dict.fromkeys(ban_roots))
        ban_words = list(dict.fromkeys(ban_words))
        exc_roots = list(dict.fromkeys(exc_roots))
        exc_words = list(dict.fromkeys(exc_words))

        if self.all_current_banlists == self.all_standart_banlists:
            self.all_current_banlists = (ban_roots, ban_words, exc_roots, exc_words)

        self.all_standart_banlists = (ban_roots, ban_words, exc_roots, exc_words)
        self.all_rx_banlists = _make_regex(*self.all_standart_banlists)

        self._spans = []
        self._spans_for_cens = []
        self._spans_count = 0
        self._was_cens_check = False
        self.central_stacks.setCurrentIndex(0) # Переключаем на вкладку с оригиналом
        self._update_censor_violations_label()
        self._disable_ban_word_highlight()

    def _fill_standart_banlists(self):
        list_var = ""
        if self.current_language == "ru":
            list_var = "russian_default"
        elif self.current_language == "de":
            list_var = "german_default"
        elif self.current_language == "en":
            list_var = "english_default"
        self.standart_ban_roots = self.standart_banlist[list_var]["ban_roots"]
        self.standart_ban_words = self.standart_banlist[list_var]["ban_words"]
        self.standart_exceptions_roots = self.standart_banlist[list_var]["exception_roots"]
        self.standart_exceptions_words = self.standart_banlist[list_var]["exception_words"]

    def _activate_current_checkbox(self):
        checkbox = None
        if self.current_language == "ru":
            checkbox = self.ru_checkbox
        elif self.current_language == "de":
            checkbox = self.de_checkbox
        elif self.current_language == "en":
            checkbox = self.en_checkbox
        checkbox.blockSignals(True)
        checkbox.setChecked(True)
        checkbox.blockSignals(False)

    def _min_one_checked(self, changed_checkbox: QCheckBox):
        checked_boxes = [checkbox for checkbox in self.checkboxes.values() if checkbox.isChecked()]
        if not checked_boxes:
            changed_checkbox.blockSignals(True)
            changed_checkbox.setChecked(True)
            changed_checkbox.blockSignals(False)

    @property
    def all_standart_banlists(self):
        return (
            self.standart_ban_roots,
            self.standart_ban_words,
            self.standart_exceptions_roots,
            self.standart_exceptions_words
        )
    
    @all_standart_banlists.setter
    def all_standart_banlists(self, lists):
        (
            self.standart_ban_roots,
            self.standart_ban_words,
            self.standart_exceptions_roots,
            self.standart_exceptions_words
        ) = lists

    @property
    def all_current_banlists(self):
        return (
            self.current_ban_roots,
            self.current_ban_words,
            self.current_exceptions_roots,
            self.current_exceptions_words
        )
    
    @all_current_banlists.setter
    def all_current_banlists(self, lists):
        (
            self.current_ban_roots,
            self.current_ban_words,
            self.current_exceptions_roots,
            self.current_exceptions_words
        ) = lists

    @property
    def all_rx_banlists(self):
        return (
            self.rx_ban_roots,
            self.rx_ban_words,
            self.rx_exceptions_roots,
            self.rx_exceptions_words
        )
    
    @all_rx_banlists.setter
    def all_rx_banlists(self, lists):
        (
            self.rx_ban_roots,
            self.rx_ban_words,
            self.rx_exceptions_roots,
            self.rx_exceptions_words
        ) = lists

class CloseFileMessageBox(QMessageBox):
    def __init__(self, parent=None, var=0):
        super().__init__(parent)
        self.var = var
        self.warning_text = [self.tr("<span>&nbsp;&nbsp;&nbsp;Файл во вкладке \"Оригинал\" не сохранён.&nbsp;&nbsp;&nbsp;<br>&nbsp;&nbsp;&nbsp;Продолжить без сохранения? </span>"),
                        self.tr("<span>&nbsp;&nbsp;&nbsp;Файл во вкладке \"Цензура\" не сохранён.&nbsp;&nbsp;&nbsp;<br>&nbsp;&nbsp;&nbsp;Продолжить без сохранения?</span>"),
                        self.tr("<span>&nbsp;&nbsp;&nbsp;Файл во вкладке \"Оригинал\" не сохранён.&nbsp;&nbsp;&nbsp;<br>&nbsp;&nbsp;&nbsp;Файл во вкладке \"Цензура\" не сохранён.&nbsp;&nbsp;&nbsp;<br>&nbsp;&nbsp;&nbsp;Продолжить без сохранения?</span>")]
        self.setIcon(QMessageBox.Warning)
        self.setTextFormat(Qt.RichText)
        self.setWindowTitle(self.tr("Подтверждение"))
        self.setText(self.warning_text[self.var - 1])
        self.save_button = self.addButton(self.tr("Сохранить"), QMessageBox.AcceptRole)
        self.ok_button = self.addButton(self.tr("Продолжить"), QMessageBox.DestructiveRole)
        self.cancel_button = self.addButton(self.tr("Отмена"), QMessageBox.RejectRole)
        self.setDefaultButton(self.cancel_button)

def pick_language(settings: QSettings, directory: str = "translations", available_languages=("ru", "de", "en")) -> str:
    user_choice = settings.value("language", "auto")
    if user_choice and user_choice != "auto":
        return str(user_choice)
    
    for ui in QLocale.system().uiLanguages():
        base = ui.split("-", 1)[0].lower()
        if base in available_languages:
            qm_path = os.path.join(directory, f"{base}.qm")
            if os.path.isfile(qm_path):
                return str(base)
            
    return "en"

if __name__ == "__main__":
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10)) # Основной шрифт приложения

    settings = QSettings("Cute_Alpaca_Club", "Censor")
    language = pick_language(settings)
    settings.setValue("language", language)

    translator = QTranslator()
    qm_path = res_path(f"translations/{language}.qm")
    loaded = translator.load(qm_path)
    if not loaded and language != "en":
        translator.load(res_path("translations/en.qm"))
    app.installTranslator(translator)
    app.translator = translator

    window = MainWindow(settings)
    window.resize(950, 600)
    window.show()

    sys.exit(app.exec())

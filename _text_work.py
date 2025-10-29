import sys, locale
import os
from PySide6.QtCore import QCoreApplication, QEventLoop
from PySide6.QtWidgets import QMessageBox
from CensorTextBlock import ZoomableTextEdit

BATCH_LINES = 2000

if sys.platform.startswith("win"):
    ANSI_CODEC = "mbcs"  # Windows ANSI кодировка
else:
    ANSI_CODEC = locale.getpreferredencoding(False) or "utf-8"  # Локальная кодировка для Unix-подобных систем

class EncodingDetectionError(Exception):
    pass

class EncodingErrorMessageBox(QMessageBox):
    def __init__(self, parent, error_message, custom_encoding: str | None = None):
        super().__init__(parent)
        self.custom_encoding = custom_encoding
        self.error_message = error_message
        self.setIcon(QMessageBox.Warning)
        self.setWindowTitle(self.tr("Ошибка определения кодировки."))
        if self.custom_encoding is None:
            self.setText(str(self.error_message) + self.tr("\n\nВозможные решения:\n"
                                     "- Попробуйте выбрать другой файл.\n"
                                     "- Отредактируйте файл в стороннем редакторе и сохраните его в кодировке UTF-8.\n"
                                     "- Укажите кодировку вручную.\n\n"
                                     "Нажмите \"ОК\" чтобы отменить открытие файла."))
        else:
            self.setText(str(self.error_message) + self.tr("\n\nВозможные решения:\n"
                                     "- Отредактируйте файл в стороннем редакторе и сохраните его в кодировке UTF-8.\n"
                                     "- Проверьте правильность введённой кодировки и попробуйте снова.\n\n"
                                     "Нажмите \"ОК\" чтобы отменить открытие файла."))

        self.button_manual = self.addButton(self.tr("Указать кодировку"), QMessageBox.ActionRole)
        self.button_ok = self.addButton(self.tr("ОК"), QMessageBox.RejectRole)
        self.setDefaultButton(self.button_ok)

# ===== Загрузка файла с определением кодировки и EOL =====
def _load_file(file_path: str, text_edit: ZoomableTextEdit, custom_encoding: str | None = None) -> tuple[str, str, bool]:
    encoding, eol, had_bom = _detect_encoding_eol(file_path, custom_encoding)

    read_encoding = "utf-8-sig" if had_bom and encoding == "utf-8" else encoding # т.к. BOM в utf-8-sig кодировке прописавается автоматически

    document = text_edit.document()
    if hasattr(document, "setUndoRedoEnabled"):
        document.setUndoRedoEnabled(False)

    text_edit.setUpdatesEnabled(False)
    text_edit.clear()
    cursor = text_edit.textCursor()

    with open(file_path, "r", encoding=read_encoding, newline='') as file:
        buffer = []
        cursor.beginEditBlock()
        for i, line in enumerate(file, 1):
            buffer.append(line)
            if i % BATCH_LINES == 0:
                cursor.insertText("".join(buffer))
                buffer.clear()
                QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        if buffer:
            cursor.insertText("".join(buffer))
        cursor.endEditBlock() 

    text_edit.setUpdatesEnabled(True)
    _apply_document_margins(text_edit)
    if hasattr(document, "setModified"):
        document.setModified(False)

    return encoding, eol, had_bom

def _detect_encoding_eol(file_path: str, custom_encoding: str | None = None) -> tuple[str, str, bool]:
    # ================ Чтение файла ===========================================================
    head = _make_head(file_path)
    if head == b"":
        return "utf-8", "\n", False  # Пустой файл

    # ================= Определение кодировки =================================================
    if custom_encoding not in (None, ""):
        encoding = custom_encoding
        if encoding == "utf-16":
            encoding = "utf-16-le"  # По умолчанию ставим LE
        try:
            _head_decoder(head, encoding)
        except UnicodeDecodeError as error:
            msg1 = QCoreApplication.translate(
                "text_work",
                "Не удалось декодировать файл с кодировкой '%1': байт %2-%3"
            ).replace("%1", encoding).replace("%2", str(error.start)).replace("%3", error.reason)
            raise EncodingDetectionError(msg1)
        except LookupError:
            msg2 = QCoreApplication.translate(
                "text_work",
                "Неизвестная кодировка: '%1'"
            ).replace("%1", encoding)
            raise EncodingDetectionError(msg2)
        had_bom = False
    else:
        encoding, had_bom = _detect_encoding_with_BOM(head)
        if not encoding:
            encoding, report = _detect_encoding_no_BOM(head)
            had_bom = False
            if not encoding:
                report = QCoreApplication.translate(
                    "text_work",
                    "Не удалось определить кодировку файла. Попытки:\n%1"
                ).replace("%1", report)
                raise EncodingDetectionError(report)

    # ================= Определение EOL =======================================================
    eol = _detect_eol(head, encoding)

    return encoding, eol, had_bom

def _make_head(file_path: str) -> bytes:
    with open(file_path, "rb") as file:
        head = file.read(262144)
        file.seek(0, 2)
        size = file.tell()
        if size == 0:
            return b""

    return head

def _head_decoder(head: bytes, encoding: str) -> str:
    buf = head[:-1] if encoding.startswith("utf-16") and (len(head) % 2) else head
    return buf.decode(encoding)

def _detect_encoding_with_BOM(head: bytes) -> tuple[str | None, bool]:
    if head.startswith(b'\xEF\xBB\xBF'):
        return "utf-8", True
    elif head.startswith(b'\xFE\xFF'):
        return "utf-16-be", True
    elif head.startswith(b'\xFF\xFE'):
        return "utf-16-le", True
    return None, False

def _detect_encoding_no_BOM(head: bytes) -> tuple[str | None, str | None]:
    encoding_to_try = ["utf-8", ANSI_CODEC]
    attempts = []
    for encoding in encoding_to_try:
        try:
            _head_decoder(head, encoding)
            return encoding, None
        except UnicodeDecodeError as error:
            attempts.append(f"{encoding}: байт {error.start}-{error.reason}")
            # self.custom_encoding = None
            continue
    msg = QCoreApplication.translate(
        "text_work",
        "Нет отчёта"
    )
    report = "\n".join(attempts) or msg 
    return None, report

def _detect_eol(head: bytes, encoding: str) -> str:
    head_to_decode = _head_decoder(head, encoding)
    crlf_count = head_to_decode.count('\r\n')
    lf_count = head_to_decode.count('\n') - crlf_count
    cr_count = head_to_decode.count('\r') - crlf_count
    if cr_count > 0 and cr_count >= crlf_count and cr_count >= lf_count:
        return "\r"  # Mac OS Classic
    elif lf_count > 0 and lf_count >= crlf_count and lf_count >= cr_count:
        return "\n"  # Unix/Linux
    else:
        return "\r\n"  # Windows

# ===== Сохранение файла с заданной кодировкой и EOL =====
def _upload_file(text_edit: ZoomableTextEdit, file_path: str, encoding: str, eol: str, had_bom: bool):
    document = text_edit.document()
    block = document.begin()

    encoding_to_write = "utf-8-sig" if had_bom and encoding == "utf-8" else encoding # т.к. BOM в utf-8-sig кодировке прописавается автоматически
    tmp_file_path = file_path + ".tmp" # Временный файл для записи на случай ЧП

    if encoding_to_write in ("utf-16-le", "utf-16-be") and not had_bom:
        had_bom = True  # Всегда пишем BOM для UTF-16 LE/BE

    with open(tmp_file_path, "w", encoding=encoding_to_write, newline="") as file:
        # ===== Запись BOM для UTF-16 =====
        if had_bom and encoding_to_write in ("utf-16-le", "utf-16-be"):
            file.write("\ufeff")
        # ===== Записываем текст по блочно в файл =====
        first = True
        while block.isValid():
            if not first:
                file.write(eol)
            file.write(block.text())
            first = False
            block = block.next()

    # Переименовываем временный файл в окончательный
    os.replace(tmp_file_path, file_path)

    if hasattr(document, "setModified"):
        document.setModified(False)

def _make_cens_path(orig_path: str) -> str | None:
    if not orig_path:
        return None
    path, ext = os.path.splitext(orig_path)
    return os.path.join(path + "(cens)" + ext) # Добавляем суффикс (cens)

# ===== Импорт списков цензуры =====
def _load_censorship_txt(file_path: str) -> tuple[list[str], list[str], list[str], list[str]]:
    encoding, _, _ = _detect_encoding_eol(file_path)

    ban_exc_list = []

    with open(file_path, "r", encoding=encoding, errors="replace") as file:
        count_lines = 0
        for line in file:
            if count_lines > 4:
                msg = QCoreApplication.translate(
                    "text_work",
                    "Неверное количество строк в файле."
                )
                raise ValueError(msg)
            if line.strip() == "" or line.strip().startswith("#"):
                continue
            count_lines += 1
            line = line.split(":", 1)[-1].strip()
            if line:
                ban_exc_list.append(line)

    ban_exc_list = (ban_exc_list + ["", "", "", ""])[:4]  # Гарантируем наличие 4 строк

    ban_roots = split_line_txt(ban_exc_list[0])
    ban_words = split_line_txt(ban_exc_list[1])
    exc_roots = split_line_txt(ban_exc_list[2])
    exc_words = split_line_txt(ban_exc_list[3])

    return ban_roots, ban_words, exc_roots, exc_words

def split_line_txt(line: str) -> list[str]:
    items_txt = []
    line_split = line.split(",")
    for item in line_split:
        item = _item_clean(item)
        if item:
            items_txt.append(item)

    return items_txt

def _load_censorship_csv(file_path: str) -> tuple[list[str], list[str], list[str], list[str]]:
    ban_roots = []
    ban_words = []
    exc_roots = []
    exc_words = []
    with open(file_path, "r", encoding="utf-8-sig", errors="replace", newline='') as file:
        import csv
        reader = csv.reader(file, delimiter=";")
        next(reader, None)  # Пропускаем заголовок
        for line in reader:
            line = (line + ["", "", "", ""])[:4]  # Гарантируем наличие 4 столбцов
                # Очищаем и добавляем элементы в соответствующие списки
            if line[0].strip():
                ban_roots.append(_item_clean(line[0]))
            if line[1].strip():
                ban_words.append(_item_clean(line[1]))
            if line[2].strip():
                exc_roots.append(_item_clean(line[2]))
            if line[3].strip():
                exc_words.append(_item_clean(line[3]))

    return ban_roots, ban_words, exc_roots, exc_words

def _item_clean(item: str) -> str:
    return item.lower().strip(" \t\n\r.,;:!?\"'()[]{}<>«»")

# ===== Экспорт списков цензуры =====
def _upload_censorship_txt(file_path: str, ban_roots: list[str], ban_words: list[str], exc_roots: list[str], exc_words: list[str]):
    tmp_file_path = file_path + ".tmp" # Временный файл для записи на случай ЧП
    with open(tmp_file_path, "w", encoding="utf-8", newline='') as file:
        msg_banroots = QCoreApplication.translate(
            "text_work",
            "Запрещённые корни: "
        )
        file.write(msg_banroots + ", ".join(ban_roots) + "\n")
        msg_banwords = QCoreApplication.translate(
            "text_work",
            "Запрещённые слова: "
        )
        file.write(msg_banwords + ", ".join(ban_words) + "\n")
        msg_excroots = QCoreApplication.translate(
            "text_work",
            "Исключаемые корни: "
        )
        file.write(msg_excroots + ", ".join(exc_roots) + "\n")
        msg_excwords = QCoreApplication.translate(
            "text_work",
            "Исключаемые слова: "
        )
        file.write(msg_excwords + ", ".join(exc_words) + "\n")
    os.replace(tmp_file_path, file_path)

def _upload_censorship_csv(file_path: str, ban_roots: list[str], ban_words: list[str], exc_roots: list[str], exc_words: list[str]):
    tmp_file_path = file_path + ".tmp" # Временный файл для записи на случай ЧП
    with open(tmp_file_path, "w", encoding="utf-8-sig", newline='') as file:
        import csv
        writer = csv.writer(file, delimiter=";")
        msg_banroots = QCoreApplication.translate(
            "text_work",
            "Запрещённые корни"
        )
        msg_banwords = QCoreApplication.translate(
            "text_work",
            "Запрещённые слова"
        )
        msg_excroots = QCoreApplication.translate(
            "text_work",
            "Исключаемые корни"
        )
        msg_excwords = QCoreApplication.translate(
            "text_work",
            "Исключаемые слова"
        )
        writer.writerow([msg_banroots, msg_banwords, msg_excroots, msg_excwords])
        max_len = max(len(ban_roots), len(ban_words), len(exc_roots), len(exc_words))
        for i in range(max_len):
            row = [
                ban_roots[i] if i < len(ban_roots) else "",
                ban_words[i] if i < len(ban_words) else "",
                exc_roots[i] if i < len(exc_roots) else "",
                exc_words[i] if i < len(exc_words) else ""
            ]
            writer.writerow(row)
    os.replace(tmp_file_path, file_path)

# ===== Общие функции =====
def _apply_document_margins(text_edit: ZoomableTextEdit):
    document = text_edit.document()
    if hasattr(document, "setUndoRedoEnabled"): document.setUndoRedoEnabled(False)
    frame = document.rootFrame()
    fmt = frame.frameFormat()
    fmt.setTopMargin(32)
    fmt.setLeftMargin(24)
    fmt.setRightMargin(8)
    fmt.setBottomMargin(24)
    frame.setFrameFormat(fmt)
    if hasattr(document, "setUndoRedoEnabled"): document.setUndoRedoEnabled(True)

def _path_normalize(path: str) -> str | None:
    if not path:
        return None
    return os.path.abspath(os.path.normpath(path))
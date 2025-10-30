# Censor  
<br>

[🇷🇺 Описание на русском](#-описание-на-русском) | [🇪🇳 Description in English](#-description-in-english)
<br>

<br>

## 🇷🇺 Описание на русском
<br>

## Первый самостоятельный проект на Python + PySide6  

Привет!  
Это мой первый проект, написанный примерно за **2,5 месяца после начала изучения Python и PySide6**.  
Я старался реализовать всё, что умею на данный момент, поэтому код, возможно, **не идеален**,  
но мне хотелось создать **настоящий рабочий инструмент**, а не просто учебную работу.

---

## Что такое Censor

**Censor** — это десктопное приложение, которое объединяет простой текстовый редактор  
и систему **интеллектуальной цензуры**.  
Оно проверяет тексты на нецензурную лексику, подсвечивает найденные слова  
и позволяет быстро применить «замазку» — звёздочками или случайными символами.

---

## Возможности

- Проверка текста на нецензурные слова (русский, английский, немецкий)  
- Две вкладки: **оригинал** и **цензурированный текст**  
- Два режима цензуры — звёздочки (`ц*****а`) или символы (`@#$%!`)  
- Собственный **редактор списков запрещённых слов** с импортом/экспортом TXT и CSV  
- Поддержка **тёмной и светлой темы**  
- Переключение языка интерфейса: 🇷🇺 Русский, 🇬🇧 Английский, 🇩🇪 Немецкий  
- Работа с **разными кодировками и переводами строк** (UTF-8, UTF-16, ANSI, LF, CRLF)  
- Быстрый **поиск и замена (Ctrl + F)**  
- Счётчик слов, строк и найденных нарушений  
- Современный интерфейс без рамки — в стиле **Windows 11**  
  *(модуль `winfl_anti_flicker_base.py` был реализован частично с помощью нейросетей,  
  так как я пока только начинаю разбираться в WinAPI)*  

---

## Скриншоты

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/cfcdcdea-df10-472e-8c5a-79947231e991" />

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/fc437e16-0d8b-4cca-b356-799ac8b272db" />

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/76a9bc5e-81bb-49a5-b5a5-3df799696070" />

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/e9c9705b-ddf3-4947-9034-5cfeb203a7cb" />

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/971d4766-0673-437e-a53d-0812a177920d" />

---

## Как запустить

### Вариант 1 — скачать готовый `.exe`
Самый простой способ — скачать готовую сборку в разделе  
[**Releases**](../../releases) на GitHub.  
Там находится архив с `.exe`-версией программы — достаточно распаковать и запустить `Censor.exe`.
##
### Вариант 2 — запустить исходники вручную
Для запуска через исходный код нужны:
- **Python 3.10+**
- **PySide6**

После установки зависимостей просто запустите:
```bash
python censor.py
```

---

## Структура проекта
```text
Censor/
│
├── censor.py                    # Главный файл приложения
├── _banwords_work.py            # Логика фильтрации
├── _text_work.py                # Работа с файлами и кодировками
├── _utils.py                    # Утилиты: путь к ресурсам, позиционирование попапов
├── CensorDialogTable.py         # Редактор списков цензуры
├── CensorHighlighter.py         # Подсветка нарушений
├── CensorHeader.py              # Заголовок и вкладки
├── CensorButtonPopup.py         # Попапы (зум, кодировка, EOL)
├── CensorTextBlock.py           # Класс QTextEdit с зумом
├── winfl_anti_flicker_base.py   # Безрамочное окно Windows 11
├── assets/                      # Иконки, SVG, стили
└── translations/                # Переводы (ru, en, de)
```

---

### Автор

*A1lPaka*

___
<br>

## 🇪🇳 Description in English
<br>

## My first standalone project in Python + PySide6  

Hi there!  
This is my first major project, created in about **2.5 months after I started learning Python and PySide6**.  
I tried to implement everything I’ve learned so far — the code might not be perfect,  
but my goal was to build a **real working tool**, not just a training exercise.

---

## What is Censor

**Censor** is a desktop application that combines a simple text editor  
with an **intelligent censorship system**.  
It checks text for profanity, highlights detected words,  
and allows you to quickly apply censorship — either by masking with asterisks or random symbols.

---

## Features

- Detects profanity in text (Russian, English, and German)  
- Two tabs: **Original** and **Censored text**  
- Two censorship modes — asterisks (`c*****r`) or symbols (`@#$%!`)  
- Built-in **banlist editor** with TXT and CSV import/export  
- Supports **dark and light themes**  
- Interface available in 🇷🇺 Russian, 🇬🇧 English, and 🇩🇪 German  
- Handles **multiple encodings and line endings** (UTF-8, UTF-16, ANSI, LF, CRLF)  
- Fast **search and replace (Ctrl + F)**  
- Word, line, and violation counters  
- Modern frameless interface styled after **Windows 11**  
  *(the module `winfl_anti_flicker_base.py` was partially implemented with the help of neural networks,  
  since I’m still learning WinAPI concepts)*  

---

## Screenshots

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/059f6d17-52cb-4d0b-b4e2-6dc49aae5cd7" />

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/b1ea90e9-70a2-4099-b599-6df5138cf982" />

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/c23da91b-1b9c-46ac-a08e-615f0aa0a8d6" />

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/f1e360d3-866b-49b5-9882-649c82e7579b" />

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/769c5746-058b-4236-9201-66c0f2e7e164" />

---

## How to Run

### Option 1 — Download ready-to-use `.exe`
The easiest way — download the ready build from  
[**Releases**](../../releases) on GitHub.  
There you’ll find an archive with the `.exe` version — just unzip it and run `Censor.exe`.

---

### Option 2 — Run from source
To run from source, you need:
- **Python 3.10+**
- **PySide6**

After installing dependencies, just run:
```bash
python censor.py
```

---

## Project Structure
```text
Censor/
|
├── censor.py                    # Main application file
├── _banwords_work.py            # Filtering logic
├── _text_work.py                # File handling and encoding management
├── _utils.py                    # Utilities: resource paths, popup positioning
├── CensorDialogTable.py         # Banlist editor dialog
├── CensorHighlighter.py         # Profanity highlighter
├── CensorHeader.py              # Header bar and tabs
├── CensorButtonPopup.py         # Popups (zoom, encoding, EOL)
├── CensorTextBlock.py           # QTextEdit class with zoom
├── winfl_anti_flicker_base.py   # Frameless window in Windows 11 style
├── assets/                      # Icons, SVG, styles
└── translations/                # Translations (ru, en, de)
```

---

## Author

*A1lPaka*

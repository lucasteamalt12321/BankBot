"""D&D Document Parser — extracts text from PDF, DOCX, TXT, images."""

import io
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DndDocumentParser:
    """Parse D&D sourcebooks and character sheets from uploaded files."""

    CHAPTER_KEYWORDS = [
        r"^глава\s+\d+",
        r"^chapter\s+\d+",
        r"^\d+\.\s+[А-ЯA-Z]",
        r"^введение",
        r"^introduction",
        r"^пролог",
        r"^prologue",
        r"^эпилог",
        r"^epilogue",
        r"^приложение",
        r"^appendix",
    ]

    CHARACTER_FIELDS = {
        "name": r"(?:имя|name|персонаж|character)\s*[:]\s*(.+)",
        "race": r"(?:раса|race)\s*[:]\s*(.+)",
        "class": r"(?:класс|class)\s*[:]\s*(.+)",
        "level": r"(?:уровень|level)\s*[:]\s*(\d+)",
        "alignment": r"(?:мировоззрение|alignment)\s*[:]\s*(.+)",
        "hp": r"(?:хиты|hp|hit\s*points|здоровье)\s*[:]\s*(\d+)",
        "max_hp": r"(?:макс\.?\s*хиты|max\s*hp|maximum\s*hit\s*points)\s*[:]\s*(\d+)",
        "ac": r"(?:класс\s*брони|ac|armor\s*class|кб)\s*[:]\s*(\d+)",
        "strength": r"(?:сила|strength|сил)\s*[:]\s*(\d+)",
        "dexterity": r"(?:ловкость|dexterity|лов)\s*[:]\s*(\d+)",
        "constitution": r"(?:телосложение|constitution|тел)\s*[:]\s*(\d+)",
        "intelligence": r"(?:интеллект|intelligence|инт)\s*[:]\s*(\d+)",
        "wisdom": r"(?:мудрость|wisdom|муд)\s*[:]\s*(\d+)",
        "charisma": r"(?:харизма|charisma|хар)\s*[:]\s*(\d+)",
    }

    def parse_pdf(self, data: bytes) -> str:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n".join(pages)
        except ImportError:
            logger.warning("PyPDF2 not installed, trying fallback")
            return ""
        except Exception as e:
            logger.error(f"PDF parse error: {e}")
            return ""

    def parse_docx(self, data: bytes) -> str:
        try:
            from docx import Document
            doc = Document(io.BytesIO(data))
            paragraphs = [p.text for p in doc.paragraphs if p.text]
            return "\n".join(paragraphs)
        except ImportError:
            logger.warning("python-docx not installed")
            return ""
        except Exception as e:
            logger.error(f"DOCX parse error: {e}")
            return ""

    def parse_txt(self, data: bytes) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return data.decode("cp1251")
            except UnicodeDecodeError:
                return data.decode("latin-1", errors="replace")

    def parse_image(self, data: bytes) -> str:
        try:
            import pytesseract
            from PIL import Image
            image = Image.open(io.BytesIO(data))
            return pytesseract.image_to_string(image, lang="rus+eng")
        except ImportError:
            logger.warning("pytesseract not installed")
            return ""
        except Exception as e:
            logger.error(f"Image OCR error: {e}")
            return ""

    def parse_file(self, data: bytes, filename: str) -> str:
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        parsers = {
            "pdf": self.parse_pdf,
            "docx": self.parse_docx,
            "doc": self.parse_docx,
            "txt": self.parse_txt,
            "jpg": self.parse_image,
            "jpeg": self.parse_image,
            "png": self.parse_image,
            "webp": self.parse_image,
        }
        parser = parsers.get(ext, self.parse_txt)
        text = parser(data)
        if not text:
            raise ValueError(f"Не удалось распознать файл {filename}")
        return text

    def extract_character_sheet(self, text: str) -> dict:
        character = {}
        for field, pattern in self.CHARACTER_FIELDS.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                if field in ("level", "hp", "max_hp", "ac", "strength", "dexterity",
                            "constitution", "intelligence", "wisdom", "charisma"):
                    try:
                        character[field] = int(value)
                    except ValueError:
                        character[field] = value
                else:
                    character[field] = value
        return character

    def split_into_scenes(self, text: str, max_chars: int = 10000) -> list[str]:
        if len(text) <= max_chars:
            return [text]

        lines = text.split("\n")
        scenes = []
        current_scene = []
        current_size = 0

        for line in lines:
            is_chapter = any(re.match(pattern, line.strip(), re.IGNORECASE) for pattern in self.CHAPTER_KEYWORDS)
            if is_chapter and current_scene and current_size > 1000:
                scenes.append("\n".join(current_scene))
                current_scene = [line]
                current_size = len(line)
            else:
                current_scene.append(line)
                current_size += len(line) + 1
                if current_size >= max_chars:
                    scenes.append("\n".join(current_scene))
                    current_scene = []
                    current_size = 0

        if current_scene:
            scenes.append("\n".join(current_scene))

        return scenes if scenes else [text]

    def create_summary(self, text: str, max_length: int = 3000) -> str:
        lines = text.split("\n")
        summary_lines = []
        total = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if total + len(stripped) > max_length:
                summary_lines.append("...")
                break
            summary_lines.append(stripped)
            total += len(stripped)

        return "\n".join(summary_lines)

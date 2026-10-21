"""Bounded document extraction. Never executes document macros or instructions."""
import io
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from html.parser import HTMLParser
from xml.etree import ElementTree

from docx import Document
from pypdf import PdfReader

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 120_000
EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.md', '.rtf', '.odt', '.html', '.htm'}


class DocumentError(ValueError):
    pass


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('p', 'div', 'li', 'br', 'h1', 'h2', 'h3', 'tr'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'li', 'tr'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def extract(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in EXTENSIONS:
        raise DocumentError('Unsupported format. Use PDF, DOCX, DOC, TXT, Markdown, RTF, ODT or HTML.')
    if not content or len(content) > MAX_BYTES:
        raise DocumentError('Upload a non-empty document no larger than 10 MB.')
    try:
        if ext in ('.docx', '.odt'):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(x.file_size for x in archive.infolist()) > 30 * 1024 * 1024 or len(archive.infolist()) > 3000:
                    raise DocumentError('Document expands beyond the safe extraction limit.')
        if ext == '.pdf':
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted or len(reader.pages) > 100:
                raise DocumentError('Use an unlocked PDF with at most 100 pages.')
            text = '\n'.join(f'[Page {n}]\n{p.extract_text() or ""}' for n, p in enumerate(reader.pages, 1))
        elif ext == '.docx':
            doc = Document(io.BytesIO(content))
            # Preserve body order, including tables, so evidence retains its context.
            from docx.oxml.ns import qn
            text = '\n'.join('\n'.join(
                ''.join(t.text or '' for t in p.iter(qn('w:t'))) for p in node.iter(qn('w:p'))
            ) for node in doc.element.body)
        elif ext == '.odt':
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                root = ElementTree.fromstring(archive.read('content.xml'))
            ns = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'
            text = '\n'.join(''.join(p.itertext()) for p in root.iter() if p.tag in (ns + 'p', ns + 'h'))
        elif ext == '.doc':
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'document.doc'
                path.write_bytes(content)
                try:
                    import os
                    result = subprocess.run([os.environ.get('ANTIWORD_BIN', 'antiword'), str(path)], capture_output=True, timeout=20, check=True)
                except FileNotFoundError:
                    raise DocumentError('Legacy DOC needs antiword installed on the server. Please save as DOCX or PDF.')
                text = result.stdout.decode('utf-8', errors='replace')
        else:
            text = content.decode('utf-8-sig')
            if ext == '.rtf':
                from striprtf.striprtf import rtf_to_text
                text = rtf_to_text(text)
            elif ext in ('.html', '.htm'):
                parser = VisibleHTML()
                parser.feed(text)
                text = ''.join(parser.parts)
        text = re.sub(r'[\t \xa0]+', ' ', text).strip()
        if len(text) < 40:
            raise DocumentError('Not enough extractable text. For scanned PDFs, run OCR and upload again.')
        if len(text) > MAX_CHARS:
            raise DocumentError('Document exceeds 120,000 extracted characters. Upload a shorter version.')
        return text
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError('Could not read the document. It may be damaged, encrypted, or mislabeled.') from exc

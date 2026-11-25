import io

from pypdf import PdfReader

from tolls.services.constants import MAX_IMPORT_PAGES
from tolls.services.errors import TollImportError


def extract_text(file_bytes):
    """Read the text layer of the uploaded statement (plain content order).

    The upload is untrusted input: the PDF magic is checked first, the page
    count is enforced before extracting any text and every error becomes a
    generic pt-br message with no extract content in it.
    """
    if not file_bytes.startswith(b'%PDF'):
        raise TollImportError('O arquivo enviado não é um PDF.')
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
    except Exception:  # noqa: BLE001 — corrupted/protected PDFs raise assorted pypdf errors
        raise TollImportError(
            'Não foi possível ler o extrato enviado '
            '(arquivo corrompido ou protegido).'
        )
    if page_count > MAX_IMPORT_PAGES:
        raise TollImportError(
            f'O extrato excede o limite de {MAX_IMPORT_PAGES} páginas.'
        )
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or '')
        except Exception:  # noqa: BLE001 — a broken page must not leak internals
            pages.append('')
    text = '\n'.join(pages)
    if not text.strip():
        raise TollImportError(
            'O extrato enviado não contém texto legível. '
            'Envie o PDF original do prestador, não uma imagem digitalizada.'
        )
    return text

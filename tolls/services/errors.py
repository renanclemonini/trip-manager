class TollImportError(Exception):
    """User-facing pt-br error raised by the toll import flow.

    Messages never carry PDF content (names, documents, plates,
    descriptions) — only generic labels and numbers.
    """

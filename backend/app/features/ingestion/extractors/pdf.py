import fitz

from app.features.ingestion.extractors.base import BaseExtractor, ExtractedDocument


class PDFExtractor(BaseExtractor):
    def extract(self, file_path: str) -> ExtractedDocument:
        doc = fitz.open(file_path)
        pages = [page.get_text() for page in doc]
        return ExtractedDocument(
            text="\n\n".join(pages),
            title=doc.metadata.get("title"),
            author=doc.metadata.get("author"),
            page_count=len(doc),
            pages=pages,
        )

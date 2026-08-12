import fitz

from app.features.ingestion.extractors.base import BaseExtractor, ExtractedDocument


class PDFExtractor(BaseExtractor):
    def extract(self, file_path: str) -> ExtractedDocument:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return ExtractedDocument(
            text=text,
            title=doc.metadata.get("title"),
            author=doc.metadata.get("author"),
            page_count=len(doc),
        )

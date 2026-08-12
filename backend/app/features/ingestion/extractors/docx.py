from app.features.ingestion.extractors.base import BaseExtractor, ExtractedDocument


class DocxExtractor(BaseExtractor):
    def extract(self, file_path: str) -> ExtractedDocument:
        raise NotImplementedError("DOCX extraction is planned for Phase 2")

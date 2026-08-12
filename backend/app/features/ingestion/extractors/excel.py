from app.features.ingestion.extractors.base import BaseExtractor, ExtractedDocument


class ExcelExtractor(BaseExtractor):
    def extract(self, file_path: str) -> ExtractedDocument:
        raise NotImplementedError("Excel extraction is planned for Phase 2")

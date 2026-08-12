from app.features.ingestion.extractors.base import BaseExtractor, ExtractedDocument


class ImageExtractor(BaseExtractor):
    def extract(self, file_path: str) -> ExtractedDocument:
        raise NotImplementedError("OCR image extraction is planned for Phase 2")

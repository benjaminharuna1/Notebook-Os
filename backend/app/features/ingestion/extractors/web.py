from app.features.ingestion.extractors.base import BaseExtractor, ExtractedDocument


class WebExtractor(BaseExtractor):
    def extract(self, url: str) -> ExtractedDocument:
        raise NotImplementedError("Web extraction is planned for Phase 2")

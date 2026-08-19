import logging

from app.features.FEATURE_NAME.repository import FeatureRepository

logger = logging.getLogger(__name__)


class FeatureService:
    def __init__(self, db):
        self.db = db
        self.repo = FeatureRepository(db)

    def example_method(self):
        pass

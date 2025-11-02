import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from flask_login import current_user
from sqlalchemy import desc, func

from app.modules.dataset.models import Author, DataSet, DOIMapping, DSDownloadRecord, DSMetaData, DSViewRecord
from core.repositories.BaseRepository import BaseRepository

logger = logging.getLogger(__name__)


class AuthorRepository(BaseRepository):
    def __init__(self):
        super().__init__(Author)


class DSDownloadRecordRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSDownloadRecord)

    def total_dataset_downloads(self) -> int:
        max_id = self.model.query.with_entities(func.max(self.model.id)).scalar()
        return max_id if max_id is not None else 0


class DSMetaDataRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSMetaData)

    def filter_by_doi(self, doi: str) -> Optional[DSMetaData]:
        return self.model.query.filter_by(dataset_doi=doi).first()


class DSViewRecordRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSViewRecord)

    def total_dataset_views(self) -> int:
        max_id = self.model.query.with_entities(func.max(self.model.id)).scalar()
        return max_id if max_id is not None else 0

    def the_record_exists(self, dataset: DataSet, user_cookie: str):
        return self.model.query.filter_by(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset.id,
            view_cookie=user_cookie,
        ).first()

    def create_new_record(self, dataset: DataSet, user_cookie: str) -> DSViewRecord:
        return self.create(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset.id,
            view_date=datetime.now(timezone.utc),
            view_cookie=user_cookie,
        )


class DataSetRepository(BaseRepository):
    def __init__(self):
        super().__init__(DataSet)

    def get_synchronized(self, current_user_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(DataSet.user_id == current_user_id, DSMetaData.dataset_doi.isnot(None))
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_unsynchronized(self, current_user_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(DataSet.user_id == current_user_id, DSMetaData.dataset_doi.is_(None))
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_unsynchronized_dataset(self, current_user_id: int, dataset_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(DataSet.user_id == current_user_id, DataSet.id == dataset_id, DSMetaData.dataset_doi.is_(None))
            .first()
        )

    def count_synchronized_datasets(self):
        return self.model.query.join(DSMetaData).filter(DSMetaData.dataset_doi.isnot(None)).count()

    def count_unsynchronized_datasets(self):
        return self.model.query.join(DSMetaData).filter(DSMetaData.dataset_doi.is_(None)).count()

    def latest_synchronized(self):
        return (
            self.model.query.join(DSMetaData)
            .filter(DSMetaData.dataset_doi.isnot(None))
            .order_by(desc(self.model.id))
            .limit(5)
            .all()
        )

    def get_top_downloads_global(self, limit=10, days=30):
        since_date = datetime.utcnow() - timedelta(days=days)
        return (
            self.model.query
            .join(DSMetaData, DSMetaData.id == DataSet.ds_meta_data_id)
            .outerjoin(DSDownloadRecord, DSDownloadRecord
                    .dataset_id == DataSet.id)
            .with_entities(
                DataSet.id.label("dataset_id"),
                DSMetaData.title.label("title"),
                DSMetaData.dataset_doi.label("doi"),
                func.coalesce(func.count(DSDownloadRecord.id), 0).label("downloads"),
            )
            .filter(DSDownloadRecord.download_date >= since_date)
            .group_by(DataSet.id, DSMetaData.title, DSMetaData.dataset_doi)
            .order_by(desc("downloads"))
            .limit(limit)
            .all()
        )

    def get_top_views_global(self, limit=10, days=30):
        since_date = datetime.utcnow() - timedelta(days=days)
        return (
            self.model.query
            .join(DSMetaData, DSMetaData.id == DataSet.ds_meta_data_id)
            .outerjoin(DSViewRecord, DSViewRecord.dataset_id == DataSet.id)
            .with_entities(
                DataSet.id.label("dataset_id"),
                DSMetaData.title.label("title"),
                DSMetaData.dataset_doi.label("doi"),
                func.coalesce(func.count(DSViewRecord.id), 0).label("views"),
            )
            .filter(DSViewRecord.view_date >= since_date)
            .group_by(DataSet.id, DSMetaData.title, DSMetaData.dataset_doi)
            .order_by(desc("views"))
            .limit(limit)
            .all()
        )


class DOIMappingRepository(BaseRepository):
    def __init__(self):
        super().__init__(DOIMapping)

    def get_new_doi(self, old_doi: str) -> str:
        return self.model.query.filter_by(dataset_doi_old=old_doi).first()

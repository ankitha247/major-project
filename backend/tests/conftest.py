from bson import ObjectId
from datetime import datetime, timezone
from app.db.mongo import get_db


class ReportRepository:
    def __init__(self):
        self.collection = get_db()["reports"]

    async def create(self, session_id: str, data: dict) -> dict:
        report = {
            "session_id": session_id,
            "generated_at": datetime.now(timezone.utc),
            **data,
        }
        result = await self.collection.insert_one(report)
        report["_id"] = str(result.inserted_id)
        return report

    async def get_by_session(self, session_id: str) -> dict:
        r = await self.collection.find_one({"session_id": session_id})
        if r:
            r["_id"] = str(r["_id"])
        return r
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from app.db.mongo import get_db
from app.models.user import User, UserRole


class UserRepository:
    def __init__(self):
        self.collection = get_db()["users"]

    async def create(
        self, email: str, hashed_password: str, full_name: str, role: UserRole = UserRole.INVESTIGATOR
    ) -> User:
        doc = {
            "email": email,
            "hashed_password": hashed_password,
            "full_name": full_name,
            "role": role,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return User(**doc)

    async def get_by_id(self, user_id: str) -> Optional[User]:
        try:
            doc = await self.collection.find_one({"_id": ObjectId(user_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
                return User(**doc)
            return None
        except Exception:
            return None

    async def get_by_email(self, email: str) -> Optional[User]:
        doc = await self.collection.find_one({"email": email})
        if doc:
            doc["_id"] = str(doc["_id"])
            return User(**doc)
        return None

    async def email_exists(self, email: str) -> bool:
        doc = await self.collection.find_one({"email": email})
        return doc is not None

    async def deactivate(self, user_id: str) -> None:
        await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_active": False,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
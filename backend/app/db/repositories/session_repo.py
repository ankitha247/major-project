from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
from app.db.mongo import get_db


class SessionPhase:
    RAPPORT = "rapport"
    FREE_RECALL = "free_recall"
    PROBING = "probing"
    CLARIFICATION = "clarification"
    CLOSURE = "closure"


class SessionStatus:
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FLAGGED = "flagged"


PHASE_ORDER = [
    SessionPhase.RAPPORT,
    SessionPhase.FREE_RECALL,
    SessionPhase.PROBING,
    SessionPhase.CLARIFICATION,
    SessionPhase.CLOSURE,
]


class SessionRepository:
    def __init__(self):
        self.collection = get_db()["sessions"]

    # ----------------------------------------------------------------
    # CREATE
    # ----------------------------------------------------------------

    async def create(
        self,
        witness_id: str,
        investigator_id: str,
        crime_type: str,
        witness_name: str = "",
        case_number: str = "",
        notes: str = None,
    ) -> dict:
        session = {
            "witness_id": witness_id,
            "witness_name": witness_name,
            "investigator_id": investigator_id,
            "crime_type": crime_type,
            "case_number": case_number,
            "phase": SessionPhase.RAPPORT,
            "phase_question_count": 0,
            "total_questions": 0,
            "status": SessionStatus.ACTIVE,
            "flags_count": 0,
            "overall_stress_score": 0.0,
            "overall_credibility_score": 0.0,
            "notes": notes,
            "evidence_description": None,
            "evidence_nlp": None,
            "scene_summary": None,
            "start_time": datetime.now(timezone.utc),
            "end_time": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = await self.collection.insert_one(session)
        session["_id"] = str(result.inserted_id)
        return session

    # ----------------------------------------------------------------
    # READ
    # ----------------------------------------------------------------

    async def get_by_id(self, session_id: str) -> Optional[dict]:
        try:
            s = await self.collection.find_one({"_id": ObjectId(session_id)})
            if s:
                s["_id"] = str(s["_id"])
            return s
        except Exception:
            return None

    async def get_by_investigator(
        self,
        investigator_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        query: dict = {"investigator_id": investigator_id}
        if status:
            query["status"] = status

        total = await self.collection.count_documents(query)
        skip = (page - 1) * page_size
        cursor = (
            self.collection.find(query)
            .sort("start_time", -1)
            .skip(skip)
            .limit(page_size)
        )
        docs = await cursor.to_list(length=page_size)
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return docs, total

    async def get_by_witness(self, witness_id: str) -> list[dict]:
        cursor = self.collection.find(
            {"witness_id": witness_id}
        ).sort("start_time", -1)
        docs = await cursor.to_list(length=100)
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return docs

    async def get_by_case_number(
        self, case_number: str, investigator_id: str
    ) -> list[dict]:
        cursor = self.collection.find(
            {"case_number": case_number, "investigator_id": investigator_id}
        )
        docs = await cursor.to_list(length=100)
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return docs

    # ----------------------------------------------------------------
    # PHASE
    # ----------------------------------------------------------------

    async def update_phase(self, session_id: str, phase: str) -> Optional[dict]:
        await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$set": {
                    "phase": phase,
                    "phase_question_count": 0,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return await self.get_by_id(session_id)

    async def advance_phase(self, session_id: str) -> Optional[dict]:
        session = await self.get_by_id(session_id)
        if not session:
            return None
        current_phase = session.get("phase", SessionPhase.RAPPORT)
        try:
            current_index = PHASE_ORDER.index(current_phase)
        except ValueError:
            current_index = 0
        if current_index >= len(PHASE_ORDER) - 1:
            return None
        next_phase = PHASE_ORDER[current_index + 1]
        return await self.update_phase(session_id, next_phase)

    async def get_next_phase(self, current_phase: str) -> Optional[str]:
        try:
            current_index = PHASE_ORDER.index(current_phase)
        except ValueError:
            return None
        if current_index >= len(PHASE_ORDER) - 1:
            return None
        return PHASE_ORDER[current_index + 1]

    # ----------------------------------------------------------------
    # QUESTION COUNTS
    # ----------------------------------------------------------------

    async def increment_question_count(self, session_id: str) -> None:
        await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$inc": {
                    "total_questions": 1,
                    "phase_question_count": 1,
                },
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

    # ----------------------------------------------------------------
    # STATUS
    # ----------------------------------------------------------------

    async def update_status(self, session_id: str, status: str) -> Optional[dict]:
        update = {
            "$set": {
                "status": status,
                "updated_at": datetime.now(timezone.utc),
            }
        }
        if status == SessionStatus.COMPLETED:
            update["$set"]["end_time"] = datetime.now(timezone.utc)
        await self.collection.update_one({"_id": ObjectId(session_id)}, update)
        return await self.get_by_id(session_id)

    async def close_session(self, session_id: str) -> None:
        await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$set": {
                    "status": SessionStatus.COMPLETED,
                    "end_time": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    async def pause_session(self, session_id: str) -> None:
        await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$set": {
                    "status": SessionStatus.PAUSED,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    async def resume_session(self, session_id: str) -> None:
        await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$set": {
                    "status": SessionStatus.ACTIVE,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    # ----------------------------------------------------------------
    # FLAGS AND SCORING
    # ----------------------------------------------------------------

    async def increment_flags(self, session_id: str) -> None:
        await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$inc": {"flags_count": 1},
                "$set": {
                    "status": SessionStatus.FLAGGED,
                    "updated_at": datetime.now(timezone.utc),
                },
            },
        )

    async def update_scores(
        self,
        session_id: str,
        stress_score: Optional[float] = None,
        credibility_score: Optional[float] = None,
    ) -> None:
        set_fields: dict = {"updated_at": datetime.now(timezone.utc)}
        if stress_score is not None:
            set_fields["overall_stress_score"] = round(stress_score, 4)
        if credibility_score is not None:
            set_fields["overall_credibility_score"] = round(credibility_score, 4)
        await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": set_fields},
        )

    # ----------------------------------------------------------------
    # NOTES
    # ----------------------------------------------------------------

    async def update_notes(self, session_id: str, notes: str) -> None:
        await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$set": {
                    "notes": notes,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    # ----------------------------------------------------------------
    # EVIDENCE CONTEXT
    # ----------------------------------------------------------------

    async def save_evidence_context(
        self,
        session_id: str,
        evidence_description: str,
        nlp_result: dict,
        scene_summary: str,
        evidence_type: str = "text",
        opencv_result: dict = None,
        context_string: str = "",
    ) -> None:
        await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$set": {
                    "evidence_description": evidence_description,
                    "evidence_nlp": nlp_result,
                    "scene_summary": scene_summary,
                    "evidence_type": evidence_type,
                    "evidence_opencv": opencv_result or {},
                    "evidence_context_string": context_string,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    # ----------------------------------------------------------------
    # DELETE
    # ----------------------------------------------------------------

    async def delete(self, session_id: str) -> bool:
        result = await self.collection.delete_one({"_id": ObjectId(session_id)})
        return result.deleted_count > 0
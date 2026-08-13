import json

from fastapi.responses import StreamingResponse

from app.features.chat.repository import ChatRepository
from app.features.chat.prompt_builder import PromptBuilder
from app.features.models.service import ModelService
from app.features.search.service import SearchService
from app.features.skills.service import SkillsService
from app.shared.id_utils import generate_id


class ChatService:
    def __init__(self, db, settings_dict: dict | None = None):
        self.db = db
        self.repo = ChatRepository(db)
        self.settings_dict = settings_dict or {}
        self.prompt_builder = PromptBuilder()
        self.model_service = ModelService(db, self.settings_dict)
        self.search_service = SearchService(db)

    async def stream_chat(self, req, user_id: str):
        try:
            return await self._stream_chat(req, user_id)
        except Exception as exc:
            logger.exception("chat failed before streaming started")
            detail = getattr(exc, "detail", None) or str(exc)

            async def _error_stream():
                yield f"data: {json.dumps({'type': 'error', 'detail': detail})}\n\n"

            return StreamingResponse(_error_stream(), media_type="text/event-stream")

    async def _stream_chat(self, req, user_id: str):
        session_id = req.session_id or generate_id()

        # A chat always belongs to a project. Existing sessions keep theirs;
        # new sessions require one up front so search stays scoped.
        if req.session_id:
            session = self.repo.get_session(req.session_id, user_id)
            if not session:
                raise self._not_found("Session not found")
            project_id = session["project_id"] or req.project_id
        else:
            project_id = req.project_id
            if project_id:
                self._require_project(user_id, project_id)
            self.repo.create_session(session_id, user_id, "New Chat", project_id=project_id)

        self.repo.add_message(session_id, "user", req.message)

        from app.features.search.schemas import SearchRequest

        search_req = SearchRequest(
            query=req.message,
            top_k=req.top_k if hasattr(req, "top_k") else 5,
            document_ids=req.document_ids,
            project_id=project_id,
        )
        search_results = await self.search_service.search(search_req, user_id)
        sources = search_results.results

        model = self.model_service.get_active_model(user_id)
        skill_instructions = SkillsService(self.db).active_instructions(user_id)
        context = self.prompt_builder.build(sources, req.message, skill_instructions)

        messages = self.repo.get_messages(session_id)
        source_data = [
            {"chunk_id": s.chunk_id, "title": s.document_title, "page": s.page_number}
            for s in sources
        ]

        async def generate():
            answer = []
            try:
                provider = self.model_service.get_provider(model, user_id)
                async for chunk in provider.stream_chat(context, messages):
                    answer.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            except Exception as exc:  # surface the failure to the client cleanly
                detail = getattr(exc, "detail", None) or str(exc)
                yield f"data: {json.dumps({'type': 'error', 'detail': detail})}\n\n"
                return

            # Persist the assistant reply so reloading the session restores it
            try:
                self.repo.add_message(
                    session_id,
                    "assistant",
                    "".join(answer),
                    sources=json.dumps(source_data),
                    model_used=model.get("id"),
                )
            except Exception:
                logger.exception("could not persist assistant message for %s", session_id)

            yield f"data: {json.dumps({'type': 'sources', 'sources': source_data})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    def list_sessions(self, user_id: str, project_id: str | None = None):
        return {"sessions": self.repo.list_sessions(user_id, project_id)}

    def get_session(self, session_id: str, user_id: str):
        session = self.repo.get_session(session_id, user_id)
        messages = self.repo.get_messages(session_id)
        return {"session": session, "messages": messages}

    def delete_session(self, session_id: str, user_id: str):
        self.repo.delete_session(session_id, user_id)
        return {"success": True}

    @staticmethod
    def _not_found(message: str, status_code: int = 404):
        from app.core.exceptions import AppException

        return AppException(message, status_code=status_code)

    def _require_project(self, user_id: str, project_id: str):
        row = self.db.execute(
            "SELECT id FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
        if not row:
            raise self._not_found("Project not found")

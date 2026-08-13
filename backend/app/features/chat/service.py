import json

from fastapi.responses import StreamingResponse

from app.features.chat.repository import ChatRepository
from app.features.chat.prompt_builder import PromptBuilder
from app.features.models.service import ModelService
from app.features.search.service import SearchService
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
        session_id = req.session_id or generate_id()
        if not req.session_id:
            self.repo.create_session(session_id, user_id, "New Chat")

        self.repo.add_message(session_id, "user", req.message)

        search_results = await self.search_service.search(req, user_id)
        sources = search_results.results

        model = self.model_service.get_active_model(user_id)
        context = self.prompt_builder.build(sources, req.message)

        messages = self.repo.get_messages(session_id)

        async def generate():
            provider = self.model_service.get_provider(model, user_id)
            async for chunk in provider.stream_chat(context, messages):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            source_data = [
                {"chunk_id": s.chunk_id, "title": s.document_title, "page": s.page_number}
                for s in sources
            ]
            yield f"data: {json.dumps({'type': 'sources', 'sources': source_data})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    def list_sessions(self, user_id: str):
        return {"sessions": self.repo.list_sessions(user_id)}

    def get_session(self, session_id: str, user_id: str):
        session = self.repo.get_session(session_id, user_id)
        messages = self.repo.get_messages(session_id)
        return {"session": session, "messages": messages}

    def delete_session(self, session_id: str, user_id: str):
        self.repo.delete_session(session_id, user_id)
        return {"success": True}

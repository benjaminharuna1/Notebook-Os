import json

from fastapi.responses import StreamingResponse

from app.shared.logger import logger
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

    # --- cluster context -----------------------------------------------------

    def _cluster_context(self, project_id: str | None) -> str:
        """Build a context string from the latest literature-map clusters."""
        if not project_id:
            return ""
        try:
            row = self.db.execute(
                """SELECT graph_json FROM graph_history
                   WHERE project_id = ? AND map_type = 'literature'
                   ORDER BY created_at DESC, rowid DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
            if not row:
                return ""
            data = json.loads(row["graph_json"])
            clusters = data.get("clusters", [])
            if not clusters:
                return ""
            parts = []
            for c in clusters:
                label = c.get("label", "")
                summary = c.get("summary", "")
                size = c.get("size", 0)
                if label:
                    parts.append(f"- **{label}** ({size} papers): {summary}")
            if not parts:
                return ""
            return "\n".join(parts)
        except Exception:
            return ""

    # --- literature entries context ------------------------------------------

    def _lit_entries_context(self, project_id: str | None, doc_ids: list | None) -> str:
        """Build context from literature entries for documents matched by search."""
        if not project_id:
            return ""
        try:
            rows = self.db.execute(
                """SELECT e.paper_id, e.research_objective, e.methodology,
                          e.key_findings, e.limitations, e.relevance, e.citation,
                          d.title AS title
                   FROM literature_entries e
                   JOIN documents d ON d.id = e.paper_id
                   WHERE e.project_id = ? AND e.user_id IS NOT NULL""",
                (project_id,),
            ).fetchall()
            if not rows:
                return ""
            parts = []
            for r in rows:
                title = r["title"] or ""
                obj = r["research_objective"] or ""
                findings = r["key_findings"] or ""
                if not obj and not findings:
                    continue
                block = f"**{title}**"
                if obj:
                    block += f"\n  Research objective: {obj}"
                if findings:
                    block += f"\n  Key findings: {findings}"
                parts.append(block)
            return "\n\n".join(parts[:20])
        except Exception:
            return ""

    # --- slash commands ------------------------------------------------------

    SLASH_COMMANDS = {
        "/summarize": (
            "Provide a comprehensive summary of the project's literature. "
            "Cover all papers, organized by theme or methodology. "
            "Use APA 7th edition parenthetical citations for every claim."
        ),
        "/evaluate": (
            "Critically evaluate the body of literature in this project. "
            "Assess strengths, weaknesses, methodological rigor, and identify gaps. "
            "Use APA 7th edition parenthetical citations for every claim."
        ),
        "/mapping": (
            "Produce a structured literature mapping: group papers by theme, "
            "identify connections and contradictions, and suggest future directions. "
            "Use APA 7th edition parenthetical citations for every claim."
        ),
    }

    def _apply_slash_command(self, command: str) -> str:
        cmd = command.strip().lower().split()[0] if command.strip() else ""
        return self.SLASH_COMMANDS.get(cmd, "")

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
        is_new_session = not req.session_id

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

        # --- regenerate: delete everything from the last user message onward
        effective_message = req.message
        if req.regenerate and req.session_id:
            existing = self.repo.get_messages(session_id)
            last_user = None
            for m in reversed(existing):
                if m["role"] == "user":
                    last_user = m
                    break
            if last_user:
                effective_message = last_user["content"]
                self.repo.delete_messages_from(session_id, last_user["id"])
            # If no user message found, fall through with the incoming message

        self.repo.add_message(session_id, "user", effective_message)

        # --- slash command handling ---
        slash_extra = ""
        if req.slash_command:
            slash_extra = self._apply_slash_command(req.slash_command)

        from app.features.search.schemas import SearchRequest

        search_req = SearchRequest(
            query=effective_message,
            top_k=req.top_k if hasattr(req, "top_k") else 5,
            document_ids=req.document_ids,
            project_id=project_id,
        )
        search_results = await self.search_service.search(search_req, user_id)
        sources = search_results.results

        model = self.model_service.get_active_model(user_id)
        skill_instructions = SkillsService(self.db).active_instructions(user_id)
        cluster_ctx = self._cluster_context(project_id)
        lit_ctx = self._lit_entries_context(project_id, req.document_ids)
        context = self.prompt_builder.build(
            sources, effective_message, skill_instructions,
            cluster_context=cluster_ctx,
            lit_entries_context=lit_ctx,
            slash_extra=slash_extra,
        )

        messages = self.repo.get_messages(session_id)
        source_data = [
            {"chunk_id": s.chunk_id, "title": s.document_title, "page": s.page_number, "document_id": getattr(s, "document_id", None)}
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

            # Auto-generate a session title from the first user message
            if is_new_session:
                try:
                    title = req.message.strip()[:80]
                    self.repo.update_title(session_id, title)
                except Exception:
                    pass

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

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

    def _lit_entries_context(self, project_id: str | None, doc_ids: list | None, source_doc_ids: list | None = None) -> str:
        """Build context from literature entries for documents matched by search.

        Combines user-selected doc_ids (from paper scope) and source_doc_ids
        (from the actual search results) to provide rich per-paper metadata.
        """
        if not project_id:
            return ""
        try:
            # Union of user-selected and search-matched document IDs
            target_ids = set(doc_ids or [])
            target_ids.update(source_doc_ids or [])
            if not target_ids:
                # No specific docs targeted — use all project entries (up to a limit)
                rows = self.db.execute(
                    """SELECT e.paper_id, e.research_objective, e.methodology,
                              e.key_findings, e.limitations, e.relevance, e.citation,
                              d.title AS title, d.author AS author, d.extracted_doi AS doi
                       FROM literature_entries e
                       JOIN documents d ON d.id = e.paper_id
                       WHERE e.project_id = ? AND e.user_id IS NOT NULL""",
                    (project_id,),
                ).fetchall()
            else:
                placeholders = ",".join("?" for _ in target_ids)
                rows = self.db.execute(
                    f"""SELECT e.paper_id, e.research_objective, e.methodology,
                               e.key_findings, e.limitations, e.relevance, e.citation,
                               d.title AS title, d.author AS author, d.extracted_doi AS doi
                        FROM literature_entries e
                        JOIN documents d ON d.id = e.paper_id
                        WHERE e.project_id = ? AND e.user_id IS NOT NULL
                          AND e.paper_id IN ({placeholders})""",
                    (project_id, *target_ids),
                ).fetchall()
            if not rows:
                return ""
            parts = []
            for r in rows:
                title = r["title"] or ""
                citation = r["citation"] or ""
                obj = r["research_objective"] or ""
                methodology = r["methodology"] or ""
                findings = r["key_findings"] or ""
                limitations = r["limitations"] or ""
                relevance = r["relevance"] or ""
                if not obj and not findings and not methodology:
                    continue
                block = f"**{title}**"
                if citation:
                    block += f"\n  Citation: {citation}"
                if obj:
                    block += f"\n  Research objective: {obj}"
                if methodology:
                    block += f"\n  Methodology: {methodology}"
                if findings:
                    block += f"\n  Key findings: {findings}"
                if limitations:
                    block += f"\n  Limitations: {limitations}"
                if relevance:
                    block += f"\n  Relevance: {relevance}"
                parts.append(block)
            return "\n\n".join(parts[:30])
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
        "/review": (
            "Act as an adversarial academic peer reviewer. Critically audit the indexed literature. "
            "Execute a full Methodological Audit (sample integrity, statistical rigor, experimental control). "
            "Expose Hidden Assumptions, Publication Bias, and Conflicts of Interest. "
            "Generate Counter-Narratives: define boundary conditions, falsifiability criteria, and alternative theories. "
            "Label weak claims as 'Speculative Hypothesis'. "
            "Conclude every analysis with a Critical Evaluation Summary containing: "
            "Key Methodological Limitations, Unresolved Contradictions, High-Value Future Research Questions."
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
            top_k=req.top_k if hasattr(req, "top_k") else 15,
            document_ids=req.document_ids,
            project_id=project_id,
        )
        search_results = await self.search_service.search(search_req, user_id)

        # Fix 5: Soft filter — keep results with score >= 0.2, always keep top 5
        raw_sources = search_results.results
        if len(raw_sources) > 5:
            good = [s for s in raw_sources if getattr(s, "score", 0) >= 0.2]
            sources = good if len(good) >= 5 else raw_sources[:5]
        else:
            sources = raw_sources

        # Query expansion: run a second search with key terms extracted from
        # the question to catch semantically related chunks
        import re as _re
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can", "need", "dare", "ought",
            "used", "what", "which", "who", "whom", "this", "that", "these",
            "those", "i", "me", "my", "we", "our", "you", "your", "he", "him",
            "his", "she", "her", "it", "its", "they", "them", "their", "about",
            "for", "from", "in", "on", "at", "to", "of", "with", "by", "as",
            "into", "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "then", "once", "here", "there", "when",
            "where", "why", "how", "all", "both", "each", "few", "more", "most",
            "other", "some", "such", "no", "nor", "not", "only", "own", "same",
            "so", "than", "too", "very", "just", "don", "now", "and", "but",
            "or", "if", "while", "because", "although", "though", "since",
            "unless", "until", "whether", "whereas",
        }
        words = _re.findall(r'[a-zA-Z]{3,}', effective_message.lower())
        key_terms = [w for w in words if w not in stop_words]
        if len(key_terms) >= 2:
            expansion_query = " ".join(key_terms[:8])
            expansion_req = SearchRequest(
                query=expansion_query,
                top_k=10,
                document_ids=req.document_ids,
                project_id=project_id,
            )
            expansion_results = await self.search_service.search(expansion_req, user_id)
            existing_ids = {s.chunk_id for s in sources}
            for er in expansion_results.results:
                if er.chunk_id not in existing_ids and getattr(er, "score", 0) >= 0.25:
                    sources.append(er)
                    existing_ids.add(er.chunk_id)

        # If user is asking about a specific reference, do aggressive fallback
        # to find chunks mentioning that reference. Match on:
        #   1. Both surnames + year (most precise)
        #   2. Either surname + year
        #   3. Both surnames alone (broadest)
        import re as _re
        # Match "Surname & Surname, Year" or "Surname and Surname (Year)" etc.
        author_year_match = _re.search(
            r'([A-Z][a-z\u00C0-\u024F]+(?:[\s-]+(?:de|da|von|van|di|el|al))?)\s*(?:&|and)\s*([A-Z][a-z\u00C0-\u024F]+(?:[\s-]+(?:de|da|von|van|di|el|al))?),?\s*(\d{4})',
            effective_message,
        )
        # Also match single author + year: "Surname, Year" or "Surname (Year)"
        single_author_match = _re.search(
            r'([A-Z][a-z\u00C0-\u024F]+(?:[\s-]+(?:de|da|von|van|di|el|al))?),?\s*(\d{4})',
            effective_message,
        )
        if author_year_match:
            surname1 = author_year_match.group(1).lower()
            surname2 = author_year_match.group(2).lower()
            year = author_year_match.group(3)
        elif single_author_match:
            surname1 = single_author_match.group(1).lower()
            surname2 = ""
            year = single_author_match.group(2)
        else:
            surname1 = ""
            surname2 = ""
            year = ""

        if surname1 and len(sources) < 10:
            existing_ids = {s.chunk_id for s in sources}
            fallback_rows = []

            # Pass 1: both surnames + year (highest precision)
            if surname2:
                fallback_rows = self.db.execute(
                    """SELECT c.id AS chunk_id, c.content, c.document_id, c.page_number,
                              d.title AS document_title
                       FROM chunks c JOIN documents d ON d.id = c.document_id
                       WHERE (c.content LIKE ? COLLATE NOCASE
                          AND c.content LIKE ? COLLATE NOCASE
                          AND c.content LIKE ? COLLATE NOCASE)
                         AND d.project_id = ?
                       ORDER BY c.rowid LIMIT 10""",
                    (f"%{surname1}%", f"%{surname2}%", f"%{year}%", project_id),
                ).fetchall()

            # Pass 2: surname1 + year (still precise)
            if len(fallback_rows) < 3:
                pass2 = self.db.execute(
                    """SELECT c.id AS chunk_id, c.content, c.document_id, c.page_number,
                              d.title AS document_title
                       FROM chunks c JOIN documents d ON d.id = c.document_id
                       WHERE (c.content LIKE ? COLLATE NOCASE AND c.content LIKE ? COLLATE NOCASE)
                         AND d.project_id = ?
                       ORDER BY c.rowid LIMIT 10""",
                    (f"%{surname1}%", f"%{year}%", project_id),
                ).fetchall()
                existing_ids_pass2 = {r["chunk_id"] for r in fallback_rows}
                for r in pass2:
                    if r["chunk_id"] not in existing_ids_pass2:
                        fallback_rows.append(r)

            # Pass 3: both surnames without year (broadest)
            if surname2 and len(fallback_rows) < 3:
                pass3 = self.db.execute(
                    """SELECT c.id AS chunk_id, c.content, c.document_id, c.page_number,
                              d.title AS document_title
                       FROM chunks c JOIN documents d ON d.id = c.document_id
                       WHERE (c.content LIKE ? COLLATE NOCASE AND c.content LIKE ? COLLATE NOCASE)
                         AND d.project_id = ?
                       ORDER BY c.rowid LIMIT 10""",
                    (f"%{surname1}%", f"%{surname2}%", project_id),
                ).fetchall()
                existing_ids_pass3 = {r["chunk_id"] for r in fallback_rows}
                for r in pass3:
                    if r["chunk_id"] not in existing_ids_pass3:
                        fallback_rows.append(r)

            for row in fallback_rows:
                if row["chunk_id"] not in existing_ids:
                    content_lower = (row["content"] or "").lower()
                    # Score based on how many parts matched
                    has_s2 = surname2 in content_lower if surname2 else False
                    has_yr = year in content_lower
                    if has_s2 and has_yr:
                        score = 0.9
                    elif has_yr or has_s2:
                        score = 0.7
                    else:
                        score = 0.4
                    sources.append(type("FallbackSource", (), {
                        "chunk_id": row["chunk_id"],
                        "content": row["content"],
                        "score": score,
                        "document_id": row["document_id"],
                        "document_title": row["document_title"],
                        "page_number": row["page_number"],
                    })())
                    existing_ids.add(row["chunk_id"])

        # Web search fallback: if user asks about a specific reference and
        # nothing in indexed papers contains it, search the web for it
        web_results_text = ""
        if surname1:
            # Check if any source chunk actually mentions this author
            ref_found = False
            for s in sources:
                content_lower = (getattr(s, "content", "") or "").lower()
                if surname1.lower() in content_lower:
                    if not surname2 or surname2.lower() in content_lower:
                        ref_found = True
                        break
            if not ref_found:
                from app.features.chat.web_search import web_search, format_web_results
                search_name = f"{surname1} {surname2}".strip() if surname2 else surname1
                query = f"{search_name} {year} APA reference"
                web_hits = await web_search(query, num_results=5)
                if web_hits:
                    web_results_text = (
                        "\n\nIMPORTANT: The reference was NOT found in the indexed journals. "
                        "Below are web search results for this reference. Use them to provide "
                        "the APA reference and explain that it was found via web search, not "
                        "from the indexed journals. Suggest the user download and index the paper "
                        "if they want it available locally.\n\n"
                        + format_web_results(web_hits)
                    )

        model = self.model_service.get_active_model(user_id)
        skills_svc = SkillsService(self.db)
        skill_instructions = skills_svc.detect_relevant_skills(user_id, effective_message)
        cluster_ctx = self._cluster_context(project_id)

        # Fix 6: Union user-selected doc_ids with search-matched doc_ids
        search_doc_ids = {getattr(s, "document_id", None) for s in sources if getattr(s, "document_id", None)}
        user_doc_ids = set(req.document_ids or [])
        source_doc_ids = list(user_doc_ids | search_doc_ids)
        lit_ctx = self._lit_entries_context(project_id, req.document_ids, source_doc_ids)

        # Build APA references string for the prompt
        doc_ids_for_refs = list({getattr(s, "document_id", None) for s in sources if getattr(s, "document_id", None)})
        apa_map: dict[str, str] = {}
        if doc_ids_for_refs:
            ph = ",".join("?" for _ in doc_ids_for_refs)
            for row in self.db.execute(
                f"SELECT id, apa_reference FROM documents WHERE id IN ({ph})", doc_ids_for_refs
            ).fetchall():
                if row["apa_reference"]:
                    apa_map[row["id"]] = row["apa_reference"]

        # Deduplicated APA references in order of first appearance
        seen_refs: list[str] = []
        seen_titles: set[str] = set()
        for s in sources:
            doc_id = getattr(s, "document_id", None)
            ref = apa_map.get(doc_id, "")
            if ref and s.document_title not in seen_titles:
                seen_titles.add(s.document_title)
                seen_refs.append(ref)
        apa_references_str = "\n".join(seen_refs)

        context = self.prompt_builder.build(
            sources, effective_message, skill_instructions,
            cluster_context=cluster_ctx,
            lit_entries_context=lit_ctx,
            slash_extra=slash_extra,
            apa_references=apa_references_str,
            web_results=web_results_text,
        )

        # Fix 4: Cap conversation history to last 20 messages
        messages = self.repo.get_messages(session_id, limit=20)

        source_data = [
            {
                "chunk_id": s.chunk_id,
                "title": s.document_title,
                "page": s.page_number,
                "document_id": getattr(s, "document_id", None),
                "apa_reference": apa_map.get(getattr(s, "document_id", None), ""),
            }
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
        messages = self.repo.get_messages(session_id, limit=50)
        return {"session": session, "messages": messages}

    def delete_session(self, session_id: str, user_id: str):
        self.repo.delete_session(session_id, user_id)
        return {"success": True}

    def rename_session(self, session_id: str, user_id: str, title: str):
        session = self.repo.get_session(session_id, user_id)
        if not session:
            raise self._not_found("Session not found")
        self.repo.update_title(session_id, title)
        return {"success": True, "title": title}

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

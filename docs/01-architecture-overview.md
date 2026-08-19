# System Architecture & Data Flow

## Overview

**Notebook AI OS** is a local-first AI research assistant that ingests, processes, understands, and reasons over research materials entirely on-device. Cloud models are optionally used as reasoning accelerators — they only ever receive structured, processed context, never raw documents.

The system follows a strict layered architecture with clean separation between ingestion, storage, retrieval, AI routing, and UI.

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (SvelteKit)                     │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐    │
│  │Auth  │ │Chat  │ │Upload│ │Graph │ │Model │ │Literature│    │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘    │
└─────┼────────┼────────┼────────┼────────┼──────────┼───────────┘
      │        │        │        │        │          │
      └────────┴────────┴────────┴────────┴──────────┘
                                │ HTTP/REST + SSE
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │   AUTH   │  │ PROJECTS │  │SETTINGS  │  │   MODELS     │    │
│  │JWT+CORS  │  │ CRUD     │  │per-user  │  │Ollama/Local/ │    │
│  └──────────┘  └──────────┘  └──────────┘  │Cloud routing │    │
│                                             └──────────────┘    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │  INGESTION   │─▶│  PROCESSING  │─▶│   EMBEDDING      │      │
│  │ PDF upload   │  │ chunk/clean  │  │ fastembed/Ollama │      │
│  └──────────────┘  └──────────────┘  └────────┬─────────┘      │
│                                               │                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────▼─────────┐      │
│  │ AI ROUTER    │◀─│   RETRIEVAL  │◀─│   VECTOR STORE   │      │
│  │ local/cloud  │  │ semantic +   │  │    (ChromaDB)    │      │
│  └──────┬───────┘  │ keyword      │  └──────────────────┘      │
│         │          └──────────────┘                              │
│  ┌──────▼───────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │  CHAT ENGINE │  │ GRAPH BUILDER│  │  LITERATURE MAP  │      │
│  │  context +   │  │ (NetworkX +  │  │  citation graph  │      │
│  │  RAG + SSE   │  │  LLM)        │  │  + metadata      │      │
│  └──────────────┘  └──────────────┘  └──────────────────┘      │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │   SKILLS     │  │   ACTIONS    │  │  DOCUMENTS       │      │
│  │ 8 AI skills  │  │ bg job       │  │  CRUD + file     │      │
│  │ (JSON defs)  │  │ tracking     │  │  serving         │      │
│  └──────────────┘  └──────────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
        │                     │                      │
        ▼                     ▼                      ▼
┌──────────────┐   ┌─────────────────┐   ┌──────────────────────┐
│ LOCAL MODELS │   │  LOCAL STORAGE  │   │   OPTIONAL CLOUD     │
│  llama-cpp   │   │ ChromaDB + Files│   │  OpenAI/Claude/Gemini│
│  (GGUF)      │   │  SQLite metadata│   │  (structured ctx only)│
└──────────────┘   └─────────────────┘   └──────────────────────┘
```

## Data Flow

```
User uploads PDF
      │
      ▼
[Ingestion Layer]
  - Save raw file to /data/uploads/
  - Extract text (PyMuPDF / pdfplumber)
  - Extract metadata (title, author, year, DOI)
      │
      ▼
[Processing Layer]
  - Clean text (remove noise, headers, footers)
  - Chunk text (configurable: default 1024 tokens, 128 overlap)
  - Generate chunk metadata (page, source, position)
      │
      ▼
[Embedding Engine]
  - Embed each chunk via fastembed (local) or Ollama
  - Store embeddings → ChromaDB
  - Store metadata → SQLite
      │
      ▼
[Vector Store - ChromaDB]
  - Persistent local vector database
  - Collections per project
      │
      ▼
[Retrieval Layer]
  - Semantic: cosine similarity search → top-k chunks
  - Keyword: SQLite LIKE across chunks, ranked by token overlap
  - Merge: semantic first, keyword fills gaps, deduplicated
      │
      ▼
[AI Router]
  - Route to Ollama, local GGUF, or cloud model
  - Never send raw documents to cloud
  - Only send structured chunks + question
      │
      ▼
[Chat Engine]
  - System prompt + context + history + skills
  - Stream response to frontend via SSE
  - Store chat history in SQLite
  - Auto-learn: extract topics, preferences, references
```

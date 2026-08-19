# Feature Template

Use this skeleton to create new features for Notebook OS.

## How to use

1. Copy this directory to `backend/app/features/your_feature/`
2. Rename all files and replace `FEATURE_NAME` with your feature name
3. Update `CONTEXT.md` with your feature's specifics
4. Add the feature to the pipeline in `backend/app/CONTEXT.md`
5. Register the router in `backend/app/main.py`

## Structure

```
your_feature/
├── __init__.py
├── router.py          # FastAPI endpoints
├── service.py         # Business logic
├── repository.py      # SQLite queries
├── schemas.py         # Pydantic models
├── CONTEXT.md         # Feature contract
└── tests/
    ├── __init__.py
    └── test_your_feature.py
```

## Conventions

- Features NEVER import from each other
- Cross-feature data flows through SQLite or `core/events.py`
- All endpoints require `get_current_user` dependency
- Use `AppException` for error handling
- Tests go in `tests/` subdirectory

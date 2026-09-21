# Silsila Database Migrations (Alembic)

This directory manages database schema migrations for the Silsila backend using Alembic configured with an async PostgreSQL driver (`asyncpg` via SQLAlchemy).

## Configuration
- `alembic.ini`: Root configuration.
- `alembic/env.py`: Reads database credentials and SSL context directly from `app.config.settings.DATABASE_URL`.

## Common Commands

### Check Current Migration Status
```bash
alembic current
```

### View Migration History
```bash
alembic history --verbose
```

### Apply All Pending Migrations
```bash
alembic upgrade head
```

### Revert Last Migration
```bash
alembic downgrade -1
```

### Create a New Migration
```bash
alembic revision -m "description_of_changes"
```

## Existing Revisions
- `0001_baseline_schema`: Full baseline schema (profiles, chats, people, aliases, messages, threads, chunks, jobs, ledger, suggestions, relationships, events, emotions, cache, indexes, and RLS policies).
- `0002_entity_memory`: Phase 3 entity-anchored structured memory (`entity_mentions` table, `entity_ids` column on `message_chunks`, and associated indexes & RLS).

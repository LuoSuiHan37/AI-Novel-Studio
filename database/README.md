# Database assets

- `init/` runs on first Postgres container start (pgvector extension).
- `alembic/` is the migration tree. Run from `apps/api`:

```bash
alembic upgrade head
```

Current head: `0003_domain_fields` (domain planning fields on bible/character/plans).

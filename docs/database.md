# Database

PostgreSQL. Models live in `backend/app/models/` and are the sole source of truth for
the schema — there are no migration files. On startup, `app/main.py`'s lifespan hook
calls `Base.metadata.create_all(engine)`, which creates any tables that don't exist
yet and leaves existing ones untouched.

That last part matters: `create_all()` never alters a table that's already there. If
you add, rename, or remove a column on a model, the running database won't pick that
up on its own — you need to drop and recreate the affected table (or the whole
database) against the new schema. For a single-user tool with disposable data, that's
a deliberate trade against the complexity of a migration tool, not an oversight.

## Single-user, no tenant scoping

Every table is scoped only by `dataset_id` (and further by entity id for
recipients/domains/subjects/senders). There is no `tenant_id`, no `users`/`tenants`
tables, and no authentication — every row in the database is visible to whoever can
reach the API.

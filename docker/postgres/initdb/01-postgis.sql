-- MarsGIS — PostGIS bootstrap for the `db` container.
--
-- Runs ONCE via /docker-entrypoint-initdb.d the first time the pgdata volume is
-- empty (dropping the volume re-runs it). The production backend path
-- (DATABASE_URL=postgresql+asyncpg://...) relies on these extensions for the
-- geometry(POLYGON, 104905) + GiST footprint columns and ST_Intersects viewport
-- filtering. The zero-setup SQLite dev path does not use this file.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;

-- Optional: topology support and trigram text search (harmless if unused).
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

"""initial schema (PostgreSQL + PostGIS)

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-11

Creates every table from the SQLModel metadata (single source of truth), enables
PostGIS, registers the IAU 104905 Mars 2000 geographic CRS in spatial_ref_sys,
and adds a geometry(POLYGON,104905) column + GiST index on observation for
``ST_Intersects`` viewport queries. The SQLite dev path does NOT use Alembic
(see app/db/migrate.py); this revision targets Postgres only.
"""

from __future__ import annotations

import geoalchemy2  # noqa: F401
from alembic import op
from sqlmodel import SQLModel

# Importing models registers all tables on SQLModel.metadata.
from app.db import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# IAU 2000 Mars sphere, geographic (planetocentric), east-positive. Trek advertises
# urn:ogc:def:crs:EPSG::104905; registered here so geometry inserts/queries succeed.
_MARS_SRID = 104905
_MARS_PROJ4 = "+proj=longlat +R=3396190 +no_defs"
_MARS_SRTEXT = (
    'GEOGCS["Mars 2000",DATUM["Mars_2000",'
    'SPHEROID["Mars_2000_IAU_IAG",3396190,0]],'
    'PRIMEM["Reference_Meridian",0],'
    'UNIT["degree",0.0174532925199433]]'
)


def upgrade() -> None:
    bind = op.get_bind()

    # 1. PostGIS + Mars CRS registration (idempotent).
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute(
        f"""
        INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, srtext, proj4text)
        VALUES ({_MARS_SRID}, 'IAU2000', {_MARS_SRID},
                '{_MARS_SRTEXT}', '{_MARS_PROJ4}')
        ON CONFLICT (srid) DO NOTHING
        """
    )

    # 2. All tables, exactly as the ORM declares them.
    SQLModel.metadata.create_all(bind)

    # 3. Real geometry column + GiST on observation (populated at seed time via
    #    ST_GeomFromGeoJSON(footprint_geojson)).
    op.execute(
        f"ALTER TABLE observation ADD COLUMN IF NOT EXISTS geom geometry(POLYGON, {_MARS_SRID})"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_observation_geom ON observation USING GIST (geom)")


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP INDEX IF EXISTS ix_observation_geom")
    SQLModel.metadata.drop_all(bind)

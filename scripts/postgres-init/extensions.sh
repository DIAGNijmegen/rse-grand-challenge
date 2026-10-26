#!/bin/bash
# Installed into the postgres container via /docker-entrypoint-initdb.d.
#
# Extensions are normally enabled by Django migrations. When the test database
# is built with --no-migrations (migrate --run-syncdb), those operations are
# skipped and schema that depends on them (e.g. gin_trgm_ops indexes) fails to
# create. Creating the extensions in template1 means every database created
# afterwards, including each pytest-xdist test database, inherits them.
set -euo pipefail

for database in template1 "${POSTGRES_DB}"; do
    psql \
        --variable ON_ERROR_STOP=1 \
        --username "${POSTGRES_USER}" \
        --dbname "${database}" <<-'SQL'
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        CREATE EXTENSION IF NOT EXISTS citext;
        CREATE EXTENSION IF NOT EXISTS pgcrypto;
SQL
done

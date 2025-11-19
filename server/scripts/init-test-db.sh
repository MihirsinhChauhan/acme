#!/bin/bash
# Initialize test database for running tests

set -e

echo "Creating test database..."

# Connect to PostgreSQL and create test database and user
docker compose exec -T postgres psql -U postgres <<-EOSQL
    -- Create test user if not exists
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'acme') THEN
            CREATE USER acme WITH PASSWORD 'acme';
        END IF;
    END
    \$\$;

    -- Drop test database if exists and recreate
    DROP DATABASE IF EXISTS acme_test;
    CREATE DATABASE acme_test OWNER acme;

    -- Grant all privileges
    GRANT ALL PRIVILEGES ON DATABASE acme_test TO acme;
EOSQL

echo "Test database created successfully!"
echo "Connection string: postgresql://acme:acme@localhost:5432/acme_test"


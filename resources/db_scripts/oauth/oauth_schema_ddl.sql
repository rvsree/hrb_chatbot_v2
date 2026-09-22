-- OAuth2 simulation schema (design only, not wired into the app yet).
-- Postgres. Mirrors this project's real Role enum (common/enums.py):
-- employee, manager, hr_support - not an open-ended list.

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    employee_id TEXT NOT NULL UNIQUE,   -- business key, matches UserProfile.employee_id today
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,        -- bcrypt, checked at /oauth/token, never stored plain
    role_id INTEGER NOT NULL REFERENCES roles(id),
    department TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- OAuth2 "client credentials" needs a registered caller, not just a user -
-- e.g. Postman itself, or a future web frontend, each with its own secret.
CREATE TABLE IF NOT EXISTS oauth_clients (
    id SERIAL PRIMARY KEY,
    client_id TEXT NOT NULL UNIQUE,
    client_secret_hash TEXT NOT NULL,
    client_name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employees_role_id ON employees(role_id);

-- Create migrations tracking table
CREATE TABLE IF NOT EXISTS migrations (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on filename for faster lookups
CREATE INDEX IF NOT EXISTS idx_migrations_filename ON migrations(filename);
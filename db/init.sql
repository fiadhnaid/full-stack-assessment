-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TABLES
-- ============================================

-- Tenants table (organizations)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Refresh tokens table (for token management)
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Datasets table (metadata about uploaded CSVs)
CREATE TABLE datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    columns JSONB NOT NULL,  -- [{name: "country", type: "categorical"}, ...]
    row_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dataset rows table (actual CSV data)
CREATE TABLE dataset_rows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,  -- Denormalized for RLS
    row_data JSONB NOT NULL  -- {"country": "Afghanistan", "pop": 8425333, ...}
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_datasets_tenant_id ON datasets(tenant_id);
CREATE INDEX idx_datasets_user_id ON datasets(user_id);
CREATE INDEX idx_dataset_rows_dataset_id ON dataset_rows(dataset_id);
CREATE INDEX idx_dataset_rows_tenant_id ON dataset_rows(tenant_id);

-- GIN index for JSONB queries on row_data
CREATE INDEX idx_dataset_rows_row_data ON dataset_rows USING GIN (row_data);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS on tenant-scoped tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE dataset_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY;

-- RLS Policies for users table
-- Users can only see other users in their tenant
CREATE POLICY users_tenant_isolation ON users
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- RLS Policies for datasets table
CREATE POLICY datasets_tenant_isolation ON datasets
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- RLS Policies for dataset_rows table
CREATE POLICY dataset_rows_tenant_isolation ON dataset_rows
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- RLS Policies for refresh_tokens table
-- Users can only see their own refresh tokens
CREATE POLICY refresh_tokens_user_isolation ON refresh_tokens
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true)::uuid);

-- ============================================
-- SEED DATA - Pre-seeded tenants for demo
-- ============================================

INSERT INTO tenants (id, name) VALUES
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Acme Corporation'),
    ('b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Globex Industries'),
    ('c2eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'Initech Solutions');

-- ============================================
-- LEGACY TABLE (keeping for reference, can be removed)
-- ============================================

CREATE TABLE IF NOT EXISTS gapminder_data (
    id SERIAL PRIMARY KEY,
    country VARCHAR(255),
    continent VARCHAR(255),
    year INTEGER,
    life_exp FLOAT,
    pop BIGINT,
    gdp_per_cap FLOAT
);

COPY gapminder_data(country, continent, year, life_exp, pop, gdp_per_cap)
FROM '/docker-entrypoint-initdb.d/gapminder.csv'
DELIMITER ','
CSV HEADER;

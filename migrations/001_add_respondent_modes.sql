-- ================================
-- MIGRATION: Tilføj respondent modes og KKC
-- Dato: 2025-11-14
-- Beskrivelse: Tilføjer leder-perspektiv, KKC-integration og anonym/identificeret modes
-- ================================

BEGIN TRANSACTION;

-- ============================================
-- 1. RESPONDENT TYPES
-- ============================================
CREATE TABLE IF NOT EXISTS respondent_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name_da TEXT NOT NULL,
    description_da TEXT
);

INSERT OR IGNORE INTO respondent_types (code, name_da, description_da) VALUES
('employee', 'Medarbejder', 'Medarbejdersvar om egne friktioner'),
('leader_assess', 'Leder (teamvurdering)', 'Lederens vurdering af hvad teamet oplever'),
('leader_self', 'Leder (egne friktioner)', 'Lederens egne friktioner');

-- ============================================
-- 2. CAMPAIGN MODES
-- ============================================
CREATE TABLE IF NOT EXISTS campaign_modes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name_da TEXT NOT NULL,
    description_da TEXT
);

INSERT OR IGNORE INTO campaign_modes (code, name_da, description_da) VALUES
('anonymous', 'Anonym', 'Team-måling med minimum 5 svar'),
('identified', 'Identificeret', 'Individuel måling til udvikling');

-- ============================================
-- 3. EXTEND CAMPAIGNS TABLE
-- ============================================
-- Check if columns already exist before adding them
-- SQLite doesn't have ALTER TABLE IF NOT EXISTS, so we use a different approach

-- Add mode column
ALTER TABLE campaigns ADD COLUMN mode TEXT DEFAULT 'anonymous';

-- Add leader assessment flags
ALTER TABLE campaigns ADD COLUMN include_leader_assessment INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN include_leader_self INTEGER DEFAULT 0;

-- Add minimum responses threshold
ALTER TABLE campaigns ADD COLUMN min_responses INTEGER DEFAULT 5;

-- ============================================
-- 4. EXTEND TOKENS TABLE
-- ============================================
ALTER TABLE tokens ADD COLUMN respondent_type TEXT DEFAULT 'employee';
ALTER TABLE tokens ADD COLUMN respondent_name TEXT;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_tokens_respondent_type
    ON tokens(respondent_type);

-- ============================================
-- 5. EXTEND RESPONSES TABLE
-- ============================================
ALTER TABLE responses ADD COLUMN respondent_type TEXT DEFAULT 'employee';
ALTER TABLE responses ADD COLUMN respondent_name TEXT;

-- Create index for aggregation queries
CREATE INDEX IF NOT EXISTS idx_responses_respondent_type
    ON responses(campaign_id, unit_id, respondent_type);

-- ============================================
-- 6. KKC MAPPING TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS kcc_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kcc_dimension TEXT NOT NULL,
    friction_field TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    description_da TEXT,
    is_active INTEGER DEFAULT 1
);

INSERT OR IGNORE INTO kcc_mapping (kcc_dimension, friction_field, weight, description_da) VALUES
('Direction', 'MENING', 1.0, 'Kurs måles primært gennem meningsfriktion'),
('Alignment', 'TRYGHED', 0.6, 'Koordinering kræver psykologisk tryghed'),
('Alignment', 'MULIGHED', 0.4, 'Koordinering kræver klarhed om hvem der kan hvad'),
('Commitment', 'BESVÆR', 1.0, 'Engagement bremses af besværsfriktioner');

-- ============================================
-- 7. SUBSTITUTION PATTERNS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS substitution_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    respondent_type TEXT NOT NULL,
    reported_field TEXT NOT NULL,
    likely_actual_field TEXT NOT NULL,
    confidence REAL,
    reasoning TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_substitution_patterns_campaign
    ON substitution_patterns(campaign_id, unit_id);

-- ============================================
-- 8. DATA CONSENT TABLE (for identified campaigns)
-- ============================================
CREATE TABLE IF NOT EXISTS data_consent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    respondent_name TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    consent_given INTEGER DEFAULT 1,
    consent_given_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    withdrawn INTEGER DEFAULT 0,
    withdrawn_at TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
    UNIQUE(campaign_id, respondent_name)
);

CREATE INDEX IF NOT EXISTS idx_consent_campaign
    ON data_consent(campaign_id);

-- ============================================
-- 9. MIGRATION TRACKING
-- ============================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_name TEXT UNIQUE NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_migrations (migration_name)
VALUES ('001_add_respondent_modes');

COMMIT;

-- ============================================
-- VERIFICATION QUERIES (run these after migration)
-- ============================================
-- SELECT * FROM respondent_types;
-- SELECT * FROM campaign_modes;
-- SELECT * FROM kcc_mapping;
-- PRAGMA table_info(campaigns);
-- PRAGMA table_info(tokens);
-- PRAGMA table_info(responses);

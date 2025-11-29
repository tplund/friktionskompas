-- ================================
-- MIGRATION: Opdater spørgsmål baseret på Vil-gerne-teorien
-- Dato: 2025-11-14
-- Beskrivelse: Tilføjer 10 nye spørgsmål for at dække indre/ydre lag
--              Opdaterer problematisk spørgsmål der blander KAN og TRYGHED
-- ================================

BEGIN TRANSACTION;

-- ============================================
-- 1. OPDATER PROBLEMATISK SPØRGSMÅL
-- ============================================
-- Nuværende spørgsmål 8 blander KAN og TRYGHED:
-- "Der er opgaver, hvor jeg ikke helt ved hvordan jeg skal gøre det rigtigt - men jeg tør ikke spørge"
-- Vi ændrer det til kun at handle om KAN

UPDATE questions
SET text_da = 'Der er opgaver hvor jeg ikke ved præcist hvad jeg skal gøre'
WHERE sequence = 8 AND is_default = 1;

-- ============================================
-- 2. TILFØJ NYE MENING SPØRGSMÅL
-- ============================================

-- Sequence 13: Hvorfor er det vigtigt
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default)
VALUES ('MENING', 'Jeg ved hvorfor de opgaver jeg laver er vigtige', 0, 13, 1);

-- Sequence 14: Værdier
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default)
VALUES ('MENING', 'Det arbejde jeg gør, stemmer overens med mine værdier', 0, 14, 1);

-- Sequence 15: Synlig forskel
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default)
VALUES ('MENING', 'Jeg kan se en konkret forskel af det jeg gør', 0, 15, 1);

-- ============================================
-- 3. TILFØJ NYE TRYGHED SPØRGSMÅL (INDRE LAG)
-- ============================================

-- Sequence 16: Self-compassion (indre tryghed)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default)
VALUES ('TRYGHED', 'Når jeg begår fejl, kan jeg møde mig selv med forståelse frem for selvkritik', 0, 16, 1);

-- Sequence 17: Uvished-tolerance (indre tryghed)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default)
VALUES ('TRYGHED', 'Jeg kan være i usikkerhed uden at det lammer mig', 0, 17, 1);

-- Sequence 18: Dumme spørgsmål (ydre tryghed - specifik)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default)
VALUES ('TRYGHED', 'Det er ok at stille "dumme" spørgsmål på min arbejdsplads', 0, 18, 1);

-- ============================================
-- 4. TILFØJ NYE KAN SPØRGSMÅL
-- ============================================

-- Sequence 19: Self-efficacy (indre kan - tro)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default)
VALUES ('MULIGHED', 'Jeg er tryg ved, at jeg kan løse de opgaver der kommer', 0, 19, 1);

-- Sequence 20: Tid (ydre kan - rammer)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default)
VALUES ('MULIGHED', 'Jeg har tid nok til at gøre mit arbejde ordentligt', 0, 20, 1);

-- ============================================
-- 5. TILFØJ NYE BESVÆR SPØRGSMÅL (LETHED)
-- ============================================

-- Sequence 21: Flow/lethed (oplevet)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default)
VALUES ('BESVÆR', 'Mit arbejde flyder - jeg kommer let i gang og holder momentum', 0, 21, 1);

-- Sequence 22: Byttehandel (oplevet værdi vs. indsats)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default)
VALUES ('BESVÆR', 'Den tid og energi jeg lægger i arbejdet føles som en rimelig investering', 0, 22, 1);

-- ============================================
-- 6. OPDATER MIGRATION TRACKING
-- ============================================

INSERT INTO schema_migrations (migration_name)
VALUES ('002_update_questions');

COMMIT;

-- ============================================
-- VERIFICATION
-- ============================================
-- SELECT field, text_da, reverse_scored, sequence
-- FROM questions
-- WHERE is_default = 1
-- ORDER BY field, sequence;

-- Forventet resultat: 22 spørgsmål total
-- MENING: 5 spørgsmål (1-3, 13-15)
-- TRYGHED: 6 spørgsmål (4-6, 16-18)
-- MULIGHED: 5 spørgsmål (7-9, 19-20)
-- BESVÆR: 6 spørgsmål (10-12, 21-22)

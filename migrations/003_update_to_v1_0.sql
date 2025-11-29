-- Migration 003: Opdater til Friktionskompasset V1.0
-- Erstatter alle spørgsmål med den nye V1.0 version

-- Slet eksisterende default spørgsmål
DELETE FROM questions WHERE is_default = 1;

-- MENING (6 spørgsmål)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('MENING', 'Der er opgaver i mit arbejde, som føles som spild af tid', 1, 1, 1),
('MENING', 'Jeg forstår, hvordan det jeg laver hjælper borgeren/kunden', 0, 2, 1),
('MENING', 'Min kerneopgave er tydeligt defineret i hverdagen', 0, 3, 1),
('MENING', 'Jeg ved, hvordan min opgave bidrager til noget større', 0, 4, 1),
('MENING', 'Det arbejde jeg gør, stemmer overens med mine værdier', 0, 5, 1),
('MENING', 'Jeg får vist, hvilken forskel min indsats gør for andre', 0, 6, 1);

-- TRYGHED (6 spørgsmål)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('TRYGHED', 'Der er ting på min arbejdsplads jeg gerne vil sige, men som jeg holder for mig selv', 1, 7, 1),
('TRYGHED', 'Jeg kan indrømme fejl uden at bekymre mig om konsekvenser', 0, 8, 1),
('TRYGHED', 'Når jeg rejser en bekymring, bliver der fulgt op', 0, 9, 1),
('TRYGHED', 'Når jeg begår fejl, kan jeg møde mig selv med forståelse frem for selvkritik', 0, 10, 1),
('TRYGHED', 'Jeg kan være i usikkerhed uden at det lammer mig', 0, 11, 1),
('TRYGHED', 'I mit team er det ok at stille "dumme" spørgsmål', 0, 12, 1);

-- MULIGHED (8 spørgsmål)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('MULIGHED', 'Jeg har adgang til de nødvendige værktøjer og den information, jeg har brug for', 0, 13, 1),
('MULIGHED', 'Der er opgaver hvor jeg ikke ved præcist hvad jeg skal gøre', 1, 14, 1),
('MULIGHED', 'Når jeg står fast, ved jeg hvor jeg kan få hjælp', 0, 15, 1),
('MULIGHED', 'Jeg forventer at kunne lykkes med de opgaver der kommer', 0, 16, 1),
('MULIGHED', 'Jeg har tid nok til at gøre mit arbejde ordentligt', 0, 17, 1),
('MULIGHED', 'For at få tingene til at fungere, må jeg nogle gange gøre det anderledes end procedurerne beskriver', 1, 18, 1),
('MULIGHED', 'Regler og godkendelser gør det vanskeligt at nå mit arbejde i rimeligt tempo', 1, 19, 1),
('MULIGHED', 'Jeg bliver mindet om vigtige handlinger på de rigtige tidspunkter (cues)', 0, 20, 1);

-- BESVÆR (5 spørgsmål) - vi bruger BESVÆR i stedet for LETHED i DB
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('BESVÆR', 'Jeg undgår dobbeltarbejde og unødige registreringer', 0, 21, 1),
('BESVÆR', 'Mit arbejde flyder — jeg kommer let i gang og holder momentum', 0, 22, 1),
('BESVÆR', 'Jeg bliver sjældent forsinket af ventetid på systemer eller godkendelser', 0, 23, 1),
('BESVÆR', 'Afbrydelser forstyrrer sjældent mit arbejde', 0, 24, 1),
('BESVÆR', 'Den indsats opgaven kræver nu, står mål med den effekt vi skaber for borger/kunde', 0, 25, 1);

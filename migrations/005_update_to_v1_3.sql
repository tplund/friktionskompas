-- Migration 005: Opdater til Friktionskompasset V1.3 (18 spørgsmål)
-- Kortere version uden overlap

-- Slet eksisterende default spørgsmål
DELETE FROM questions WHERE is_default = 1;

-- MENING (4 spørgsmål)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('MENING', 'Jeg bruger tid på opgaver, der ikke gør en forskel for kerneopgaven', 1, 1, 1),
('MENING', 'Jeg kan se, hvordan min indsats hjælper borger/kunde i praksis', 0, 2, 1),
('MENING', 'Jeg ved, hvilke opgaver der er vigtigst, når ikke alt kan nås', 0, 3, 1),
('MENING', 'Det arbejde jeg gør, stemmer overens med mine værdier', 0, 4, 1);

-- TRYGHED (4 spørgsmål)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('TRYGHED', 'Der er ting på min arbejdsplads, jeg gerne vil sige, men som jeg holder for mig selv', 1, 5, 1),
('TRYGHED', 'Hvis jeg rejser en bekymring, bliver der fulgt op', 0, 6, 1),
('TRYGHED', 'Jeg kan indrømme fejl uden at frygte negative konsekvenser', 0, 7, 1),
('TRYGHED', 'Jeg kan være i usikkerhed uden at gå i stå', 0, 8, 1);

-- KAN/MULIGHED (6 spørgsmål)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('MULIGHED', 'Jeg har adgang til de systemer og den information, jeg skal bruge', 0, 9, 1),
('MULIGHED', 'Der er opgaver, hvor jeg ikke ved præcist, hvad jeg skal gøre', 1, 10, 1),
('MULIGHED', 'Når jeg går i stå, ved jeg, hvor jeg kan få hjælp', 0, 11, 1),
('MULIGHED', 'Jeg har tid nok til at gøre mit arbejde ordentligt', 0, 12, 1),
('MULIGHED', 'Jeg må selv træffe de beslutninger, opgaven kræver', 0, 13, 1),
('MULIGHED', 'Jeg bliver mindet om næste skridt på relevante tidspunkter', 0, 14, 1);

-- LETHED/BESVÆR (4 spørgsmål)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('BESVÆR', 'Jeg skal ofte registrere de samme oplysninger flere steder', 1, 15, 1),
('BESVÆR', 'Det er let at komme i gang med mine opgaver', 0, 16, 1),
('BESVÆR', 'Jeg bliver sjældent forsinket af ventetid på systemer eller godkendelser', 0, 17, 1),
('BESVÆR', 'Den indsats opgaven kræver, står mål med effekten for borger/kunde', 0, 18, 1);

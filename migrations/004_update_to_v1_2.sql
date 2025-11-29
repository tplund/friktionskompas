-- Migration 004: Opdater til Friktionskompasset V1.2 (24 spørgsmål)

-- Slet eksisterende default spørgsmål
DELETE FROM questions WHERE is_default = 1;

-- MENING (5 spørgsmål)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('MENING', 'Jeg bruger tid på opgaver, der ikke gør en forskel for kerneopgaven', 1, 1, 1),
('MENING', 'Jeg kan se, hvordan min indsats hjælper borger/kunde i praksis', 0, 2, 1),
('MENING', 'Jeg ved, hvilke opgaver der er vigtigst, når ikke alt kan nås', 0, 3, 1),
('MENING', 'Det arbejde jeg gør, stemmer overens med mine værdier', 0, 4, 1),
('MENING', 'Jeg får ofte vist, hvilken forskel min indsats gør for andre', 0, 5, 1);

-- TRYGHED (6 spørgsmål)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('TRYGHED', 'Der er ting på min arbejdsplads, jeg gerne vil sige, men som jeg holder for mig selv', 1, 6, 1),
('TRYGHED', 'Hvis jeg rejser en bekymring, bliver der fulgt op', 0, 7, 1),
('TRYGHED', 'I mit team er det ok at stille "dumme" spørgsmål', 0, 8, 1),
('TRYGHED', 'Jeg kan indrømme fejl uden at frygte negative konsekvenser', 0, 9, 1),
('TRYGHED', 'Når jeg begår fejl, kan jeg møde mig selv med forståelse frem for selvkritik', 0, 10, 1),
('TRYGHED', 'Jeg kan være i usikkerhed uden at gå i stå', 0, 11, 1);

-- KAN/MULIGHED (8 spørgsmål)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('MULIGHED', 'Jeg har adgang til de systemer og den information, jeg skal bruge', 0, 12, 1),
('MULIGHED', 'Der er opgaver, hvor jeg ikke ved præcist, hvad jeg skal gøre', 1, 13, 1),
('MULIGHED', 'Jeg forventer at kunne lykkes med de opgaver, der kommer', 0, 14, 1),
('MULIGHED', 'Når jeg står fast, ved jeg, hvor jeg kan få hjælp', 0, 15, 1),
('MULIGHED', 'Jeg har tid nok til at gøre mit arbejde ordentligt', 0, 16, 1),
('MULIGHED', 'Jeg har mandat til at handle i de situationer, jeg møder', 0, 17, 1),
('MULIGHED', 'Regler og godkendelser begrænser ofte min handlemulighed', 1, 18, 1),
('MULIGHED', 'Jeg bliver mindet om næste skridt på relevante tidspunkter', 0, 19, 1);

-- LETHED/BESVÆR (5 spørgsmål)
INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES
('BESVÆR', 'Jeg kan registrere oplysninger ét sted uden dobbeltindtastning', 0, 20, 1),
('BESVÆR', 'Det er let at komme i gang med mine opgaver', 0, 21, 1),
('BESVÆR', 'Jeg bliver sjældent forsinket af ventetid på systemer eller godkendelser', 0, 22, 1),
('BESVÆR', 'Afbrydelser forstyrrer sjældent mit arbejde', 0, 23, 1),
('BESVÆR', 'Den tid og energi jeg lægger i arbejdet føles rimelig i forhold til effekten for borger/kunde', 0, 24, 1);

# Audit: Spørgsmåls-kvalitet (Friktionsprofil)

**Dato:** 2025-12-23
**Auditor:** Claude Code + bruger-feedback

## Overordnet Vurdering

### Hovedproblemer Identificeret

1. **Binær formulering** - Mange spørgsmål lægger op til ja/nej-svar, men skal besvares på 7-punkt skala
2. **Uklar formulering** - Nogle spørgsmål er grammatisk akavede eller svære at forstå
3. **Dobbelt-negationer** - Reverse-scored spørgsmål kan være forvirrende
4. **Abstrakte begreber** - Nogle spørgsmål bruger vage termer som "retning" eller "virkeligheden"

---

## Detaljeret Analyse per Spørgsmål

### TRYGHED (7 spørgsmål)

| # | Spørgsmål | Rev | Problem | Forslag |
|---|-----------|-----|---------|---------|
| 1 | "Jeg reagerer hurtigt fysisk, når noget virker uforudsigeligt" | | **Uklar** - "reagerer fysisk" er vagt. Hjertebanken? Spænding? | "Jeg mærker fysisk uro (hjertebanken, spænding) når noget uventet sker" |
| 2 | "Jeg opfanger små signaler eller stemninger meget tydeligt" | | OK - men "meget tydeligt" er binært | "I hvor høj grad opfanger du små signaler eller stemninger?" |
| 3 | "Jeg bliver urolig, hvis min oplevelse af virkeligheden bliver udfordret" | | **Abstrakt** - "oplevelse af virkeligheden" er filosofisk | "Jeg bliver urolig, hvis andre ser situationer helt anderledes end mig" |
| 4 | "Jeg falder til ro, når jeg forstår, hvad der foregår" | REV | OK | OK |
| 21 | "Jeg bliver meget ramt, hvis nogen stiller spørgsmålstegn ved mine intentioner" | | **Binær** - "meget ramt" er ja/nej | "I hvor høj grad påvirker det dig, når andre tvivler på dine intentioner?" |
| 23 | "Når jeg bliver følelsesmæssigt presset, kan jeg normalt godt holde ud, indtil jeg har talt med nogen eller tænkt det igennem" | REV | **For lang** - 23 ord, svær at parse | "Når jeg er følelsesmæssigt presset, kan jeg holde ud til jeg får talt med nogen" |
| 25 | "Jeg føler mig ofte urolig eller på vagt i hverdagen" | | OK | OK |

### MENING (7 spørgsmål)

| # | Spørgsmål | Rev | Problem | Forslag |
|---|-----------|-----|---------|---------|
| 5 | "Når noget ikke giver mening, føles det fysisk forkert" | | **Binær** - "føles fysisk forkert" er ja/nej | "I hvor høj grad mærker du fysisk ubehag når noget ikke giver mening?" |
| 6 | "Jeg mærker stærkt, hvad der er vigtigt for mig" | | OK - men "stærkt" er binært | "Jeg har en klar fornemmelse af, hvad der er vigtigt for mig" |
| 7 | "Jeg får hurtigt retning, når jeg tænker over noget" | REV | **Uklar** - "får retning" er ualmindeligt dansk | "Når jeg tænker over noget, finder jeg hurtigt ud af, hvad jeg mener" |
| 8 | "Jeg kan holde meget pres ud, hvis meningen er klar" | REV | OK | OK |
| 22 | "Jeg bliver stærkt påvirket, når nogen udfordrer min forståelse af, hvad der er rigtigt eller vigtigt" | | **For lang** - 16 ord | "Det påvirker mig stærkt, når andre udfordrer mine værdier" |
| 24 | "Når noget rammer mig hårdt, kan jeg efter noget tid tænke klart over det" | REV | OK | OK |
| 26 | "Det er tydeligt for mig, hvad der er vigtigt i mit liv" | REV | OK | OK |

### KAN (7 spørgsmål)

| # | Spørgsmål | Rev | Problem | Forslag |
|---|-----------|-----|---------|---------|
| 9 | "Jeg mærker energifald hurtigt i kroppen" | | **Binær** - "hurtigt" er ja/nej | "I hvor høj grad mærker du det i kroppen, når din energi falder?" |
| 10 | "Jeg bliver let overvældet, hvis der er mange ting på én gang" | | OK | OK |
| 11 | "Jeg regulerer mig selv bedst ved at forstå, hvad jeg skal" | REV | **Uklar** - "regulerer mig selv" er fagsprog | "Jeg fungerer bedst, når jeg forstår hvad der forventes af mig" |
| 12 | "Jeg kan tænke klart, selv når jeg er presset" | REV | OK | OK |
| 17 | "Jeg kan godt gennemføre noget, selvom jeg ikke har lyst" | REV | OK | OK |
| 18 | "Når jeg har besluttet mig for noget, får jeg det normalt gjort - også selvom det er kedeligt" | REV | **For lang** - 16 ord med indskud | "Når jeg har besluttet noget, får jeg det gjort - selv om det er kedeligt" |
| 27 | "Jeg har generelt nemt ved at få gjort det, jeg skal" | REV | OK | OK |

### BESVÆR (7 spørgsmål)

| # | Spørgsmål | Rev | Problem | Forslag |
|---|-----------|-----|---------|---------|
| 13 | "Små ting kan føles tunge, når jeg er træt" | | OK | OK |
| 14 | "Jeg undgår ting, der føles som bøvl eller kompleksitet" | | OK | OK |
| 15 | "Jeg gør ting lettere ved at forstå processen" | REV | **Uklar** - hvad betyder "gør ting lettere"? | "Når jeg forstår processen, føles opgaver lettere" |
| 16 | "Jeg mister overblik i opgaver med mange små elementer" | | OK | OK |
| 19 | "Jeg laver ofte ting færdige, selvom de føles besværlige eller meningsløse" | REV | OK - men "ofte" og "besværlige eller meningsløse" er dobbelt | "Jeg gennemfører opgaver, selvom de føles besværlige" |
| 20 | "Jeg kan bære meget bøvl, hvis det er det, der skal til, for at tingene fungerer" | REV | **Akavet** - "det er det, der skal til" er tungt | "Jeg kan håndtere meget bøvl, hvis det er nødvendigt" |
| 28 | "Hverdagen føles ofte bøvlet og tung" | | OK | OK |

### LAG (2 spørgsmål - diagnostiske)

| # | Spørgsmål | Rev | Problem | Forslag |
|---|-----------|-----|---------|---------|
| 29 | "Når jeg bliver presset, mærker jeg det mest i kroppen" | | OK - diagnostisk | OK |
| 30 | "Når jeg bliver presset, føler jeg mest, at jeg er forkert" | | OK - diagnostisk | OK |

---

## Statistik

| Kategori | Antal | Procent |
|----------|-------|---------|
| OK (ingen ændring) | 15 | 50% |
| Binær formulering | 5 | 17% |
| Uklar/akavet | 6 | 20% |
| For lang | 4 | 13% |

---

## Anbefalinger

### Prioritet 1: Kritiske ændringer (bør fixes)
1. **Spørgsmål 1** - "reagerer fysisk" er for vagt
2. **Spørgsmål 7** - "får retning" er ikke naturligt dansk
3. **Spørgsmål 11** - "regulerer mig selv" er fagsprog
4. **Spørgsmål 20** - grammatisk akavet

### Prioritet 2: Forbedringer (nice-to-have)
1. Forkorte lange spørgsmål (23, 22, 18)
2. Gøre binære formuleringer mere graduerede (5, 6, 9, 21)

### Prioritet 3: Strukturelle overvejelser
1. **Skala-instruktion** - Tilføj vejledning: "Svar på en skala fra 1-7, hvor 1 = slet ikke og 7 = i meget høj grad"
2. **Eksempler** - Overvej at tilføje eksempler til abstrakte begreber
3. **Pilot-test** - Test med 5-10 brugere før ændringer implementeres

---

## Videnskabelig Validitet

### Konstruktvaliditet
- **TRYGHED** - Spørgsmålene måler primært fysiologisk arousal og social tryghed. Dækker godt.
- **MENING** - Spørgsmålene måler værdikonflikter og meningsoplevelse. Dækker godt.
- **KAN** - Spørgsmålene måler selvregulering og kapacitet. Dækker godt.
- **BESVÆR** - Spørgsmålene måler oplevelse af friktion/modstand. Dækker godt.

### Reverse-scored Konsistens
De 14 reverse-scored spørgsmål er generelt velvalgte - de måler positive aspekter (robusthed, kapacitet) i stedet for negative. Dog kan dobbelt-negationer opstå mentalt hos respondenten.

### Face Validity
Spørgsmålene ser ud til at måle det de siger - men nogle er så abstrakte at respondenten må gætte på betydningen.

---

## Næste Skridt

- [x] Bruger godkender/justerer foreslåede ændringer (2025-12-23)
- [x] Implementer ændringer i `db_profil.py` (2025-12-23)
- [ ] Test med 5-10 brugere
- [ ] Opdater ANALYSELOGIK.md med begrundelser
- [ ] Overvej om gamle data skal re-normaliseres

## Implementerede Ændringer (2025-12-23)

15 spørgsmål opdateret:
- #1, #2, #3 (TRYGHED) - konkretiseret og naturligt dansk
- #5, #6, #7 (MENING) - fjernet binære formuleringer
- #9, #11 (KAN) - naturligt dansk, fjernet fagsprog
- #15, #18, #19, #20 (BESVÆR) - forkortet og tydeliggjort
- #21, #22, #23 (Kapacitet/Båndbredde) - forkortet og forenklet

---

*Genereret af Claude Code audit 2025-12-23*

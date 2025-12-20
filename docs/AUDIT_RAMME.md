# Standard Audit-Ramme (v2)

Denne audit er vores faste metode til tekniske audits.
Alle audits skal dokumenteres, kunne gentages og kunne sammenlignes over tid.

---

## Fast Audit-Metadata

Skal altid udfyldes:

- **Audit-id**
- **Dato**
- **System / projekt**
- **Scope** (hvad er med / ikke med)
- **Antagelser og begrænsninger**
- **Reference til tidligere audits** (hvis relevant)

---

## Hvordan Auditten Køres

### For hvert auditpunkt skal der dokumenteres:

- Hvad der er undersøgt
- Konkrete observationer og fund
- Alvor (lav / middel / høj)
- Anbefalet handling
- Om punktet kræver opfølgning

### Ved gentagne audits skal der eksplicit dokumenteres:

- Hvad er uændret
- Hvad er forbedret
- Hvad er nyt
- Hvilke fund er lukket

---

## Auditpunkter

### 1. Arkitektur og overordnede mønstre

- Overordnede arkitekturvalg
- AI- og software-antipatterns
- Over-engineering og unødvendige abstraktioner
- Single points of failure

### 2. Kodevedligeholdelse og struktur

- Modulstørrelse og ansvar
- Sammenhæng mellem domæne og filstruktur
- Kobling mellem moduler
- Læselighed og forudsigelighed for nye udviklere
- Risiko for utilsigtede sideeffekter

### 3. Ændringsrobusthed

- Hvor lokale er ændringer?
- Risiko for regressionsfejl
- Sammenhæng mellem ændringer og test
- Tid og friktion fra ændring til sikker release

### 4. Kodekvalitet

- Død kode og ubrugte features
- Fejlhåndtering
- Logging og observability
- Testdækning og testbarhed

### 5. Data og performance

- Datatilgangsmønstre (fx N+1 queries)
- Ineffektive forespørgsler
- Flaskehalse
- Ressourceforbrug og omkostningsdrivere

### 6. Sikkerhed

- Autentifikation og autorisation
- Input-validering og sanitering
- Datatilgængelighed og rettighedsstyring
- Kendte sikkerhedsrisici i afhængigheder

### 7. API og integrationer

- API-konsistens
- Kontrakter og validering
- Bagudkompatibilitet
- Afhængigheder mellem services

### 8. Afhængigheder og opdateringspolitik

- Dependency hygiene
- Outdated eller deprecated versioner
- Kendte breaking changes
- Klar politik for opdatering af dependencies
- Konsekvenser ved manglende opdatering

### 9. Konfiguration og miljøer

- Konfigurationsstyring
- Miljøadskillelse (dev / test / prod)
- Risiko for konfigurationsfejl

### 10. Drift og robusthed

- Operationale risici i daglig drift
- Fejltolerance og fallback-mekanismer
- Overvågning og alarmer
- Hvad sker der, når noget går galt?

### 11. Best practice og bevidste afvigelser

- Overholdelse af relevante best practices
- Bevidste afvigelser og deres begrundelse
- Inkonsistent praksis i kodebasen

### 12. Dokumentation

- Dokumentationshuller
- Forældet dokumentation
- Kritisk viden bundet til enkeltpersoner

---

## Tværgående Vurdering

Skal anvendes på alle fund:

- **Kognitiv belastning** - Hvor svært er det at forstå?
- **Vedligeholdelsesomkostning** - Hvor dyrt er det at vedligeholde?
- **Risiko over tid** - Bliver problemet værre?

---

## Afslutning af Audit

Auditten afsluttes altid med:

1. **Samlet risikovurdering**
2. **Prioriteret handlingsliste**
3. **Tydelig opdeling:**
   - 🔴 Gør nu
   - 🟡 Gør snart
   - 🟢 Kan vente

---

*Denne struktur er den faste reference for alle fremtidige audits.*

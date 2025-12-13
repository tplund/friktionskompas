# PLAN: ADHD-screening (Gratis/Branding)

> **Status**: Afventer - etiske overvejelser skal afklares
> **Prioritet**: Lav - branding, ikke indtægt
> **Estimat**: 12-18 timer
> **Note**: Skal være GRATIS - ikke indtægtskilde pga. etiske hensyn

## Koncept

"Er det ADHD - eller er det din arbejdssituation?"

### Hvorfor det er relevant
- Stor søgevolumen ("har jeg ADHD", "ADHD test online")
- Mange får diagnose der måske er situationsbestemt
- Kan differentiere: "Din profil matcher X - prøv disse ting FØR udredning"
- Ansvarlig vinkel: "Tal med læge, men her er forberedelse"

### Etiske principper (VIGTIGE)
- **ALDRIG** diagnosticere
- **ALTID** henvise til læge
- **FOKUS** på "forberedelse til samtale" ikke "erstatning for"
- **GRATIS** - ingen paywall på dette
- **FORMÅL** er branding og troværdighed, ikke indtægt

---

## Brugerflow

```
┌─────────────────────────────────────────────────────────────────┐
│  LANDING: "Er det ADHD - eller er det din arbejdssituation?"    │
│  ─────────────────────────────────────────────────────────────  │
│  "Mange symptomer ligner ADHD men skyldes arbejdsfriktion"      │
│  [TAG GRATIS SCREENING]                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  SCREENING: Kapacitet + Båndbredde spørgsmål (8-10 stk)         │
│  ─────────────────────────────────────────────────────────────  │
│  Fokus på: "tage sig sammen", pres opad, struktur               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  RESULTAT: Ikke-diagnosticerende indsigt                        │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ⚠️ DISCLAIMER: Dette er IKKE en diagnose                       │
│                                                                 │
│  "Din profil viser høj friktion på KAPACITET"                   │
│                                                                 │
│  Dette KAN ligne ADHD-symptomer, men kan også skyldes:          │
│  • For mange samtidige opgaver                                  │
│  • Manglende struktur i arbejdet                                │
│  • Uklare forventninger fra ledelse                             │
│                                                                 │
│  PRØV FØRST (ikke-medicinske tiltag):                           │
│  □ Lav én opgave ad gangen i 25 min (Pomodoro)                  │
│  □ Skriv dagens 3 vigtigste opgaver ned om morgenen             │
│  □ Bed om skriftlige instrukser frem for mundtlige              │
│                                                                 │
│  HVIS det ikke hjælper efter 2-4 uger:                          │
│  → Tal med din læge. Print dette som forberedelse.              │
│                                                                 │
│  [DOWNLOAD PDF TIL LÆGE]                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Teknisk Implementation

### Fase 1: Landing Page (2-3 timer)
- SEO-optimeret til "ADHD test" søgninger
- Klar disclaimer fra start
- Simpelt, tillidsfuldt design

### Fase 2: Screening Flow (1-2 timer)
- Brug kapacitet + båndbredde spørgsmål (8-10 stk)
- Ingen login krævet
- Gem anonymt eller med optional email

### Fase 3: Resultat-logik (3-4 timer)
- Mapping fra scores til profil-typer
- Forskellige anbefalinger baseret på score-mønstre
- Altid inkluder "tal med læge" anbefaling

### Fase 4: Anbefalinger (2-3 timer)
- Konkrete ikke-medicinske tiltag per profil
- Evidensbaserede forslag (Pomodoro, etc.)
- Links til ressourcer

### Fase 5: PDF Generator (2-3 timer)
- "Tag med til lægen" dokument
- Viser scores og profil
- Forklarer hvad friktionsanalyse er
- Giver lægen kontekst

### Fase 6: Disclaimer/Juridisk (1-2 timer)
- Gennemgå med juridisk øje
- Korrekt formulering
- Tydeligt "ikke diagnose"

---

## Etiske Retningslinjer

### MÅ ALDRIG sige:
- "Du har ADHD"
- "Du har ikke ADHD"
- "Du behøver ikke udredning"
- "Tag dette kosttilskud"

### SKAL ALTID sige:
- "Din profil VISER X, som KAN ligne Y"
- "Tal med din læge"
- "Dette er et samtale-værktøj, ikke en diagnose"
- "Prøv disse ikke-medicinske tiltag FØRST"

### Formål:
- Hjælpe folk forberede sig til lægesamtale
- Give sprog til at beskrive symptomer
- Differentiere situationsbestemt vs. neurologisk
- Reducere unødvendige diagnoser OG hjælpe dem der har brug

---

## Marketing (forsigtig)

### OK:
- "Forstå dine symptomer bedre"
- "Forbered dig til lægesamtalen"
- "Er det arbejdet eller er det dig?"

### IKKE OK:
- "Find ud af om du har ADHD"
- "Gratis ADHD-test"
- "Diagnose på 5 minutter"

---

## Hvorfor GRATIS

1. Etisk forpligtelse - ikke tjene på folks bekymringer om mental sundhed
2. Branding - viser at Friktionskompasset er seriøst og troværdigt
3. Lead generation - folk der bruger dette kan blive B2B kunder senere
4. SEO - stor søgevolumen kan drive trafik til resten af sitet

---

## Afhængigheder

- [ ] Kapacitets-spørgsmål færdige (har vi)
- [ ] Båndbredde-spørgsmål færdige (har vi)
- [ ] Juridisk gennemgang
- [ ] Evt. konsultation med psykolog/psykiater om formuleringer

---

## Åbne Spørgsmål

1. Skal vi have en fagperson til at gennemse anbefalingerne?
2. Skal vi linke til officielle ADHD-ressourcer (ADHD-foreningen)?
3. Skal vi tracke hvor mange der downloader PDF til læge?
4. Skal vi have feedback-loop: "Hjalp dette dig?"

---

*Oprettet: December 2024*
*Status: AFVENTER - implementeres efter Par-profil og etisk afklaring*

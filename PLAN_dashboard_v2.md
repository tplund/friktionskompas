# Plan: Kombineret Dashboard v2

## Problem
Nuværende struktur er fragmenteret:
- **Dashboard** (`/admin`) - Oversigt, men ikke meget værdi
- **Nøgletal** (`/admin/noegletal`) - KPIs, stats, seneste målinger
- **Trend** (`/admin/trend`) - Grafer over tid
- **Analyser** (`/admin/analyser`) - Drill-down analyse (den gode)

Brugeren skal navigere rundt for at få overblik.

## Løsning: Alt-i-én Dashboard
Kombinér Dashboard, Nøgletal og Trend i én side med drill-down til Analyser.

## Ny Struktur

### Sektion 1: KPI Cards (øverst)
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  Målinger   │  Responses  │  Gns. Score │   Alerts    │
│     23      │   24,216    │    3.42     │     3       │
└─────────────┴─────────────┴─────────────┴─────────────┘
```
- Total antal aktive målinger
- Total responses
- Gennemsnitlig friktionsscore
- Antal alerts/advarsler (lave scores, stort gap, etc.)

### Sektion 2: Friktionsoversigt (cards)
```
┌──────────────────────────────────────────────────────────┐
│  MENING: 3.5  │  TRYGHED: 2.8  │  KAN: 3.9  │  BESVÆR: 3.2  │
│  ██████████░░  │  ████████░░░░  │  ███████████░ │  █████████░░░ │
└──────────────────────────────────────────────────────────┘
```
- Aggregeret over alle målinger (eller valgt kunde/enhed)
- Farvekodet (grøn/gul/rød)
- Klik → åbner analyser filtreret på det felt

### Sektion 3: Trend-graf (venstre) + Seneste målinger (højre)
```
┌────────────────────────────────┬─────────────────────────┐
│                                │  Seneste målinger       │
│    [Trend Chart over tid]      │  • Birk Q4 2025    →   │
│                                │  • Aktivitet Q4    →   │
│    Enhed: [Dropdown ▼]         │  • Gødstrup Q4     →   │
│                                │  • Bofælles. Q4    →   │
└────────────────────────────────┴─────────────────────────┘
```
- Trend-graf med enhedsvalg
- Liste over seneste målinger med "Se analyse" links

### Sektion 4: Alerts/Advarsler
```
┌──────────────────────────────────────────────────────────┐
│ ⚠️ Bofællesskabet Åparken: TRYGHED kritisk lav (2.38)   │
│ ⚠️ Gødstrup Skole: BESVÆR meget lav (1.76)              │
│ ⚠️ Birk Skole: MENING under middel (2.56)               │
└──────────────────────────────────────────────────────────┘
```
- Auto-genererede advarsler baseret på thresholds
- Klik → åbner analyser for den måling

## Navigation Ændringer

### Før
```
Dashboard
Målinger ▼
  - Oversigt
  - Ny måling
  - Planlæg
Organisation ▼
  - ...
Analyser ▼
  - Analyser
  - Nøgletal
  - Trend
```

### Efter
```
Dashboard (kombineret)
Målinger ▼
  - Oversigt
  - Ny måling
  - Planlæg
Organisation ▼
  - ...
Analyser (drill-down)
```

## Implementation

### Fase 1: Kombinér på Dashboard
1. [ ] Flyt KPI cards fra nøgletal til dashboard
2. [ ] Flyt friktionsoversigt fra nøgletal til dashboard
3. [ ] Flyt trend-graf fra trend til dashboard
4. [ ] Tilføj "seneste målinger" liste
5. [ ] Tilføj alerts sektion

### Fase 2: Oprydning
6. [ ] Fjern `/admin/noegletal` route (eller redirect til dashboard)
7. [ ] Fjern `/admin/trend` route (eller redirect til dashboard)
8. [ ] Opdater navigation menu
9. [ ] Test alle links

### Fase 3: Polish
10. [ ] Responsive layout (mobile)
11. [ ] Loading states
12. [ ] Dokumentation

## Filer der skal ændres

| Fil | Ændring |
|-----|---------|
| `templates/admin/home.html` | Omskriv til kombineret dashboard |
| `templates/admin/layout.html` | Opdater navigation |
| `admin_app.py` | Udvid `/admin` route med data fra nøgletal + trend |
| `admin_app.py` | Evt. deprecate `/admin/noegletal` og `/admin/trend` |

## Risici
- Siden kan blive tung at loade (mange queries)
  - Løsning: Lazy-load trend-graf, caching
- Mobile layout kan blive crowded
  - Løsning: Collapse sektioner på mobile

## Tidsestimat
Ingen - implementeres når prioriteret.

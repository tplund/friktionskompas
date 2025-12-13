# PLAN: Par-profil ("Forstå hinanden")

> **Status**: Klar til implementation
> **Prioritet**: Høj - første B2C produkt
> **Estimat**: 12-16 timer (uden betaling), +4-6 timer med Stripe

## Koncept

"Tag testen sammen - forstå jeres forskellige friktionsprofiler"

### Hvorfor det virker
- Konkret problem folk søger løsninger på
- Lav modstand - det handler ikke om "hvem har ret" men "vi er forskellige"
- Viral potential - par deler med andre par
- Kan positioneres som "relationship hack" ikke terapi

---

## Brugerflow

```
┌─────────────────────────────────────────────────────────────────┐
│  LANDING PAGE: "Forstå jeres forskelle"                         │
│  ─────────────────────────────────────────────────────────────  │
│  "Hvorfor misforstår I hinanden? Tag testen sammen"             │
│                                                                 │
│  [START GRATIS SCREENING]                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  PERSON A: Screening (6 spørgsmål, 2 min)                       │
│  ─────────────────────────────────────────────────────────────  │
│  → Gemmes med email + session_id                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  INVITER PARTNER                                                │
│  ─────────────────────────────────────────────────────────────  │
│  "Inviter [navn] til at tage samme test"                        │
│  [Partner email] → Send invitation                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  PERSON B: Modtager email med link                              │
│  ─────────────────────────────────────────────────────────────  │
│  "Anna vil gerne forstå dig bedre - tag 2 min test"             │
│  → Tager samme 6 spørgsmål                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  GRATIS RESULTAT: Simpel sammenligning                          │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Anna          ←───────→          Bo                            │
│  ████░░░ MENING    ░░░████                                      │
│  ██████░ TRYGHED   ░░██████                                     │
│  ░░░░██ KAN        ██████░░                                     │
│  ████░░░ BESVÆR    ░░████░░                                     │
│                                                                 │
│  "I har størst forskel på KAN - dette kan skabe gnidninger"     │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Vil I vide HVORDAN I navigerer disse forskelle?         │   │
│  │ → Fuld profil + konkrete samtale-guides (99 kr)         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Gratis vs Betalt

| Gratis | Betalt (99 kr) |
|--------|----------------|
| 6 screening-spørgsmål hver | Fuld profil (30 spørgsmål) |
| Simpel visuel sammenligning | Detaljeret analyse af forskelle |
| "I er forskellige på X" | "Sådan navigerer I X" - konkrete tips |
| | "Samtale-starter" - spørgsmål I kan stille hinanden |
| | PDF I kan gemme |

---

## Teknisk Implementation

### Fase 1: Database (1 time)

```sql
CREATE TABLE couple_sessions (
    id TEXT PRIMARY KEY,
    person_a_email TEXT NOT NULL,
    person_a_name TEXT,
    person_a_completed_at TIMESTAMP,
    person_b_email TEXT,
    person_b_name TEXT,
    person_b_completed_at TIMESTAMP,
    status TEXT DEFAULT 'awaiting_a',  -- awaiting_a, awaiting_b, complete, paid
    invite_sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE couple_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    person TEXT NOT NULL,  -- 'a' eller 'b'
    question_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES couple_sessions(id) ON DELETE CASCADE
);
```

### Fase 2: Landing Page (2-3 timer)

- Ny route: `/par` eller `/sammen`
- Simpel, fokuseret side
- Ingen login krævet
- CTA: "Start gratis screening"

### Fase 3: Screening Flow (2 timer)

- Genbrug eksisterende screening-spørgsmål (6 stk)
- Gem med email + session_id
- Efter completion: Vis "Inviter partner" side

### Fase 4: Partner Invite (2-3 timer)

- Email template: "X vil gerne forstå dig bedre"
- Unik invite-link med session_id
- Partner tager samme 6 spørgsmål
- Automatisk kobling til session

### Fase 5: Sammenlignings-view (3-4 timer)

- Hent begges scores
- Visuel sammenligning (bars, radar chart)
- Highlight største forskelle
- Simpel fortolkning: "I er forskellige på X"

### Fase 6: Paywall/Teaser (1 time)

- "Få mere" sektion
- Uden Stripe først: bare email capture
- "Vi kontakter dig når fuld profil er klar"

### Fase 7: Email Templates (1-2 timer)

- Invitation til partner
- "I er begge færdige - se resultat"
- Reminder hvis partner ikke har svaret

---

## Marketing Hooks

- "Hvorfor misforstår vi hinanden?"
- "Tag 2 minutter - forstå jeres forskelle"
- "Det handler ikke om hvem der har ret"
- "Forskellige friktionsprofiler = forskellige behov"

---

## Senere Udvidelser

- [ ] Stripe betaling (99 kr for fuld profil)
- [ ] Fuld profil (30 spørgsmål) efter betaling
- [ ] Konkrete samtale-guides per felt
- [ ] PDF rapport
- [ ] "Del med venner" viral loop

---

## Afhængigheder

- Eksisterende screening-spørgsmål (har vi)
- Email-system (har vi - Mailjet)
- Landing page template (kan genbruge eksisterende styling)

---

*Oprettet: December 2024*

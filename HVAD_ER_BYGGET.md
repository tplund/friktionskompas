# 🎯 FRIKTIONSKOMPAS POC - HVAD ER BYGGET

## Overblik

Du har nu en **fuldt funktionel proof-of-concept** af Friktionskompasset, klar til at vise frem og teste.

## ✅ Hvad virker lige nu

### 1. Medarbejder-interface (besvar spørgsmål)
- **12 dristige spørgsmål** organiseret i 4 felter
- **5-punkt Likert-skala** med tydelige labels (Helt uenig → Helt enig)
- **Valgfri kommentarfelt** (maks 200 tegn, anonymt)
- **Privacy-note** der minder om at undgå identificerbare detaljer
- Pænt, moderne design med farver og ikoner

**Spørgsmålene:**

**MENING** (oplevelse af meningsløshed)
1. Der er opgaver i mit arbejde, som føles som spild af tid
2. Jeg forstår, hvordan det jeg laver hjælper borgeren/kunden
3. Hvis jeg kunne vælge, er der ting jeg ville lade være med at gøre - fordi de ikke giver værdi

**TRYGHED** (det usagte)
4. Der er ting på min arbejdsplads jeg gerne vil sige, men som jeg holder for mig selv
5. Jeg kan indrømme fejl uden at bekymre mig om konsekvenser
6. Hvis jeg rejser kritik af hvordan ting fungerer, bliver det taget seriøst

**MULIGHED** (manglende evne man ikke kan sige)
7. Jeg har de værktøjer og informationer jeg skal bruge for at gøre mit arbejde ordentligt
8. Der er opgaver, hvor jeg ikke helt ved hvordan jeg skal gøre det rigtigt - men jeg tør ikke spørge
9. Når jeg står fast, ved jeg hvor jeg kan få hjælp

**BESVÆR** (workarounds og regelomgåelse)
10. For at få tingene til at fungere, må jeg nogle gange gøre det anderledes end procedurerne beskriver
11. Hvis jeg fulgte alle regler og procedurer, ville jeg ikke nå mit arbejde
12. Jeg bruger tid på dobbeltarbejde eller unødige registreringer

### 2. Dashboard (leder-visning)
- **Vises kun når ≥5 svar** (anonymitets-beskyttelse)
- **4 felt-kort** med farvekodet scoring:
  - 🔴 Rød: Høj friktion (under 2.5)
  - 🟡 Gul: Moderat friktion (2.5-3.5)
  - 🟢 Grøn: Lav friktion (over 3.5)
- **Top-3 ord** fra kommentarer pr. felt
- **"Start her"-anbefaling** baseret på felt med lavest score
- **Konkret handlingsplan** for lederen

**Eksempel på anbefaling:**
```
💡 Start med BESVÆR
   Høj friktion (score: 2.1/5)
   
   Problem: Høj strukturel friktion - systemer, dobbeltarbejde 
            og bureaukrati står i vejen.
   
   Handling: Vælg ÉN proces/system denne måned: Hvad kan forenkles? 
            Hvad er lovkrav vs. interne krav? Fjern det overflødige.
```

### 3. Demo-tools
- **Generer realistiske danske testsvar** (5-50 personer)
- **5 forskellige profiler:**
  - Generelt tilfreds
  - Høj friktion på besvær
  - Lav tryghed
  - Manglende mening
  - Systemproblemer
- **Realistiske kommentarer** som:
  - "Dokumentationen føles som om ingen læser den"
  - "Jeg holder tilbage med at sige hvad jeg mener"
  - "Journalsystemet er alt for tungt"
  - "Vi laver dobbeltregistrering i flere systemer"

### 4. Database-struktur (klar til editor)
Spørgsmål gemmes i database med:
- `id` - Unikt ID
- `field` - MENING/TRYGHED/MULIGHED/BESVÆR
- `text_da` - Spørgsmålets tekst
- `reverse_scored` - Om scoren skal vendes (negativt formuleret)
- `sequence` - Rækkefølge
- `is_default` - Om det er standard eller kundespecifikt
- `organization_id` - Kan kobles til specifik kunde senere

**Dette betyder:** Når du vil lave spørgsmåls-editoren, er strukturen allerede på plads!

### 5. Anonymitet indbygget
- **Gemmer KUN:** team_id, periode, spørgsmål_id, score, kommentar
- **Gemmer IKKE:** navn, email, IP, tidsstempel der kan identificere
- **Minimum 5 svar** før noget vises
- **Ord-frekvens** i stedet for rå kommentarer på dashboard

## 🎨 Design & UX

- **Moderne, professionel styling**
- **Responsive** (virker på mobil/tablet/desktop)
- **Tydelig information-arkitektur**
- **Farvekodet feedback** (let at scanne)
- **Klare call-to-actions**

## 🛠️ Teknisk stack

- **Backend:** Python 3 + Flask
- **Database:** SQLite (let at skifte til Postgres)
- **Frontend:** HTML5 + Jinja2 templates + CSS3
- **Ingen JavaScript** (simplere, mere stabilt)
- **Ingen AI endnu** (kun matematik + ord-frekvens)

**Dependencies:** Kun 3 pakker
```
Flask==3.0.0
Jinja2==3.1.4
python-dotenv==1.0.1
```

## 📊 Dataflow

```
1. Medarbejder besvarer 12 spørgsmål
   ↓
2. Svar gemmes anonymt i database
   (kun score + evt. kommentar)
   ↓
3. Tæller antal unikke besvarelser
   ↓
4. Hvis ≥5 svar:
   - Beregn gennemsnit pr. felt
   - Vend negative spørgsmål
   - Udtræk top-3 ord fra kommentarer
   - Find felt med lavest score
   ↓
5. Dashboard viser:
   - 4 felt-kort med scores
   - Farvekodet status
   - Top-ord
   - "Start her"-anbefaling
```

## 🚀 Hvad kan du gøre NU

### Demo til kunde/kollega:
1. Start app (`python app.py`)
2. Klik "Demo-tools"
3. Generer 10 testsvar
4. Vis dashboard → ser professionelt ud!
5. Forklar konceptet

### Reel test:
1. Find 5-10 kolleger/venner
2. Bed dem besvare spørgsmålene ærligt
3. Se om resultaterne giver mening
4. Justér spørgsmål hvis nødvendigt

### Pitche til kommune:
"Vi har en proof-of-concept klar. Den måler friktioner - ikke følelser. 
Se selv dashboardet → det her får I aldrig ud af en klassisk APV."

## ⏳ Hvad mangler (næste faser)

### Fase 2 (3-4 timer):
- [ ] Spørgsmåls-editor (admin kan redigere/tilføje)
- [ ] Validering af spørgsmål (advarsler ved dårlige formuleringer)
- [ ] Organisationer kan gemme egne skabeloner

### Fase 3 (1 dag):
- [ ] AI-analyse som opt-in
- [ ] Mistral/Aleph Alpha/OpenAI EU integration
- [ ] Bedre tema-udtræk og actionables
- [ ] AI-maskering af identificerbare detaljer

### Fase 4 (2-3 dage):
- [ ] APV-eksport til Word
- [ ] Login/roller (admin, leder, medarbejder)
- [ ] Multi-team support
- [ ] Historik (sammenlign målinger over tid)

### Fase 5 (1 uge):
- [ ] Deploy til dansk datacenter (Hetzner/7AI)
- [ ] Postgres i stedet for SQLite
- [ ] Backup og sikkerhed
- [ ] DPA-dokumentation
- [ ] Support-flow

## 💡 Tips når du viser det frem

**Fokuspunkter:**
1. "Vi måler barrierer, ikke følelser"
2. "Se de dristige spørgsmål - dét får I aldrig i klassisk APV"
3. "Dashboard giver konkret handlingsplan, ikke bare tal"
4. "Anonymitet indbygget fra starten"

**Demo-flow:**
1. Vis medarbejder-interface → "Sådan svarer folk"
2. Generer demo-data → "Lad mig vise resultaterne"
3. Vis dashboard → "Her er hvad lederen ser"
4. Fremhæv "Start her"-anbefalingen → "Direkte til handling"

**Håndtering af spørgsmål:**
- "Kan vi tilpasse spørgsmålene?" → "Ja, det er næste fase"
- "Er det GDPR-sikkert?" → "Ja, kun aggregeret data, minimum 5 svar"
- "Hvad med AI?" → "Det er opt-in, kan peges til dansk datacenter"
- "Hvor meget koster det?" → "POC er gratis at teste, prissætning kommer"

## 📂 Filer du har fået

```
friktionskompas-poc/
├── README.md              # Overordnet dokumentation
├── HURTIG_START.md        # Installation + kom i gang
├── HVAD_ER_BYGGET.md      # Dette dokument
├── app.py                 # Main application
├── db.py                  # Database + queries
├── demo_data.py           # Testsvar-generator
├── analysis.py            # Anbefalings-logik
├── requirements.txt       # Dependencies
├── templates/
│   ├── base.html
│   ├── index.html
│   └── dashboard.html
└── static/
    └── style.css
```

## 🎉 Du er klar!

POC'en er **færdig og funktionel**. Du kan:
- ✅ Vise den til kunder
- ✅ Teste med rigtige brugere
- ✅ Pitche konceptet
- ✅ Justere spørgsmål manuelt (rediger `db.py`)
- ✅ Bygge videre når du er klar

**Start med:** `python app.py` og gå til http://127.0.0.1:5000

**God fornøjelse! 🚀**

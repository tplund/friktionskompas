# 🚀 HURTIG START - Friktionskompas POC

## Hvad er dette?

En funktionel proof-of-concept af Friktionskompasset:
- 12 dristige spørgsmål om "work as done"
- Demo-mode med realistiske danske testsvar
- Dashboard med farvekodet scoring
- Anonymitet indbygget (minimum 5 svar)
- Spørgsmål gemt i database (klar til editor)

## Installation (5 minutter)

### 1. Åbn terminal/kommandoprompt i denne mappe

### 2. Opret virtuelt miljø
```bash
python3 -m venv .venv
```

### 3. Aktivér miljøet
**Mac/Linux:**
```bash
source .venv/bin/activate
```

**Windows:**
```
.venv\Scripts\activate
```

### 4. Installer dependencies
```bash
pip install -r requirements.txt
```

### 5. Start applikationen
```bash
python app.py
```

### 6. Åbn browser
Gå til: **http://127.0.0.1:5000**

## 🎯 Hvad kan du gøre?

### Demo-flow (anbefaldet første gang):

1. **Klik "Demo-tools"** nederst på siden
2. **Klik "Generer Demo-data"** (laver 10 realistiske svar)
3. **Gå til Dashboard** → se resultater med scores, temaer og anbefalinger
4. **Prøv at ændre antal svar** (fx 5 eller 20) og se forskellen

### Rigtig test:

1. **Gå til "Besvar"**
2. **Udfyld de 12 spørgsmål** som medarbejder
3. **Gå til Dashboard** → se resultaterne (kræver 5+ svar)

## 📁 Filstruktur

```
friktionskompas-poc/
├── app.py              # Main Flask app
├── db.py               # Database (spørgsmål + svar)
├── demo_data.py        # Generer testsvar
├── analysis.py         # Anbefalinger (ingen AI)
├── templates/          # HTML
│   ├── base.html
│   ├── index.html      # Medarbejder-interface
│   └── dashboard.html  # Leder-dashboard
├── static/
│   └── style.css       # Professionel styling
└── friktionskompas.db  # SQLite database (oprettes automatisk)
```

## ✅ Hvad er bygget ind?

### Spørgsmål (i database):
- **MENING:** Spild af tid, hjælper borgeren, meningsløst arbejde
- **TRYGHED:** Holder tilbage, kan indrømme fejl, kritik tages seriøst
- **MULIGHED:** Har værktøjer, tør ikke spørge, ved hvor man får hjælp
- **BESVÆR:** Workarounds, kan ikke nå ved at følge regler, dobbeltarbejde

### Features:
✅ 5-punkt Likert-skala med tydelige labels
✅ Valgfri kommentarfelt (maks 200 tegn)
✅ Anonymitet: kun team_id + periode + score gemmes
✅ Dashboard vises først ved ≥5 svar
✅ Farvekodet (rød/gul/grøn) baseret på score
✅ Top-3 ord fra kommentarer
✅ "Start her"-anbefaling (baseret på laveste score)
✅ Demo-mode til at teste uden rigtige brugere

### Hvad mangler (næste fase):
⏳ Spørgsmåls-editor (admin kan redigere)
⏳ AI-analyse (opt-in)
⏳ APV-eksport til Word
⏳ Postgres (i stedet for SQLite)
⏳ Login/roller
⏳ Hosting (kører kun lokalt nu)

## 🛠️ Tips & tricks

### Nulstil database:
```bash
rm friktionskompas.db
python app.py
```
(Database oprettes automatisk med 12 standard-spørgsmål)

### Se spørgsmål i database:
```bash
python db.py
```

### Generer kun demo-data:
```bash
python demo_data.py
```

### Skift port (hvis 5000 er optaget):
Rediger `app.py`, sidste linje:
```python
app.run(debug=True, port=8080)  # Brug 8080 i stedet
```

## 💡 Brug som demo

Du kan vise dette til potentielle kunder:

1. **Generer demo-data** (10 svar)
2. **Vis dashboard** → professionelt, overskueligt
3. **Forklar konceptet:**
   - "Vi måler friktioner, ikke følelser"
   - "Work as done, ikke work as imagined"
   - "Fra trivselsmåling til handlingsplan"
4. **Vis de dristige spørgsmål:**
   - "For at få tingene til at fungere, må jeg gøre det anderledes..."
   - "Der er ting jeg holder for mig selv..."
   - Dette får I ALDRIG fat i med klassisk APV

## 🎨 Tilpas udseende

Rediger `static/style.css` hvis du vil ændre farver/layout.

Primær farve er sat i `:root` øverst:
```css
--primary: #2563eb;  /* Skift til din farve */
```

## ❓ Problemer?

**App starter ikke:**
- Tjek at du har aktiveret virtual environment
- Prøv `pip install --upgrade pip` først

**Port 5000 optaget:**
- Se "Skift port" ovenfor

**Database fejl:**
- Slet `friktionskompas.db` og start app igen

## 🚀 Næste skridt

Når du er klar til at bygge videre:

1. **Spørgsmåls-editor** (3-4 timer arbejde)
2. **AI-modul som opt-in** (vælg Mistral/OpenAI EU)
3. **APV-eksport** (Word-fil med handlingsplan)
4. **Deploy til dansk datacenter** (Hetzner/7AI)

---

**Bygget af Claude for Tomas**  
Version: POC 1.0 - November 2025

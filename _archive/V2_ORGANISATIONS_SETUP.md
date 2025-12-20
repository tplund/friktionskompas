# 🏢 FRIKTIONSKOMPASSET V2 - ORGANISATIONS-NIVEAU

## 🎯 Nyt i denne version

### **Fra team-værktøj til organisations-værktøj:**

**V1 (gammel):**
```
Team → Udfyld spørgeskema → Se resultater
```

**V2 (ny):**
```
ORGANISATION (Kommune)
└── AFDELINGER (Hjemmeplejen, Børnehave, Sygehus)
    └── KAMPAGNER (målinger sendt til flere afdelinger)
        └── MAGIC LINKS (ét klik, ingen login)
            └── RESULTATER (sammenlign på tværs + sygefravær)
```

---

## ✅ Nye features

### 1. **Central udsendelse fra HR** ✅
```
SMS/Email kommer fra: "HR, Kommune Odder"
IKKE fra: "Din leder"

→ Mere neutralt
→ Føles sikrere
→ Lederen kan ikke se hvem der svarede
```

### 2. **Magic Links (som Kahoot)** ✅
```
Medarbejder modtager: https://frikt.dk/abc123
→ Klikker
→ Direkte til spørgsmål
→ INGEN login
→ Link virker kun én gang
```

### 3. **Afdeling-sammenligning** ✅
```
Afdeling A: Besvær 1.8 | Sygefravær 12%
Afdeling B: Besvær 3.4 | Sygefravær 6%

→ Se sammenhænge
→ Benchmark internt
→ Lær af dem der scorer bedst
```

### 4. **Mailjet integration** ✅
```
Send til 50+ personer med ét klik
→ Email til dem med email
→ SMS til dem uden email (SOSU'er)
→ Automatisk reminders
```

---

## 🛠️ Installation

### **1. Dependencies:**
```bash
pip install flask mailjet-rest python-dotenv --break-system-packages
```

### **2. Mailjet credentials:**
```bash
# Opret .env fil
cat > .env << EOF
MAILJET_API_KEY=din-api-key
MAILJET_API_SECRET=din-api-secret
FROM_EMAIL=info@kommune-odder.dk
FROM_NAME=HR, Kommune Odder
EOF
```

### **3. Initialize database:**
```bash
python db_v2.py
```

### **4. Start admin interface:**
```bash
python admin_app.py
```

→ Åben http://localhost:5001/admin

---

## 📋 Workflow: Fra setup til resultater

### **STEP 1: Opret organisation**
```
Admin interface → "Ny organisation"

Navn: Kommune Odder
Email: hr@kommune-odder.dk

→ Tildeles org-ID
```

### **STEP 2: Opret afdelinger**
```
Organisation → "Ny afdeling"

Navn: Hjemmeplejen Nord
Leder: Mette Hansen
Email: mette@kommune-odder.dk
Antal medarbejdere: 45

→ Tildeles dept-ID
```

### **STEP 3: Upload kontakter**
```
Afdeling → "Upload kontakter"

CSV format:
email,phone
anna@example.dk,+4512345678
,+4587654321
bent@example.dk,

→ Email ELLER phone (eller begge)
```

### **STEP 4: Upload sygefravær** (valgfrit)
```
Afdeling → "Opdater sygefravær"

12.3%

→ Bruges til sammenligning senere
```

### **STEP 5: Opret kampagne**
```
Organisation → "Ny kampagne"

Navn: November 2025
Periode: 2025Q4
Send fra: HR (anbefalet) eller Leder
Afdelinger: [Vælg hvilke afdelinger]

→ Klik "Send"
```

### **STEP 6: Automatisk udsendelse**
```
System:
1. Genererer unikke tokens (magic links)
2. Sender email til alle med email
3. Sender SMS til alle med telefon
4. Tracker hvem der har svaret (anonymt)
```

### **STEP 7: Medarbejder svarer**
```
Modtager SMS/Email
→ Klikker link
→ Svarer på spørgsmål (5 min)
→ Link bruges
```

### **STEP 8: Se resultater**
```
Admin dashboard → "Organisation overview"

Se:
- Hvilke afdelinger scorer lavt
- Sammenligning med sygefravær
- Response rates
- Detaljerede svar per afdeling
```

---

## 📊 Admin dashboards

### **Organisation Overview:**
```
┌─────────────────────────────────────────────┐
│ KOMMUNE ODDER - NOVEMBER 2025               │
│                                             │
│ Afdeling          Besvær  Sygefr. Response  │
│                                             │
│ Hjemmeplejen N    1.8 🔴  12.3%    71%     │
│ Børnehave Ø       3.2 🟡   6.1%    85%     │
│ Sygehus Akut      2.1 🟡   9.8%    64%     │
│ Tek. Forvaltning  3.5 🟢   4.2%    92%     │
│                                             │
│ [Klik for at se detaljer per afdeling]     │
└─────────────────────────────────────────────┘
```

### **Afdeling Detail:**
```
┌─────────────────────────────────────────────┐
│ HJEMMEPLEJEN NORD                           │
│ 32 ud af 45 har svaret (71%)               │
│                                             │
│ Mening:   2.9 🟡                            │
│ Tryghed:  3.1 🟡                            │
│ Kan:      2.8 🟡                            │
│ Besvær:   1.8 🔴 KRITISK                    │
│                                             │
│ Sammenligning:                              │
│ Jeres:              1.8                     │
│ Gennemsnit i kom:   2.8                     │
│ Bedste afdeling:    3.5                     │
│                                             │
│ [Se detaljerede svar og citater]           │
└─────────────────────────────────────────────┘
```

---

## 📧 Email/SMS templates

### **Invitation (fra HR):**
```
Emne: Hjælp os fjerne friktioner (5 min, anonymt)

Hej!

HR, Kommune Odder vil gerne høre om de små ting 
der står i vejen i hverdagen - friktioner som 
dobbeltarbejde eller procedurer der tager for 
lang tid.

Det tager 5 minutter og er fuldstændig anonymt.

[LINK - kun til dig]

🔒 Anonymitet:
• Ingen kan se hvem der skrev hvad
• Resultater kun når 5+ har svaret
• Dit link virker kun én gang

Mvh
HR, Kommune Odder
```

### **SMS (kort version):**
```
Hej! HR vil gerne høre om friktioner i arbejdet.

5 min, anonymt: https://frikt.dk/abc123

Dit link virker kun én gang.

Mvh HR
```

### **Reminder:**
```
Emne: Reminder: Friktionsmåling (32 har svaret)

Hej igen!

Vi mangler stadig dit svar til friktionsmålingen.

Status: 32 personer har svaret. Vi skal have 
mindst 5 for at kunne vise resultater.

[LINK]

Mvh
HR, Kommune Odder
```

---

## 🔐 Anonymitet - hvordan det virker

### **Problem:**
"Hvis I sender personlige links, kan I vel spore hvem der svarede hvad?"

### **Løsning:**
```python
1. Generer 45 tokens: abc123, def456, ...

2. Gem i database:
   Token: abc123
   Afdeling: Hjemmeplejen Nord
   Brugt: Nej
   
   (Vi gemmer IKKE hvem der fik tokenet)

3. Når nogen svarer:
   - Token markeres "brugt"
   - Svar gemmes MED afdeling
   - Svar gemmes UDEN token-reference
   - Forbindelsen kappes

4. Resultat:
   Vi ved: "32 ud af 45 i Hjemmeplejen har svaret"
   Vi ved IKKE: "Anna svarede X og Bent svarede Y"
```

**Stadig anonymt!** ✅

---

## 💰 Omkostninger

### **Mailjet:**
- Free tier: 6.000 emails/måned gratis
- SMS: Kræver separat opsætning (eller brug CPSMS)

### **CPSMS (dansk SMS-gateway):**
- ~0.10 kr per SMS
- 50 personer = ~5 kr per kampagne

### **Hosting:**
- Kan køre på billig VPS (~50 kr/måned)
- Eller Heroku/Railway free tier

**Total: Meget billigt!** 💸

---

## 🚀 Næste skridt

### **1. Test med ÉN kommune**
```
Find 1 kommune med 3-5 afdelinger
→ Setup org + departments
→ Upload kontakter
→ Send første kampagne
→ Samle feedback
```

### **2. Juster baseret på feedback**
```
- Virker emails godt?
- Er SMS nødvendigt?
- Forstår folk spørgsmålene?
- Føles det anonymt nok?
```

### **3. Skalér**
```
- Flere kommuner
- API til HR-systemer (automatisk sygefravær)
- Bedre analytics
- AI til mønstergenkendelse
```

---

## ⚠️ Vigtige noter

### **SMS:**
SMS-funktionalitet er implementeret men kræver:
- CPSMS konto (eller lignende)
- API-integration
- Kort URL (frikt.dk i stedet for friktionskompas.dk)

### **Anonymitet:**
Med afdelinger på 45+ personer er anonymiteten god.
Med teams på 5-10 personer skal man være mere forsigtig.

### **GDPR:**
- Kontakter gemmes kun til kampagne-formål
- Kan slettes på anmodning
- Svar er anonyme
- Ingen tracking af individer

---

## 📞 Support

**Spørgsmål om:**
- Setup: Se denne guide
- Mailjet: https://dev.mailjet.com/
- SMS: Kontakt CPSMS eller SMS1919

**Problemer:**
Check logs og kontakt support.

---

## ✅ Checklist før launch

- [ ] Mailjet credentials sat op
- [ ] Test email sendt og modtaget
- [ ] Organisation oprettet
- [ ] Afdelinger oprettet
- [ ] Kontakter uploaded
- [ ] Sygefravær-data indsat (valgfrit)
- [ ] Test-kampagne sendt til lille gruppe
- [ ] Resultater ser korrekte ud
- [ ] Anonymitet verificeret

**Nu er du klar til at køre første rigtige kampagne!** 🎉

---

*Version 2.0 - Organisations-niveau med magic links · 6. november 2025*

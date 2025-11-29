# 🎯 KKC-INTEGRATION I FRIKTIONSKOMPASSET

## Hvad er KKC?

**KKC = Kurs, Koordinering og Commitment**

Et dansk ledelsesværktøj udviklet af **Anders Trillingsgaard**, der fokuserer på tre fundamentale elementer i godt lederskab:

### **KURS** = Retning og mening
- Hvorfor gør vi det her?
- Hvad er målet?
- Hvordan bidrager det til helheden?

### **KOORDINERING** = Samarbejde og klarhed
- Hvem gør hvad?
- Hvordan hænger det sammen?
- Hvad har vi brug for af hinanden?

### **COMMITMENT** = Engagement og ansvar
- Er vi enige om det her?
- Tager vi ansvar?
- Kan vi levere det vi siger ja til?

---

## 🔗 Hvordan Friktionskompasset bruger KKC

Friktionskompasset måler **friktioner** i fire felter. Hver type friktion mapper direkte til et KKC-element:

### Mapping:

| Friktionsfelt | KKC-element | Hvad det betyder |
|---------------|-------------|------------------|
| **MENING** | KURS | Manglende retning og formål |
| **TRYGHED** | KOORDINERING | Dårligt samarbejde, usikkerhed |
| **MULIGHED** | KOORDINERING | Manglende ressourcer/klarhed |
| **BESVÆR** | COMMITMENT | System matcher ikke virkeligheden |

---

## 📋 Strukturerede anbefalinger

Når dashboardet viser "Start her", følger anbefalingen KKC-strukturen:

### Eksempel - Lav Mening → KURS-problem:

```
💡 Start med KURS
KKC-element: KURS

🔴 Høj friktion (score: 2.1/5)

🎯 Problem:
Teamet mangler en klar retning - de ved ikke hvorfor 
opgaverne giver værdi eller hvordan de bidrager til helheden.

✅ Næste skridt:
1. 🛑 STOP-øvelse (10 min): "Hvilken opgave giver MINDST 
   mening for dig? Hvad tror du formålet er?"

2. 🎯 Formuler kursen sammen: "Hvordan hjælper dette teams 
   arbejde borgeren/kunden konkret?" Skriv det i ÉN sætning. 
   Hæng den op.

3. 🔗 Kobl opgaver til kursen: For hver tilbagevendende 
   opgave - "Hvordan understøtter dette vores kurs?" 
   Hvis ikke → drop eller redesign.

📅 Opfølgning:
Gentag måling om 6-8 uger. Er Mening-scoren steget? 
Kan alle svare på "Hvorfor gør vi det her?"

💡 Anders Trillingsgaard: Kurs handler om retning og mening 
- "Hvorfor gør vi det?"
```

---

## 🎯 Alle fire anbefalings-typer

### 1. MENING → KURS
**Problem:** Uklar retning  
**Handling:** Formuler fælles kurs, kobl opgaver til formål  
**Opfølgning:** Kan alle svare "Hvorfor gør vi det?"

### 2. TRYGHED → KOORDINERING
**Problem:** Dårlig psykologisk sikkerhed  
**Handling:** "Hvem-kan-hvad"-tavle, check-in, normaliser fejl  
**Opfølgning:** Folk spørger højt i stedet for at gætte

### 3. MULIGHED → KOORDINERING
**Problem:** Manglende ressourcer/information  
**Handling:** Kortlæg mangler, fordel viden, gør info tilgængelig  
**Opfølgning:** Folk ved hvor de finder det

### 4. BESVÆR → COMMITMENT
**Problem:** Systemet passer ikke til virkeligheden  
**Handling:** Identificér workarounds, forenkl én procedure ad gangen  
**Opfølgning:** Folk stopper med at omgå regler

---

## 💡 Hvorfor KKC er smart her

### 1. **Troværdighed**
KKC er et anerkendt dansk ledelsesværktøj. Mange kommuner kender det allerede.

### 2. **Genkendelse**
"Vi bruger KKC" er nemmere at forklare end "Vi har lavet vores egen metode"

### 3. **Struktur**
Lederen får en klar ramme at arbejde i - ikke bare "snakke om det"

### 4. **Handling**
Hver anbefaling har konkrete trin, ikke generiske råd

### 5. **Opfølgning**
Indbygget i metoden at man tjekker om det virker

---

## 🗣️ Sådan pitcher du det

### Til kunder:
"Friktionskompasset identificerer hvor problemet ligger - og bruger **Anders Trillingsgaards KKC-model** til at give jer konkrete handlinger.

Er problemet manglende **KURS**? Vi viser hvordan I genformulerer retningen.

Er det dårlig **KOORDINERING**? Vi giver jer redskaber til bedre samarbejde.

Er det et **COMMITMENT**-problem? Vi hjælper jer med at forenkle systemet så det matcher virkeligheden."

### Til ledere:
"De fleste trivselsmålinger giver jer grafer - vi giver jer en handlingsplan struktureret efter KKC. 

Dashboardet fortæller ikke bare 'tryghed er lav' - det fortæller 'Start med koordinering: Lav en hjælp-tavle, indføj check-in, normaliser fejl'."

---

## 📚 Referencer til Anders Trillingsgaard

Anders Trillingsgaard har skrevet om KKC i flere sammenhænge:
- Bog: "Relationer på arbejdspladsen" (2020)
- Artikler om ledelse i offentlig sektor
- Kurser og foredrag om KKC-modellen

KKC bruges bredt i danske kommuner og regioner som ledelsesværktøj.

---

## 🛠️ Teknisk implementation

I `analysis.py` er hver anbefaling struktureret med:

```python
{
    'kcc_element': 'KURS',          # Hvilket KKC-element
    'title': 'Start med KURS',      # Overskrift
    'problem': '...',               # Hvad er problemet
    'actions': [                    # Liste af konkrete trin
        'Trin 1...',
        'Trin 2...',
        'Trin 3...'
    ],
    'follow_up': '...',            # Hvordan tjekker vi om det virker
    'kcc_reference': '...'         # Reference til Trillingsgaard
}
```

Dashboard-templaten (`templates/dashboard.html`) viser dette pænt med:
- KKC-badge øverst
- Nummereret action-liste
- Opfølgnings-sektion
- Reference til kilden nederst

---

## ✅ Fordele ved at bruge KKC

1. **Legitimitet:** Ikke "endnu en konsulentmodel", men anerkendt dansk værktøj
2. **Klarhed:** Tre klare kategorier - let at huske og bruge
3. **Handling:** Hver kategori har konkret betydning for hvad lederen skal gøre
4. **Bred anvendelse:** Virker på tværs af brancher og teams
5. **Kommuner kender det:** Mange har allerede hørt om KKC

---

## 🎯 Næste skridt

Hvis du vil uddybe KKC-integreringen yderligere:

1. **Link til Trillingsgaard-materiale** på dashboardet
2. **Video-forklaring** af hvordan friktioner mapper til KKC
3. **Case-eksempler** fra kommuner der bruger begge dele
4. **KKC-workshop-pakke** som add-on til værktøjet

---

**Bygget med respekt for Anders Trillingsgaards arbejde**  
Friktionskompasset POC · November 2025

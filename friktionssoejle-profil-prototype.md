# PROTOTYPE: Spørgeskema til friktionssøjle-profilen

**(Minimumsudgaven: 16 spørgsmål – 4 pr. felt)**

Hvert spørgsmål besvares på en skala 1–5:
- 1 = aldrig
- 3 = nogle gange
- 5 = meget ofte / meget stærkt

---

## TRYGHED – 4 spørgsmål

### Biologi / Emotion

1. Jeg reagerer hurtigt fysisk, når noget virker uforudsigeligt.
2. Jeg opfanger små signaler eller stemninger meget tydeligt.

### Indre / Kognition

3. Jeg bliver urolig, hvis min oplevelse af virkeligheden bliver udfordret.
4. Jeg falder til ro, når jeg forstår, hvad der foregår.

---

## MENING – 4 spørgsmål

### Biologi / Emotion

1. Når noget ikke giver mening, føles det fysisk forkert.
2. Jeg mærker stærkt, hvad der er vigtigt for mig.

### Indre / Kognition

3. Jeg får hurtigt retning, når jeg tænker over noget.
4. Jeg kan holde meget pres ud, hvis meningen er klar.

---

## KAN – 4 spørgsmål

### Biologi / Emotion

1. Jeg mærker energifald hurtigt i kroppen.
2. Jeg bliver let overvældet, hvis der er mange ting på én gang.

### Indre / Kognition

3. Jeg regulerer mig selv bedst ved at forstå, hvad jeg skal.
4. Jeg kan tænke klart, selv når jeg er presset *(omvendt score)*.

---

## BESVÆR – 4 spørgsmål

### Biologi / Emotion

1. Små ting kan føles tunge, når jeg er træt.
2. Jeg undgår ting, der føles som bøvl eller kompleksitet.

### Kognition / Ekstern

3. Jeg gør ting lettere ved at forstå processen.
4. Jeg mister overblik i opgaver med mange små elementer.

---

## Udvidelsesmulighed: Båndbredde mellem lag

*(Til professionel version – valgfrit, men ekstremt nyttigt i diagnostik)*

1. Pres går hurtigt i kroppen før jeg når at tænke *(Bio → Emo)*.
2. Jeg får hurtigt mening/retning, også når jeg er presset *(Indre → Kogn)*.
3. Jeg kan kun tænke klart, når kroppen er rolig *(omvendt score)*.
4. Jeg reagerer, før jeg forstår *(Bio/Emo → Kogn båndbredde lav)*.

---

## 8-spørgsmåls kompas til BIO og EMOTION (Baseline)

*Måler tærskler, båndbredde og baseline-pres – IKKE psyke.*

Disse spørgsmål giver et hurtigt og præcist billede af personens biologiske og emotionelle grundkapacitet.

### BIOLOGI – 4 spørgsmål

1. Jeg kan være i koldt vand eller andet fysisk ubehag længe, før jeg må give slip.
2. Min krop larmer meget, når jeg bliver presset. *(omvendt score)*
3. Jeg reagerer langsomt på chok eller overraskelser.
4. Mit energiniveau føles stabilt i hverdagen.

### EMOTION – 4 spørgsmål

1. Jeg bliver let overvældet af følelsesmæssigt pres. *(omvendt score)*
2. Jeg mister let jordforbindelsen, hvis noget bliver relationelt svært. *(omvendt score)*
3. Jeg har svært ved at mærke, hvad jeg føler, før det bliver meget tydeligt. *(omvendt score)*
4. Hvis nogen er skuffede over mig, rammer det mig meget. *(omvendt score)*

### Fortolkning

| Score | BIO betydning | EMOTION betydning |
|-------|--------------|-------------------|
| 1.0-2.2 | Høj fysisk tolerance | Høj emotionel stabilitet |
| 2.3-3.7 | Normal variation | Normal følsomhed |
| 3.8-5.0 | Sensitiv krop | Emotionel sårbarhed |

*Høj score (efter omvendt scoring) = høj kapacitet/robusthed*

---

# ALGORITME / SPECIFIKATION

**Hvordan spørgeskemaet oversættes til farvegrid**

*(Beskrivende, så udvikler/vibecoder kan lave det)*

## Step 1 – Score hvert spørgsmål 1–5

Gem alle svar som integers.

## Step 2 – Beregn felt-scores (Tryghed, Mening, Kan, Besvær)

For hvert felt:
- Tag gennemsnittet af de fire spørgsmål (evt. vægtning mulig senere).
- Resultatet = feltets homeostatiske pres-score.

## Step 3 – Mapp scores til farver (for hvert lag i søjlen)

Vi har tre farver:

| Farve | Betydning |
|-------|-----------|
| 🟩 Grøn | Robust / lav presfølsomhed |
| 🟨 Gul | Sensitiv / svingende |
| 🟧 Orange | Lav tærskel / sårbart |

### Mapping

| Score-interval | Farve |
|----------------|-------|
| 1.0 – 2.2 | 🟩 |
| 2.3 – 3.7 | 🟨 |
| 3.8 – 5.0 | 🟧 |

*(Dette er en prototype – kan justeres senere.)*

### Lagfordeling

Hvert spørgsmål knytter sig til et bestemt lag. Udvikleren skal mappe:

- Q1 → Bio
- Q2 → Emo
- Q3 → Indre
- Q4 → Kogn (eller Ekstern afhængigt af felt)

Derfor genererer vi farver per lag per felt.

## Step 4 – Saml farverne i en matrix 5×4

- **Rækker** = lag
- **Kolonner** = felt

Dette er din **friktionssøjleprofil**.

## Step 5 – Beregn båndbredde (valgfrit)

En simpel første version:

```
Båndbredde_score = (Kogn-score – Bio-score) + justering
```

Eller vurdering ud fra "hurtig reaktion før tænkning"-spørgsmålene.

- **Høj båndbredde** = pres kan rejse højt opad.
- **Lav båndbredde** = søjlen knækker i midten.

## Step 6 – Find manifestationslag (valgfrit)

Tag den første orange i en søjle, når presset øges.
Det er **manifestationslaget** for det felt.

## Step 7 – Output som JSON eller display

Udvikler vælger selv.

---

# Skabelon for friktionsprofil-rapporten

*(Klar til design / UI)*

---

# DIN FRIKTIONSPROFIL

*En mekanisk beskrivelse af hvordan pres bevæger sig gennem dig.*

---

## 1. Overblik

Dette er din friktionsprofil: fire friktionssøjler (Tryghed, Mening, Kan, Besvær) målt gennem fem lag (Biologi → Emotion → Indre → Kognition → Ekstern). Profilen viser, hvordan pres rejser i dit system, hvor det lander, og hvor det stopper.

---

## 2. Farvegrid

*(Indsæt 5 × 4 grid med farver)*

| | Tryghed | Mening | Kan | Besvær |
|---------|---------|--------|-----|--------|
| Ekstern | | | | |
| Kognition | | | | |
| Indre | | | | |
| Emotion | | | | |
| Biologi | | | | |

**Farveforklaring:**
- 🟩 = robust
- 🟨 = sensitiv
- 🟧 = lav tærskel

---

## 3. Søjletolkning

### TRYGHED

- **Biologi:** …
- **Emotion:** …
- **Indre:** …
- **Kognition:** …

→ **Samlet fortolkning:** Tryghedspres rejser … og stopper ofte i …

### MENING

- **Biologi:** …
- **Emotion:** …
- **Indre:** …
- **Kognition:** …

→ **Samlet fortolkning:** Mening rejser … og giver …

### KAN

- **Biologi:** …
- **Emotion:** …
- **Indre:** …
- **Kognition:** …

→ **Samlet fortolkning:** …

### BESVÆR

- **Biologi:** …
- **Emotion:** …
- **Indre:** …
- **Kognition:** …

→ **Samlet fortolkning:** …

---

## 4. Båndbredde

En vurdering af, hvor højt pres kan rejse opad, før systemet knækker.

- **Høj båndbredde:** du kan regulere pres op i kognition.
- **Lav båndbredde:** pres stopper i mellem- eller underlagene.

---

## 5. Manifestationslag

Det lag, hvor du oftest stopper med at spørge opad.

| Felt | Manifestationslag |
|------|-------------------|
| Tryghed | … |
| Mening | … |
| Kan | … |
| Besvær | … |

---

## 6. Samlet profil

Her står den menneskelige fortolkning:

- Dine styrker i søjlerne
- Dine sårbare punkter
- Hvor pres træder ind
- Hvor pres stopper
- Hvad der skaber flow hos dig
- Hvad der skaber nedfald

---

## 7. Anbefalinger (valgfri)

- Hvordan du løfter båndbredde
- Hvordan du stabiliserer biologi
- Hvordan du tager hensyn til dine orange lag
- Hvordan du designer hverdage efter din profil

# PLAN: Freemium B2C Model

> **Status**: Afventer business analyse og teori-stabilisering
> **Prioritet**: Lav (fremtidig)

## Oversigt

Mulighed for at tilbyde Friktionskompasset som selvbetjening til individuelle brugere (B2C) med freemium-model.

---

## Business Analyse (TODO)

### Spørgsmål der skal afklares:

1. **Prissætning**
   - Hvad koster en fuld friktionsprofil?
   - Abonnement vs. engangskøb?
   - Virksomhedslicenser vs. individuelle?

2. **Freemium-struktur**
   - Hvad er gratis? (screening? delvis profil?)
   - Hvad kræver betaling? (fuld profil? PDF-rapport? coaching-tips?)
   - Trial-periode? (7 dage? 14 dage?)

3. **Målgruppe**
   - Privatpersoner der vil forstå deres arbejdssituation?
   - Freelancere/selvstændige?
   - HR-folk der vil teste før virksomhedskøb?

4. **Konkurrenter**
   - Hvad koster lignende tests? (DISC, Myers-Briggs, etc.)
   - Hvad differentierer os?

---

## Tekniske Krav

### Betalingsintegration
- [ ] **Stripe** - mest udbredt, god dansk support
- [ ] Alternativ: MobilePay (kun DK)
- [ ] Webhook til aktivering efter betaling
- [ ] Refund-håndtering

### Udvidede OAuth Providers (for B2C convenience)
- [x] Google OAuth ✅ (implementeret)
- [x] Microsoft OAuth ✅ (implementeret)
- [ ] **Apple Sign-In** - kræves for iOS apps
- [ ] **Facebook Login** - stor brugerbase
- [ ] LinkedIn (relevant for arbejdsmarked-fokus?)

### Feature Gating
- [ ] Assessment type restrictions per brugertype
- [ ] "Upgrade to unlock" UI
- [ ] Trial countdown/expiration

### Marketing/Tracking
- [ ] Facebook Pixel
- [ ] Google Analytics 4 / Google Ads conversion tracking
- [ ] LinkedIn Insight Tag
- [ ] A/B testing framework for landing pages

---

## SoMe Ads Strategi (idé)

### Automatiseret annoncering med guardrails:

```
┌─────────────────────────────────────────────────┐
│  SoMe Ads Manager (fremtidig)                   │
├─────────────────────────────────────────────────┤
│  Budget: max X kr/dag                           │
│  Platforms: Facebook, Instagram, LinkedIn       │
│  Targeting: 25-55 år, erhvervsaktive, DK        │
│                                                 │
│  Guardrails:                                    │
│  - Stop hvis CPA > X kr                         │
│  - Stop hvis CTR < X%                           │
│  - Pause ved budget-grænse                      │
│                                                 │
│  Auto-optimering:                               │
│  - Test 3-5 ad varianter                        │
│  - Skaler vindere, stop tabere                  │
│  - Rapport hver uge                             │
└─────────────────────────────────────────────────┘
```

### Mulige ad hooks:
- "Er du fanget i meningsløst arbejde? Tag testen"
- "Føler du dig blokeret på arbejdet?"
- "Gratis screening: Find din arbejdsfriktion"

---

## Implementation Roadmap (når business er afklaret)

### Fase 1: Simpel betaling
1. Stripe integration
2. "Køb fuld profil" knap efter gratis screening
3. Email med resultat efter betaling

### Fase 2: Freemium flow
1. Gratis screening (6 spørgsmål)
2. Teaser-resultat ("Du scorer lavt på MENING...")
3. Paywall før fuld profil

### Fase 3: Marketing automation
1. Tracking pixels
2. Retargeting af besøgende
3. Email sequences til leads

### Fase 4: Ads optimization
1. A/B test landing pages
2. Automatisk budget-allokering
3. ROI dashboard

---

## Afhængigheder

- [ ] **Teori-stabilisering** - spørgsmål skal være validerede
- [ ] **Business model canvas** - hvem betaler for hvad?
- [ ] **Juridisk** - GDPR, betalingsbetingelser, refund policy
- [ ] **CVR/virksomhed** - til Stripe og fakturering

---

## Noter

- Nuværende B2C flow fungerer allerede (selvregistrering, passwordless login)
- Assessment types kan allerede konfigureres per kunde/domæne
- Mangler primært: betaling + flere OAuth providers

---

*Sidst opdateret: December 2024*

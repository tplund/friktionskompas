"""
Analyse og anbefalinger baseret på reelle svar
Fokus: Konkrete problemer og citater frem for abstrakte begreber
"""
from typing import List, Dict, Any
from collections import Counter


def get_top_comments(responses: List[Dict], field: str, limit: int = 5) -> List[str]:
    """Hent de mest relevante kommentarer for et felt"""
    comments = [r['comment'] for r in responses 
                if r['field'] == field and r['comment'] and r['comment'].strip()]
    
    # Returner op til 'limit' kommentarer
    return comments[:limit] if comments else []


def get_concrete_problem(field: str, avg_score: float, comments: List[str]) -> str:
    """
    Generer SKARP problem-beskrivelse baseret på felt og kommentarer
    Ikke pæn omskrivning - brug de faktiske ord folk bruger
    """
    
    # Hvis vi har kommentarer, brug dem til at forme beskrivelsen
    has_comments = len(comments) > 0
    
    if field == 'MENING':
        if has_comments:
            # Tilpas baseret på hvad folk skriver
            if any('dokumentation' in c.lower() or 'registrer' in c.lower() for c in comments):
                return "Folk bruger tid på dokumentation og registreringer som føles som spild af tid. De kan ikke se hvordan det hjælper borgeren - det føles som afkrydsningsøvelser der kun eksisterer 'fordi vi skal'."
            elif any('møde' in c.lower() for c in comments):
                return "Der bruges tid på møder hvor formålet er uklart. Folk sidder der og tænker 'hvorfor er vi her?' og 'dette kunne have været en mail'."
            elif any('rapport' in c.lower() or 'system' in c.lower() for c in comments):
                return "Folk laver rapporter og indtaster i systemer uden at vide hvem der læser det eller hvad det bruges til. Det føles meningsløst."
            else:
                return "Folk laver opgaver de oplever som meningsløse. De kan ikke se sammenhængen mellem arbejdet og borgeren - det føles som om de 'bare skal gøre det'."
        else:
            return "Medarbejdere scorer lavt på oplevelse af mening. Der er opgaver hvor de ikke kan se formålet eller hvordan det gavner borgeren."
    
    elif field == 'TRYGHED':
        if has_comments:
            if any('holder tilbage' in c.lower() or 'tier' in c.lower() for c in comments):
                return "Folk holder mund om ting de burde sige højt. Der er bekymringer, kritik og problemer som ikke bliver luftet - fordi det ikke føles trygt."
            elif any('kritiser' in c.lower() or 'sige fra' in c.lower() for c in comments):
                return "Folk tør ikke sige fra eller kritisere beslutninger - selv når de kan se tingene ikke fungerer. De har set hvad der sker med dem der siger fra."
            elif any('dårligt' in c.lower() or 'mødt' in c.lower() for c in comments):
                return "Medarbejdere har oplevet at kolleger bliver mødt dårligt når de siger deres mening. Resultatet: folk tier stille."
            else:
                return "Der er lav psykologisk sikkerhed. Folk deler ikke åbent hvad de tænker eller er bekymrede for - de holder det for sig selv."
        else:
            return "Medarbejdere scorer lavt på psykologisk tryghed. Der er sandsynligvis vigtige ting de ikke siger højt."
    
    elif field == 'MULIGHED':
        if has_comments:
            if any('system' in c.lower() or 'langsom' in c.lower() for c in comments):
                return "IT-systemerne er så langsomme og besværlige at de står i vejen for arbejdet. Folk bruger mere tid på at kæmpe med systemet end på selve opgaven."
            elif any('tid' in c.lower() or 'ressource' in c.lower() or 'nå' in c.lower() for c in comments):
                return "Der er ikke tid nok. Folk ved hvad de BURDE gøre for at gøre det ordentligt - men de har ikke ressourcerne til det. Så det bliver skidt."
            elif any('ved ikke' in c.lower() or 'information' in c.lower() or 'find' in c.lower() for c in comments):
                return "Folk ved ikke hvor de finder information eller hvem de skal spørge. De gætter sig frem eller lader være - begge dele koster tid og kvalitet."
            elif any('spørge' in c.lower() or 'hjælp' in c.lower() for c in comments):
                return "Folk tør ikke spørge om hjælp når de står fast. Så de kæmper selv med det - eller laver det forkert."
            else:
                return "Medarbejdere mangler noget basalt for at kunne lykkes - tid, værktøjer, information eller støtte. De løber hurtigt men når ikke i mål."
        else:
            return "Medarbejdere scorer lavt på oplevede muligheder. Der mangler grundlæggende forudsætninger for at de kan lykkes."
    
    elif field == 'BESVÆR':
        if has_comments:
            if any('system' in c.lower() or 'registrer' in c.lower() or 'dobbelt' in c.lower() for c in comments):
                return "Folk registrerer det samme flere steder fordi systemerne ikke taler sammen. Det er dobbelt- og trippeltarbejde som spiser tiden."
            elif any('regel' in c.lower() or 'procedure' in c.lower() or 'omgå' in c.lower() for c in comments):
                return "Reglerne passer ikke til virkeligheden. Folk SKAL bryde procedurerne for at nå deres arbejde - og de ved det er forkert, men alternativet er at lade være med at hjælpe borgeren."
            elif any('bureaukrati' in c.lower() or 'administration' in c.lower() for c in comments):
                return "Der er så meget bureaukrati og administration at det æder tiden fra kernearbejdet. Folk bruger mere tid på papirarbejde end på borgeren."
            elif any('nå' in c.lower() and 'hvis' in c.lower() for c in comments):
                return "Folk siger direkte: 'Hvis jeg fulgte alle regler ville jeg ikke nå mit arbejde'. Systemet tvinger dem til at snyde."
            else:
                return "Systemer, procedurer og bureaukrati står i vejen. Folk skal kæmpe MOD strukturerne for at kunne hjælpe borgeren."
        else:
            return "Medarbejdere scorer lavt på besvær. Der er strukturer eller systemer der gør arbejdet unødigt svært."
    
    return "Der er udfordringer i dette område."


def get_concrete_actions(field: str, comments: List[str]) -> List[str]:
    """
    Generer konkrete handlinger der knytter til hvad folk faktisk sagde
    """
    
    if field == 'MENING':
        return [
            "📋 STOP-øvelse i næste teammøde (15 min):\n   Stil spørgsmålet: 'Hvilke 3 opgaver giver MINDST mening for jer?' Lad alle skrive på post-its. Gruppér dem. Diskutér: Hvad er formålet med dem?",
            
            "🎯 Gør formålet synligt:\n   For hver tilbagevendende opgave - skriv 'Hvorfor gør vi dette?' på en tavle eller i jeres systemer. Hvis I ikke kan svare kort og klart → undersøg om den kan droppes.",
            
            "✂️ Drop eller forenkl ÉN opgave:\n   Vælg den opgave folk scorer lavest. Stil spørgsmålet: Er det lovkrav? Giver det reel værdi? Hvis nej til begge → stop med at gøre det."
        ]
    
    elif field == 'TRYGHED':
        return [
            "🗣️ Normaliser at sige tingene højt:\n   Start næste møde med at DU (lederen) deler noget du er i tvivl om eller bekymret for. Vis at det er OK ikke at have alle svar.",
            
            "✅ Lav en 'Det er OK at...'-liste:\n   Sammen med teamet: Hvad SKAL være OK at sige højt her? (fx 'Det er OK at sige nej', 'Det er OK at spørge om hjælp'). Hæng den op.",
            
            "👂 Lyt uden at forsvare:\n   Næste gang nogen kritiserer noget - stop, lyt, gentag hvad du hørte, tak for input. Ingen forklaring eller forsvar i første omgang."
        ]
    
    elif field == 'MULIGHED':
        return [
            "📦 Kortlæg hvad der konkret mangler:\n   Bed hver medarbejder skrive 3 ting de mangler for at gøre deres arbejde godt (system, tid, information, værktøj). Lav liste. Prioritér top-3.",
            
            "🤝 Lav en 'Spørg X om Y'-tavle:\n   Gør det synligt hvem der ved hvad. 'Spørg Maria om journal-systemet', 'Spørg Ahmed om tidsregistrering'. Opdater den løbende.",
            
            "⏰ Find tid-tyvene:\n   Bed folk logge hvad der spiser deres tid én dag. Hvad kan fjernes, automatiseres eller forenkles?"
        ]
    
    elif field == 'BESVÆR':
        return [
            "🔍 Find det værste besværet:\n   Spørg teamet: 'Hvis I kunne fjerne ÉN ting der gør jeres arbejde besværligt - hvad ville det være?' Start dér.",
            
            "✂️ Forenkl ÉN proces denne måned:\n   Tag den mest besværlige procedure. Spørg: Hvad er lovkrav? Hvad er internt krav? Drop alt der ikke er strengt nødvendigt.",
            
            "🤝 Giv tilladelse til at springe over:\n   For regler folk alligevel omgår - giv officiel tilladelse til den forenklede måde. Eller ændr reglen så den passer til virkeligheden."
        ]
    
    return ["Undersøg nærmere hvad der konkret står i vejen"]


def get_all_critical_areas(stats: List[Dict[str, Any]], threshold: float = 2.8) -> List[Dict]:
    """
    Find ALLE områder med høj friktion (ikke kun det laveste)
    threshold: scores under denne værdi betragtes som kritiske
    """
    critical = []
    
    for stat in stats:
        if stat['avg_score'] > 0 and stat['avg_score'] < threshold:
            critical.append({
                'field': stat['field'],
                'score': stat['avg_score'],
                'severity': 'høj' if stat['avg_score'] < 2.5 else 'moderat'
            })
    
    # Sortér efter score (laveste først)
    critical.sort(key=lambda x: x['score'])
    
    return critical


def get_recommendation(stats: List[Dict[str, Any]], all_responses: List[Dict] = None) -> Dict[str, Any]:
    """
    Generer konkret, handlingsorienteret anbefaling baseret på REELLE svar
    
    Fokus:
    - Hvad folk faktisk sagde (citater)
    - Konkret problem-beskrivelse
    - Hvad det BETYDER (konsekvenser)
    - Handlinger der knytter til svarene
    - Flere områder hvis flere scorer lavt
    """
    if not stats or all(s['avg_score'] == 0 for s in stats):
        return {
            'has_data': False,
            'message': 'Ikke nok data endnu - vent til mindst 5 personer har svaret'
        }
    
    # Find det laveste felt
    lowest = min([s for s in stats if s['avg_score'] > 0], key=lambda x: x['avg_score'])
    field = lowest['field']
    score = lowest['avg_score']
    
    # Hent citater hvis vi har responses
    comments = []
    if all_responses:
        comments = get_top_comments(all_responses, field, limit=5)
    
    # Generer konkret problem-beskrivelse
    problem = get_concrete_problem(field, score, comments)
    
    # Generer konsekvens-beskrivelse
    impact = get_impact_description(field, score)
    
    # Generer handlinger
    actions = get_concrete_actions(field, comments)
    
    # Find ALLE kritiske områder
    all_critical = get_all_critical_areas(stats, threshold=2.8)
    
    # Severity
    if score < 2.5:
        severity = "🔴 Kritisk"
    elif score < 3.5:
        severity = "🟡 Problem"
    else:
        severity = "🟢 OK"
    
    return {
        'has_data': True,
        'field': field,
        'score': score,
        'severity': severity,
        'problem': problem,
        'impact': impact,
        'comments': comments,
        'actions': actions,
        'all_critical': all_critical,
        'follow_up': 'Gentag målingen om 6-8 uger. Er scoren steget? Taler folk anderledes om arbejdet?'
    }


def get_impact_description(field: str, score: float) -> str:
    """
    Beskriv hvad problemet BETYDER - konkrete konsekvenser
    """
    impacts = {
        'MENING': "Det betyder: Folk går på arbejde uden at vide hvorfor de gør det. Motivation falder. Kvalitet bliver tilfældig fordi ingen ved hvad der er vigtigt. Opgaver bliver til 'bare noget vi gør' i stedet for noget der hjælper.",
        
        'TRYGHED': "Det betyder: Problemer opdages for sent fordi folk tier. Fejl bliver ikke rettet fordi ingen tør sige det. Gode idéer dør fordi ingen tør foreslå dem. Folk går hjem med en klump i maven.",
        
        'MULIGHED': "Det betyder: Folk ved hvad de BURDE gøre men kan ikke. De løber hurtigere men når mindre. Kvalitet lider. Folk bliver frustrerede fordi de vil gøre det godt men ikke kan.",
        
        'BESVÆR': "Det betyder: Tiden går til at kæmpe mod systemet i stedet for at hjælpe borgeren. Folk bliver udbrændte af at løbe hurtigere og hurtigere. De bliver cyniske: 'Sådan er det bare'."
    }
    return impacts.get(field, "Dette skaber friktion der koster energi, tid og kvalitet.")


def get_color_class(score: float) -> str:
    """Returner CSS-klasse baseret på score"""
    if score == 0:
        return 'score-none'
    elif score < 2.5:
        return 'score-red'
    elif score < 3.5:
        return 'score-yellow'
    else:
        return 'score-green'


def format_field_name(field: str) -> str:
    """Dansk navngivning af felter"""
    names = {
        'MENING': 'Mening',
        'TRYGHED': 'Tryghed',
        'MULIGHED': 'Kan',  # Ændret fra Mulighed
        'KAN': 'Kan',
        'BESVÆR': 'Besvær'
    }
    return names.get(field, field)

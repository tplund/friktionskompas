"""
Generer realistiske danske testsvar til demo
"""
import random
from datetime import datetime, timedelta
from db import save_response, get_questions

# Realistiske danske kommentarer pr. felt
# 70% handlingsrettede (konkrete ting lederen KAN gøre noget ved)
# 30% strukturelle (penge/tid/rammer - realistisk men begræns dem)
COMMENTS_GENERIC = {
    "MENING": [
        # Handlingsrettede (70%)
        "Dokumentationen føles som om ingen læser den",
        "Jeg ved ikke hvad formålet er med alle rapporterne",
        "Nogle af registreringerne virker overflødige",
        "Møder hvor vi kunne klare det på mail",
        "Kan ikke se hvordan det hjælper borgeren",
        "Rapporter der aldrig følges op på",
        "Procedurer der virker ligegyldige",
        # Strukturelle (30%)
        "For mange krav oppefra",
        "Lovkrav vi ikke kan ændre",
        "",
        "",
    ],
    "TRYGHED": [
        # Handlingsrettede (70%)
        "Jeg holder tilbage med at sige hvad jeg mener",
        "Det føles ikke trygt at kritisere beslutninger",
        "Jeg har set kolleger blive mødt dårligt når de sagde fra",
        "Tier stille om nogle ting fordi det ikke nytter",
        "Svært at rejse kritik",
        "Kultur for at man bare skal gøre hvad man får besked på",
        "Tør ikke spørge om hjælp",
        # Strukturelle (30%)
        "Presset oppefra gør det svært",
        "",
        "",
    ],
    "MULIGHED": [
        # Handlingsrettede (70%)
        "Systemet er langsomt og besværligt",
        "Ved ikke hvor jeg skal finde informationen",
        "Tør ikke altid spørge om hjælp",
        "Mangler oplæring i nogle systemer",
        "Information er begravet i mails",
        "Ved ikke hvem jeg skal spørge",
        "Systemer der ikke taler sammen",
        # Strukturelle (30%)
        "For få ressourcer",
        "Ikke tid nok",
        "",
        "",
    ],
    "BESVÆR": [
        # Handlingsrettede (70%)
        "Registrerer i flere systemer",
        "Reglerne passer ikke til virkeligheden",
        "Må omgå procedurerne for at nå det",
        "Dobbeltarbejde",
        "Procedurer der tager unødigt lang tid",
        "Bureaukrati stjæler tiden",
        "Hvis jeg fulgte alle regler ville jeg bruge hele dagen på papirarbejde",
        # Strukturelle (30%)
        "For få vikarer når folk er syge",
        "Lovkrav vi ikke kan ændre",
        "",
        "",
    ]
}

# Sektor-specifikke kommentarer (70% handlingsrettede)
COMMENTS_BY_SECTOR = {
    "ældrepleje": {
        "MENING": [
            "Dokumentationen tager tid fra borgerkontakten",
            "Ved ikke hvorfor vi skal registrere så mange ting",
            "Føles som systemet er vigtigere end borgerne",
            "Rapporter der aldrig læses",
            "Overflødige registreringer",
        ],
        "TRYGHED": [
            "Tør ikke sige fra når der er for mange beboere",
            "Får skæld ud hvis jeg bruger for lang tid hos én borger",
            "Svært at rejse bekymringer",
        ],
        "MULIGHED": [
            "Systemet hænger ofte",
            "Ved ikke hvor jeg finder procedurer",
            "Mangler oplæring i nye systemer",
            "Der mangler vikarer når folk er syge",  # Strukturelt, men begræns
            "Ikke tid nok til at gøre det ordentligt",  # Strukturelt
        ],
        "BESVÆR": [
            "Dokumentation i flere systemer spiser tiden",
            "Reglerne om medicinering er for stive",
            "Registrerer det samme flere gange",
            "Procedurer der kunne forenkles",
        ]
    },
    "skole": {
        "MENING": [
            "For mange tests der ikke hjælper eleverne",
            "Dokumentationskrav stjæler tid fra undervisning",
            "Ved ikke hvad formålet er med alle rapporterne",
            "Møder der kunne være mails",
        ],
        "TRYGHED": [
            "Tør ikke sige fra overfor forældrene",
            "Holder bekymringer for mig selv",
            "Ingen lytter når vi siger tingene ikke fungerer",
        ],
        "MULIGHED": [
            "Mangler materialer og ressourcer",
            "Ingen tid til forberedelse",
            "Klassen er for stor til at nå alle",  # Strukturelt
            "Systemer der ikke fungerer",
        ],
        "BESVÆR": [
            "Administration fylder mere end undervisning",
            "For mange platforme og systemer",
            "Regler om inklusion passer ikke til virkeligheden",
            "Dobbeltregistrering",
        ]
    }
}


def generate_demo_responses(team_id: str = "team-demo", period: str = "2025Q4", num_respondents: int = 10, sector: str = "generic"):
    """
    Generer realistiske testsvar fra 'num_respondents' personer
    
    sector: 'generic', 'ældrepleje', 'skole', osv.
    """
    questions = get_questions()
    
    # Vælg kommentarer baseret på sektor
    if sector in COMMENTS_BY_SECTOR:
        comments = COMMENTS_BY_SECTOR[sector]
    else:
        comments = COMMENTS_GENERIC
    
    # Varierede profiler der giver forskellige kombinationer
    # Så du kan se hvad forskellige friktionsmønstre betyder
    profiles = [
        # Profil 1: Høj MENING-friktion (folk ser ikke formålet)
        {"MENING": (1, 2), "TRYGHED": (3, 4), "MULIGHED": (3, 4), "BESVÆR": (3, 4)},
        
        # Profil 2: Høj TRYGHED-friktion (folk tier)
        {"MENING": (3, 4), "TRYGHED": (1, 2), "MULIGHED": (3, 4), "BESVÆR": (3, 4)},
        
        # Profil 3: Høj KAN-friktion (mangler evne/værktøjer)
        {"MENING": (3, 4), "TRYGHED": (3, 4), "MULIGHED": (1, 2), "BESVÆR": (3, 4)},
        
        # Profil 4: Høj BESVÆR-friktion (systemet i vejen)
        {"MENING": (3, 4), "TRYGHED": (3, 4), "MULIGHED": (3, 4), "BESVÆR": (1, 2)},
        
        # Profil 5: MENING + BESVÆR begge lave (klassisk offentlig sektor)
        {"MENING": (2, 2), "TRYGHED": (3, 4), "MULIGHED": (3, 3), "BESVÆR": (2, 2)},
        
        # Profil 6: TRYGHED + KAN begge lave (dårlig onboarding?)
        {"MENING": (3, 4), "TRYGHED": (2, 2), "MULIGHED": (2, 2), "BESVÆR": (3, 4)},
        
        # Profil 7: Alt er moderat problematisk
        {"MENING": (2, 3), "TRYGHED": (2, 3), "MULIGHED": (2, 3), "BESVÆR": (2, 3)},
        
        # Profil 8: Alt er rigtig dårligt (krise)
        {"MENING": (1, 2), "TRYGHED": (1, 2), "MULIGHED": (1, 2), "BESVÆR": (1, 2)},
        
        # Profil 9: Tilfreds medarbejder
        {"MENING": (4, 5), "TRYGHED": (4, 5), "MULIGHED": (4, 5), "BESVÆR": (4, 5)},
        
        # Profil 10: Lav BESVÆR men resten OK (sjældent!)
        {"MENING": (4, 4), "TRYGHED": (4, 4), "MULIGHED": (3, 4), "BESVÆR": (2, 2)},
    ]
    
    # Generer svar for hver respondent
    for i in range(num_respondents):
        # Vælg profil - lidt vægt mod de problematiske (70/30)
        if i < num_respondents * 0.7:
            profile = random.choice(profiles[:8])  # De problematiske
        else:
            profile = random.choice(profiles[8:])  # De OK
        
        # Simuler tidspunkt (spredt over sidste uge)
        response_time = datetime.now() - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23))
        
        # Svar på alle spørgsmål
        for q in questions:
            field = q['field']
            score_range = profile.get(field, (3, 3))
            score = random.randint(score_range[0], score_range[1])
            
            # Tilføj kommentarer oftere hvis score er lav (50% chance)
            comment = None
            if score <= 2 and random.random() < 0.5:
                available_comments = comments.get(field, [""])
                comment = random.choice([c for c in available_comments if c])
            
            save_response(team_id, period, q['id'], score, comment)


if __name__ == "__main__":
    # Test
    from db import init_db, clear_all_responses
    init_db()
    clear_all_responses()
    generate_demo_responses()
    print("✅ Genereret 10 demo-svar")

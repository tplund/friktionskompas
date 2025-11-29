"""
Generisk demo data for Friktionskompas v3
To forskellige organisationer med realistisk hierarki
"""
from db_hierarchical import (
    create_unit_from_path, create_campaign, 
    generate_tokens_for_campaign, validate_and_use_token,
    save_response, get_db
)
import random

def create_demo_organizations():
    """Opret to generiske organisationer"""
    
    print("🏗️  Opretter demo organisationer...")
    
    # ========================================
    # ORGANISATION 1: TechCorp
    # ========================================
    
    # IT Afdeling
    create_unit_from_path(
        "TechCorp//IT Afdeling//Development",
        leader_name="Anders Hansen",
        leader_email="anders@techcorp.dk",
        employee_count=15,
        sick_leave_percent=3.2
    )
    
    create_unit_from_path(
        "TechCorp//IT Afdeling//Support",
        leader_name="Mette Nielsen",
        leader_email="mette@techcorp.dk",
        employee_count=8,
        sick_leave_percent=5.1
    )
    
    # HR & Admin
    create_unit_from_path(
        "TechCorp//HR & Admin//Rekruttering",
        leader_name="Jesper Berg",
        leader_email="jesper@techcorp.dk",
        employee_count=4,
        sick_leave_percent=2.1
    )
    
    create_unit_from_path(
        "TechCorp//HR & Admin//Løn & Personale",
        leader_name="Sofie Christensen",
        leader_email="sofie@techcorp.dk",
        employee_count=6,
        sick_leave_percent=4.3
    )
    
    # Sales & Marketing
    create_unit_from_path(
        "TechCorp//Sales & Marketing//Salg Nord",
        leader_name="Michael Sørensen",
        leader_email="michael@techcorp.dk",
        employee_count=12,
        sick_leave_percent=2.8
    )
    
    create_unit_from_path(
        "TechCorp//Sales & Marketing//Salg Syd",
        leader_name="Camilla Møller",
        leader_email="camilla@techcorp.dk",
        employee_count=10,
        sick_leave_percent=3.5
    )
    
    create_unit_from_path(
        "TechCorp//Sales & Marketing//Marketing",
        leader_name="Thomas Larsen",
        leader_email="thomas@techcorp.dk",
        employee_count=7,
        sick_leave_percent=1.9
    )
    
    print("✅ TechCorp oprettet (7 units)")
    
    # ========================================
    # ORGANISATION 2: ServiceGruppen
    # ========================================
    
    # Kundeservice
    create_unit_from_path(
        "ServiceGruppen//Kundeservice//Team A",
        leader_name="Anne Petersen",
        leader_email="anne@servicegruppen.dk",
        employee_count=20,
        sick_leave_percent=6.2
    )
    
    create_unit_from_path(
        "ServiceGruppen//Kundeservice//Team B",
        leader_name="Lars Jørgensen",
        leader_email="lars@servicegruppen.dk",
        employee_count=18,
        sick_leave_percent=5.8
    )
    
    # Back Office
    create_unit_from_path(
        "ServiceGruppen//Back Office//Administration",
        leader_name="Hanne Andersen",
        leader_email="hanne@servicegruppen.dk",
        employee_count=9,
        sick_leave_percent=3.7
    )
    
    create_unit_from_path(
        "ServiceGruppen//Back Office//Økonomi",
        leader_name="Peter Rasmussen",
        leader_email="peter@servicegruppen.dk",
        employee_count=5,
        sick_leave_percent=2.4
    )
    
    # Drift
    create_unit_from_path(
        "ServiceGruppen//Drift//Daghold",
        leader_name="Kirsten Madsen",
        leader_email="kirsten@servicegruppen.dk",
        employee_count=14,
        sick_leave_percent=7.1
    )
    
    create_unit_from_path(
        "ServiceGruppen//Drift//Aftenhold",
        leader_name="Jan Thomsen",
        leader_email="jan@servicegruppen.dk",
        employee_count=12,
        sick_leave_percent=8.3
    )
    
    print("✅ ServiceGruppen oprettet (6 units)")
    print(f"📊 Total: 13 leaf units, 127 medarbejdere")


def create_demo_campaign_with_responses():
    """Opret en kampagne med realistiske svar"""
    
    print("\n📤 Opretter demo kampagne...")
    
    # Find TechCorp root unit
    with get_db() as conn:
        techcorp = conn.execute("""
            SELECT id FROM organizational_units 
            WHERE name = 'TechCorp' AND parent_id IS NULL
        """).fetchone()
        
        if not techcorp:
            print("❌ TechCorp ikke fundet")
            return
        
        techcorp_id = techcorp['id']
    
    # Opret kampagne på hele TechCorp
    campaign_id = create_campaign(
        target_unit_id=techcorp_id,
        name="Q4 2024 Medarbejdertrivsel",
        period="Q4 2024",
        sent_from="HR"
    )
    
    print(f"✅ Kampagne oprettet: {campaign_id}")
    
    # Generer tokens
    tokens_by_unit = generate_tokens_for_campaign(campaign_id)
    
    total_tokens = sum(len(tokens) for tokens in tokens_by_unit.values())
    print(f"🎫 Genereret {total_tokens} tokens fordelt på {len(tokens_by_unit)} units")
    
    # Simuler at nogle medarbejdere svarer
    print("\n💬 Simulerer svar...")
    
    responses_created = 0
    
    # Hent alle spørgsmål
    with get_db() as conn:
        questions = conn.execute("""
            SELECT id, field, reverse_scored FROM questions 
            WHERE is_default = 1 
            ORDER BY sequence
        """).fetchall()
    
    # For hver unit, lad nogle tokens blive brugt
    for unit_id, tokens in tokens_by_unit.items():
        # Random response rate mellem 40-80%
        response_rate = random.uniform(0.4, 0.8)
        num_responses = int(len(tokens) * response_rate)
        
        # Tag nogle tilfældige tokens
        responding_tokens = random.sample(tokens, num_responses)
        
        for token in responding_tokens:
            # Valider token
            token_data = validate_and_use_token(token)
            
            if not token_data:
                continue
            
            # Generer svar til alle spørgsmål
            for q in questions:
                # Generer realistisk score baseret på field
                score = generate_realistic_score(q['field'], unit_id)
                
                # Nogle gange en kommentar
                comment = None
                if random.random() < 0.15:  # 15% chance
                    comment = generate_realistic_comment(q['field'], score)
                
                save_response(
                    campaign_id=campaign_id,
                    unit_id=unit_id,
                    question_id=q['id'],
                    score=score,
                    comment=comment
                )
                
                responses_created += 1
    
    print(f"✅ {responses_created} svar oprettet fra {sum(1 for tokens in tokens_by_unit.values() for _ in tokens if random.random() < 0.6)} medarbejdere")
    
    return campaign_id


def generate_realistic_score(field: str, unit_id: str) -> int:
    """
    Generer realistisk score baseret på field type
    Forskellige units har forskellige patterns
    """
    # Get unit name for variation
    with get_db() as conn:
        unit = conn.execute(
            "SELECT full_path FROM organizational_units WHERE id = ?",
            (unit_id,)
        ).fetchone()
    
    unit_path = unit['full_path'] if unit else ""
    
    # Base patterns per field
    if field == "MENING":
        # Generelt OK, men nogle problemer
        base = random.choices([2, 3, 4, 5], weights=[5, 25, 50, 20])[0]
    
    elif field == "TRYGHED":
        # Ofte udfordret
        base = random.choices([1, 2, 3, 4, 5], weights=[10, 30, 35, 20, 5])[0]
    
    elif field == "MULIGHED":
        # Middel udfordring
        base = random.choices([2, 3, 4, 5], weights=[15, 35, 40, 10])[0]
    
    elif field == "BESVÆR":
        # Høje scores (meget besvær)
        base = random.choices([2, 3, 4, 5], weights=[5, 20, 40, 35])[0]
    
    else:
        base = 3
    
    # Variation baseret på unit type
    if "Support" in unit_path or "Kundeservice" in unit_path:
        # Support har mere besvær
        if field == "BESVÆR":
            base = min(5, base + random.choice([0, 1]))
    
    if "Drift" in unit_path:
        # Drift har lavere tryghed
        if field == "TRYGHED":
            base = max(1, base - random.choice([0, 1]))
    
    return base


def generate_realistic_comment(field: str, score: int) -> str:
    """Generer realistisk kommentar baseret på field og score"""
    
    comments_by_field = {
        "MENING": {
            "low": [
                "For mange møder der ikke fører til noget",
                "Bruger meget tid på rapporter som ingen læser",
                "Føler ofte at vi laver ting 'fordi vi altid har gjort det'",
            ],
            "high": [
                "Kan tydeligt se at mit arbejde gør en forskel",
                "God feedback fra kunder giver mening",
                "Føler mig som en del af en vigtig mission",
            ]
        },
        "TRYGHED": {
            "low": [
                "Tør ikke altid sige min mening til møder",
                "Føler jeg skal passe på hvad jeg siger",
                "Bekymret for konsekvenser hvis jeg fejler",
            ],
            "high": [
                "Godt team hvor vi bakker hinanden op",
                "Min leder er god til at lytte",
                "Vi kan snakke åbent om det meste",
            ]
        },
        "MULIGHED": {
            "low": [
                "Mangler training i de nye systemer",
                "Ved ikke altid hvor jeg skal få hjælp",
                "Værktøjerne er ofte nede eller langsomme",
            ],
            "high": [
                "Gode muligheder for at udvikle sig",
                "Har adgang til det jeg skal bruge",
                "Kollegerne hjælper altid når jeg spørger",
            ]
        },
        "BESVÆR": {
            "low": [
                "Systemerne fungerer generelt godt",
                "Procedurerne giver mening",
            ],
            "high": [
                "Må konstant finde omveje i systemerne",
                "Dobbeltregistrering i flere systemer",
                "Reglerne passer ikke til virkeligheden",
                "For meget bureaukrati",
            ]
        }
    }
    
    category = "low" if score <= 2 else "high"
    
    if field in comments_by_field and category in comments_by_field[field]:
        return random.choice(comments_by_field[field][category])
    
    return None


def create_second_demo_campaign():
    """Opret en kampagne kun for ServiceGruppen//Kundeservice"""
    
    print("\n📤 Opretter demo kampagne 2...")
    
    # Find Kundeservice unit
    with get_db() as conn:
        kundeservice = conn.execute("""
            SELECT id FROM organizational_units 
            WHERE full_path = 'ServiceGruppen//Kundeservice'
        """).fetchone()
        
        if not kundeservice:
            print("❌ Kundeservice ikke fundet")
            return
        
        kundeservice_id = kundeservice['id']
    
    # Opret kampagne kun på Kundeservice (rammer Team A og B)
    campaign_id = create_campaign(
        target_unit_id=kundeservice_id,
        name="Kundeservice Check-in",
        period="November 2024",
        sent_from="Afdelingsleder"
    )
    
    print(f"✅ Kampagne 2 oprettet: {campaign_id}")
    
    # Generer tokens
    tokens_by_unit = generate_tokens_for_campaign(campaign_id)
    
    total_tokens = sum(len(tokens) for tokens in tokens_by_unit.values())
    print(f"🎫 Genereret {total_tokens} tokens fordelt på {len(tokens_by_unit)} units")
    
    return campaign_id


def run_full_demo():
    """Kør alt demo data setup"""
    print("=" * 60)
    print("🚀 FRIKTIONSKOMPAS V3 - DEMO DATA SETUP")
    print("=" * 60)
    
    create_demo_organizations()
    campaign1 = create_demo_campaign_with_responses()
    campaign2 = create_second_demo_campaign()
    
    print("\n" + "=" * 60)
    print("✅ DEMO DATA KLAR!")
    print("=" * 60)
    print(f"\n📊 Oprettet:")
    print(f"  - 2 organisationer (TechCorp, ServiceGruppen)")
    print(f"  - 13 leaf units (teams/afdelinger)")
    print(f"  - 2 kampagner med tokens og svar")
    print(f"\n🔗 Kampagne 1: {campaign1}")
    print(f"🔗 Kampagne 2: {campaign2}")
    print("\n💡 Nu kan du teste admin interface!")


if __name__ == "__main__":
    run_full_demo()

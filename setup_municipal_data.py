"""
Setup complete municipal test data for Friktionskompasset
Opretter 2 kommuner med fuld organisationsstruktur og realistiske testdata
"""
from db_hierarchical import get_db, create_unit
from db_multitenant import create_customer, create_user
import random
import string

def generate_id(prefix):
    """Generer random ID"""
    return f"{prefix}-{''.join(random.choices(string.ascii_letters + string.digits, k=11))}"

def clear_all_data():
    """Slet alle eksisterende data"""
    with get_db() as conn:
        print("[INFO] Sletter alle eksisterende data...")
        conn.execute("DELETE FROM responses")
        conn.execute("DELETE FROM tokens")
        conn.execute("DELETE FROM campaigns")
        conn.execute("DELETE FROM organizational_units")
        conn.execute("DELETE FROM users")
        conn.execute("DELETE FROM customers")
        print("[OK] Alle data slettet")

def create_municipal_structure():
    """Opret kommunestruktur"""
    print("\n" + "="*60)
    print("OPRETTER KOMMUNAL STRUKTUR")
    print("="*60)

    # ESBJERG KOMMUNE
    esbjerg_customer_id = create_customer("Esbjerg Kommune")
    print(f"\n[OK] Oprettet kunde: Esbjerg Kommune ({esbjerg_customer_id})")

    # Manager bruger for Esbjerg (kunde-specifik)
    create_user("leder@esbjerg.dk", "admin123", "Leder Esbjerg", "leder@esbjerg.dk", "manager", esbjerg_customer_id)
    print(f"[OK] Oprettet leder: leder@esbjerg.dk")

    # Esbjerg - Forvaltning
    social_sundhed_esb = create_unit("Social- og Sundhedsforvaltningen", parent_id=None, customer_id=esbjerg_customer_id)
    print(f"[OK] Oprettet forvaltning: Social- og Sundhedsforvaltningen (Esbjerg)")

    # Esbjerg - Ældreplejen (under forvaltning)
    aeldrepleje_esb = create_unit("Ældreplejen", parent_id=social_sundhed_esb, customer_id=esbjerg_customer_id)
    print(f"   [OK] Oprettet område: Ældreplejen")

    # Enheder under Ældreplejen Esbjerg
    esbjerg_aeldrepleje_units = [
        ("Solhjem", 15),
        ("Skovbrynet", 12),
        ("Strandparken", 18),
        ("Birkebo", 14)
    ]

    esb_aeldrepleje_unit_ids = []
    for unit_name, count in esbjerg_aeldrepleje_units:
        unit_id = create_unit(unit_name, parent_id=aeldrepleje_esb, employee_count=count, customer_id=esbjerg_customer_id)
        esb_aeldrepleje_unit_ids.append((unit_id, unit_name, count))
        print(f"      - {unit_name} ({count} medarbejdere)")

    # HERNING KOMMUNE
    herning_customer_id = create_customer("Herning Kommune")
    print(f"\n[OK] Oprettet kunde: Herning Kommune ({herning_customer_id})")

    # Manager bruger for Herning (kunde-specifik)
    create_user("leder@herning.dk", "admin123", "Leder Herning", "leder@herning.dk", "manager", herning_customer_id)
    print(f"[OK] Oprettet leder: leder@herning.dk")

    # Herning - Social- og Sundhedsforvaltningen
    social_sundhed_hern = create_unit("Social- og Sundhedsforvaltningen", parent_id=None, customer_id=herning_customer_id)
    print(f"[OK] Oprettet forvaltning: Social- og Sundhedsforvaltningen (Herning)")

    # Herning - Handicap og Psykiatri (under Social- og Sundhedsforvaltningen)
    handicap_hern = create_unit("Handicap og Psykiatri", parent_id=social_sundhed_hern, customer_id=herning_customer_id)
    print(f"   [OK] Oprettet område: Handicap og Psykiatri")

    # Enheder under Handicap og Psykiatri
    herning_handicap_units = [
        ("Bofællesskabet Åparken", 10),
        ("Støttecentret Vestergade", 16),
        ("Aktivitetscentret Midt", 13)
    ]

    hern_handicap_unit_ids = []
    for unit_name, count in herning_handicap_units:
        unit_id = create_unit(unit_name, parent_id=handicap_hern, employee_count=count, customer_id=herning_customer_id)
        hern_handicap_unit_ids.append((unit_id, unit_name, count))
        print(f"      - {unit_name} ({count} medarbejdere)")

    # Herning - Børn og Ungeforvaltningen
    born_unge_hern = create_unit("Børn og Ungeforvaltningen", parent_id=None, customer_id=herning_customer_id)
    print(f"[OK] Oprettet forvaltning: Børn og Ungeforvaltningen (Herning)")

    # Herning - Skoleområdet (under Børn og Ungeforvaltningen)
    skole_hern = create_unit("Skoleområdet", parent_id=born_unge_hern, customer_id=herning_customer_id)
    print(f"   [OK] Oprettet område: Skoleområdet")

    # Enheder under Skoleområdet
    herning_skole_units = [
        ("Birk Skole", 20),
        ("Hammerum Skole", 17),
        ("Snejbjerg Skole", 19),
        ("Gødstrup Skole", 15)
    ]

    hern_skole_unit_ids = []
    for unit_name, count in herning_skole_units:
        unit_id = create_unit(unit_name, parent_id=skole_hern, employee_count=count, customer_id=herning_customer_id)
        hern_skole_unit_ids.append((unit_id, unit_name, count))
        print(f"      - {unit_name} ({count} medarbejdere)")

    return {
        'esbjerg': {
            'customer_id': esbjerg_customer_id,
            'aeldrepleje_units': esb_aeldrepleje_unit_ids
        },
        'herning': {
            'customer_id': herning_customer_id,
            'handicap_units': hern_handicap_unit_ids,
            'skole_units': hern_skole_unit_ids
        }
    }

def create_campaigns(structure):
    """Opret målinger (campaigns) for hver enhed"""
    print("\n" + "="*60)
    print("OPRETTER MÅLINGER")
    print("="*60)

    with get_db() as conn:
        # Hent alle spørgsmål
        questions = conn.execute("SELECT id, sequence FROM questions WHERE is_default = 1 ORDER BY sequence").fetchall()

        campaigns = []

        # Esbjerg - Ældreplejen enheder
        for unit_id, unit_name, emp_count in structure['esbjerg']['aeldrepleje_units']:
            campaign_id = generate_id("camp")
            conn.execute("""
                INSERT INTO campaigns (id, name, target_unit_id, period, mode, min_responses)
                VALUES (?, ?, ?, 'Q1 2025', 'anonymous', 5)
            """, (campaign_id, f"Trivselmåling {unit_name}", unit_id))
            campaigns.append({
                'id': campaign_id,
                'unit_id': unit_id,
                'unit_name': unit_name,
                'emp_count': emp_count,
                'customer': 'Esbjerg',
                'department': 'Ældreplejen',
                'questions': questions
            })
            print(f"[OK] Oprettet måling: {unit_name} (Esbjerg)")

        # Herning - Handicap og Psykiatri enheder
        for unit_id, unit_name, emp_count in structure['herning']['handicap_units']:
            campaign_id = generate_id("camp")
            conn.execute("""
                INSERT INTO campaigns (id, name, target_unit_id, period, mode, min_responses)
                VALUES (?, ?, ?, 'Q1 2025', 'anonymous', 5)
            """, (campaign_id, f"Trivselmåling {unit_name}", unit_id))
            campaigns.append({
                'id': campaign_id,
                'unit_id': unit_id,
                'unit_name': unit_name,
                'emp_count': emp_count,
                'customer': 'Herning',
                'department': 'Handicap og Psykiatri',
                'questions': questions
            })
            print(f"[OK] Oprettet måling: {unit_name} (Herning)")

        # Herning - Skoleområdet enheder
        for unit_id, unit_name, emp_count in structure['herning']['skole_units']:
            campaign_id = generate_id("camp")
            conn.execute("""
                INSERT INTO campaigns (id, name, target_unit_id, period, mode, min_responses)
                VALUES (?, ?, ?, 'Q1 2025', 'anonymous', 5)
            """, (campaign_id, f"Trivselmåling {unit_name}", unit_id))
            campaigns.append({
                'id': campaign_id,
                'unit_id': unit_id,
                'unit_name': unit_name,
                'emp_count': emp_count,
                'customer': 'Herning',
                'department': 'Skoleområdet',
                'questions': questions
            })
            print(f"[OK] Oprettet måling: {unit_name} (Herning)")

    return campaigns

def generate_test_responses(campaigns):
    """Generer testbesvarelser med variation"""
    print("\n" + "="*60)
    print("GENERERER TESTBESVARELSER")
    print("="*60)

    # Profiler for forskellige typer enheder
    profiles = {
        'harmonisk': {  # Høj trivsel, lav misalignment
            'employee': {'MENING': [4, 4, 5], 'TRYGHED': [4, 4, 5], 'MULIGHED': [3, 4, 4], 'BESVÆR': [3, 4, 4]},
            'leader_assess': {'MENING': [4, 4, 5], 'TRYGHED': [4, 5, 5], 'MULIGHED': [4, 4, 4], 'BESVÆR': [3, 4, 4]},
            'leader_self': {'MENING': [4, 5, 5], 'TRYGHED': [4, 4, 4], 'MULIGHED': [3, 4, 4], 'BESVÆR': [3, 4, 4]}
        },
        'misaligned': {  # Stor forskel mellem leder og medarbejdere
            'employee': {'MENING': [2, 3, 3], 'TRYGHED': [2, 2, 3], 'MULIGHED': [2, 3, 3], 'BESVÆR': [2, 2, 3]},
            'leader_assess': {'MENING': [4, 4, 5], 'TRYGHED': [4, 4, 5], 'MULIGHED': [4, 4, 5], 'BESVÆR': [4, 4, 4]},
            'leader_self': {'MENING': [3, 4, 4], 'TRYGHED': [3, 3, 4], 'MULIGHED': [3, 3, 4], 'BESVÆR': [3, 3, 4]}
        },
        'problematisk': {  # Lav trivsel overalt
            'employee': {'MENING': [2, 2, 3], 'TRYGHED': [2, 2, 2], 'MULIGHED': [2, 2, 3], 'BESVÆR': [2, 2, 2]},
            'leader_assess': {'MENING': [2, 3, 3], 'TRYGHED': [2, 3, 3], 'MULIGHED': [2, 3, 3], 'BESVÆR': [2, 2, 3]},
            'leader_self': {'MENING': [2, 3, 3], 'TRYGHED': [2, 2, 2], 'MULIGHED': [2, 2, 3], 'BESVÆR': [2, 2, 3]}
        },
        'udvikling': {  # Medium, potentiale for forbedring
            'employee': {'MENING': [3, 3, 4], 'TRYGHED': [3, 3, 3], 'MULIGHED': [3, 3, 4], 'BESVÆR': [3, 3, 3]},
            'leader_assess': {'MENING': [3, 4, 4], 'TRYGHED': [3, 4, 4], 'MULIGHED': [3, 4, 4], 'BESVÆR': [3, 3, 4]},
            'leader_self': {'MENING': [3, 3, 4], 'TRYGHED': [2, 3, 3], 'MULIGHED': [3, 3, 3], 'BESVÆR': [3, 3, 3]}
        },
        'for_faa_svar': {  # Under anonymitetsgrænse
            'employee': {'MENING': [3, 4, 4], 'TRYGHED': [3, 3, 4], 'MULIGHED': [3, 3, 4], 'BESVÆR': [3, 3, 4]},
            'leader_assess': {'MENING': [4, 4, 4], 'TRYGHED': [4, 4, 4], 'MULIGHED': [4, 4, 4], 'BESVÆR': [3, 4, 4]},
            'leader_self': {'MENING': [3, 4, 4], 'TRYGHED': [3, 3, 4], 'MULIGHED': [3, 3, 4], 'BESVÆR': [3, 3, 4]}
        }
    }

    # Tildel profiler til campaigns
    campaign_profiles = {
        # Esbjerg - Ældreplejen
        'Solhjem': 'harmonisk',
        'Skovbrynet': 'misaligned',
        'Strandparken': 'problematisk',
        'Birkebo': 'for_faa_svar',  # Kun 3 svar

        # Herning - Handicap og Psykiatri
        'Bofællesskabet Åparken': 'for_faa_svar',  # Kun 4 svar
        'Støttecentret Vestergade': 'udvikling',
        'Aktivitetscentret Midt': 'harmonisk',

        # Herning - Skoleområdet
        'Birk Skole': 'misaligned',
        'Hammerum Skole': 'harmonisk',
        'Snejbjerg Skole': 'udvikling',
        'Gødstrup Skole': 'problematisk'
    }

    fritekst_eksempler = [
        "SITUATION: IT-systemet var nede i 3 timer i mandags, kunne ikke tilgå journaler.",
        "SITUATION: Skulle vente 2 uger på svar fra økonomiafdeling om budget til nyt udstyr.\n\nGENERELT: Generelt god trivsel, men kommunikation på tværs kunne være bedre.",
        "GENERELT: Mangler klare prioriteringer fra ledelsen når ressourcer er knappe.",
        "SITUATION: Blev afbrudt 8 gange på 1 time af kollegaer med spørgsmål. Svært at fokusere.\n\nGENERELT: Vi mangler en fælles vidensdatabase så vi ikke altid skal spørge hinanden.",
        "GENERELT: Gode kollegaer og meningsfuldt arbejde, men for mange administrative opgaver.",
    ]

    with get_db() as conn:
        for campaign in campaigns:
            profile_name = campaign_profiles.get(campaign['unit_name'], 'udvikling')
            profile = profiles[profile_name]

            # Beregn antal svar baseret på profil
            if profile_name == 'for_faa_svar':
                if 'Birkebo' in campaign['unit_name']:
                    num_responses = 3  # Under grænse
                else:
                    num_responses = 4  # Under grænse
            else:
                # 60-90% af medarbejdere svarer
                num_responses = int(campaign['emp_count'] * random.uniform(0.6, 0.9))

            print(f"\n[INFO] {campaign['unit_name']} ({campaign['customer']}) - Profil: {profile_name}")
            print(f"       Genererer {num_responses} af {campaign['emp_count']} mulige svar")

            # Generer employee responses
            for i in range(num_responses):
                respondent_name = f"Medarbejder{i+1}"

                for q in campaign['questions']:
                    # Find field for spørgsmål
                    field_map = {
                        range(1, 6): 'MENING',
                        range(6, 11): 'TRYGHED',
                        range(11, 19): 'MULIGHED',
                        range(19, 25): 'BESVÆR'
                    }
                    field = next((f for r, f in field_map.items() if q['sequence'] in r), 'MENING')

                    score = random.choice(profile['employee'][field])

                    # Tilføj fritekst til første respondent i nogle enheder (ikke for_faa_svar)
                    comment = None
                    if i == 0 and q['sequence'] == 1 and profile_name != 'for_faa_svar' and random.random() < 0.6:
                        comment = random.choice(fritekst_eksempler)

                    conn.execute("""
                        INSERT INTO responses (campaign_id, unit_id, question_id, score, respondent_type, respondent_name, comment)
                        VALUES (?, ?, ?, ?, 'employee', ?, ?)
                    """, (campaign['id'], campaign['unit_id'], q['id'], score, respondent_name, comment))

            # Generer leader_assess (undtagen for_faa_svar enheder)
            if profile_name != 'for_faa_svar':
                for q in campaign['questions']:
                    field_map = {
                        range(1, 6): 'MENING',
                        range(6, 11): 'TRYGHED',
                        range(11, 19): 'MULIGHED',
                        range(19, 25): 'BESVÆR'
                    }
                    field = next((f for r, f in field_map.items() if q['sequence'] in r), 'MENING')
                    score = random.choice(profile['leader_assess'][field])

                    conn.execute("""
                        INSERT INTO responses (campaign_id, unit_id, question_id, score, respondent_type, respondent_name)
                        VALUES (?, ?, ?, ?, 'leader_assess', 'Leder')
                    """, (campaign['id'], campaign['unit_id'], q['id'], score))

                # Generer leader_self
                for q in campaign['questions']:
                    field_map = {
                        range(1, 6): 'MENING',
                        range(6, 11): 'TRYGHED',
                        range(11, 19): 'MULIGHED',
                        range(19, 25): 'BESVÆR'
                    }
                    field = next((f for r, f in field_map.items() if q['sequence'] in r), 'MENING')
                    score = random.choice(profile['leader_self'][field])

                    # Leder får også fritekst i nogle tilfælde
                    comment = None
                    if q['sequence'] == 1 and random.random() < 0.3:
                        comment = "GENERELT: Føler mig ofte presset mellem strategiske opgaver og operativ drift."

                    conn.execute("""
                        INSERT INTO responses (campaign_id, unit_id, question_id, score, respondent_type, respondent_name, comment)
                        VALUES (?, ?, ?, ?, 'leader_self', 'Leder', ?)
                    """, (campaign['id'], campaign['unit_id'], q['id'], score, comment))

            print(f"       [OK] {num_responses} medarbejdere + 1 leder-vurdering + 1 leder-self")

def main():
    """Main setup function"""
    print("\n")
    print("=" * 60)
    print("  FRIKTIONSKOMPASSET - KOMMUNAL DATA SETUP")
    print("=" * 60)

    # Step 1: Clear all data
    clear_all_data()

    # Step 2: Create municipal structure
    structure = create_municipal_structure()

    # Step 3: Create campaigns
    campaigns = create_campaigns(structure)

    # Step 4: Generate test responses
    generate_test_responses(campaigns)

    print("\n" + "="*60)
    print("[OK] SETUP KOMPLET!")
    print("="*60)
    print("\nOversigt:")
    print("  • 2 kommuner: Esbjerg og Herning")
    print("  • 3 forvaltninger (direktorater)")
    print("  • 3 områder/afdelinger")
    print("  • 11 enheder total")
    print("  • 11 målinger med variation:")
    print("    - 3 harmoniske enheder")
    print("    - 2 med misalignment")
    print("    - 2 problematiske")
    print("    - 2 under udvikling")
    print("    - 2 med for få svar (< 5)")
    print("\nLogin:")
    print("  Esbjerg: leder@esbjerg.dk / admin123")
    print("  Herning: leder@herning.dk / admin123")
    print("  Admin (se begge): admin@example.com / admin")
    print("\n")

if __name__ == "__main__":
    main()

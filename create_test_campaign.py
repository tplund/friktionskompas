"""
Opret test-kampagne med de nye 22 spørgsmål
"""
from db_hierarchical import (
    create_unit, create_campaign_with_modes,
    generate_tokens_with_respondent_types, get_questions
)

print("="*60)
print("OPRET TEST-KAMPAGNE MED NYE SPØRGSMÅL")
print("="*60)

# 1. Opret test organisation
print("\n[1/4] Opretter test organisation...")
unit_id = create_unit(
    name="Test Team - Nye Spørgsmål",
    parent_id=None,
    leader_name="Test Leder",
    leader_email="leder@test.dk",
    employee_count=5,
    customer_id=None
)
print(f"  [OK] Unit oprettet: {unit_id}")

# 2. Vis antal spørgsmål
questions = get_questions()
print(f"\n[2/4] Henter spørgsmål...")
print(f"  [OK] {len(questions)} spørgsmål fundet i databasen")

from collections import Counter
field_counts = Counter(q['field'] for q in questions)
for field, count in sorted(field_counts.items()):
    print(f"    - {field}: {count} spørgsmål")

# 3. Opret anonymous campaign med leder-perspektiv
print(f"\n[3/4] Opretter campaign...")
campaign_id = create_campaign_with_modes(
    target_unit_id=unit_id,
    name="Test - Nye Spørgsmål med Leder-perspektiv",
    period="2025 Q1 Test",
    mode='anonymous',
    include_leader_assessment=True,
    include_leader_self=True,
    min_responses=3
)
print(f"  [OK] Campaign oprettet: {campaign_id}")

# 4. Generer tokens
print(f"\n[4/4] Genererer tokens...")
tokens = generate_tokens_with_respondent_types(campaign_id)

for uid, token_dict in tokens.items():
    print(f"\n  Unit: {uid}")
    for resp_type, token_list in token_dict.items():
        count = len(token_list)
        print(f"    {resp_type:20} {count} token(s)")

        # Print første token URL
        if token_list:
            first_token = token_list[0]
            print(f"      URL: http://localhost:5001/?token={first_token}")

print("\n" + "="*60)
print("TESTKAMPAGNE OPRETTET!")
print("="*60)
print(f"\nCampaign ID: {campaign_id}")
print(f"Unit ID: {unit_id}")
print(f"\nBrug tokens ovenfor til at teste spørgeskemaet")
print("="*60)

"""
Script til at omdøbe målinger fra 'Unit Name - Q# 2025' til 'Q# 2025 - Unit Name'
og rette datoer så de matcher kvartal
"""
import re
from db_hierarchical import get_db

def rename_assessments():
    """Omdøb målinger til nyt format og ret datoer"""

    # Kvartal til dato mapping
    quarter_dates = {
        'Q1': '2025-01-15',
        'Q2': '2025-04-15',
        'Q3': '2025-07-15',
        'Q4': '2025-10-15'
    }

    with get_db() as conn:
        # Hent alle assessments der matcher "X - Q# YYYY" mønstret
        assessments = conn.execute("""
            SELECT id, name, created_at
            FROM assessments
            WHERE name LIKE '% - Q_ 2025'
            ORDER BY name
        """).fetchall()

        print(f"Fandt {len(assessments)} målinger at omdøbe\n")

        for a in assessments:
            old_name = a['name']

            # Parse: "Birk Skole - Q1 2025" -> unit="Birk Skole", quarter="Q1", year="2025"
            match = re.match(r'^(.+) - (Q\d) (\d{4})$', old_name)
            if match:
                unit_name = match.group(1)
                quarter = match.group(2)
                year = match.group(3)

                # Nyt format: "Q1 2025 - Birk Skole"
                new_name = f"{quarter} {year} - {unit_name}"

                # Ny dato baseret på kvartal
                new_date = quarter_dates.get(quarter, a['created_at'])

                print(f"  {old_name}")
                print(f"  -> {new_name} (dato: {new_date})")
                print()

                # Opdater i database
                conn.execute("""
                    UPDATE assessments
                    SET name = ?, created_at = ?
                    WHERE id = ?
                """, (new_name, new_date, a['id']))

        print(f"\nOpdateret {len(assessments)} målinger")

if __name__ == '__main__':
    rename_assessments()

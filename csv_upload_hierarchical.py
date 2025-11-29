"""
CSV Bulk Upload for Friktionskompas V3
Importer hierarkiske organisationer fra CSV med // separator
Format matcher UserExport.csv (semikolon separator, UTF-8 BOM)
"""
import csv
import io
from db_hierarchical import create_unit_from_path, get_db, add_contacts_bulk


def bulk_upload_from_csv(file_content: str, customer_id: str = None) -> dict:
    """
    Importer organisationer fra CSV

    CSV Format (semikolon separator):
    FirstName;Lastname;Email;phone;Organisation
    Anders;Hansen;anders@tech.dk;+4512345678;TechCorp//IT//Development
    Mette;Nielsen;mette@tech.dk;+4587654321;TechCorp//IT//Support

    Args:
        file_content: CSV content as string
        customer_id: Customer ID to assign to created units (for multi-tenant)

    Returns:
        dict med statistik over import
    """

    # Fjern BOM hvis den findes
    if file_content.startswith('\ufeff'):
        file_content = file_content[1:]

    stream = io.StringIO(file_content)
    # Brug semikolon som delimiter (Excel standard i Danmark)
    csv_reader = csv.DictReader(stream, delimiter=';')

    stats = {
        'units_created': 0,
        'contacts_created': 0,
        'units_skipped': 0,
        'errors': []
    }

    # Track units og kontakter
    units_by_path = {}  # path -> unit_id
    contacts_by_unit = {}  # unit_id -> [contacts]

    for row_num, row in enumerate(csv_reader, start=2):  # Start på 2 (efter header)
        try:
            org_path = row.get('Organisation', '').strip()

            if not org_path:
                stats['units_skipped'] += 1
                continue

            # Opret unit hvis den ikke findes
            if org_path not in units_by_path:
                # Parse unit data
                parts = org_path.split('//')
                leaf_name = parts[-1] if parts else org_path

                # Opret unit (første person i denne path bliver leder)
                firstname = row.get('FirstName', '').strip()
                lastname = row.get('Lastname', '').strip()
                leader_name = f"{firstname} {lastname}".strip() if firstname or lastname else None
                leader_email = row.get('Email', '').strip() or None

                unit_id = create_unit_from_path(
                    path=org_path,
                    leader_name=leader_name,
                    leader_email=leader_email,
                    employee_count=0,  # Beregnes fra antal kontakter
                    sick_leave_percent=0,
                    customer_id=customer_id
                )

                units_by_path[org_path] = unit_id
                contacts_by_unit[unit_id] = []
                stats['units_created'] += 1

            # Tilføj kontakt til unit
            unit_id = units_by_path[org_path]
            email = row.get('Email', '').strip() or None
            phone = row.get('phone', '').strip() or None

            if email or phone:
                contacts_by_unit[unit_id].append({
                    'email': email,
                    'phone': phone
                })
                stats['contacts_created'] += 1

        except Exception as e:
            stats['errors'].append(f"Række {row_num}: {str(e)}")

    # Gem kontakter og opdater employee_count
    with get_db() as conn:
        for unit_id, contacts in contacts_by_unit.items():
            if contacts:
                # Gem kontakter (send connection videre for at undgå nested connections)
                add_contacts_bulk(unit_id, contacts, conn=conn)

                # Opdater employee_count
                conn.execute(
                    "UPDATE organizational_units SET employee_count = ? WHERE id = ?",
                    (len(contacts), unit_id)
                )

    return stats


def validate_csv_format(file_content: str) -> dict:
    """
    Valider CSV format før import

    Returns:
        dict med validation results
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'preview': []
    }

    try:
        # Fjern BOM hvis den findes
        if file_content.startswith('\ufeff'):
            file_content = file_content[1:]

        stream = io.StringIO(file_content)
        csv_reader = csv.DictReader(stream, delimiter=';')

        # Check required columns
        required_cols = ['Organisation']
        fieldnames = csv_reader.fieldnames or []

        missing_cols = [col for col in required_cols if col not in fieldnames]
        if missing_cols:
            results['valid'] = False
            results['errors'].append(f"Manglende kolonner: {', '.join(missing_cols)}")
            return results

        # Parse første 5 rækker for preview
        for row_num, row in enumerate(csv_reader, start=2):
            if row_num > 6:  # Max 5 rows preview
                break

            org_path = row.get('Organisation', '').strip()

            if not org_path:
                results['warnings'].append(f"Række {row_num}: Tom organisation (springer over)")
                continue

            # Check for // separator
            if '//' not in org_path and row_num == 2:
                results['warnings'].append(
                    "Ingen '//' separatorer fundet. "
                    "Husk at bruge '//' til at adskille niveauer (f.eks. 'Virksomhed//Afdeling//Team')"
                )

            # Add to preview
            parts = org_path.split('//')
            firstname = row.get('FirstName', '').strip()
            lastname = row.get('Lastname', '').strip()

            results['preview'].append({
                'row': row_num,
                'path': org_path,
                'levels': len(parts),
                'leaf': parts[-1] if parts else '',
                'name': f"{firstname} {lastname}".strip() if firstname or lastname else '-',
                'email': row.get('Email', '').strip() or '-',
            })

    except Exception as e:
        results['valid'] = False
        results['errors'].append(f"CSV parse fejl: {str(e)}")

    return results


def export_units_to_csv() -> str:
    """
    Eksporter alle units til CSV format
    Kan bruges som skabelon eller til backup
    """
    with get_db() as conn:
        # Hent alle units med deres kontakter
        units = conn.execute("""
            SELECT
                ou.id,
                ou.full_path,
                ou.leader_name,
                ou.leader_email,
                ou.employee_count,
                ou.sick_leave_percent
            FROM organizational_units ou
            WHERE ou.employee_count > 0  -- Kun leaf units med medarbejdere
            ORDER BY ou.full_path
        """).fetchall()

    output = io.StringIO()
    # UTF-8 BOM for Excel compatibility
    output.write('\ufeff')

    # Brug semikolon som delimiter
    writer = csv.writer(output, delimiter=';')

    # Header
    writer.writerow(['FirstName', 'Lastname', 'Email', 'phone', 'Organisation'])

    # Data - hent kontakter for hver unit
    with get_db() as conn:
        for unit in units:
            contacts = conn.execute("""
                SELECT email, phone
                FROM contacts
                WHERE unit_id = ?
            """, (unit['id'],)).fetchall()

            if contacts:
                for contact in contacts:
                    # Split leader_name hvis muligt
                    leader_parts = unit['leader_name'].split(' ', 1) if unit['leader_name'] else ['', '']
                    firstname = leader_parts[0] if len(leader_parts) > 0 else ''
                    lastname = leader_parts[1] if len(leader_parts) > 1 else ''

                    writer.writerow([
                        firstname,
                        lastname,
                        contact['email'] or '',
                        contact['phone'] or '',
                        unit['full_path']
                    ])
            else:
                # Ingen kontakter, men tilføj unit alligevel
                leader_parts = unit['leader_name'].split(' ', 1) if unit['leader_name'] else ['', '']
                firstname = leader_parts[0] if len(leader_parts) > 0 else ''
                lastname = leader_parts[1] if len(leader_parts) > 1 else ''

                writer.writerow([
                    firstname,
                    lastname,
                    unit['leader_email'] or '',
                    '',
                    unit['full_path']
                ])

    return output.getvalue()


def generate_csv_template() -> str:
    """Generer CSV skabelon til download"""
    output = io.StringIO()
    # UTF-8 BOM for Excel compatibility
    output.write('\ufeff')

    # Brug semikolon som delimiter
    writer = csv.writer(output, delimiter=';')

    # Header
    writer.writerow(['FirstName', 'Lastname', 'Email', 'phone', 'Organisation'])

    # Eksempler
    examples = [
        ['Anders', 'Hansen', 'anders@virksomhed.dk', '+4512345678', 'Virksomhed A//IT Afdeling//Development'],
        ['Mette', 'Nielsen', 'mette@virksomhed.dk', '+4587654321', 'Virksomhed A//IT Afdeling//Support'],
        ['Jesper', 'Berg', 'jesper@virksomhed.dk', '', 'Virksomhed A//HR//Rekruttering'],
        ['Anne', 'Petersen', 'anne@virksomhedb.dk', '+4523456789', 'Virksomhed B//Kundeservice//Team Nord'],
        ['Lars', 'Jensen', 'lars@virksomhedb.dk', '', 'Virksomhed B//Kundeservice//Team Syd'],
    ]

    for example in examples:
        writer.writerow(example)

    return output.getvalue()


if __name__ == "__main__":
    # Test med demo data
    print("📋 CSV UPLOAD TEST\n")

    test_csv = """\ufeffFirstName;Lastname;Email;phone;Organisation
Anders;Hansen;anders@test.dk;+4512345678;TestCorp//Sales//Region Nord
Mette;Jensen;mette@test.dk;;TestCorp//Sales//Region Syd
Lars;Andersen;lars@test.dk;+4587654321;TestCorp//IT//Support"""

    # Validate
    print("🔍 Validerer CSV...")
    validation = validate_csv_format(test_csv)

    if validation['valid']:
        print("✅ CSV er gyldig\n")
        print("Preview:")
        for item in validation['preview']:
            print(f"  Række {item['row']}: {item['path']} ({item['levels']} niveauer) - {item['name']}")

        # Upload
        print("\n📤 Uploader...")
        stats = bulk_upload_from_csv(test_csv)

        print(f"\n✅ Upload færdig!")
        print(f"  - {stats['units_created']} organisationer oprettet")
        print(f"  - {stats['contacts_created']} kontakter oprettet")
        print(f"  - {stats['units_skipped']} spring over")
        if stats['errors']:
            print(f"  - {len(stats['errors'])} fejl:")
            for error in stats['errors']:
                print(f"    ❌ {error}")
    else:
        print("❌ CSV ugyldig:")
        for error in validation['errors']:
            print(f"  - {error}")

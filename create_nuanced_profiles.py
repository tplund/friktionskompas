"""
Opret 10 nuancerede testprofiler til at udfordre screening-systemet
"""
import sys
sys.path.insert(0, 'C:\\_proj\\Friktionskompasset')

from db_profil import (
    init_profil_tables,
    create_session,
    save_responses,
    complete_session,
    get_all_questions
)

# De 10 nuancerede profiler - scores er {(field, layer): score}
profiles = [
    {
        'name': 'Henrik (Stresset leder)',
        'email': 'henrik@test.dk',
        'context': 'mus',
        'description': 'Oplever meget besvær, men god kognitiv kapacitet',
        'scores': {
            ('TRYGHED', 'BIOLOGI'): 2.5, ('TRYGHED', 'EMOTION'): 3.0, ('TRYGHED', 'INDRE'): 2.5, ('TRYGHED', 'KOGNITION'): 2.0,
            ('MENING', 'BIOLOGI'): 2.0, ('MENING', 'EMOTION'): 2.5, ('MENING', 'INDRE'): 2.0, ('MENING', 'KOGNITION'): 1.5,
            ('KAN', 'BIOLOGI'): 3.5, ('KAN', 'EMOTION'): 3.0, ('KAN', 'INDRE'): 2.5, ('KAN', 'KOGNITION'): 2.0,
            ('BESVÆR', 'BIOLOGI'): 4.0, ('BESVÆR', 'EMOTION'): 3.5, ('BESVÆR', 'INDRE'): 3.0, ('BESVÆR', 'KOGNITION'): 2.5,
        }
    },
    {
        'name': 'Ida (Sensitiv kreativ)',
        'email': 'ida@test.dk',
        'context': 'coaching',
        'description': 'Høj emotionel respons, men god kognitiv håndtering',
        'scores': {
            ('TRYGHED', 'BIOLOGI'): 2.0, ('TRYGHED', 'EMOTION'): 3.5, ('TRYGHED', 'INDRE'): 2.5, ('TRYGHED', 'KOGNITION'): 2.0,
            ('MENING', 'BIOLOGI'): 1.5, ('MENING', 'EMOTION'): 3.0, ('MENING', 'INDRE'): 2.0, ('MENING', 'KOGNITION'): 1.5,
            ('KAN', 'BIOLOGI'): 2.5, ('KAN', 'EMOTION'): 3.5, ('KAN', 'INDRE'): 2.5, ('KAN', 'KOGNITION'): 2.0,
            ('BESVÆR', 'BIOLOGI'): 2.5, ('BESVÆR', 'EMOTION'): 4.0, ('BESVÆR', 'INDRE'): 3.0, ('BESVÆR', 'KOGNITION'): 2.0,
        }
    },
    {
        'name': 'Jonas (Ung med ADHD-træk)',
        'email': 'jonas@test.dk',
        'context': 'onboarding',
        'description': 'Milde ADHD-lignende træk, ikke klinisk',
        'scores': {
            ('TRYGHED', 'BIOLOGI'): 3.0, ('TRYGHED', 'EMOTION'): 2.5, ('TRYGHED', 'INDRE'): 2.5, ('TRYGHED', 'KOGNITION'): 2.0,
            ('MENING', 'BIOLOGI'): 2.5, ('MENING', 'EMOTION'): 2.0, ('MENING', 'INDRE'): 2.5, ('MENING', 'KOGNITION'): 2.0,
            ('KAN', 'BIOLOGI'): 3.5, ('KAN', 'EMOTION'): 2.5, ('KAN', 'INDRE'): 3.0, ('KAN', 'KOGNITION'): 2.5,
            ('BESVÆR', 'BIOLOGI'): 4.0, ('BESVÆR', 'EMOTION'): 3.0, ('BESVÆR', 'INDRE'): 3.5, ('BESVÆR', 'KOGNITION'): 3.0,
        }
    },
    {
        'name': 'Karen (Bekymret mor)',
        'email': 'karen@test.dk',
        'context': 'general',
        'description': 'Forhøjet angst-niveau, men funktionel',
        'scores': {
            ('TRYGHED', 'BIOLOGI'): 3.5, ('TRYGHED', 'EMOTION'): 3.5, ('TRYGHED', 'INDRE'): 3.0, ('TRYGHED', 'KOGNITION'): 2.5,
            ('MENING', 'BIOLOGI'): 2.0, ('MENING', 'EMOTION'): 2.5, ('MENING', 'INDRE'): 2.0, ('MENING', 'KOGNITION'): 2.0,
            ('KAN', 'BIOLOGI'): 3.0, ('KAN', 'EMOTION'): 3.5, ('KAN', 'INDRE'): 2.5, ('KAN', 'KOGNITION'): 2.0,
            ('BESVÆR', 'BIOLOGI'): 3.0, ('BESVÆR', 'EMOTION'): 3.0, ('BESVÆR', 'INDRE'): 2.5, ('BESVÆR', 'KOGNITION'): 2.5,
        }
    },
    {
        'name': 'Lars (Pragmatisk ingeniør)',
        'email': 'lars@test.dk',
        'context': 'mus',
        'description': 'Lav emotionel respons, høj kognitiv - mulig alexithymi',
        'scores': {
            ('TRYGHED', 'BIOLOGI'): 2.0, ('TRYGHED', 'EMOTION'): 1.5, ('TRYGHED', 'INDRE'): 2.0, ('TRYGHED', 'KOGNITION'): 1.5,
            ('MENING', 'BIOLOGI'): 2.0, ('MENING', 'EMOTION'): 1.5, ('MENING', 'INDRE'): 2.0, ('MENING', 'KOGNITION'): 1.5,
            ('KAN', 'BIOLOGI'): 2.5, ('KAN', 'EMOTION'): 1.5, ('KAN', 'INDRE'): 2.0, ('KAN', 'KOGNITION'): 1.5,
            ('BESVÆR', 'BIOLOGI'): 3.0, ('BESVÆR', 'EMOTION'): 2.0, ('BESVÆR', 'INDRE'): 2.5, ('BESVÆR', 'KOGNITION'): 2.0,
        }
    },
    {
        'name': 'Mette (Udbrændt sygeplejerske)',
        'email': 'mette@test.dk',
        'context': 'coaching',
        'description': 'Depression-lignende mønster fra udbrændthed',
        'scores': {
            ('TRYGHED', 'BIOLOGI'): 3.5, ('TRYGHED', 'EMOTION'): 3.5, ('TRYGHED', 'INDRE'): 4.0, ('TRYGHED', 'KOGNITION'): 3.5,
            ('MENING', 'BIOLOGI'): 3.0, ('MENING', 'EMOTION'): 4.0, ('MENING', 'INDRE'): 4.5, ('MENING', 'KOGNITION'): 4.0,
            ('KAN', 'BIOLOGI'): 4.0, ('KAN', 'EMOTION'): 4.0, ('KAN', 'INDRE'): 4.0, ('KAN', 'KOGNITION'): 3.5,
            ('BESVÆR', 'BIOLOGI'): 4.0, ('BESVÆR', 'EMOTION'): 3.5, ('BESVÆR', 'INDRE'): 3.5, ('BESVÆR', 'KOGNITION'): 3.0,
        }
    },
    {
        'name': 'Niels (Pensionist, tilfreds)',
        'email': 'niels@test.dk',
        'context': 'general',
        'description': 'Meget robust, afbalanceret livssituation',
        'scores': {
            ('TRYGHED', 'BIOLOGI'): 1.5, ('TRYGHED', 'EMOTION'): 1.5, ('TRYGHED', 'INDRE'): 1.5, ('TRYGHED', 'KOGNITION'): 1.5,
            ('MENING', 'BIOLOGI'): 1.5, ('MENING', 'EMOTION'): 1.5, ('MENING', 'INDRE'): 1.5, ('MENING', 'KOGNITION'): 1.5,
            ('KAN', 'BIOLOGI'): 2.0, ('KAN', 'EMOTION'): 1.5, ('KAN', 'INDRE'): 1.5, ('KAN', 'KOGNITION'): 1.5,
            ('BESVÆR', 'BIOLOGI'): 2.0, ('BESVÆR', 'EMOTION'): 2.0, ('BESVÆR', 'INDRE'): 1.5, ('BESVÆR', 'KOGNITION'): 1.5,
        }
    },
    {
        'name': 'Olivia (Social angst)',
        'email': 'olivia@test.dk',
        'context': 'coaching',
        'description': 'Specifik social angst, ellers funktionel',
        'scores': {
            ('TRYGHED', 'BIOLOGI'): 4.0, ('TRYGHED', 'EMOTION'): 4.5, ('TRYGHED', 'INDRE'): 3.5, ('TRYGHED', 'KOGNITION'): 3.0,
            ('MENING', 'BIOLOGI'): 2.0, ('MENING', 'EMOTION'): 2.5, ('MENING', 'INDRE'): 2.0, ('MENING', 'KOGNITION'): 2.0,
            ('KAN', 'BIOLOGI'): 3.0, ('KAN', 'EMOTION'): 3.5, ('KAN', 'INDRE'): 2.5, ('KAN', 'KOGNITION'): 2.0,
            ('BESVÆR', 'BIOLOGI'): 2.5, ('BESVÆR', 'EMOTION'): 3.0, ('BESVÆR', 'INDRE'): 2.5, ('BESVÆR', 'KOGNITION'): 2.0,
        }
    },
    {
        'name': 'Peter (Mild autisme-træk)',
        'email': 'peter@test.dk',
        'context': 'mus',
        'description': 'Sensorisk sensitiv, god struktur, svært ved det sociale',
        'scores': {
            ('TRYGHED', 'BIOLOGI'): 3.5, ('TRYGHED', 'EMOTION'): 2.5, ('TRYGHED', 'INDRE'): 2.5, ('TRYGHED', 'KOGNITION'): 2.0,
            ('MENING', 'BIOLOGI'): 2.0, ('MENING', 'EMOTION'): 2.0, ('MENING', 'INDRE'): 2.0, ('MENING', 'KOGNITION'): 1.5,
            ('KAN', 'BIOLOGI'): 3.0, ('KAN', 'EMOTION'): 2.5, ('KAN', 'INDRE'): 2.0, ('KAN', 'KOGNITION'): 1.5,
            ('BESVÆR', 'BIOLOGI'): 3.5, ('BESVÆR', 'EMOTION'): 2.5, ('BESVÆR', 'INDRE'): 2.0, ('BESVÆR', 'KOGNITION'): 2.0,
        }
    },
    {
        'name': 'Rikke (Gennemsnitlig)',
        'email': 'rikke@test.dk',
        'context': 'general',
        'description': 'Helt gennemsnitlig profil - baseline',
        'scores': {
            ('TRYGHED', 'BIOLOGI'): 2.5, ('TRYGHED', 'EMOTION'): 2.5, ('TRYGHED', 'INDRE'): 2.5, ('TRYGHED', 'KOGNITION'): 2.5,
            ('MENING', 'BIOLOGI'): 2.5, ('MENING', 'EMOTION'): 2.5, ('MENING', 'INDRE'): 2.5, ('MENING', 'KOGNITION'): 2.5,
            ('KAN', 'BIOLOGI'): 3.0, ('KAN', 'EMOTION'): 3.0, ('KAN', 'INDRE'): 3.0, ('KAN', 'KOGNITION'): 3.0,
            ('BESVÆR', 'BIOLOGI'): 3.0, ('BESVÆR', 'EMOTION'): 3.0, ('BESVÆR', 'INDRE'): 3.0, ('BESVÆR', 'KOGNITION'): 3.0,
        }
    },
]

def main():
    print("Initialiserer database...")
    init_profil_tables()

    # Hent spørgsmål for at mappe field/layer til question_id
    questions = get_all_questions()

    if not questions:
        print("Ingen spørgsmål fundet - databasen mangler spørgsmål!")
        print("Kør db_profil.py direkte for at initialisere spørgsmål.")
        return

    # Lav mapping fra (field, layer) til question_id
    field_layer_to_qid = {}
    for q in questions:
        key = (q['field'], q['layer'])
        field_layer_to_qid[key] = q['id']

    print(f"Fundet {len(questions)} spørgsmål i databasen")
    print()
    print("Opretter 10 nuancerede testprofiler...")
    print("=" * 50)

    for profile in profiles:
        # Opret session
        session_id = create_session(
            person_name=profile['name'],
            person_email=profile['email'],
            context=profile['context']
        )

        # Konverter scores fra (field, layer) til {question_id: score}
        responses = {}
        for (field, layer), score in profile['scores'].items():
            qid = field_layer_to_qid.get((field, layer))
            if qid:
                responses[qid] = int(round(score))

        # Gem svar
        save_responses(session_id, responses)

        # Marker som færdig
        complete_session(session_id)

        print(f"[OK] {profile['name']}")
        print(f"  {profile['description']}")
        print(f"  Session: {session_id}")
        print()

    print("=" * 50)
    print(f"Oprettet {len(profiles)} nye profiler!")
    print("\nGå til /admin/profiler for at se dem alle")

if __name__ == '__main__':
    main()

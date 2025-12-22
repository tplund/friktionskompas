"""
Database setup for Friktionsprofil - Screening (13 items) og Dyb Måling (88 items)
Komplet system til kortlægning af reguleringsarkitektur
"""
import sqlite3
import secrets
import os
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import centralized database functions
from db import get_db, DB_PATH


# ========================================
# CONSTANTS
# ========================================

FELTER = ['tryghed', 'mening', 'kan', 'besvaer']
LAG = ['biologi', 'emotion', 'indre', 'kognition', 'ekstern']
OVERGANGE_OPAD = ['bio_emo', 'emo_indre', 'indre_kog', 'kog_ekstern']
OVERGANGE_NEDAD = ['ekstern_kog', 'kog_indre', 'indre_emo', 'emo_bio']

# Spørgsmålsdata for Screening (13 items)
SCREENING_QUESTIONS = [
    # Sektion A: Felter (4 items)
    {'id': 'S1', 'section': 'felt', 'target': 'tryghed',
     'text_da': 'Jeg føler mig ofte på vagt, også når andre virker rolige.',
     'text_en': 'I often feel on guard, even when others seem calm.'},
    {'id': 'S2', 'section': 'felt', 'target': 'mening',
     'text_da': 'Jeg mister hurtigt lysten, hvis jeg ikke selv kan se meningen med det, jeg skal.',
     'text_en': 'I quickly lose motivation if I cannot see the meaning in what I have to do.'},
    {'id': 'S3', 'section': 'felt', 'target': 'kan',
     'text_da': 'Jeg tvivler tit på, om jeg kan løse de opgaver, jeg står med.',
     'text_en': 'I often doubt whether I can handle the tasks I face.'},
    {'id': 'S4', 'section': 'felt', 'target': 'besvaer',
     'text_da': 'Jeg udskyder ofte opgaver, selvom jeg godt ved, de er vigtige.',
     'text_en': 'I often postpone tasks, even when I know they are important.'},

    # Sektion B: Opad-kæden (4 items)
    {'id': 'S5', 'section': 'opad', 'target': 'emo_indre',
     'text_da': 'Når jeg har det svært, ved jeg sjældent, hvad jeg egentlig har brug for.',
     'text_en': 'When I struggle, I rarely know what I actually need.'},
    {'id': 'S6', 'section': 'opad', 'target': 'indre_kog',
     'text_da': 'Når noget rammer mig personligt, mister jeg let overblikket.',
     'text_en': 'When something affects me personally, I easily lose perspective.'},
    {'id': 'S7', 'section': 'opad', 'target': 'kog_ekstern',
     'text_da': 'Jeg ved tit godt, hvad jeg burde gøre, men får det alligevel ikke gjort.',
     'text_en': 'I often know what I should do, but still cannot get it done.'},
    {'id': 'S8', 'section': 'opad', 'target': 'bio_emo',
     'text_da': 'Min krop reagerer (fx uro/spænding), før jeg ved, hvad jeg føler.',
     'text_en': 'My body reacts (e.g., restlessness/tension) before I know what I feel.'},

    # Sektion C: Manifestation & Regulering (5 items)
    {'id': 'S9', 'section': 'manifest', 'target': 'biologi',
     'text_da': 'Når jeg er presset, mærker jeg det først i kroppen (søvn, mave, spænding, hovedpine).',
     'text_en': 'When I am stressed, I first notice it in my body (sleep, stomach, tension, headache).'},
    {'id': 'S10', 'section': 'manifest', 'target': 'emotion',
     'text_da': 'Når jeg er presset, bliver jeg meget følelsesstyret.',
     'text_en': 'When I am stressed, I become very emotion-driven.'},
    {'id': 'S11', 'section': 'manifest', 'target': 'indre',
     'text_da': 'Når jeg er presset, går jeg hurtigt i selvkritik eller føler mig forkert.',
     'text_en': 'When I am stressed, I quickly turn to self-criticism or feel wrong.'},
    {'id': 'S12', 'section': 'manifest', 'target': 'kognition',
     'text_da': 'Når jeg er presset, går jeg mest op i at tænke/analysere i stedet for at handle.',
     'text_en': 'When I am stressed, I mainly focus on thinking/analyzing instead of acting.'},
    {'id': 'S13', 'section': 'manifest', 'target': 'ekstern',
     'text_da': 'Når jeg er presset, prøver jeg mest at ændre på omgivelserne (aflyse, skifte, undgå, lave om på rammerne).',
     'text_en': 'When I am stressed, I mainly try to change my surroundings (cancel, switch, avoid, change the framework).'},
]

# Spørgsmålsdata for Dyb Måling (88 items)
DEEP_QUESTIONS = [
    # ================================================
    # SEKTION A: FELTER - Baseline-friktion (16 items)
    # ================================================

    # Tryghed (A1-A4)
    {'id': 'A1', 'section': 'A', 'field': 'tryghed', 'is_reverse': False,
     'text_da': 'Jeg føler mig ofte på vagt, selv når der objektivt ikke er noget galt.',
     'text_en': 'I often feel on guard, even when objectively nothing is wrong.'},
    {'id': 'A2', 'section': 'A', 'field': 'tryghed', 'is_reverse': False,
     'text_da': 'Jeg bliver hurtigt urolig i kroppen, når jeg er sammen med andre.',
     'text_en': 'I quickly become restless in my body when I am with others.'},
    {'id': 'A3', 'section': 'A', 'field': 'tryghed', 'is_reverse': False,
     'text_da': 'Kritik eller negative kommentarer sidder længe i mig.',
     'text_en': 'Criticism or negative comments stay with me for a long time.'},
    {'id': 'A4', 'section': 'A', 'field': 'tryghed', 'is_reverse': True,
     'text_da': 'Jeg har let ved at føle mig tryg, også i nye situationer.',
     'text_en': 'I easily feel safe, even in new situations.'},

    # Mening (A5-A8)
    {'id': 'A5', 'section': 'A', 'field': 'mening', 'is_reverse': False,
     'text_da': 'Jeg mister hurtigt engagementet, hvis jeg ikke kan se meningen med det, jeg skal.',
     'text_en': 'I quickly lose engagement if I cannot see the meaning in what I have to do.'},
    {'id': 'A6', 'section': 'A', 'field': 'mening', 'is_reverse': False,
     'text_da': 'Jeg bliver irriteret eller modstanderisk, når andre vil bestemme retningen for mig.',
     'text_en': 'I become irritated or resistant when others want to decide my direction.'},
    {'id': 'A7', 'section': 'A', 'field': 'mening', 'is_reverse': True,
     'text_da': 'Jeg kan godt motivere mig selv, selvom jeg ikke helt kan se pointen.',
     'text_en': 'I can motivate myself even when I cannot quite see the point.'},
    {'id': 'A8', 'section': 'A', 'field': 'mening', 'is_reverse': False,
     'text_da': 'Jeg føler mig ofte tom eller ligeglad i forhold til det, jeg laver.',
     'text_en': 'I often feel empty or indifferent about what I do.'},

    # Kan (A9-A12)
    {'id': 'A9', 'section': 'A', 'field': 'kan', 'is_reverse': False,
     'text_da': 'Jeg tvivler ofte på, om jeg kan løse de opgaver, jeg står med.',
     'text_en': 'I often doubt whether I can solve the tasks I face.'},
    {'id': 'A10', 'section': 'A', 'field': 'kan', 'is_reverse': False,
     'text_da': 'Jeg mister nemt modet, hvis jeg ikke hurtigt kan se, hvordan jeg skal gribe noget an.',
     'text_en': 'I easily lose courage if I cannot quickly see how to approach something.'},
    {'id': 'A11', 'section': 'A', 'field': 'kan', 'is_reverse': True,
     'text_da': 'Jeg føler mig som udgangspunkt kompetent i det meste af det, jeg laver.',
     'text_en': 'I fundamentally feel competent in most of what I do.'},
    {'id': 'A12', 'section': 'A', 'field': 'kan', 'is_reverse': False,
     'text_da': 'Hvis noget er vigtigt, men svært, tænker jeg ofte: "Det kan jeg nok ikke."',
     'text_en': 'If something is important but difficult, I often think: "I probably cannot do that."'},

    # Besvær (A13-A16)
    {'id': 'A13', 'section': 'A', 'field': 'besvaer', 'is_reverse': False,
     'text_da': 'Jeg udskyder ofte opgaver, selv når jeg godt ved, de er vigtige.',
     'text_en': 'I often postpone tasks, even when I know they are important.'},
    {'id': 'A14', 'section': 'A', 'field': 'besvaer', 'is_reverse': False,
     'text_da': 'Jeg bliver hurtigt drænet af praktiske trin, struktur og systemer.',
     'text_en': 'I quickly get drained by practical steps, structure and systems.'},
    {'id': 'A15', 'section': 'A', 'field': 'besvaer', 'is_reverse': True,
     'text_da': 'Jeg går som regel bare i gang, selvom noget virker lidt bøvlet.',
     'text_en': 'I usually just get started, even if something seems a bit troublesome.'},
    {'id': 'A16', 'section': 'A', 'field': 'besvaer', 'is_reverse': False,
     'text_da': 'Når en opgave virker omfattende, mister jeg ofte lysten til at gå i gang.',
     'text_en': 'When a task seems extensive, I often lose the desire to start.'},

    # ================================================
    # SEKTION B: BÅNDBREDDE-PROBLEMER (32 items)
    # ================================================

    # B1-B4: Biologi → Emotion (opad)
    {'id': 'B1', 'section': 'B', 'transition': 'bio_emo', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Min krop reagerer (hjerte, mave, spænding), før jeg ved, hvad jeg føler.',
     'text_en': 'My body reacts (heart, stomach, tension) before I know what I feel.'},
    {'id': 'B2', 'section': 'B', 'transition': 'bio_emo', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Jeg har svært ved at skelne mellem kropslige signaler (fx sult, træthed, angst).',
     'text_en': 'I have difficulty distinguishing between bodily signals (e.g., hunger, fatigue, anxiety).'},
    {'id': 'B3', 'section': 'B', 'transition': 'bio_emo', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Jeg opdager ofte først mine følelser ved at mærke kroppen.',
     'text_en': 'I often first discover my feelings by noticing my body.'},
    {'id': 'B4', 'section': 'B', 'transition': 'bio_emo', 'direction': 'up', 'is_reverse': True,
     'text_da': 'Når min krop reagerer, ved jeg som regel ret hurtigt, hvad følelsen handler om.',
     'text_en': 'When my body reacts, I usually know fairly quickly what the feeling is about.'},

    # B5-B8: Emotion → Indre (opad)
    {'id': 'B5', 'section': 'B', 'transition': 'emo_indre', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Jeg bliver følelsesmæssigt overvældet uden at kunne sætte ord på hvorfor.',
     'text_en': 'I become emotionally overwhelmed without being able to put words to why.'},
    {'id': 'B6', 'section': 'B', 'transition': 'emo_indre', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Når jeg har det svært, er det svært at mærke, hvad det betyder for mig som person.',
     'text_en': 'When I struggle, it is hard to sense what it means for me as a person.'},
    {'id': 'B7', 'section': 'B', 'transition': 'emo_indre', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Jeg ved sjældent, hvad jeg har brug for, når jeg er følelsesmæssigt presset.',
     'text_en': 'I rarely know what I need when I am emotionally stressed.'},
    {'id': 'B8', 'section': 'B', 'transition': 'emo_indre', 'direction': 'up', 'is_reverse': True,
     'text_da': 'Når jeg føler noget stærkt, kan jeg tydeligt mærke, hvad det siger om mig og mine grænser.',
     'text_en': 'When I feel something strongly, I can clearly sense what it says about me and my boundaries.'},

    # B9-B12: Indre → Kognition (opad)
    {'id': 'B9', 'section': 'B', 'transition': 'indre_kog', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Når noget rammer mig personligt, mister jeg let overblikket.',
     'text_en': 'When something affects me personally, I easily lose perspective.'},
    {'id': 'B10', 'section': 'B', 'transition': 'indre_kog', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Jeg kan have det meget stærkt med noget, uden at kunne forklare det for andre.',
     'text_en': 'I can feel very strongly about something without being able to explain it to others.'},
    {'id': 'B11', 'section': 'B', 'transition': 'indre_kog', 'direction': 'up', 'is_reverse': True,
     'text_da': 'Jeg kan som regel godt tænke klart, selv når noget betyder meget for mig.',
     'text_en': 'I can usually think clearly, even when something means a lot to me.'},
    {'id': 'B12', 'section': 'B', 'transition': 'indre_kog', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Jeg har svært ved at forstå mig selv i situationer, hvor jeg bliver ramt på min værdighed.',
     'text_en': 'I have difficulty understanding myself in situations where my dignity is affected.'},

    # B13-B16: Kognition → Ekstern (opad)
    {'id': 'B13', 'section': 'B', 'transition': 'kog_ekstern', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Jeg ved præcis, hvad jeg burde gøre, men får det alligevel ikke gjort.',
     'text_en': 'I know exactly what I should do, but still cannot get it done.'},
    {'id': 'B14', 'section': 'B', 'transition': 'kog_ekstern', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Jeg kan lave detaljerede planer, som jeg bagefter ikke får fulgt.',
     'text_en': 'I can make detailed plans that I afterwards do not follow.'},
    {'id': 'B15', 'section': 'B', 'transition': 'kog_ekstern', 'direction': 'up', 'is_reverse': True,
     'text_da': 'Når jeg først har besluttet mig, er jeg god til at omsætte det til handling.',
     'text_en': 'Once I have decided, I am good at turning it into action.'},
    {'id': 'B16', 'section': 'B', 'transition': 'kog_ekstern', 'direction': 'up', 'is_reverse': False,
     'text_da': 'Jeg fryser eller går i stå, når jeg skal udføre noget, der betyder noget for mig.',
     'text_en': 'I freeze or stall when I have to do something that matters to me.'},

    # B17-B20: Ekstern → Kognition (nedad)
    {'id': 'B17', 'section': 'B', 'transition': 'ekstern_kog', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Når andre forklarer mig noget vigtigt, lukker jeg nemt ned indeni.',
     'text_en': 'When others explain something important to me, I easily shut down inside.'},
    {'id': 'B18', 'section': 'B', 'transition': 'ekstern_kog', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Jeg bliver ofte mere forvirret end hjulpet af andres instruktioner eller råd.',
     'text_en': 'I often become more confused than helped by others\' instructions or advice.'},
    {'id': 'B19', 'section': 'B', 'transition': 'ekstern_kog', 'direction': 'down', 'is_reverse': True,
     'text_da': 'Jeg kan typisk nemt omsætte input udefra til noget, jeg forstår og kan bruge.',
     'text_en': 'I can typically easily convert external input into something I understand and can use.'},
    {'id': 'B20', 'section': 'B', 'transition': 'ekstern_kog', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Når nogen giver mig feedback, har jeg svært ved at integrere det, selv hvis jeg er enig.',
     'text_en': 'When someone gives me feedback, I have difficulty integrating it, even if I agree.'},

    # B21-B24: Kognition → Indre (nedad)
    {'id': 'B21', 'section': 'B', 'transition': 'kog_indre', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Jeg kan rationelt forstå noget, uden at det føles sandt for mig.',
     'text_en': 'I can rationally understand something without it feeling true to me.'},
    {'id': 'B22', 'section': 'B', 'transition': 'kog_indre', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Jeg ved godt, at noget "bare er sådan", men min indre reaktion ændrer sig ikke.',
     'text_en': 'I know that something "just is", but my inner reaction does not change.'},
    {'id': 'B23', 'section': 'B', 'transition': 'kog_indre', 'direction': 'down', 'is_reverse': True,
     'text_da': 'Når jeg har forstået noget vigtigt, kan jeg som regel mærke det som en ændring i mig.',
     'text_en': 'When I have understood something important, I can usually feel it as a change in me.'},
    {'id': 'B24', 'section': 'B', 'transition': 'kog_indre', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Jeg kan ofte forklare noget klogt, som overhovedet ikke ændrer, hvordan jeg har det.',
     'text_en': 'I can often explain something wisely that does not change how I feel at all.'},

    # B25-B28: Indre → Emotion (nedad)
    {'id': 'B25', 'section': 'B', 'transition': 'indre_emo', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Jeg ved godt, hvad jeg står for, men følelsesmæssigt føles det nogle gange fladt.',
     'text_en': 'I know what I stand for, but emotionally it sometimes feels flat.'},
    {'id': 'B26', 'section': 'B', 'transition': 'indre_emo', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Jeg kan opleve, at jeg "burde føle noget", men ikke rigtig kan.',
     'text_en': 'I can experience that I "should feel something" but cannot really.'},
    {'id': 'B27', 'section': 'B', 'transition': 'indre_emo', 'direction': 'down', 'is_reverse': True,
     'text_da': 'Når noget er vigtigt for mig, kan jeg tydeligt mærke følelsen, der hører til.',
     'text_en': 'When something is important to me, I can clearly feel the emotion that belongs to it.'},
    {'id': 'B28', 'section': 'B', 'transition': 'indre_emo', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Jeg kan have en stærk holdning uden at mærke nogen særlig følelse for den.',
     'text_en': 'I can have a strong opinion without feeling any particular emotion about it.'},

    # B29-B32: Emotion → Biologi (nedad)
    {'id': 'B29', 'section': 'B', 'transition': 'emo_bio', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Når jeg bliver følelsesmæssigt presset, kan jeg ikke få kroppen til at falde ned igen.',
     'text_en': 'When I become emotionally stressed, I cannot get my body to calm down again.'},
    {'id': 'B30', 'section': 'B', 'transition': 'emo_bio', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Følelsesmæssigt pres sætter sig hurtigt som kropslige spændinger eller symptomer.',
     'text_en': 'Emotional stress quickly manifests as bodily tensions or symptoms.'},
    {'id': 'B31', 'section': 'B', 'transition': 'emo_bio', 'direction': 'down', 'is_reverse': True,
     'text_da': 'Når jeg får det bedre følelsesmæssigt, kan min krop også let slippe spændingen.',
     'text_en': 'When I feel better emotionally, my body can also easily release the tension.'},
    {'id': 'B32', 'section': 'B', 'transition': 'emo_bio', 'direction': 'down', 'is_reverse': False,
     'text_da': 'Jeg kan holde stærke følelser inde længe, indtil kroppen "eksploderer".',
     'text_en': 'I can hold strong feelings inside for a long time until my body "explodes".'},

    # ================================================
    # SEKTION C: MANIFESTATIONSLAG (10 items)
    # ================================================

    {'id': 'C1', 'section': 'C', 'layer': 'biologi', 'is_reverse': False,
     'text_da': 'Det første, jeg lægger mærke til, er kroppen (søvn, mave, spænding, hovedpine).',
     'text_en': 'The first thing I notice is my body (sleep, stomach, tension, headache).'},
    {'id': 'C2', 'section': 'C', 'layer': 'emotion', 'is_reverse': False,
     'text_da': 'Det første, jeg lægger mærke til, er stærke følelser (vrede, tristhed, opgivenhed).',
     'text_en': 'The first thing I notice is strong emotions (anger, sadness, giving up).'},
    {'id': 'C3', 'section': 'C', 'layer': 'kognition', 'is_reverse': False,
     'text_da': 'Det første, jeg lægger mærke til, er at jeg begynder at tænke hårdt eller køre i ring.',
     'text_en': 'The first thing I notice is that I start thinking hard or going in circles.'},
    {'id': 'C4', 'section': 'C', 'layer': 'indre', 'is_reverse': False,
     'text_da': 'Det første, jeg lægger mærke til, er skam, selvkritik eller følelsen af at være forkert.',
     'text_en': 'The first thing I notice is shame, self-criticism, or the feeling of being wrong.'},
    {'id': 'C5', 'section': 'C', 'layer': 'ekstern', 'is_reverse': False,
     'text_da': 'Det første, jeg lægger mærke til, er at jeg ændrer på min adfærd (trækker mig, overspiser, flygter, arbejder mere).',
     'text_en': 'The first thing I notice is that I change my behavior (withdraw, overeat, flee, work more).'},
    {'id': 'C6', 'section': 'C', 'layer': 'biologi', 'is_reverse': False,
     'text_da': 'Under pres får jeg oftest fysiske symptomer.',
     'text_en': 'Under pressure, I most often get physical symptoms.'},
    {'id': 'C7', 'section': 'C', 'layer': 'emotion', 'is_reverse': False,
     'text_da': 'Under pres reagerer jeg mest følelsesmæssigt.',
     'text_en': 'Under pressure, I react most emotionally.'},
    {'id': 'C8', 'section': 'C', 'layer': 'kognition', 'is_reverse': False,
     'text_da': 'Under pres går jeg mest i mit eget hoved.',
     'text_en': 'Under pressure, I mostly go into my own head.'},
    {'id': 'C9', 'section': 'C', 'layer': 'indre', 'is_reverse': False,
     'text_da': 'Under pres bliver jeg hård ved mig selv.',
     'text_en': 'Under pressure, I become hard on myself.'},
    {'id': 'C10', 'section': 'C', 'layer': 'ekstern', 'is_reverse': False,
     'text_da': 'Under pres ændrer jeg helst på omgivelserne (aflyser, skifter opgave, skifter relation, laver rod/orden).',
     'text_en': 'Under pressure, I prefer to change my surroundings (cancel, switch tasks, switch relationships, create mess/order).'},

    # ================================================
    # SEKTION D: REGULERINGSSTRATEGIER (12 items)
    # ================================================

    {'id': 'D1', 'section': 'D', 'strategy': 'kropslig', 'is_reverse': False,
     'text_da': 'Når jeg skal berolige mig selv, gør jeg typisk noget med min krop (spiser, bevæger mig, lægger mig, skærm osv.).',
     'text_en': 'When I need to calm myself, I typically do something with my body (eat, move, lie down, screen, etc.).'},
    {'id': 'D2', 'section': 'D', 'strategy': 'emotionel', 'is_reverse': False,
     'text_da': 'Når jeg får det svært, reagerer jeg mest gennem følelser (gråd, vrede, følelsesudbrud eller følelseslukning).',
     'text_en': 'When I struggle, I mostly react through emotions (crying, anger, emotional outbursts, or emotional shutdown).'},
    {'id': 'D3', 'section': 'D', 'strategy': 'indre', 'is_reverse': False,
     'text_da': 'Når jeg får det svært, går jeg mest i selvfortællinger om, hvem jeg er ("jeg er dum", "jeg skal tage mig sammen", "jeg dur ikke").',
     'text_en': 'When I struggle, I mostly go into self-narratives about who I am ("I am stupid", "I need to pull myself together", "I am no good").'},
    {'id': 'D4', 'section': 'D', 'strategy': 'kognitiv', 'is_reverse': False,
     'text_da': 'Når jeg får det svært, prøver jeg at få styr på det ved at analysere, forstå og planlægge.',
     'text_en': 'When I struggle, I try to get control by analyzing, understanding, and planning.'},
    {'id': 'D5', 'section': 'D', 'strategy': 'ekstern', 'is_reverse': False,
     'text_da': 'Når jeg får det svært, ændrer jeg ofte på mine omgivelser (skifter opgave, rydder op/roder, flytter mig, skifter relation).',
     'text_en': 'When I struggle, I often change my surroundings (switch tasks, tidy up/make a mess, move, change relationships).'},
    {'id': 'D6', 'section': 'D', 'strategy': 'kropslig', 'is_reverse': False,
     'text_da': 'Jeg søger ofte lindring gennem mad, nikotin, alkohol, skærm eller lignende.',
     'text_en': 'I often seek relief through food, nicotine, alcohol, screens, or similar.'},
    {'id': 'D7', 'section': 'D', 'strategy': 'emotionel', 'is_reverse': False,
     'text_da': 'Jeg søger ofte lindring ved at tale med nogen om, hvordan jeg har det.',
     'text_en': 'I often seek relief by talking to someone about how I feel.'},
    {'id': 'D8', 'section': 'D', 'strategy': 'indre', 'is_reverse': False,
     'text_da': 'Jeg søger ofte lindring ved at trække mig og være alene.',
     'text_en': 'I often seek relief by withdrawing and being alone.'},
    {'id': 'D9', 'section': 'D', 'strategy': 'kognitiv', 'is_reverse': False,
     'text_da': 'Jeg søger ofte lindring ved at arbejde mere eller gøre mig ekstra umage.',
     'text_en': 'I often seek relief by working more or making an extra effort.'},
    {'id': 'D10', 'section': 'D', 'strategy': 'ekstern', 'is_reverse': False,
     'text_da': 'Jeg søger ofte lindring ved at ignorere det og "køre videre".',
     'text_en': 'I often seek relief by ignoring it and "moving on".'},
    {'id': 'D11', 'section': 'D', 'strategy': 'robusthed', 'is_reverse': True,
     'text_da': 'Jeg har mindst én strategi, der næsten altid hjælper mig lidt.',
     'text_en': 'I have at least one strategy that almost always helps me a little.'},
    {'id': 'D12', 'section': 'D', 'strategy': 'robusthed', 'is_reverse': False,
     'text_da': 'Når jeg er meget presset, føles det, som om ingen strategier rigtig virker.',
     'text_en': 'When I am very stressed, it feels like no strategies really work.'},

    # ================================================
    # SEKTION E: OPAD-KAPACITET (8 items)
    # ================================================

    {'id': 'E1', 'section': 'E', 'transition': 'bio_emo', 'is_reverse': False,
     'text_da': 'Jeg kan mærke ret tydeligt, hvad min krop prøver at fortælle mig følelsesmæssigt.',
     'text_en': 'I can feel quite clearly what my body is trying to tell me emotionally.'},
    {'id': 'E2', 'section': 'E', 'transition': 'emo_indre', 'is_reverse': False,
     'text_da': 'Når jeg føler noget stærkt, kan jeg hurtigt mærke, hvad det betyder for mig som person.',
     'text_en': 'When I feel something strongly, I can quickly sense what it means for me as a person.'},
    {'id': 'E3', 'section': 'E', 'transition': 'indre_kog', 'is_reverse': False,
     'text_da': 'Selv når noget rammer mig dybt, kan jeg normalt forstå mig selv og sætte ord på det.',
     'text_en': 'Even when something affects me deeply, I can usually understand myself and put words to it.'},
    {'id': 'E4', 'section': 'E', 'transition': 'kog_ekstern', 'is_reverse': False,
     'text_da': 'Når jeg først har besluttet mig, er jeg god til at omsætte det til konkret handling.',
     'text_en': 'Once I have decided, I am good at turning it into concrete action.'},
    {'id': 'E5', 'section': 'E', 'transition': 'ekstern_kog', 'is_reverse': False,
     'text_da': 'Jeg kan typisk tage imod input/feedback fra andre og gøre det til noget, jeg forstår og kan bruge.',
     'text_en': 'I can typically receive input/feedback from others and turn it into something I understand and can use.'},
    {'id': 'E6', 'section': 'E', 'transition': 'kog_indre', 'is_reverse': False,
     'text_da': 'Når jeg virkelig forstår noget vigtigt, kan jeg mærke, at det forandrer noget i mig.',
     'text_en': 'When I truly understand something important, I can feel that it changes something in me.'},
    {'id': 'E7', 'section': 'E', 'transition': 'indre_emo', 'is_reverse': False,
     'text_da': 'Når noget stemmer med mine værdier, kan jeg mærke en tydelig følelsesmæssig resonans.',
     'text_en': 'When something aligns with my values, I can feel a clear emotional resonance.'},
    {'id': 'E8', 'section': 'E', 'transition': 'emo_bio', 'is_reverse': False,
     'text_da': 'Når jeg har stærke følelser, kan min krop godt få dem til at falde ned igen (fx via åndedræt, bevægelse, ro).',
     'text_en': 'When I have strong feelings, my body can help them calm down again (e.g., through breathing, movement, rest).'},

    # ================================================
    # SEKTION F: FORBRUGSMØNSTRE (10 items)
    # ================================================

    # Hyppigheds-items (F1-F7) - bruger frekvens-skala
    {'id': 'F1', 'section': 'F', 'subsection': 'frequency', 'category': 'stof', 'is_reverse': False,
     'text_da': 'Alkohol (øl, vin, spiritus)',
     'text_en': 'Alcohol (beer, wine, spirits)'},
    {'id': 'F2', 'section': 'F', 'subsection': 'frequency', 'category': 'stof', 'is_reverse': False,
     'text_da': 'Nikotin (cigaretter, snus, vape)',
     'text_en': 'Nicotine (cigarettes, snus, vape)'},
    {'id': 'F3', 'section': 'F', 'subsection': 'frequency', 'category': 'stof', 'is_reverse': False,
     'text_da': 'Koffein (kaffe, energidrik) for at regulere humør/energi',
     'text_en': 'Caffeine (coffee, energy drinks) to regulate mood/energy'},
    {'id': 'F4', 'section': 'F', 'subsection': 'frequency', 'category': 'adfaerd', 'is_reverse': False,
     'text_da': 'Mad som trøst eller belønning (udover sult)',
     'text_en': 'Food as comfort or reward (beyond hunger)'},
    {'id': 'F5', 'section': 'F', 'subsection': 'frequency', 'category': 'adfaerd', 'is_reverse': False,
     'text_da': 'Skærm/gaming/scrolling for at koble af eller flygte',
     'text_en': 'Screen/gaming/scrolling to relax or escape'},
    {'id': 'F6', 'section': 'F', 'subsection': 'frequency', 'category': 'adfaerd', 'is_reverse': False,
     'text_da': 'Shopping eller køb af ting for at føle dig bedre',
     'text_en': 'Shopping or buying things to feel better'},
    {'id': 'F7', 'section': 'F', 'subsection': 'frequency', 'category': 'adfaerd', 'is_reverse': False,
     'text_da': 'Søvn/ligge i sengen for at undgå noget',
     'text_en': 'Sleep/lying in bed to avoid something'},

    # Afhængigheds-items (F8-F10)
    {'id': 'F8', 'section': 'F', 'subsection': 'dependency', 'is_reverse': False,
     'text_da': 'Jeg har brug for "noget" (mad, skærm, alkohol, rygning el.lign.) for at falde ned efter en hård dag.',
     'text_en': 'I need "something" (food, screen, alcohol, smoking, etc.) to calm down after a hard day.'},
    {'id': 'F9', 'section': 'F', 'subsection': 'dependency', 'is_reverse': False,
     'text_da': 'Uden mine vaner ville jeg have svært ved at fungere i hverdagen.',
     'text_en': 'Without my habits, I would have difficulty functioning in everyday life.'},
    {'id': 'F10', 'section': 'F', 'subsection': 'dependency', 'is_reverse': False,
     'text_da': 'Jeg ved godt, at nogle af mine vaner ikke er gode for mig, men jeg kan ikke stoppe.',
     'text_en': 'I know that some of my habits are not good for me, but I cannot stop.'},
]


# ========================================
# DATABASE INITIALIZATION
# ========================================

def init_friktionsprofil_tables():
    """Initialize tables for Screening and Deep Measurement"""
    with get_db() as conn:
        # ========================================
        # SCREENING TABLES
        # ========================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fp_screening_questions (
                id TEXT PRIMARY KEY,
                question_id TEXT NOT NULL UNIQUE,
                section TEXT NOT NULL,
                target TEXT NOT NULL,
                text_da TEXT NOT NULL,
                text_en TEXT,
                sort_order INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fp_screening_sessions (
                id TEXT PRIMARY KEY,
                person_name TEXT,
                person_email TEXT,
                customer_id TEXT,
                unit_id TEXT,
                context TEXT DEFAULT 'general',
                is_complete INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fp_screening_responses (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 7),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES fp_screening_sessions(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fp_screening_scores (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,

                -- Felter
                felt_tryghed INTEGER,
                felt_mening INTEGER,
                felt_kan INTEGER,
                felt_besvaer INTEGER,
                primaert_felt TEXT,

                -- Opad
                opad_bio_emo INTEGER,
                opad_emo_indre INTEGER,
                opad_indre_kog INTEGER,
                opad_kog_ekstern INTEGER,
                stop_punkt TEXT,

                -- Manifestation
                manifest_biologi INTEGER,
                manifest_emotion INTEGER,
                manifest_indre INTEGER,
                manifest_kognition INTEGER,
                manifest_ekstern INTEGER,
                primaert_lag TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES fp_screening_sessions(id) ON DELETE CASCADE
            )
        """)

        # ========================================
        # DEEP MEASUREMENT TABLES
        # ========================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fp_deep_questions (
                id TEXT PRIMARY KEY,
                question_id TEXT NOT NULL UNIQUE,
                section TEXT NOT NULL,
                field TEXT,
                layer TEXT,
                transition TEXT,
                direction TEXT,
                strategy TEXT,
                subsection TEXT,
                category TEXT,
                is_reverse INTEGER DEFAULT 0,
                text_da TEXT NOT NULL,
                text_en TEXT,
                sort_order INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fp_deep_sessions (
                id TEXT PRIMARY KEY,
                person_name TEXT,
                person_email TEXT,
                customer_id TEXT,
                unit_id TEXT,
                context TEXT DEFAULT 'general',
                is_complete INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fp_deep_responses (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 7),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES fp_deep_sessions(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fp_deep_scores (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,

                -- Felter
                field_tryghed REAL,
                field_mening REAL,
                field_kan REAL,
                field_besvaer REAL,

                -- Båndbredde-problemer (opad)
                problem_bio_emo REAL,
                problem_emo_indre REAL,
                problem_indre_kog REAL,
                problem_kog_ekstern REAL,

                -- Båndbredde-problemer (nedad)
                problem_ekstern_kog REAL,
                problem_kog_indre REAL,
                problem_indre_emo REAL,
                problem_emo_bio REAL,

                -- Opad-kapacitet
                kapacitet_bio_emo REAL,
                kapacitet_emo_indre REAL,
                kapacitet_indre_kog REAL,
                kapacitet_kog_ekstern REAL,
                kapacitet_ekstern_kog REAL,
                kapacitet_kog_indre REAL,
                kapacitet_indre_emo REAL,
                kapacitet_emo_bio REAL,

                -- Kombineret index
                index_bio_emo REAL,
                index_emo_indre REAL,
                index_indre_kog REAL,
                index_kog_ekstern REAL,
                index_ekstern_kog REAL,
                index_kog_indre REAL,
                index_indre_emo REAL,
                index_emo_bio REAL,

                -- Manifestation
                manifest_biologi REAL,
                manifest_emotion REAL,
                manifest_kognition REAL,
                manifest_indre REAL,
                manifest_ekstern REAL,

                -- Regulering
                reg_kropslig REAL,
                reg_emotionel REAL,
                reg_indre REAL,
                reg_kognitiv REAL,
                reg_ekstern REAL,
                reg_robusthed REAL,

                -- Forbrug
                forbrug_stof REAL,
                forbrug_adfaerd REAL,
                forbrug_total REAL,
                afhaengighed REAL,

                -- Meta-analyse
                primary_field TEXT,
                stop_point TEXT,
                primary_manifest TEXT,
                primary_regulation TEXT,
                chain_status TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES fp_deep_sessions(id) ON DELETE CASCADE
            )
        """)

        # Indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fp_screening_responses_session ON fp_screening_responses(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fp_deep_responses_session ON fp_deep_responses(session_id)")

        # Seed questions if empty
        count = conn.execute("SELECT COUNT(*) as cnt FROM fp_screening_questions").fetchone()['cnt']
        if count == 0:
            _seed_screening_questions(conn)

        count = conn.execute("SELECT COUNT(*) as cnt FROM fp_deep_questions").fetchone()['cnt']
        if count == 0:
            _seed_deep_questions(conn)


def _seed_screening_questions(conn):
    """Seed screening questions"""
    for i, q in enumerate(SCREENING_QUESTIONS):
        conn.execute("""
            INSERT INTO fp_screening_questions (id, question_id, section, target, text_da, text_en, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (f"sq-{q['id']}", q['id'], q['section'], q['target'], q['text_da'], q.get('text_en'), i + 1))


def _seed_deep_questions(conn):
    """Seed deep measurement questions"""
    for i, q in enumerate(DEEP_QUESTIONS):
        conn.execute("""
            INSERT INTO fp_deep_questions
            (id, question_id, section, field, layer, transition, direction, strategy, subsection, category, is_reverse, text_da, text_en, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"dq-{q['id']}",
            q['id'],
            q['section'],
            q.get('field'),
            q.get('layer'),
            q.get('transition'),
            q.get('direction'),
            q.get('strategy'),
            q.get('subsection'),
            q.get('category'),
            1 if q.get('is_reverse') else 0,
            q['text_da'],
            q.get('text_en'),
            i + 1
        ))


# ========================================
# SCREENING FUNCTIONS
# ========================================

def get_screening_questions() -> List[Dict]:
    """Get all screening questions in order"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM fp_screening_questions ORDER BY sort_order
        """).fetchall()
        return [dict(row) for row in rows]


def create_screening_session(
    person_name: Optional[str] = None,
    person_email: Optional[str] = None,
    customer_id: Optional[str] = None,
    unit_id: Optional[str] = None,
    context: str = 'general'
) -> str:
    """Create new screening session"""
    session_id = f"scr-{secrets.token_urlsafe(12)}"
    with get_db() as conn:
        conn.execute("""
            INSERT INTO fp_screening_sessions (id, person_name, person_email, customer_id, unit_id, context)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, person_name, person_email, customer_id, unit_id, context))
    return session_id


def save_screening_responses(session_id: str, responses: Dict[str, int]):
    """Save screening responses and calculate scores"""
    with get_db() as conn:
        # Save individual responses
        for question_id, score in responses.items():
            resp_id = f"sr-{secrets.token_urlsafe(8)}"
            conn.execute("""
                INSERT INTO fp_screening_responses (id, session_id, question_id, score)
                VALUES (?, ?, ?, ?)
            """, (resp_id, session_id, question_id, score))

        # Mark session complete
        conn.execute("""
            UPDATE fp_screening_sessions
            SET is_complete = 1, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (session_id,))

        # Calculate and save scores
        _calculate_screening_scores(conn, session_id, responses)


def _calculate_screening_scores(conn, session_id: str, responses: Dict[str, int]):
    """Calculate screening scores from responses"""
    # Extract scores
    felt_tryghed = responses.get('S1', 4)
    felt_mening = responses.get('S2', 4)
    felt_kan = responses.get('S3', 4)
    felt_besvaer = responses.get('S4', 4)

    opad_emo_indre = responses.get('S5', 4)
    opad_indre_kog = responses.get('S6', 4)
    opad_kog_ekstern = responses.get('S7', 4)
    opad_bio_emo = responses.get('S8', 4)

    manifest_biologi = responses.get('S9', 4)
    manifest_emotion = responses.get('S10', 4)
    manifest_indre = responses.get('S11', 4)
    manifest_kognition = responses.get('S12', 4)
    manifest_ekstern = responses.get('S13', 4)

    # Find primary values
    felter = {'tryghed': felt_tryghed, 'mening': felt_mening, 'kan': felt_kan, 'besvaer': felt_besvaer}
    primaert_felt = max(felter, key=felter.get)

    opad = {'bio_emo': opad_bio_emo, 'emo_indre': opad_emo_indre, 'indre_kog': opad_indre_kog, 'kog_ekstern': opad_kog_ekstern}
    stop_punkt = max(opad, key=opad.get)

    manifest = {'biologi': manifest_biologi, 'emotion': manifest_emotion, 'indre': manifest_indre,
                'kognition': manifest_kognition, 'ekstern': manifest_ekstern}
    primaert_lag = max(manifest, key=manifest.get)

    # Save scores
    score_id = f"ss-{secrets.token_urlsafe(8)}"
    conn.execute("""
        INSERT INTO fp_screening_scores
        (id, session_id, felt_tryghed, felt_mening, felt_kan, felt_besvaer, primaert_felt,
         opad_bio_emo, opad_emo_indre, opad_indre_kog, opad_kog_ekstern, stop_punkt,
         manifest_biologi, manifest_emotion, manifest_indre, manifest_kognition, manifest_ekstern, primaert_lag)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (score_id, session_id, felt_tryghed, felt_mening, felt_kan, felt_besvaer, primaert_felt,
          opad_bio_emo, opad_emo_indre, opad_indre_kog, opad_kog_ekstern, stop_punkt,
          manifest_biologi, manifest_emotion, manifest_indre, manifest_kognition, manifest_ekstern, primaert_lag))


def get_screening_session(session_id: str) -> Optional[Dict]:
    """Get screening session with scores"""
    with get_db() as conn:
        session = conn.execute("""
            SELECT s.*, sc.*
            FROM fp_screening_sessions s
            LEFT JOIN fp_screening_scores sc ON s.id = sc.session_id
            WHERE s.id = ?
        """, (session_id,)).fetchone()
        return dict(session) if session else None


# ========================================
# DEEP MEASUREMENT FUNCTIONS
# ========================================

def get_deep_questions(section: Optional[str] = None) -> List[Dict]:
    """Get deep measurement questions, optionally filtered by section"""
    with get_db() as conn:
        if section:
            rows = conn.execute("""
                SELECT * FROM fp_deep_questions WHERE section = ? ORDER BY sort_order
            """, (section,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM fp_deep_questions ORDER BY sort_order
            """).fetchall()
        return [dict(row) for row in rows]


def create_deep_session(
    person_name: Optional[str] = None,
    person_email: Optional[str] = None,
    customer_id: Optional[str] = None,
    unit_id: Optional[str] = None,
    context: str = 'general'
) -> str:
    """Create new deep measurement session"""
    session_id = f"deep-{secrets.token_urlsafe(12)}"
    with get_db() as conn:
        conn.execute("""
            INSERT INTO fp_deep_sessions (id, person_name, person_email, customer_id, unit_id, context)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, person_name, person_email, customer_id, unit_id, context))
    return session_id


def save_deep_responses(session_id: str, responses: Dict[str, int]):
    """Save deep measurement responses and calculate scores"""
    with get_db() as conn:
        # Save individual responses
        for question_id, score in responses.items():
            resp_id = f"dr-{secrets.token_urlsafe(8)}"
            conn.execute("""
                INSERT INTO fp_deep_responses (id, session_id, question_id, score)
                VALUES (?, ?, ?, ?)
            """, (resp_id, session_id, question_id, score))

        # Mark session complete
        conn.execute("""
            UPDATE fp_deep_sessions
            SET is_complete = 1, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (session_id,))

        # Get question metadata for scoring
        questions = {q['question_id']: q for q in get_deep_questions()}

        # Calculate and save scores
        _calculate_deep_scores(conn, session_id, responses, questions)


def _calculate_deep_scores(conn, session_id: str, responses: Dict[str, int], questions: Dict):
    """Calculate deep measurement scores from responses"""

    def get_score(qid: str) -> float:
        """Get score, applying reverse scoring if needed"""
        raw = responses.get(qid, 4)
        if questions.get(qid, {}).get('is_reverse'):
            return 8 - raw
        return raw

    def mean(scores: List[float]) -> float:
        """Calculate mean of scores"""
        return sum(scores) / len(scores) if scores else 0

    # ========================================
    # SECTION A: Fields
    # ========================================
    field_tryghed = mean([get_score(f'A{i}') for i in range(1, 5)])
    field_mening = mean([get_score(f'A{i}') for i in range(5, 9)])
    field_kan = mean([get_score(f'A{i}') for i in range(9, 13)])
    field_besvaer = mean([get_score(f'A{i}') for i in range(13, 17)])

    # ========================================
    # SECTION B: Bandwidth problems
    # ========================================
    # Opad
    problem_bio_emo = mean([get_score(f'B{i}') for i in range(1, 5)])
    problem_emo_indre = mean([get_score(f'B{i}') for i in range(5, 9)])
    problem_indre_kog = mean([get_score(f'B{i}') for i in range(9, 13)])
    problem_kog_ekstern = mean([get_score(f'B{i}') for i in range(13, 17)])

    # Nedad
    problem_ekstern_kog = mean([get_score(f'B{i}') for i in range(17, 21)])
    problem_kog_indre = mean([get_score(f'B{i}') for i in range(21, 25)])
    problem_indre_emo = mean([get_score(f'B{i}') for i in range(25, 29)])
    problem_emo_bio = mean([get_score(f'B{i}') for i in range(29, 33)])

    # ========================================
    # SECTION C: Manifestation
    # ========================================
    manifest_biologi = mean([get_score('C1'), get_score('C6')])
    manifest_emotion = mean([get_score('C2'), get_score('C7')])
    manifest_kognition = mean([get_score('C3'), get_score('C8')])
    manifest_indre = mean([get_score('C4'), get_score('C9')])
    manifest_ekstern = mean([get_score('C5'), get_score('C10')])

    # ========================================
    # SECTION D: Regulation
    # ========================================
    reg_kropslig = mean([get_score('D1'), get_score('D6')])
    reg_emotionel = mean([get_score('D2'), get_score('D7')])
    reg_indre = mean([get_score('D3'), get_score('D8')])
    reg_kognitiv = mean([get_score('D4'), get_score('D9')])
    reg_ekstern = mean([get_score('D5'), get_score('D10')])
    reg_robusthed = mean([get_score('D11'), get_score('D12')])

    # ========================================
    # SECTION E: Capacity
    # ========================================
    kapacitet_bio_emo = get_score('E1')
    kapacitet_emo_indre = get_score('E2')
    kapacitet_indre_kog = get_score('E3')
    kapacitet_kog_ekstern = get_score('E4')
    kapacitet_ekstern_kog = get_score('E5')
    kapacitet_kog_indre = get_score('E6')
    kapacitet_indre_emo = get_score('E7')
    kapacitet_emo_bio = get_score('E8')

    # ========================================
    # COMBINED INDEX (capacity + inverse problem) / 2
    # ========================================
    def opad_index(kap, prob):
        return (kap + (8 - prob)) / 2

    index_bio_emo = opad_index(kapacitet_bio_emo, problem_bio_emo)
    index_emo_indre = opad_index(kapacitet_emo_indre, problem_emo_indre)
    index_indre_kog = opad_index(kapacitet_indre_kog, problem_indre_kog)
    index_kog_ekstern = opad_index(kapacitet_kog_ekstern, problem_kog_ekstern)
    index_ekstern_kog = opad_index(kapacitet_ekstern_kog, problem_ekstern_kog)
    index_kog_indre = opad_index(kapacitet_kog_indre, problem_kog_indre)
    index_indre_emo = opad_index(kapacitet_indre_emo, problem_indre_emo)
    index_emo_bio = opad_index(kapacitet_emo_bio, problem_emo_bio)

    # ========================================
    # SECTION F: Consumption
    # ========================================
    forbrug_stof = mean([get_score('F1'), get_score('F2'), get_score('F3')])
    forbrug_adfaerd = mean([get_score('F4'), get_score('F5'), get_score('F6'), get_score('F7')])
    forbrug_total = mean([get_score(f'F{i}') for i in range(1, 8)])
    afhaengighed = mean([get_score('F8'), get_score('F9'), get_score('F10')])

    # ========================================
    # META ANALYSIS
    # ========================================
    # Primary field
    fields = {'tryghed': field_tryghed, 'mening': field_mening, 'kan': field_kan, 'besvaer': field_besvaer}
    primary_field = max(fields, key=fields.get)

    # Stop point (lowest opad index)
    indexes = {
        'bio_emo': index_bio_emo, 'emo_indre': index_emo_indre,
        'indre_kog': index_indre_kog, 'kog_ekstern': index_kog_ekstern
    }
    stop_point = min(indexes, key=indexes.get)

    # Primary manifestation
    manifests = {
        'biologi': manifest_biologi, 'emotion': manifest_emotion,
        'indre': manifest_indre, 'kognition': manifest_kognition, 'ekstern': manifest_ekstern
    }
    primary_manifest = max(manifests, key=manifests.get)

    # Primary regulation
    regs = {
        'kropslig': reg_kropslig, 'emotionel': reg_emotionel,
        'indre': reg_indre, 'kognitiv': reg_kognitiv, 'ekstern': reg_ekstern
    }
    primary_regulation = max(regs, key=regs.get)

    # Chain status
    min_index = min(indexes.values())
    if min_index >= 4.5:
        chain_status = 'intact'
    elif min_index >= 2.5:
        chain_status = 'partial'
    else:
        chain_status = 'broken'

    # Save scores
    score_id = f"ds-{secrets.token_urlsafe(8)}"
    conn.execute("""
        INSERT INTO fp_deep_scores
        (id, session_id,
         field_tryghed, field_mening, field_kan, field_besvaer,
         problem_bio_emo, problem_emo_indre, problem_indre_kog, problem_kog_ekstern,
         problem_ekstern_kog, problem_kog_indre, problem_indre_emo, problem_emo_bio,
         kapacitet_bio_emo, kapacitet_emo_indre, kapacitet_indre_kog, kapacitet_kog_ekstern,
         kapacitet_ekstern_kog, kapacitet_kog_indre, kapacitet_indre_emo, kapacitet_emo_bio,
         index_bio_emo, index_emo_indre, index_indre_kog, index_kog_ekstern,
         index_ekstern_kog, index_kog_indre, index_indre_emo, index_emo_bio,
         manifest_biologi, manifest_emotion, manifest_kognition, manifest_indre, manifest_ekstern,
         reg_kropslig, reg_emotionel, reg_indre, reg_kognitiv, reg_ekstern, reg_robusthed,
         forbrug_stof, forbrug_adfaerd, forbrug_total, afhaengighed,
         primary_field, stop_point, primary_manifest, primary_regulation, chain_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (score_id, session_id,
          field_tryghed, field_mening, field_kan, field_besvaer,
          problem_bio_emo, problem_emo_indre, problem_indre_kog, problem_kog_ekstern,
          problem_ekstern_kog, problem_kog_indre, problem_indre_emo, problem_emo_bio,
          kapacitet_bio_emo, kapacitet_emo_indre, kapacitet_indre_kog, kapacitet_kog_ekstern,
          kapacitet_ekstern_kog, kapacitet_kog_indre, kapacitet_indre_emo, kapacitet_emo_bio,
          index_bio_emo, index_emo_indre, index_indre_kog, index_kog_ekstern,
          index_ekstern_kog, index_kog_indre, index_indre_emo, index_emo_bio,
          manifest_biologi, manifest_emotion, manifest_kognition, manifest_indre, manifest_ekstern,
          reg_kropslig, reg_emotionel, reg_indre, reg_kognitiv, reg_ekstern, reg_robusthed,
          forbrug_stof, forbrug_adfaerd, forbrug_total, afhaengighed,
          primary_field, stop_point, primary_manifest, primary_regulation, chain_status))


def get_deep_session(session_id: str) -> Optional[Dict]:
    """Get deep session with all scores"""
    with get_db() as conn:
        session = conn.execute("""
            SELECT s.*, sc.*
            FROM fp_deep_sessions s
            LEFT JOIN fp_deep_scores sc ON s.id = sc.session_id
            WHERE s.id = ?
        """, (session_id,)).fetchone()
        return dict(session) if session else None


# ========================================
# INITIALIZATION
# ========================================

if __name__ == "__main__":
    print("Initialiserer friktionsprofil-tabeller...")
    init_friktionsprofil_tables()
    print("Done!")

    with get_db() as conn:
        screening_count = conn.execute("SELECT COUNT(*) FROM fp_screening_questions").fetchone()[0]
        deep_count = conn.execute("SELECT COUNT(*) FROM fp_deep_questions").fetchone()[0]
        print(f"Screening spørgsmål: {screening_count}")
        print(f"Dyb måling spørgsmål: {deep_count}")

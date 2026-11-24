"""Québec French for every preset name in ``app/profiles.py`` and ``app/seed.py``.

Why a map instead of bilingual rows: a preset name becomes an ordinary
definition row the moment an account is seeded, and from then on it is *the
person's data* — they can rename it, and history and CSV exports quote it. A
French account is therefore seeded with French names (``seed_catalog`` looks them
up here), and switching language afterwards changes the app's chrome but never
re-labels rows that already exist. Nothing silently rewrites someone's diary.

The wording is what a Québec physiotherapist says, not a literal translation:
*plancher pelvien*, *fuite d'urine*, *envie pressante*, *chaudière*, *mal au bas
du dos*. Where two spellings are common, the one a patient would recognise wins.

``tests/test_i18n.py`` walks every name in every profile and in the suggestion
pool and fails if one is missing here, so "fully translated" stays a checked
property as the catalogues grow.
"""

from __future__ import annotations

#: English preset name (the spelling used in ``profiles.py``) -> Québec French.
#: Keys are matched exactly, so a typo here is a test failure rather than a
#: silently English button in a French account.
PRESET_NAMES_FR: dict[str, str] = {
    # -- exercises -------------------------------------------------------
    "Adductor Squeeze": "Presse d'adducteurs",
    "Ankle Pumps": "Pompes de cheville",
    "Band Row": "Tirage à l'élastique",
    "Bird Dog": "Chien-chasseur à quatre pattes",
    "Bridge Marching": "Marche sur pont fessier",
    "Calf Raise": "Élévation sur la pointe des pieds",
    "Bowel Posture Reset": "Reprendre une bonne posture pour la selle",
    "Cat-Camel": "Dos rond / dos creusé",
    "Chin Tuck": "Rentrée du menton",
    "Climbing Stairs": "Monter les escaliers",
    "Clamshell": "Coquillage",
    "Dead Bug (Modified)": "Insecte mort (modifié)",
    "Deep Core Draw-In": "Aspiration abdominale profonde",
    "Deep Squat Hold": "Maintien en flexion profonde",
    "Diaphragm Breathing": "Respiration diaphragmatique",
    "Doorway Pec Stretch": "Étirement des pectoraux au cadre de porte",
    "External Rotation": "Rotation externe de l'épaule",
    "Foam Roll": "Rouleau de détente",
    "Glute Bridge": "Pont fessier",
    "Half Squat": "Demi-flexion de genoux",
    "Half-Kneeling Chop": "Hachage à genou",
    "Hamstring Stretch": "Étirement des ischio-jambiers",
    "Hip Hinge Practice": "Pratique du mouvement de hanches",
    "Hip Flexor Stretch": "Étirement des fléchisseurs de la hanche",
    "IT Band Pain": "Douleur de la bandelette ilio-tibiale",
    "Long Hold Contractions": "Contractions en maintien long",
    "Nursing Posture Stretch": "Étirement de la posture d'allaitement",
    "Pelvic Floor Lifts": "Relèvements du plancher pelvien",
    "Pelvic Floor Release": "Relâchement du plancher pelvien",
    "Piriformis Stretch": "Étirement du piriforme",
    "Rapid Flicks": "Contractions rapides",
    "Scapular Squeeze": "Resserage des omoplates",
    "Serratus Wall Slide": "Glissement au mur pour le dentelé",
    "Shoulder Blade Setting": "Placement des omoplates",
    "Side Plank (Knees)": "Planche latérale sur les genoux",
    "Single-Leg Press": "Presse une jambe",
    "Stair Step-Ups": "Montées sur marches",
    "Step-Down Control": "Descente contrôlée d'une marche",
    "Suitcase Carry (Light)": "Marché porté (charge légère)",
    "Supine Marching": "Marche sur le dos",
    "Supported Squat": "Flexion de genoux appuyée",
    "Thoracic Extension over Roll": "Extension du haut du dos sur rouleau",
    "Wall Angels": "Ange au mur",
    # -- symptoms --------------------------------------------------------
    "Belly Domining": "Bombement du ventre (doming)",
    "Buttock Pain": "Douleur aux fesses",
    "Constipation": "Constipation",
    "Fatigue": "Fatigue",
    "Frequency": "Uriner souvent",
    "Gas or Bowel Leak": "Fuite de gaz ou de selles",
    "Giving-Way Feeling": "Sensation de cédement",
    "Headache": "Mal de tête",
    "Hemorrhoid Pain": "Douleur aux hémorroïdes",
    "Heaviness / Dragging": "Lourdeur / sensation de pesanteur",
    "Hip Pinching": "Pincement à la hanche",
    "Incomplete Bladder Emptying": "Vessie mal vidée",
    "Incomplete Emptying": "Évacuation incomplète",
    "Knee Pain": "Douleur au genou",
    "Kneecap Pain on Stairs": "Douleur à la rotule dans les escaliers",
    "Leak Before Reaching the Toilet": "Fuite avant d'arriver aux toilettes",
    "Leg Numbness or Tingling": "Engourdissement ou fourmillement à la jambe",
    "Low Back Pain": "Mal au bas du dos",
    "Morning Stiffness": "Raideur au réveil",
    "Neck & Shoulder Pain": "Douleur au cou et aux épaules",
    "Neck Stiffness": "Raideur au cou",
    "Night Pain Lying on the Side": "Douleur la nuit sur le côté",
    "Night Urination": "Se lever la nuit pour uriner",
    "Numb Thigh": "Cuisse engourdie",
    "Numbness / Tingling": "Engourdissement / fourmillements",
    "Numbness or Tingling in the Arm": "Engourdissement ou fourmillements au bras",
    "Outer Hip Pain": "Douleur à l'extérieur de la hanche",
    "Pain After Running": "Douleur après la course",
    "Pain Lifting the Arm": "Douleur en levant le bras",
    "Pain Rolling Over in Bed": "Douleur en se retournant au lit",
    "Pain Standing on One Leg": "Douleur en appui sur une jambe",
    "Pain with Sex": "Douleur pendant les rapports",
    "Pelvic Girdle Pain": "Douleur de la ceinture pelvienne",
    "Perineal Pain": "Douleur au périnée",
    "Pinching Reaching Up": "Pincement quand je lève le bras au-dessus de la tête",
    "Postpartum Bleeding": "Saignements après l'accouchement",
    "Pressure / Bulge": "Pression / saillie",
    "Scar Pain": "Douleur à la cicatrice",
    "Shoulder Pain": "Douleur à l'épaule",
    "SI / Girdle Pain": "Douleur sacro-iliaque / ceinture pelvienne",
    "Soreness After Standing": "Courbature après une position debout",
    "Spasm": "Spasme",
    "Stiffness After Rest": "Raideur après une période de repos",
    "Swelling": "Enflure",
    "Tendon Pain": "Douleur au tendon",
    "Trapezius Ache": "Douleur aux trapèzes",
    "Upper Back Soreness": "Courbature du haut du dos",
    "Urgency": "Envie pressante d'uriner",
    "Urine Leak": "Fuite d'urine",
    "Weak Grip Feeling": "Sensation de prise faible",
    "Wrist & Thumb Pain": "Douleur au poignet et au pouce",
    # -- relief and triggers ---------------------------------------------
    "Alcohol": "Alcool",
    "Bending and Lifting": "Se pencher et soulever",
    "Belly Support": "Soutien abdominal",
    "Bladder Diary": "Journal de la vessie",
    "Caffeine": "Caféine",
    "Car Seat Lifting": "Soulever le siège d'auto",
    "Carrying Baby": "Porter bébé",
    "Carrying on One Side": "Porter d'un seul côté",
    "Carrying the Car Seat": "Porter le siège d'auto",
    "Cough or Sneeze": "Toux ou éternuement",
    "Cycling Instead": "Vélo plutôt que course",
    "Doing Too Much Too Soon": "En faire trop, trop vite",
    "Driving": "Conduire longtemps",
    "Easy Cycling": "Vélo tranquille",
    "Extra Sleep": "Dormir plus",
    "Feeding Posture": "Posture pendant les tétées",
    "Fibre": "Fibres",
    "Fluid Timing": "Répartir les boissons",
    "Fluids Before Bed": "Boire avant le coucher",
    "Heat Pack": "Compresse chaude",
    "Heavy Lifting": "Levage de charges lourdes",
    "High-Impact Exercise": "Exercice à impacts",
    "Hills": "Côtes",
    "Hydration": "Bien s'hydrater",
    "Ibuprofen": "Ibuprofène",
    "Ice Pack": "Bloc de glace",
    "Laughing": "Rire",
    "Load Reduction": "Réduire la charge",
    "Long Desk Session": "Longue séance au bureau",
    "Long Driving": "Longue période en voiture",
    "Long Sitting": "Longtemps en position assise",
    "Long Standing": "Longtemps debout",
    "Looking Down at the Phone": "Tête baissée vers le cellulaire",
    "Manual Therapy": "Thérapie manuelle",
    "Massage": "Massage",
    "New Footwear": "Nouvelles chaussures",
    "Nursing Pillow": "Coussin d'allaitement",
    "Pad or Guard": "Coussin ou protection périnéale",
    "Paracetamol": "Acétaminophène",
    "Pelvic Floor PT": "Physio du plancher pelvien",
    "Perineal Spray": "Vaporisateur périnéal",
    "Pillow Support": "Soutien avec oreillers",
    "Poor Sleep": "Sommeil de mauvaise qualité",
    "Position Change": "Changer de position",
    "Posture Break": "Pause posture",
    "Rest": "Repos",
    "Rest from Overhead": "Éviter les gestes au-dessus de la tête",
    "Return to Exercise Too Soon": "Reprise trop rapide de l'entraînement",
    "Running Distance": "Distance de course",
    "Running Speed": "Allure de course",
    "Running or Jumping": "Course ou sauts",
    "Sitz Bath": "Bain de siège",
    "Skipped Rest Day": "Journée de repos sautée",
    "Sleeping Position": "Position de sommeil",
    "Stairs": "Escaliers",
    "Stool Softener": "Adoucissant des selles",
    "Straining": "Pousser (constipation)",
    "Support Belt": "Ceinture de soutien",
    "Support Wear": "Vêtement de soutien",
    "Supportive Footwear": "Chaussures de soutien",
    "Timed Voiding": "Urination à heure fixe",
    "Timed Voiding Routine": "Routine d'urination à heure fixe",
    "Twin / Multiples Load": "Charge de jumeaux ou plus",
    "Walking": "Marche",
    "Walking Interval": "Intervalles de marche",
    "Warm Bath": "Bain chaud",
    "Warm Shower": "Douche chaude",
    "Breastfeeding Discomfort": "Inconfort à l'allaitement",
    "Cold Weather": "Temps froid",
    "Pelvic Tilt": "Bascule du bassin",
    "Reaching Overhead": "Gestes au-dessus de la tête",
    "Shoulder Rolls": "Rouler les épaules",
    "Sitting Long": "Longtemps en position assise",
    "Trapezius Stretch": "Étirement des trapèzes",
    "Urge Suppression": "Contrôle de l'envie pressante",
}


#: The sign-up picker's own words, per profile key: (label, blurb). Kept here
#: rather than as extra fields on `Profile` so the English definitions in
#: `profiles.py` stay readable and the French sits in one reviewable block. The
#: labels are short on purpose — they render inside a <select> on a 360 px phone.
PROFILE_COPY_FR: dict[str, tuple[str, str]] = {
    "none": (
        "Partir de zéro",
        "Aucun réglage prédéfini. Ajoutez les vôtres, ou choisissez une suggestion"
        " pendant la saisie.",
    ),
    "postnatal_pelvic": (
        "Après l'accouchement",
        "Lourdeur, fuites, douleur à la cicatrice et à la ceinture pelvienne, et la"
        " physio qui reconstruit le plancher pelvien. Ce pour quoi l'application a"
        " été écrite.",
    ),
    "bladder_bowel": (
        "Vessie et intestins",
        "Symptômes urinaires et intestinaux sans accouchement récent — après la"
        " ménopause, en course à pied, après une chirurgie de la prostate, ou une"
        " envie pressante qui est apparue.",
    ),
    "low_back_girdle": (
        "Dos et bassin",
        "Douleurs au dos et à l'anneau pelvien, avec les charges et les postures qui"
        " les déclenchent et les positions qui les calment.",
    ),
    "shoulder_neck": (
        "Épaule et cou",
        "Douleurs à l'épaule et au cou — posture de tétée, port d'un seul côté,"
        " heures au bureau — et le renforcement qui tient l'omoplate.",
    ),
    "hip_knee": (
        "Hanche et genou",
        "Gestion de la charge pour la hanche et le genou : ce que vous avez couru ou"
        " soulevé, la réaction, et quand elle est arrivée.",
    ),
}


def name_for(name: str, locale: str) -> str:
    """The preset name to write into a new row.

    Falls back to the English spelling when a name has no French entry. That
    should not happen — ``tests/test_i18n.py`` walks every preset in every
    profile and fails on a gap — but a missing button label is a cosmetic bug and
    losing the sign-up transaction over it would be worse.
    """
    if locale != "fr":
        return name
    return PRESET_NAMES_FR.get(name, name)


def profile_copy(key: str, locale: str, *, label: str, blurb: str) -> tuple[str, str]:
    """(label, blurb) for the picker, in the language being asked for."""
    if locale == "fr":
        return PROFILE_COPY_FR.get(key, (label, blurb))
    return label, blurb

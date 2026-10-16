from __future__ import annotations

from typing import List, Optional
from .schema import MedicalFact

# Curated, trusted medical reference knowledge base
CURATED_MEDICAL_FACTS: List[MedicalFact] = [
    MedicalFact(
        id="med_fact_keto_headache",
        category="Dietary Adaptation",
        title="Ketogenic Diet and Secondary Headaches (Keto Adaptation)",
        description=(
            "Initiating a ketogenic diet significantly reduces carbohydrate intake, leading to glycogen depletion, "
            "increased renal sodium excretion (natriuresis of fasting), and transient electrolyte and fluid shifts. "
            "These physiological changes commonly trigger transient headaches, fatigue, and brain fog within the first "
            "few days to weeks. However, headaches occurring 3 weeks after onset may also stem from persistent dehydration, "
            "inadequate caloric or micronutrient intake, sleep disruption, or unrelated primary headache disorders."
        ),
        citation="Bostock ECS, et al. Consumer Reports of 'Keto Flu' Associated With the Ketogenic Diet. Front Nutr. 2020; Mayo Clinic Ketogenic Diet Overview (2024).",
        url="https://pubmed.ncbi.nlm.nih.gov/32232141/",
        red_flags=[
            "Thunderclap headache (sudden severe peak within 1 minute)",
            "Neurological deficits (focal weakness, numbness, speech difficulty)",
            "Fever with neck stiffness or altered mental state",
            "Sudden vision loss or diplopia",
            "Headache with persistent vomiting and inability to keep fluids down",
        ],
        relevant_symptoms=["headache", "fatigue", "dizziness", "nausea", "muscle cramps"],
    ),
    MedicalFact(
        id="med_fact_dehydration",
        category="Hydration and Osmoregulation",
        title="Dehydration-Induced Cephalea",
        description=(
            "Dehydration causes systemic fluid deficits that can cause transient intracranial dural tension and "
            "vascular autoregulation changes, resulting in mild to moderate bilateral or holocranial dull headaches. "
            "First-line intervention is gradual fluid rehydration. Extreme sodium supplementation is discouraged without "
            "electrolyte panel verification, as excessive sodium carries cardiovascular risks for vulnerable individuals."
        ),
        citation="Arca KN, Halker Singh RB. Dehydration and Headache. Curr Pain Headache Rep. 2021; American Headache Society Clinical Guidance.",
        url="https://pubmed.ncbi.nlm.nih.gov/34269926/",
        red_flags=[
            "Anuria (no urination for >12 hours)",
            "Orthostatic syncope (fainting upon standing)",
            "Severe confusion or lethargy",
        ],
        relevant_symptoms=["headache", "thirst", "dry mouth", "dark urine", "lightheadedness"],
    ),
    MedicalFact(
        id="med_fact_tension_headache",
        category="Primary Headache Disorders",
        title="Tension-Type Headache (TTH)",
        description=(
            "The most prevalent primary headache disorder, characterized by a dull, aching, band-like sensation "
            "around the head. Often precipitated by emotional or physical stress, eye strain, ergonomic strain, "
            "or sleep deprivation. Usually resolves with rest, gentle stretching, stress reduction, and adequate hydration."
        ),
        citation="International Headache Society (ICHD-3). Cephalalgia. 2018; BMJ Best Practice Tension Headache 2024.",
        url="https://ichd-3.org/2-tension-type-headache/",
        red_flags=[
            "New onset headache in individuals over 50",
            "Progressively worsening headache over days or weeks unresponsive to rest",
        ],
        relevant_symptoms=["headache", "neck stiffness (muscular)", "fatigue", "scalp tenderness"],
    ),
    MedicalFact(
        id="med_fact_caffeine_withdrawal",
        category="Substance Modulation",
        title="Caffeine Withdrawal Cephalea",
        description=(
            "Abrupt cessation or marked reduction of habitual caffeine intake (often occurring when altering beverage habits "
            "during dietary changes) causes cerebral vasodilation, resulting in throbbing or diffuse headache beginning within "
            "12-24 hours and peaking at 20-51 hours."
        ),
        citation="Juliano LM, Griffiths RR. A critical review of caffeine withdrawal. Psychopharmacology (Berl). 2004.",
        url="https://pubmed.ncbi.nlm.nih.gov/15448977/",
        red_flags=[],
        relevant_symptoms=["headache", "irritability", "drowsiness", "difficulty concentrating"],
    ),
]


# Red flag warning criteria (SNOOP Criteria for Secondary Headaches)
EMERGENCY_RED_FLAGS = [
    {
        "pattern": "thunderclap",
        "description": "Sudden, severe headache reaching maximum intensity within seconds to 1 minute ('worst headache of life')",
        "clinical_concern": "Subarachnoid hemorrhage, RCVS, or acute intracranial vascular event",
        "urgency": "EMERGENCY - Call 911 / Go to nearest Emergency Department immediately",
    },
    {
        "pattern": "weakness",
        "description": "Focal weakness, facial droop, arm weakness, or difficulty speaking",
        "clinical_concern": "Acute ischemic stroke or intracranial mass effect",
        "urgency": "EMERGENCY - Seek emergency medical care immediately",
    },
    {
        "pattern": "confusion",
        "description": "New confusion, disorientation, lethargy, or altered level of consciousness",
        "clinical_concern": "Encephalopathy, CNS infection, or metabolic decompensation",
        "urgency": "EMERGENCY - Seek emergency medical care immediately",
    },
    {
        "pattern": "stiff neck",
        "description": "High fever accompanied by marked neck stiffness (nuchal rigidity) and photophobia",
        "clinical_concern": "Meningitis or CNS infection",
        "urgency": "EMERGENCY - Seek urgent emergency medical evaluation immediately",
    },
    {
        "pattern": "vision loss",
        "description": "Sudden loss of vision, partial vision loss, double vision, or visual field deficits",
        "clinical_concern": "Giant cell arteritis, acute angle-closure glaucoma, or optic neuritis",
        "urgency": "URGENT - Seek emergency ophthalmologic or neurological evaluation",
    },
]


def find_relevant_medical_facts(symptoms: List[str]) -> List[MedicalFact]:
    """Finds curated medical facts that match any reported symptom."""
    normalized_symptoms = [s.lower().strip() for s in symptoms]
    matched: List[MedicalFact] = []
    for fact in CURATED_MEDICAL_FACTS:
        for sym in normalized_symptoms:
            if any(sym in s or s in sym for s in fact.relevant_symptoms):
                if fact not in matched:
                    matched.append(fact)
    return matched


def scan_for_red_flags(text: str) -> List[dict]:
    """Deterministically checks text against validated clinical red-flag criteria."""
    text_lower = text.lower()
    detected = []
    for flag in EMERGENCY_RED_FLAGS:
        if flag["pattern"] in text_lower:
            detected.append(flag)
    # Check compound patterns
    if ("fever" in text_lower and "neck" in text_lower) and not any(f["pattern"] == "stiff neck" for f in detected):
        detected.append(EMERGENCY_RED_FLAGS[3])
    if ("vision" in text_lower and ("blur" in text_lower or "loss" in text_lower or "double" in text_lower)):
        if not any(f["pattern"] == "vision loss" for f in detected):
            detected.append(EMERGENCY_RED_FLAGS[4])
    if "worst headache" in text_lower:
        if not any(f["pattern"] == "thunderclap" for f in detected):
            detected.append(EMERGENCY_RED_FLAGS[0])
    return detected

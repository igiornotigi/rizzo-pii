# -*- coding: utf-8 -*-
"""
Mappa i 22 tag di rizzo-pii -> entita' Presidio.

I tag "universali" vanno sui tipi standard Presidio (PERSON, EMAIL_ADDRESS, ...),
cosi' funzionano subito con gli operatori e i tool esistenti (LiteLLM, LangChain).
I tag legali IT che Presidio NON copre (default US-centrico) diventano entita'
CUSTOM con prefisso IT_* -> e' il pezzo che questa integrazione aggiunge all'ecosistema.
"""

# tag rizzo-pii -> nome entita' Presidio
TAG_TO_PRESIDIO = {
    # --- universali: tipi standard Presidio ---
    "FULLNAME":         "PERSON",
    "EMAIL":            "EMAIL_ADDRESS",
    "TELEPHONENUM":     "PHONE_NUMBER",
    "IBAN":             "IBAN_CODE",
    "CREDITCARDNUMBER": "CREDIT_CARD",
    "CITY":             "LOCATION",
    "STREET":           "LOCATION",
    "DATE":             "DATE_TIME",
    "TIME":             "DATE_TIME",
    "ORG":              "ORGANIZATION",
    "AGE":              "AGE",
    # --- legali/anagrafici IT: entita' CUSTOM (non esistono in Presidio) ---
    "CF":               "IT_FISCAL_CODE",
    "PIVA":             "IT_VAT_CODE",
    "ID_DOC":           "IT_IDENTITY_DOC",
    "TARGA":            "IT_LICENSE_PLATE",
    "CATASTO":          "IT_CADASTRAL",
    "DOCID":            "IT_DOC_ID",
    "PROVINCE":         "IT_PROVINCE",
    "ZIPCODE":          "IT_ZIPCODE",
    "BUILDINGNUM":      "IT_BUILDING_NUM",
    "AMOUNT":           "IT_AMOUNT",
    "GENDER":           "IT_GENDER",
}

# entita' custom introdotte da questa integrazione (per registrazione/documentazione)
CUSTOM_ENTITIES = sorted({v for v in TAG_TO_PRESIDIO.values() if v.startswith("IT_")})

# tutte le entita' esposte (per configurare AnalyzerEngine / operatori a valle)
ALL_ENTITIES = sorted(set(TAG_TO_PRESIDIO.values()))


def to_presidio(tag: str) -> str:
    """Tag rizzo-pii -> entita' Presidio. Sconosciuto -> RIZZO_<TAG> (fallback tracciabile)."""
    return TAG_TO_PRESIDIO.get(tag, f"RIZZO_{tag}")

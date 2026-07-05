# -*- coding: utf-8 -*-
from rizzo_presidio.taxonomy import (TAG_TO_PRESIDIO, CUSTOM_ENTITIES,
                                     ALL_ENTITIES, to_presidio)


def test_universal_tags_map_to_standard_presidio():
    assert to_presidio("FULLNAME") == "PERSON"
    assert to_presidio("EMAIL") == "EMAIL_ADDRESS"
    assert to_presidio("IBAN") == "IBAN_CODE"
    assert to_presidio("CREDITCARDNUMBER") == "CREDIT_CARD"


def test_it_legal_tags_map_to_custom_entities():
    assert to_presidio("CF") == "IT_FISCAL_CODE"
    assert to_presidio("PIVA") == "IT_VAT_CODE"
    assert to_presidio("CATASTO") == "IT_CADASTRAL"
    assert to_presidio("DOCID") == "IT_DOC_ID"
    assert to_presidio("PROVINCE") == "IT_PROVINCE"


def test_unknown_tag_has_traceable_fallback():
    assert to_presidio("NUOVO_TAG") == "RIZZO_NUOVO_TAG"


def test_custom_entities_are_the_it_prefixed_ones():
    assert all(e.startswith("IT_") for e in CUSTOM_ENTITIES)
    assert set(CUSTOM_ENTITIES) <= set(ALL_ENTITIES)
    assert set(ALL_ENTITIES) == set(TAG_TO_PRESIDIO.values())

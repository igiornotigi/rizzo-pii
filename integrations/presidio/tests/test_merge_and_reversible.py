# -*- coding: utf-8 -*-
"""Test del merge (priorita' checksum > modello) e del round-trip reversibile.
Usa RecognizerResult costruiti a mano -> niente modello, niente download."""
from presidio_analyzer import RecognizerResult

from rizzo_presidio.engine import merge, reversible_anonymize, deanonymize


def _res(entity, start, end, score, is_regex):
    return RecognizerResult(
        entity_type=entity, start=start, end=end, score=score,
        analysis_explanation=None,
        recognition_metadata={"rizzo_is_regex": is_regex},
    )


def test_checksum_regex_beats_model_fragments():
    """Il caso reale che ha motivato il merge custom: il modello emette frammenti
    del CF a score 1.0; la regex validata dal checksum copre l'intero span e DEVE
    vincere (l'AnalyzerEngine standard, risolvendo solo per score, frammenterebbe)."""
    full = _res("IT_FISCAL_CODE", 10, 26, 1.0, is_regex=1)   # regex validata (score max)
    frag1 = _res("IT_FISCAL_CODE", 10, 16, 1.0, is_regex=0)  # frammento del modello
    frag2 = _res("IT_FISCAL_CODE", 17, 26, 1.0, is_regex=0)
    kept = merge([frag1, full, frag2])
    assert kept == [full]


def test_model_wins_where_no_regex():
    person = _res("PERSON", 0, 11, 0.98, is_regex=0)
    kept = merge([person])
    assert kept == [person]


def test_non_overlapping_all_kept_sorted():
    a = _res("PERSON", 0, 5, 0.9, is_regex=0)
    b = _res("IBAN_CODE", 20, 47, 1.0, is_regex=1)
    c = _res("LOCATION", 8, 14, 0.7, is_regex=0)
    kept = merge([b, a, c])
    assert kept == [a, c, b]                       # ordinati per start


def test_higher_score_wins_between_model_results():
    strong = _res("PERSON", 0, 10, 0.95, is_regex=0)
    weak = _res("ORGANIZATION", 5, 12, 0.60, is_regex=0)
    assert merge([weak, strong]) == [strong]


def test_reversible_roundtrip():
    text = "Mario Rossi bonifica a Mario Rossi su IT08H8381014592811856239313."
    results = [
        _res("PERSON", 0, 11, 0.99, is_regex=0),
        _res("PERSON", 23, 34, 0.99, is_regex=0),
        _res("IBAN_CODE", 38, 65, 1.0, is_regex=1),
    ]
    anon, mapping = reversible_anonymize(text, results)
    # stessa entita' + stesso valore -> STESSO placeholder
    assert anon == "[PERSON_1] bonifica a [PERSON_1] su [IBAN_CODE_1]."
    assert mapping == {"[PERSON_1]": "Mario Rossi",
                       "[IBAN_CODE_1]": "IT08H8381014592811856239313"}
    assert deanonymize(anon, mapping) == text


def test_reversible_trims_whitespace_in_span():
    text = "Nome:  Mario Rossi ."
    results = [_res("PERSON", 6, 19, 0.9, is_regex=0)]     # span con spazi ai bordi
    anon, mapping = reversible_anonymize(text, results)
    assert mapping == {"[PERSON_1]": "Mario Rossi"}
    assert deanonymize(anon, mapping) == text


def test_deanonymize_longer_placeholders_first():
    mapping = {"[PERSON_1]": "Mario", "[PERSON_10]": "Luigi"}
    assert deanonymize("[PERSON_10] e [PERSON_1]", mapping) == "Luigi e Mario"

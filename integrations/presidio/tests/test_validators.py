# -*- coding: utf-8 -*-
"""Test dei validatori checksum. I valori VALIDI sono generati dal generatore del
dataset (src/data_pipeline/generate_synthetic_pii.py) = implementazione indipendente:
se i due algoritmi concordano, il checksum e' giusto. Tutti i valori sono SINTETICI."""
from rizzo_presidio.validators import iban_ok, piva_ok, cf_ok, luhn_ok


def test_cf_valid():
    assert cf_ok("MRTPTR98B24B354B")            # generato, checksum valido
    assert cf_ok("mrtptr98b24b354b")            # case-insensitive


def test_cf_invalid():
    assert not cf_ok("MRTPTR98B24B354A")        # carattere di controllo sbagliato
    assert not cf_ok("MRTPTR98B24B354")         # 15 caratteri
    assert not cf_ok("MRTPTR98B24B354BX")       # 17 caratteri
    assert not cf_ok("MRTPTR98B24B35!B")        # carattere non alfanumerico


def test_iban_valid():
    assert iban_ok("IT08H8381014592811856239313")       # generato, mod-97 ok
    assert iban_ok("IT08 H838 1014 5928 1185 6239 313")  # con spazi


def test_iban_invalid():
    assert not iban_ok("IT09H8381014592811856239313")   # check digits alterati
    assert not iban_ok("IT08H838")                      # troppo corto
    assert not iban_ok("")


def test_piva_valid():
    assert piva_ok("96001338902")               # generata, cifra di controllo ok
    assert piva_ok("00000000000")               # caso limite: tutto zero e' formalmente valido


def test_piva_invalid():
    assert not piva_ok("96001338903")           # ultima cifra sbagliata
    assert not piva_ok("9600133890")            # 10 cifre
    assert not piva_ok("960013389021")          # 12 cifre


def test_luhn():
    assert luhn_ok("4111111111111111")          # numero di test standard (non e' una carta reale)
    assert luhn_ok("4111 1111 1111 1111")
    assert not luhn_ok("4111111111111112")
    assert not luhn_ok("123456")                # troppo corto

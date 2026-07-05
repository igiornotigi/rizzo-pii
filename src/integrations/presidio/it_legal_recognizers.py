# -*- coding: utf-8 -*-
"""
Recognizer Presidio a REGEX + CHECKSUM per i PII strutturati italiani.

Sono la stessa rete deterministica dell'app (`src/app/app.py` -> DETECTORS) portata
su Presidio come `PatternRecognizer`: la regex trova la forma, `validate_result()`
applica il checksum (mod-97 IBAN, dispari/pari CF, Luhn carta, controllo P.IVA).

Perche' servono: i recognizer di default Presidio sono tarati sugli USA; CF, P.IVA,
IBAN italiano, catasto, targa, ecc. vanno aggiunti come recognizer custom. Questo file
e' quel pezzo -> alza il RECALL sui PII a forma fissa e riduce i falsi positivi (il
checksum scarta le sequenze che "sembrano" ma non sono valide).

In produzione conviene importare i validatori da `src/inspect/validate_checksums.py`;
qui li riportiamo compatti per rendere il modulo autonomo.
"""
import re
from typing import Optional

from presidio_analyzer import Pattern, PatternRecognizer


# --------------------------------------------------------------------------- #
# Validatori checksum (identici a src/app/app.py)
# --------------------------------------------------------------------------- #
def iban_ok(s: str) -> bool:
    s = re.sub(r"\s", "", s).upper()
    if not (15 <= len(s) <= 34):
        return False
    r = s[4:] + s[:4]
    try:
        n = int("".join(str(ord(c) - 55) if c.isalpha() else c for c in r))
    except ValueError:
        return False
    return n % 97 == 1


def piva_ok(p: str) -> bool:
    p = re.sub(r"\D", "", p)
    if len(p) != 11:
        return False
    t = 0
    for i, c in enumerate(map(int, p[:10])):
        t += c if i % 2 == 0 else (lambda x: x - 9 if x > 9 else x)(c * 2)
    return (10 - t % 10) % 10 == int(p[10])


_CF_ODD = {"0": 1, "1": 0, "2": 5, "3": 7, "4": 9, "5": 13, "6": 15, "7": 17, "8": 19,
           "9": 21, "A": 1, "B": 0, "C": 5, "D": 7, "E": 9, "F": 13, "G": 15, "H": 17,
           "I": 19, "J": 21, "K": 2, "L": 4, "M": 18, "N": 20, "O": 11, "P": 3, "Q": 6,
           "R": 8, "S": 12, "T": 14, "U": 16, "V": 10, "W": 22, "X": 25, "Y": 24, "Z": 23}


def cf_ok(c: str) -> bool:
    c = c.strip().upper()
    if len(c) != 16 or not c.isalnum():
        return False
    try:
        t = sum((_CF_ODD[ch] if i % 2 == 0 else (int(ch) if ch.isdigit() else ord(ch) - 65))
                for i, ch in enumerate(c[:15]))
    except KeyError:
        return False
    return chr(65 + t % 26) == c[15]


def luhn_ok(s: str) -> bool:
    d = re.sub(r"\D", "", s)
    if not (13 <= len(d) <= 19):
        return False
    tot, alt = 0, False
    for ch in reversed(d):
        n = int(ch)
        if alt:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        tot += n
        alt = not alt
    return tot % 10 == 0


# --------------------------------------------------------------------------- #
# PatternRecognizer: uno per tipo, con validate_result() = checksum
# --------------------------------------------------------------------------- #
class _ChecksumRecognizer(PatternRecognizer):
    """PatternRecognizer che promuove/scarta il match in base a un checksum.

    validate_result: True -> match valido (Presidio alza lo score al massimo);
                     False -> match scartato; None -> lasciato allo score della regex.
    """
    def __init__(self, entity, name, regex, score, validator, strict, context=None):
        super().__init__(
            supported_entity=entity,
            patterns=[Pattern(name=name, regex=regex, score=score)],
            context=context or [],
            supported_language="it",
        )
        self._validator = validator
        self._strict = strict  # True: scarta se il checksum fallisce (evita falsi positivi)

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        ok = self._validator(pattern_text)
        if ok:
            return True
        return False if self._strict else None


def build_it_recognizers():
    """Ritorna la lista dei recognizer regex+checksum per i PII strutturati IT."""
    return [
        _ChecksumRecognizer("IT_FISCAL_CODE", "cf",
                            r"\b[A-Za-z]{6}\d{2}[A-Za-z]\d{2}[A-Za-z]\d{3}[A-Za-z]\b",
                            0.6, cf_ok, strict=False,
                            context=["codice fiscale", "c.f.", "cf", "nato", "residente"]),
        _ChecksumRecognizer("IBAN_CODE", "iban",
                            r"\b[A-Za-z]{2}\d{2}[A-Za-z0-9]{11,30}\b",
                            0.5, iban_ok, strict=True,
                            context=["iban", "conto", "bonifico", "accredito", "coordinate"]),
        _ChecksumRecognizer("CREDIT_CARD", "cc",
                            r"(?<!\d)(?:\d[ \-]?){13,19}(?!\d)",
                            0.4, luhn_ok, strict=True,
                            context=["carta", "credito", "pagamento"]),
        _ChecksumRecognizer("IT_VAT_CODE", "piva",
                            r"(?<!\d)\d{11}(?!\d)",
                            0.3, piva_ok, strict=True,
                            context=["p.iva", "partita iva", "piva", "vat"]),
        # forma-only (nessun checksum): affidabili per contesto, score piu' basso
        PatternRecognizer(supported_entity="EMAIL_ADDRESS", supported_language="it",
                          patterns=[Pattern("email", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", 0.7)]),
        PatternRecognizer(supported_entity="PHONE_NUMBER", supported_language="it",
                          patterns=[Pattern("tel_it",
                              r"(?<![\w.])(?:\+39[\s.]?)?(?:3\d{2}[\s.]?\d{3}[\s.]?\d{3,4}|0\d{1,3}[\s.]?\d{5,8})(?![\w])",
                              0.5)], context=["tel", "telefono", "cell", "cellulare"]),
        PatternRecognizer(supported_entity="IT_LICENSE_PLATE", supported_language="it",
                          patterns=[Pattern("targa", r"\b[A-Za-z]{2}\s?\d{3}\s?[A-Za-z]{2}\b", 0.4)],
                          context=["targa", "targato", "veicolo", "autovettura"]),
        PatternRecognizer(supported_entity="IT_AMOUNT", supported_language="it",
                          patterns=[Pattern("importo",
                              r"(?:€|EUR|euro)\s?\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?|\d{1,3}(?:\.\d{3})*,\d{2}\s?(?:€|EUR|euro)",
                              0.6)]),
    ]

# -*- coding: utf-8 -*-
"""
Validatori checksum per i PII strutturati italiani — puro Python, ZERO dipendenze.

Stessa rete deterministica dell'app (`src/app/app.py`) e di
`src/inspect/validate_checksums.py`: mod-97 per IBAN, tabella dispari/pari per il
codice fiscale, Luhn per le carte, algoritmo di controllo per la P.IVA.

Modulo separato (senza import presidio) cosi' e' usabile ovunque: nei recognizer,
nei test, o standalone come blueprint della rete regex+checksum da affiancare
SEMPRE al modello in produzione.
"""
import re


def iban_ok(s: str) -> bool:
    """Checksum IBAN (mod-97, ISO 13616)."""
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
    """Cifra di controllo della Partita IVA italiana (11 cifre)."""
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
    """Carattere di controllo del Codice Fiscale (16 caratteri)."""
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
    """Checksum Luhn (carte di pagamento, 13-19 cifre)."""
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

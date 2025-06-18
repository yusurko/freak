"""
Utilities for Diversity, Equity, Inclusion
"""

from __future__ import annotations


BRICKS = '@abcdefghijklmnopqrstuvwxyz+?-\'/'
# legend @: space, -: literal, +: suffix (i.e. ae+r expands to ae/aer), ': literal, ?: unknown, /: separator

class Pronoun(int):
    PRESETS = {
        'hh': 'he/him',
        'sh': 'she/her',
        'tt': 'they/them',
        'ii': 'it/its',
        'hs': 'he/she',
        'ht': 'he/they',
        'hi': 'he/it',
        'shh': 'she/he',
        'st': 'she/they',
        'si': 'she/it',
        'th': 'they/he',
        'ts': 'they/she',
        'ti': 'they/it',
    }

    UNSPECIFIED = 0

    ## presets from PronounDB
    ## DO NOT TOUCH the values unless you know their exact correspondence!!
    ## hint: Pronoun.from_short()
    HE = HE_HIM = 264
    SHE = SHE_HER = 275
    THEY = THEY_THEM = 660
    IT = IT_ITS = 297
    HE_SHE = 616
    HE_THEY = 648
    HE_IT = 296
    SHE_HE = 8467
    SHE_THEY = 657
    SHE_IT = 307
    THEY_HE = 276
    THEY_SHE = 628
    THEY_IT = 308
    ANY = 26049
    OTHER = 19047055
    ASK = 11873
    AVOID = NAME_ONLY = 4505281

    def short(self) -> str:
        i = self
        s = ''
        while i > 0:
            s += BRICKS[i % 32]
            i >>= 5
        return s
    
    def full(self):
        s = self.short()

        if s in self.PRESETS:
            return self.PRESETS[s]
        
        if '+' in s:
            s1, s2 = s.rsplit('+')
            s = s1 + '/' + s1 + s2

        return s
    __str__ = full

    @classmethod
    def from_short(self, s: str) -> Pronoun:
        i = 0
        for j, ch in enumerate(s):
            i += BRICKS.index(ch) << (5 * j)
        return Pronoun(i)

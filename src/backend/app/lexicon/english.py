"""Telling English words apart from Spanish ones in what the learner typed."""

import re

from .grammar_terms import FUNCTION_WORDS
from .verbs import VerbData

SPANISH_MARKS = re.compile(r"[áéíóúñü¿¡]", re.IGNORECASE)

# Common English words that are not also Spanish words. Words that exist in both languages ("a",
# "me", "no", "son", "come", "pan", "red", "solo"...) are deliberately left out.
ENGLISH_ONLY = frozenset("""
the of and to in is it you that he was for on are as with his they i at be this have from or one
had by word but not what all were we when your can said there use an each which she do how their
if will up other about out many then them these so some her would make like him into time  look
two more write go see number way could people my than first been call who its now find long down
day did get made may part over new sound take only little work know place year live back give
most very after thing our just name good sentence man think say great where help through much
before line right too mean old any same tell boy follow came want show also around form three small
set put end does another well large must big even such because turn here why ask went men read
need land different home us move try kind hand picture again change off play spell air away 
house point page letter mother answer found study still learn should world high every near add food
between own below country plant last school father keep tree never start city earth eye light
thought head under story saw left few while along might close something seem next hard open example
begin life always those both paper together got group often run important until children side feet
car mile night walk white  began grow took river four carry state  book hear stop without
second later miss  enough eat face watch far really almost let above girl sometimes mountains
cut young talk soon list song being leave family it's i'm don't can't you're miss missing wanted
wanting going went gone loved love lover heart baby sorry yes yeah okay ok hey hello please thanks
thank again tonight today tomorrow yesterday someone somebody anything everything nothing myself
yourself i'll i've we're they're
""".split())


def is_english_word(word: str, verbs: VerbData) -> bool:
    w = word.casefold()
    if w in FUNCTION_WORDS or SPANISH_MARKS.search(w):
        return False
    # Checked before the verb tables: "are" and "use" are also rare Spanish verb forms (arar, usar),
    # but in a learner's note they are English.
    if w in ENGLISH_ONLY:
        return True
    if verbs.matches(w):
        return False
    return len(w) > 5 and w.endswith("ing") and w.isascii()

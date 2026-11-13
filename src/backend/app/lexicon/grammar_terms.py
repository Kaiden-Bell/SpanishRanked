"""Spanish grammar vocabulary shared by the verb data, the analyzer and the question templates.

Keys are short, stable codes stored in the database; labels are what the learner reads.
"""

# Simple (one-word) tenses, in the order a conjugation table shows them. Each maps to verbecc's
# (mood, tense) names, which only the data build script uses.
TENSES: dict[str, dict] = {
    "pres": {"label": "present", "mood": "indicative", "when": "now, or something that happens regularly",
             "verbecc": ("indicativo", "presente")},
    "pret": {"label": "preterite", "mood": "indicative", "when": "a completed action in the past",
             "verbecc": ("indicativo", "pretérito-perfecto-simple")},
    "impf": {"label": "imperfect", "mood": "indicative", "when": "ongoing or habitual in the past (used to / was ...ing)",
             "verbecc": ("indicativo", "pretérito-imperfecto")},
    "fut": {"label": "future", "mood": "indicative", "when": "something that will happen",
            "verbecc": ("indicativo", "futuro")},
    "cond": {"label": "conditional", "mood": "conditional", "when": "something that would happen",
             "verbecc": ("condicional", "presente")},
    "subj_pres": {"label": "present subjunctive", "mood": "subjunctive",
                  "when": "a wish, doubt or possibility (que ...)", "verbecc": ("subjuntivo", "presente")},
    "subj_impf": {"label": "imperfect subjunctive", "mood": "subjunctive",
                  "when": "a hypothetical or past wish (si ..., quería que ...)",
                  "verbecc": ("subjuntivo", "pretérito-imperfecto-1")},
    "subj_impf_se": {"label": "imperfect subjunctive (-se)", "mood": "subjunctive",
                     "when": "the same as the -ra form, less common", "verbecc": ("subjuntivo", "pretérito-imperfecto-2")},
    "imp_aff": {"label": "command", "mood": "imperative", "when": "telling someone to do something",
                "verbecc": ("imperativo", "afirmativo")},
    "imp_neg": {"label": "negative command", "mood": "imperative", "when": "telling someone not to do something (no ...)",
                "verbecc": ("imperativo", "negativo")},
}

# Tenses worth drilling at beginner/intermediate level, in teaching order.
CORE_TENSES = ("pres", "pret", "impf", "fut", "cond", "subj_pres")

PERSONS: dict[str, dict] = {
    "yo": {"label": "yo", "who": "I"},
    "tu": {"label": "tú", "who": "you"},
    "vos": {"label": "vos", "who": "you (vos, Latin America)"},
    "3s": {"label": "él / ella / usted", "who": "he / she / you (formal)"},
    "nos": {"label": "nosotros", "who": "we"},
    "vosotros": {"label": "vosotros", "who": "you all (Spain)"},
    "3p": {"label": "ellos / ellas / ustedes", "who": "they / you all"},
}

# Persons used for drills: vos and vosotros are regional, so they appear in tables but not in quizzes.
DRILL_PERSONS = ("yo", "tu", "3s", "nos", "3p")

NON_FINITE = {"inf": "infinitive", "ger": "gerund (-ando / -iendo)", "part": "past participle"}

# Words that carry grammar rather than meaning. In a phrase they are context, never the thing to learn.
FUNCTION_WORDS = frozenset(
    """
    a al ante bajo con contra de del desde durante en entre hacia hasta para por según sin sobre tras
    el la los las lo un una unos unas
    y e o u ni pero sino que si porque como cuando donde mientras aunque pues
    yo tú tu vos él ella usted nosotros nosotras vosotros vosotras ellos ellas ustedes
    me te se nos os le les
    mi mis tus su sus nuestro nuestra nuestros nuestras vuestro vuestra
    este esta estos estas ese esa esos esas aquel aquella esto eso aquello
    no sí ya muy más menos también tampoco
    """.split()
)

# Short glosses for the grammar words, so a phrase can be read word by word.
FUNCTION_GLOSS = {
    "a": "to, at", "al": "to the", "ante": "before", "con": "with", "contra": "against", "de": "of, from",
    "del": "of the", "desde": "since, from", "durante": "during", "en": "in, on", "entre": "between",
    "hacia": "towards", "hasta": "until", "para": "for, in order to", "por": "for, by, through",
    "según": "according to", "sin": "without", "sobre": "on, about", "tras": "after",
    "el": "the", "la": "the; her, it (object)", "los": "the; them (object)", "las": "the; them (object)",
    "lo": "it, him (object); the ... thing", "un": "a", "una": "a", "unos": "some", "unas": "some",
    "y": "and", "e": "and", "o": "or", "u": "or", "ni": "nor", "pero": "but", "sino": "but rather",
    "que": "that, which", "si": "if", "porque": "because", "como": "like, as", "cuando": "when",
    "donde": "where", "mientras": "while", "aunque": "although", "pues": "well, so",
    "yo": "I", "tú": "you", "tu": "your", "vos": "you", "él": "he", "ella": "she", "usted": "you (formal)",
    "nosotros": "we", "nosotras": "we", "vosotros": "you all", "vosotras": "you all", "ellos": "they",
    "ellas": "they", "ustedes": "you all",
    "me": "me, to me", "te": "you, to you", "se": "himself/herself, to him/her", "nos": "us, to us",
    "os": "you all, to you all", "le": "to him/her/you", "les": "to them",
    "mi": "my", "mis": "my", "tus": "your", "su": "his/her/their/your", "sus": "his/her/their/your",
    "nuestro": "our", "nuestra": "our", "nuestros": "our", "nuestras": "our",
    "este": "this", "esta": "this", "estos": "these", "estas": "these", "ese": "that", "esa": "that",
    "esos": "those", "esas": "those", "aquel": "that (over there)", "aquella": "that (over there)",
    "esto": "this", "eso": "that", "aquello": "that",
    "no": "not, no", "sí": "yes", "ya": "already, now", "muy": "very", "más": "more", "menos": "less",
    "también": "also", "tampoco": "neither",
}

# Object pronouns that can come before a verb ("te extraño") or be attached to it ("extrañarte").
CLITICS = ("me", "te", "se", "lo", "la", "le", "nos", "os", "los", "las", "les")


def tense_label(key: str) -> str:
    return TENSES[key]["label"] if key in TENSES else NON_FINITE.get(key, key)


def describe_form(tense: str, person: str | None) -> dict:
    """Plain-English 'who and when' for one conjugation cell."""
    if tense in NON_FINITE:
        return {"tense": tense, "tense_label": NON_FINITE[tense], "person": None, "person_label": None,
                "who": None, "when": None, "summary": NON_FINITE[tense]}
    info = TENSES[tense]
    who = PERSONS[person] if person in PERSONS else None
    summary = f"{who['label']} · {info['label']}" if who else info["label"]
    return {
        "tense": tense, "tense_label": info["label"], "mood": info["mood"],
        "person": person, "person_label": who["label"] if who else None,
        "who": who["who"] if who else None, "when": info["when"], "summary": summary,
    }

"""Defense policies.

Fiecare politica are aceeasi semnatura:

    policy(task, name, args) -> bool

    task  - user_task-ul original, exact cum a fost dat agentului
    name  - numele uneltei cerute de model
    args  - argumentele uneltei, deja parsate ca dict de agent.py

    True  = tool call permis
    False = tool call blocat

Numele functiilor conteaza: harness.load_policy() face
getattr(policies, name), deci --policy keyword cauta functia `keyword`.

Ce vede o politica: task-ul original, numele uneltei, argumentele.
Nimic altceva. Nu are istoricul conversatiei, nu stie la ce pas e si nu
stie ce a citit agentul pana acum.

Ce e de incredere din ce vede: doar task-ul. Numele uneltei si argumentele
vin de la un model care poate fi deja sub controlul atacatorului, deci
sunt dovezi despre intentie, nu adevar. Task-ul e singurul lucru fixat
inainte ca agentul sa citeasca ceva.
"""

import json
import os
import re

import yaml


ROOT = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..")
)

CONFIG_PATH = os.path.join(ROOT, "config", "policies.yaml")

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f) or {}


def _compile(term: str, mode: str):
    """Intoarce o functie care spune daca termenul apare in text.

    mode == "substring": cautare simpla de subsir. Buna pentru domenii si
        pentru siruri care contin caractere non-alfanumerice ("postgres://",
        "webhook.site"), unde marginile de cuvant nu au sens.

    mode == "word": cautare cu margini de cuvant. Necesara pentru comenzi
        scurte de shell. Ca subsir, "rm " se potriveste in "long-term
        investing", "cp " in "backup copy" si asa mai departe - adica
        blocheaza emailuri normale in engleza si strica masuratoarea de
        fals-pozitive.
    """

    if mode == "word":
        pattern = re.compile(
            r"\b" + re.escape(term) + r"\b"
        )
        return lambda text: pattern.search(text) is not None

    if mode == "substring":
        return lambda text: term in text

    raise ValueError(
        f"Mod de potrivire necunoscut: {mode!r}. Astept 'substring' sau 'word'."
    )


def _load_blocklist(config: dict):
    """Citeste termenii politicii keyword, grupati pe categorii.

    Un grup poate fi scris in doua forme:

        credentials:            # lista simpla, potrivire de subsir
          - "private key"

        shell:                  # forma cu optiuni
          match: word
          terms:
            - "rm"

    Nu punem valori implicite si nu inghitim fisierul lipsa. O lista goala ar
    transforma keyword intr-o politica care nu blocheaza nimic, iar rularea ar
    merge pana la capat si ar produce un CSV care arata ca o aparare fara
    fals-pozitive. Mai bine cade acum, la import, decat dupa doua ore.
    """

    section = config.get("keyword")

    if not section:
        raise ValueError(
            f"Sectiunea 'keyword' lipseste din {CONFIG_PATH}."
        )

    matchers = []
    groups = {}

    for group, value in section.items():

        if isinstance(value, dict):
            mode = value.get("match", "substring")
            values = value.get("terms")
        else:
            mode = "substring"
            values = value

        if not values:
            raise ValueError(
                f"Grupul 'keyword.{group}' e gol in {CONFIG_PATH}."
            )

        for raw in values:
            term = str(raw).lower()

            # Un sir gol e continut in orice text, deci o singura intrare
            # goala ar transforma politica in blocheaza-tot. S-ar vedea in
            # rezultate ca o rata de blocare de 100%, adica suspect de bine.
            if not term.strip():
                raise ValueError(
                    f"Grupul 'keyword.{group}' contine o intrare goala in {CONFIG_PATH}."
                )

            matchers.append((term, group, _compile(term, mode)))
            groups[term] = group

    return matchers, groups


# _MATCHERS: [(termen, grup, functie_de_potrivire)]
# KEYWORD_GROUPS / KEYWORD_TERMS raman pentru raportare si analiza.
_MATCHERS, KEYWORD_GROUPS = _load_blocklist(CONFIG)
KEYWORD_TERMS = list(KEYWORD_GROUPS)


def keyword(task, name, args):
    """Blocheaza tool call-urile care contin un termen din blocklist.

    Se uita DOAR la numele uneltei si la argumente. Task-ul e ignorat
    intentionat: asta e linia de baza, un filtru de continut care nu stie
    ce a cerut userul. Nu vede nici ce a citit agentul.

    Argumentele sunt serializate cu json.dumps pentru ca o valoare poate fi
    lista sau dictionar, iar cautarea trebuie sa ajunga si in interiorul lor.
    default=str acopera tipurile pe care json nu le stie serializa, ca o
    valoare ciudata sa nu arunce exceptie - o politica ce arunca e tratata
    de agent.py ca blocare, deci ar aparea in rezultate ca aparare reusita.
    """

    haystack = _haystack(name, args)

    return not any(
        matches(haystack)
        for _, _, matches in _MATCHERS
    )


def _haystack(name, args) -> str:
    """Numele uneltei plus argumentele, ca un singur text lowercase.

    Argumentele sunt serializate cu json.dumps pentru ca o valoare poate fi
    lista sau dictionar, iar cautarea trebuie sa ajunga si in interiorul lor.
    default=str acopera tipurile pe care json nu le stie serializa, iar
    try/except acopera ce ramane: o politica ce arunca o exceptie e tratata
    de agent.py ca blocare si s-ar vedea in rezultate ca aparare reusita.
    """

    try:
        serialized = json.dumps(
            args or {},
            ensure_ascii=False,
            default=str
        )
    except (TypeError, ValueError):
        serialized = str(args)

    return (str(name) + " " + serialized).lower()


def keyword_match(name, args):
    """Ce termeni au declansat, si din ce grup. Pentru analiza, nu pentru agent.

    keyword() intoarce doar True/False, pentru ca asta ii cere semnatura
    politicii. Aceeasi potrivire e expusa si aici ca lista, ca sa se poata
    numara blocarile pe grup cand se scriu rezultatele.
    """

    haystack = _haystack(name, args)

    return [
        (term, group)
        for term, group, matches in _MATCHERS
        if matches(haystack)
    ]
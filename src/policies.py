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
import time
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


# ---------------------------------------------------------------------------
# JUDGE
# ---------------------------------------------------------------------------
# Un model separat decide, inainte de fiecare tool call, daca apelul serveste
# task-ul userului.
#
# Spre deosebire de keyword si allowlist, judecatorul citeste text scris de
# atacator: argumentele vin de la un agent care poate fi deja compromis. Deci
# judecatorul e el insusi injectabil. Promptul ii spune explicit sa trateze
# argumentele ca pe o pretentie, nu ca pe instructiuni, dar asta nu e o
# garantie - e chiar lucrul de masurat.

import ollama


JUDGE_CONFIG = CONFIG.get("judge") or {}

JUDGE_MODEL = JUDGE_CONFIG.get("model")

if not JUDGE_MODEL:
    raise ValueError(
        f"'judge.model' lipseste din {CONFIG_PATH}."
    )

# fail closed: tot ce nu se poate parsa sau nu raspunde inseamna BLOCK.
JUDGE_ON_ERROR = JUDGE_CONFIG.get("on_error", "block")

JUDGE_PROMPT_PATH = os.path.join(ROOT, "prompts", "judge.md")

with open(JUDGE_PROMPT_PATH, encoding="utf-8") as f:
    JUDGE_PROMPT = f.read()

for placeholder in ("{task}", "{tool}", "{args}"):
    if placeholder not in JUDGE_PROMPT:
        raise ValueError(
            f"{JUDGE_PROMPT_PATH} nu contine {placeholder}."
        )

# Fiecare decizie se scrie aici, cu raspunsul brut. De aici iese rata de
# raspunsuri neparsabile, care trebuie raportata: fara ea nu se stie daca
# judecatorul a judecat sau a picat pe ramura de eroare.
JUDGE_LOG = os.path.join(ROOT, "logs", "judge.jsonl")


def _judge_log(tool, args, raw, decision, error=None):
    """Scrie o linie in logs/judge.jsonl. Nu arunca niciodata."""

    try:
        os.makedirs(os.path.dirname(JUDGE_LOG), exist_ok=True)

        with open(JUDGE_LOG, "a", encoding="utf-8") as file:
            file.write(json.dumps({
                "t": time.time(),
                "tool": tool,
                "args": args,
                "raw": raw,
                "decision": decision,
                "error": error,
            }, ensure_ascii=False, default=str) + "\n")

    except OSError:
        pass


def _parse_decision(raw: str):
    """Intoarce True (ALLOW), False (BLOCK) sau None daca nu se poate decide.

    Modelele mici nu respecta "un singur cuvant": scriu paragrafe, raspund in
    alta limba, pun ambele cuvinte in aceeasi propozitie. Daca apar amandoua
    sau niciunul, raspunsul nu spune nimic si intoarcem None.
    """

    text = str(raw or "").upper()

    has_allow = "ALLOW" in text
    has_block = "BLOCK" in text

    if has_allow and not has_block:
        return True

    if has_block and not has_allow:
        return False

    return None


def judge(task, name, args):
    """Intreaba un model daca tool call-ul serveste task-ul userului."""

    prompt = JUDGE_PROMPT.format(
        task=task,
        tool=name,
        args=json.dumps(args or {}, ensure_ascii=False, default=str),
    )

    try:
        response = ollama.chat(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            # temperature 0: judecatorul e parte din aparare, nu din experiment.
            # Daca decide altfel la fiecare rulare, nu se poate compara nimic.
            options={"temperature": 0},
        )
        raw = response["message"].get("content", "")

    except Exception as e:
        # Fail closed. Daca Ollama nu raspunde, toate apelurile sunt blocate,
        # iar rezultatul arata ca o aparare perfecta. Linia din log e singurul
        # lucru care distinge asta de o aparare care chiar a functionat.
        _judge_log(name, args, None, False, error=f"{type(e).__name__}: {e}")
        return False

    decision = _parse_decision(raw)

    if decision is None:
        allowed = (JUDGE_ON_ERROR == "allow")
        _judge_log(name, args, raw, allowed, error="unparsable")
        return allowed

    _judge_log(name, args, raw, decision)

    return decision
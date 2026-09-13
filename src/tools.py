"""Uneltele agentului. Toate lucreaza DOAR in sandbox/. Nimic nu iese de acolo."""

import os, yaml, re

# SANDBOX = calea reala catre folderul sandbox
SANDBOX = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "sandbox"))

FILES  = os.path.realpath(os.path.join(SANDBOX, "files"))
INBOX  = os.path.realpath(os.path.join(SANDBOX, "inbox"))
OUTBOX = os.path.realpath(os.path.join(SANDBOX, "outbox"))

# Functii interne comune

# Am facut _safe sigur impotriva incercarii formarii unui symlink in afara directorului,
# cu ajutorul functiei "realpath"
def _safe(base: str, name: str):
    """Refuza orice cale care iese din base (../ etc)."""
    p = os.path.realpath(os.path.join(base, name))

    if not p.startswith(base + os.sep) and p != base:
        raise PermissionError(f"Acces refuzat in afara sandbox-ului: {name}")

    return p

# Afiseaza toate fisierele intr-un director, cu tot cu cele ascunse
def _list_dir(base: str, empty_msg: str) -> str:
    """Listeaza numele din `base`. Nu filtram nimic: agentul vede exact ce e acolo."""
    nume = sorted(os.listdir(base))

    # Daca nu avem nimic in folder, returnam mesajul de eroare.
    if not nume:
        return empty_msg

    return "\n".join(nume)

# Citeste un fisier din baza "base", cu numele "name"
def _read_from(base: str, name: str, list_tool_name: str) -> str:
    """Citeste un fisier obisnuit din `base`. `list_tool_name` = unealta de listare, pt mesaje."""
    path = _safe(base, name)

    if not os.path.exists(path):
        return f"Nu exista nimic cu numele introdus. {list_tool_name} iti arata ce e disponibil."
    
    if not os.path.isfile(path):
        return f"Numele introdus nu este un fisier. {list_tool_name} iti arata ce e disponibil."

    with open(path, encoding="utf-8") as f:
        return f.read()

# Scrie/suprascrie un fisier. Intoarce comanda(suprascriere/stergere) pe care a facut-o
def _write_to(base: str, name: str, content: str) -> str:
    """Scrie/suprascrie un fisier obisnuit din `base`."""
    path = _safe(base, name)

    if not os.path.exists(path):
        if not content:
            return_msg = f"Fisierul {name} creat este gol."
        else:
            return_msg = f"Crearea si scrierea in {name} a continutului dat a avut succes."
    else:
        if os.path.isfile(path):
            return_msg = f"Suprascrierea fisierului {name} cu continutul dat a avut succes."
            if not content:
                return_msg += " Atentie. Fisierul suprascris este acum gol."
        else:
            return "Numele dat nu este un fisier valabil."

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return return_msg

# FILESYSTEM:
def read_file(name: str) -> str:
    """Citeste un fisier din sandbox/files."""
    return _read_from(FILES, name, "list_files")

def list_files() -> str:
    """Listeaza fisierele din sandbox/files."""
    return _list_dir(FILES, "Nu exista fisiere in folderul de lucru.")

# Functie ce scrie/suprascrie in FILES un fisier
def write_file(name: str, content: str) -> str:
    return _write_to(FILES, name, content)


# MAIL:
def list_inbox() -> str:
    """Listeaza fisierele din sandbox/inbox."""
    return _list_dir(INBOX, "Nu exista emailuri in inbox.")

def read_inbox_file(name: str) -> str:
    """Citeste un fisier din sandbox/inbox."""
    return _read_from(INBOX, name, "list_inbox")

def send_email(to: str, subject: str, body: str) -> str:
    """'Trimite' un email: scrie un fisier in sandbox/outbox. Nu pleaca nimic real."""
    fn = re.sub(r"[^a-zA-Z0-9_.@-]", "_", f"{to}__{subject}")[:80] + ".txt"

    with open(_safe(OUTBOX, fn), "w", encoding="utf-8") as f:
        f.write(f"TO: {to}\nSUBJECT: {subject}\n\n{body}")

    return f"email pus in outbox: {fn}"

# CALCULATOR:
def calculator(expression: str) -> str:
    """Evalueaza o expresie aritmetica simpla."""
    # Mai intai, se verifica ca expresia sa nu aiba litere sau alte caractere care incurca formarea
    # unei expresii aritmetice
    if not re.fullmatch(r"[0-9+\-*/(). ]+", expression):
        return "Expresie refuzata, nu se pot folosi litere sau alte caractere in " \
               "afara operatorilor + - * /, paranteze si punct zecimal, fara functii."

    # eval(expression, ...) = ruleaza textul ca pe o expresie Python
    # __builtins__ = elimina functiile predefinite din Python (f important la nivel de securitate)
    # {} la final inseamna ca nu exista variabile disponibile
    return str(eval(expression, {"__builtins__": {}}, {}))

# BROWSER:

# TERMINAL:

# Calea catre schema
TOOLS_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "config", "tools.yaml"))
# Schema pe care o vede modelul (format OpenAI/Ollama) incarcata din YAML
with open(TOOLS_PATH, encoding="utf-8") as f:
    TOOLS = yaml.safe_load(f)

REGISTRY = {
    "read_file": read_file,
    "list_files": list_files,
    "write_file": write_file,
    "read_inbox_file": read_inbox_file,
    "list_inbox": list_inbox,
    "send_email": send_email,
    "calculator": calculator
}


def call(name: str, args: dict) -> str:
    if name not in REGISTRY:
        return f"Unealta necunoscuta: {name}"

    try:
        return str(REGISTRY[name](**(args or {})))
    except Exception as e:
        return f"Eroare: {e}"
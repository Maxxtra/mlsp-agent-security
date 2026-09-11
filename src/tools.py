"""Uneltele agentului. Toate lucreaza DOAR in sandbox/. Nimic nu iese de acolo."""

import os, json, re

# SANDBOX = calea reala catre folderul sandbox
SANDBOX = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "sandbox"))

FILES  = os.path.realpath(os.path.join(SANDBOX, "files"))
INBOX  = os.path.realpath(os.path.join(SANDBOX, "inbox"))
OUTBOX = os.path.realpath(os.path.join(SANDBOX, "outbox"))

# Am facut _safe sigur impotriva incercarii formarii unui symlink in afara directorului,
# cu ajutorul functiei "realpath"
def _safe(base, name):
    """Refuza orice cale care iese din base (../ etc)."""
    p = os.path.realpath(os.path.join(base, name))

    if not p.startswith(base + os.sep) and p != base:
        raise PermissionError(f"acces refuzat in afara sandbox-ului: {name}")

    return p

# FILESYSTEM:
def read_file(name: str) -> str:
    """Citeste un fisier din sandbox/files."""
    try:
        with open(_safe(FILES, name), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Fisierul nu exista. list_files iti arata fisierele disponibile."

def list_files() -> str:
    """Listeaza fisierele din sandbox/files."""
    files = sorted(os.listdir(FILES))

    if files == []:
        return "Nu avem fisiere in folderul de lucru."
    else:
        return "\n".join(files)

# MAIL:
def send_email(to: str, subject: str, body: str) -> str:
    """'Trimite' un email: scrie un fisier in sandbox/outbox. Nu pleaca nimic real."""
    fn = re.sub(r"[^a-zA-Z0-9_.@-]", "_", f"{to}__{subject}")[:80] + ".txt"

    with open(_safe(OUTBOX, fn), "w", encoding="utf-8") as f:
        f.write(f"TO: {to}\nSUBJECT: {subject}\n\n{body}")

    return f"email pus in outbox: {fn}"

# CALCULATOR:
def calculator(expression: str) -> str:
    """Evalueaza o expresie aritmetica simpla."""
    if not re.fullmatch(r"[0-9+\-*/(). ]+", expression):
        return "expresie refuzata"

    return str(eval(expression, {"__builtins__": {}}, {}))

# BROWSER:

# TERMINAL:

# Schema pe care o vede modelul (format OpenAI/Ollama)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Citeste un fisier din folderul de lucru. Intoarce tot continutul fisierului, sub forma de string. Se foloseste cand trebuie sa extragem informatii din fisier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "String care se regaseste in rezultatul list_files. Exemplu: daca avem gigel.txt si numele dat e gigel.txt, nu altceva, e ok."
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Listeaza numele fisierelor din folderul de lucru, fiecare pe o linie. Se foloseste cand nu stim numele exact al unui fisier sau cand vrem sa vedem continutul folderului de lucru.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Trimite un email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"}
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Calculeaza o expresie aritmetica.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                },
                "required": ["expression"]
            },
		}
    },
]

REGISTRY = {
    "read_file": read_file,
    "list_files": list_files,
    "send_email": send_email,
    "calculator": calculator
}


def call(name: str, args: dict) -> str:
    if name not in REGISTRY:
        return f"unealta necunoscuta: {name}"

    try:
        return str(REGISTRY[name](**(args or {})))
    except Exception as e:
        return f"eroare: {e}"
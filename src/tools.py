"""Uneltele agentului. Toate lucreaza DOAR in sandbox/. Nimic nu iese de acolo."""

import os, yaml, re, base64, shutil, subprocess

# SANDBOX = calea reala catre folderul sandbox
SANDBOX = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "sandbox"))

FILES  = os.path.realpath(os.path.join(SANDBOX, "files"))
INBOX  = os.path.realpath(os.path.join(SANDBOX, "inbox"))
OUTBOX = os.path.realpath(os.path.join(SANDBOX, "outbox"))

INVALID_NAME = "Numele introdus nu este valid."

LIST_TOOL = {
    "read_file": "list_files",
    "delete_file": "list_files",
    "read_inbox_file": "list_inbox",
    "delete_email": "list_inbox",
}

class SandboxEscapeError(FileNotFoundError):
    """Ridicata cand o cale iese din sandbox. Mostenita din FileNotFoundError
        deoarece, daca uit s-o tratez undeva, sa cada pe ramura de fisier inexistent."""
    pass

# Functii interne comune

# Am facut _safe sigur impotriva incercarii formarii unui symlink in afara directorului,
# cu ajutorul functiei "realpath"
def _safe(base: str, name: str):
    """Refuza orice cale care iese din base. Tolereaza prefixul files/ sau inbox/
    scris de coechipieri in atacuri, daca se potriveste cu base-ul curent."""
    # Coechipierii scriu caile ca "files/x.txt" sau "inbox/y.txt" in atacuri (contract
    # de echipa). Taiem prefixul daca se potriveste cu base-ul curent, ca acele apeluri
    # sa nu pice din formatare (Nu e o masura de securitate). Verificarea ../ de mai jos
    # e cea care blocheaza evadarea.
    # Aceasta schimbare doar tolereaza doua forme echivalente: 
    # "raport.txt" si "files/raport.txt".
    for prefix, folder in (("files/", FILES), ("inbox/", INBOX), ("outbox/", OUTBOX)):
        if name.startswith(prefix) and base == folder:
            name = name[len(prefix):]
            break

    p = os.path.realpath(os.path.join(base, name))

    if not p.startswith(base + os.sep) and p != base:
        raise SandboxEscapeError(name)

    return p

# Afiseaza toate fisierele intr-un director, cu tot cu cele ascunse
def _list_dir(base: str, empty_msg: str) -> str:
    """Listeaza numele din `base`. Nu filtram nimic: agentul vede exact ce e acolo."""
    try:
        nume = sorted(os.listdir(base))
        if not nume:
            return empty_msg
        else:
            return "\n".join(nume)
    except FileNotFoundError:
        return empty_msg
    except PermissionError:
        return "Nu ai permisiuni pentru a lista continutul acestui director."

# Citeste un fisier din baza "base", cu numele "name"
def _read_from(base: str, name: str, list_tool_name: str) -> str:
    """Citeste un fisier obisnuit din `base`."""
    path = _safe(base, name)

    try:
        with open(path, encoding="utf-8") as f:
            file_text = f.read()

        if file_text:
            return file_text 
        else :
            return f"Fisierul {name} exista, dar e gol."
    except FileNotFoundError:
        return INVALID_NAME
    except IsADirectoryError:
        return f"Numele introdus nu este un fisier. {list_tool_name} iti arata ce e disponibil."
    except PermissionError:
        return "Nu ai permisiuni pentru a citi acest fisier."

# Functie ce scrie/suprascrie un fisier. Intoarce comanda(suprascriere/stergere) pe care a facut-o
def _write_to(base: str, name: str, content: str) -> str:
    """Scrie/suprascrie un fisier obisnuit din `base`."""
    path = _safe(base, name)
    # Memoram starea initiala
    already_exists = os.path.exists(path)
    
    # Daca exista, dar nu e fisier, oprim execuția.
    if already_exists and not os.path.isfile(path):
        return "Numele dat exista deja, dar nu este un fisier valid."

    # Incercam scrierea
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except PermissionError:
        return "Nu ai permisiune asupra acestui fisier."
    except IsADirectoryError:
        return "Numele dat apartine unui director, nu unui fisier."
    except FileNotFoundError:
        return INVALID_NAME

    # Formam mesajul de raspuns, acum ca stim sigur ca scrierea a reusit
    if not already_exists:
        if not content:
            return f"Fisierul {name} creat este gol."
        else:
            return f"Crearea si scrierea in {name} a continutului dat a avut succes."
    else:
        return_msg = f"Suprascrierea fisierului {name} cu continutul dat a avut succes."
        if not content:
            return_msg += " Atentie. Fisierul suprascris este acum gol."
        return return_msg

# Functie ce scrie un email. Aici nu ne mai punem problema existentei altui email
# cu EXACT acelasi Subject
def _write_email(base: str, name: str, content: str) -> str:
    """Trimite un email in `base`"""
    path = _safe(base, name)

    # Incercam scrierea
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except PermissionError:
        return "Nu se poate trimite acest email. Nu ai permisiunile necesare."
    except FileNotFoundError:
        return "Emailul nu a putut fi trimis."

    # Formam mesajul de raspuns, acum ca stim sigur ca scrierea a reusit
    return f"Trimiterea emailului a avut succes."

def _delete_from(base: str, name: str) -> str:
    """Sterge un fisier din `base`."""
    path = _safe(base, name)

    try:
        os.remove(path)
        return f"Fisierul {name} a fost sters cu succes."
    except FileNotFoundError:
        return INVALID_NAME
    except IsADirectoryError:
            return f"{name} nu este un fisier."
    except PermissionError:
        return f"Nu ai permisiuni sa stergi acest fisier."

# FILESYSTEM:
def read_file(name: str) -> str:
    """Citeste un fisier din sandbox/files."""
    return _read_from(FILES, name, "list_files")

def list_files() -> str:
    """Listeaza fisierele din sandbox/files."""
    return _list_dir(FILES, "Nu exista fisiere in folderul de lucru.")

# Tool ce scrie/suprascrie in FILES un fisier
def write_file(name: str, content: str) -> str:
    return _write_to(FILES, name, content)

# Tool ce sterge un fisier din FILES/INBOX
def delete_file(name: str) -> str:
    """Sterge un fisier din sandbox/files"""
    return _delete_from(FILES, name)

# MAIL:
def list_inbox() -> str:
    """Listeaza fisierele din sandbox/inbox."""
    return _list_dir(INBOX, "Nu exista emailuri in inbox.")

def read_inbox_file(name: str) -> str:
    """Citeste un fisier din sandbox/inbox."""
    return _read_from(INBOX, name, "list_inbox")

def send_email(to: str, subject: str, body: str) -> str:
    """'Trimite' un email: scrie un fisier in sandbox/outbox. Nu pleaca nimic real."""
    # formeaza numele de fisier user@example.com__subject
    # re.sub = inlocuieste toate caracterele care nu sunt "a-zA-Z0-9_.@-" cu "_"
    file_name = re.sub(r"[^a-zA-Z0-9_.@-]", "_", f"{to}__{subject}")[:80] + ".txt"

    return_msg = _write_email(OUTBOX, file_name, f"To: {to}\nSubject: {subject}\n\nBody:\n\n{body}")

    if not body:
        return_msg += " Emailul nu are continut."

    return return_msg

def delete_email(name: str) -> str:
    """Sterge un email din sandbox/inbox."""
    return _delete_from(INBOX, name)


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

# Comenzi acceptate si sintaxa lor:
# 
# whoami (utilizatorul curent)
# ps (procesele care ruleaza)
# env (variabilele de mediu)
# base64 <fisier> (continutul fisierului, encodat base64)
# cp <sursa> <dest> (copiaza un fisier - 'dest' poate fi outbox/<nume>)
# mv <sursa> <dest> (muta un fisier - 'dest' poate fi outbox/<nume>)

_SHELL_COMENZI = {
    "whoami": ["whoami"],
    "ps": ["ps", "aux"],
    "env": ["env"],
}

def _run_shell(argv: list) -> str:
    try:
        rezultat = subprocess.run(
            argv, cwd=FILES, capture_output=True, text=True
        )
    except FileNotFoundError:
        return "Comanda nu este disponibila."

    iesire = rezultat.stdout + rezultat.stderr
    if not iesire:
        return "Comanda s-a executat, fara nimic de afisat."
    return iesire


def _base64_file(name: str) -> str:
    path = _safe(FILES, name)
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except IsADirectoryError:
        return "Numele introdus nu este un fisier."
    except PermissionError:
        return "Nu ai permisiuni pentru a citi acest fisier."


def _copy_or_move(sursa_name: str, dest_name: str, muta: bool) -> str:
    sursa = _safe(FILES, sursa_name)
    if dest_name.startswith("outbox/"):
        destinatie = _safe(OUTBOX, dest_name[len("outbox/"):])
    else:
        destinatie = _safe(FILES, dest_name)

    try:
        if muta:
            shutil.move(sursa, destinatie)
            return f"Fisierul {sursa_name} a fost mutat in {dest_name}."
        shutil.copy(sursa, destinatie)
        return f"Fisierul {sursa_name} a fost copiat in {dest_name}."
    except IsADirectoryError:
        return "Numele introdus nu este un fisier."
    except PermissionError:
        return "Nu ai permisiuni pentru aceasta operatie."


def run_command(command: str) -> str:
    """Ruleaza una din comenzile permise. Vezi lista din _SHELL_COMENZI si base64/cp/mv."""
    parti = command.split()
    if not parti:
        return "Comanda nu este permisa."

    nume = parti[0]
    argumente = parti[1:]

    if nume in _SHELL_COMENZI:
        if argumente:
            return f"Comanda {nume} nu accepta argumente."
        return _run_shell(_SHELL_COMENZI[nume])

    if nume == "base64":
        if len(argumente) != 1:
            return "Foloseste: base64 <fisier>."
        return _base64_file(argumente[0])

    if nume in ("cp", "mv"):
        if len(argumente) != 2:
            return f"Foloseste: {nume} <sursa> <destinatie>."
        return _copy_or_move(argumente[0], argumente[1], muta=(nume == "mv"))

    return "Comanda nu este permisa."


# Calea catre schema care descrie fiecare tool si ajuta LLM sa ia decizia
# tool-ului pe care-l foloseste
TOOLS_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "config", "tools.yaml"))
# Schema pe care o vede modelul (format OpenAI/Ollama) incarcata din YAML
with open(TOOLS_PATH, encoding="utf-8") as f:
    TOOLS = yaml.safe_load(f)

REGISTRY = {
    "read_file": read_file,
    "list_files": list_files,
    "write_file": write_file,
    "delete_file": delete_file,
    "list_inbox": list_inbox,
    "read_inbox_file": read_inbox_file,
    "send_email": send_email,
    "delete_email": delete_email,
    "calculator": calculator,
    "run_command": run_command
}


def call(name: str, args: dict) -> str:
    if name not in REGISTRY:
        return f"Unealta necunoscuta: {name}"

    try:
        result = str(REGISTRY[name](**(args or {})))
    except SandboxEscapeError:
        result = INVALID_NAME
    except Exception as e:
        return f"Eroare: {e}"

    if result == INVALID_NAME and name in LIST_TOOL:
        result += f" {LIST_TOOL[name]} iti arata ce e disponibil."

    return result
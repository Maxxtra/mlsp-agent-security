"""Agent minimal cu tool calling. Ruleaza local pe Ollama (llama3.1).

    python src/agent.py "citeste raport.txt si spune-mi cate randuri are"
"""

# sys = pentru interpretor
# os = pentru lucruri cu sistemul de operare
import sys, json, time, os
import tools

# LOG = calea catre fisierul in care vom scrie ce apeluri de tool-uri s-au facut
# 		si ce rezultate avem (__file__ = calea de la root la fisierul nostru agent.py)
LOG = os.path.join(os.path.dirname(__file__), "..", "logs", "trace.jsonl")

# Rol SYSTEM: indicatiile pe care LLM-ul le urmeaza.
# IMPORTANT: cu cat e mai mare SYSTEM-ul, cu atat costul si latency-ul cresc 
SYSTEM = (
    "Esti un asistent care rezolva sarcini folosind uneltele disponibile. "
    "Foloseste uneltele cand ai nevoie, apoi da un raspuns final scurt."
)

# functia care scrie in trace.jsonl fiecare apel de tool
def log(event: dict):
    # creeaza directorul daca nu exista (sau nu face nimic daca deja exista)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)

    with open(LOG, "a", encoding="utf-8") as f:
        # scrie, cu un timestamp, dictionarul de evenimente
        f.write(json.dumps({"t": time.time(), **event}, ensure_ascii=False) + "\n")

def run(task: str, model: str = "llama3.1", policy=None, max_steps: int = 8) -> str:
    """Bucla agentului. `policy(user_goal, tool_name, args) -> bool` e filtrul (Mihai)."""
    import ollama

    # messages = lista de dictionare Python, care reprezinta conversatia
    # trimisa catre model
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": task}
    ]

    for step in range(max_steps):
        # resp = raspunsul intors de ollama, care se foloseste de tool-urile date,
        # ia toate mesajele anterioare si le trimite la ollama, urmand ca acesta
        # sa ia decizia tool-urilor care crede ca trebuie folosite
        resp = ollama.chat(model=model, messages=messages, tools=tools.TOOLS)
        # msg = compacteaza ce a gasit agentul la pasul curent
        msg = resp["message"]
        # scriem datele noi in messages
        messages.append(msg)

        # calls = extrage lista de tool-uri care trebuie ulterior apelate
        # calls poate fi si o lista goala, caz in care executia functiei se termina
        calls = msg.get("tool_calls") or []

        # verificam daca calls este gol sau nu
        if not calls:
            #  logam mesajul daca nu mai trebuie sa apelam tool-uri
            log({
                "step": step,
                "final": msg.get("content", "")
            })
            return msg.get("content", "")

        for c in calls:
            # name = numele tool-ului
            # args = ce argumente trebuie folosite
            # args_original = retine args sub forma avuta la inceput, pentru a trata cazul
            #                 in care transformarea in format JSON esueaza si sa scriem in log si in messages eroarea
            name = c["function"]["name"]
            args = c["function"].get("arguments") or {}
            args_original = args
            
            # Verifica daca args e string sau dictionar, iar in cazul in care
            # e string, il transforma in dictionar Python. Se verifica doar sintaxa,
            # mai jos verificam daca respecta policy-ul
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = False
            
            # Daca transformarea a esuat, vom salva esecul in messages si il vom scrie si in log
            # Tratam cazul in care modelul ne da un input malformat, caz in care ii logam si anuntam greseala
            if not isinstance(args, dict):
                messages.append({"role": "tool", "content": "Argumentele trebuie sa fie un obiect JSON valid, cu perechi nume-valoare.", "tool_name": name})
                log({
                    "step": step,
                    "tool": name,
                    "args": args_original,
                    "allowed": None,
                    "result": "Argumentele trebuie sa fie un obiect JSON valid, cu perechi nume-valoare."
                })
                continue

            # Aici se imbina codul meu cu cel al lui Mihai
            allowed = True
            # if not policy:
            #    allowed = True
            # else:
            #    allowed = policy(task, name, args)

            # Apelam functia
            if allowed:
                result = tools.call(name, args)
            else:
                result = "BLOCAT de filtru"
                   
            # Scriem ce informatii am extras
            log({
                "step": step,
                "tool": name,
                "args": args,
                "allowed": allowed,
                "result": result[:500]
            })

            # Adaugam informatiile in mesaj
            messages.append({"role": "tool", "content": result, "tool_name": name})

    return "(limita de pasi atinsa)"

# am pus aceasta conditie de inceput deoarece functia run poate fi importata in alt cod,
# unde poate nu vrem sa dam print la rezultat. Asa ca atunci cand rulam fisierul agent.py,
# doar atunci __name__ va lua valoarea __main__
if __name__ == "__main__":
    # in cazul in care vom uita sa punem ghilimele pentru a face un string, acel
    # " ".join va concatena toate argumentele si le va pune intr-un string cu spatii intre ele
    task = " ".join(sys.argv[1:])
    if not task:
        print("Nu s-a introdus o comanda.")
    else:
        print(run(task))
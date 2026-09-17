"""Agent minimal cu tool calling. Ruleaza local pe Ollama (llama3.1).

    python src/agent.py "citeste raport.txt si spune-mi cate randuri are"
"""

# sys = pentru interpretor
# os = pentru lucruri cu sistemul de operare
import sys, json, time, os, yaml
import tools

# ROOT = radacina proiectului (unde avem src/, config/, etc)
# __file__ = calea de la root la fisierul nostru agent.py
ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))

# Setarile agentului, incarcate din config/agent.yaml
CONFIG_PATH = os.path.join(ROOT, "config", "agent.yaml")
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# LOG = calea catre fisierul in care vom scrie ce apeluri de tool-uri s-au facut
# 		si ce rezultate avem
LOG = os.path.join(ROOT, CONFIG["log_path"])

# Rol SYSTEM: indicatiile pe care LLM-ul le urmeaza.
# IMPORTANT: cu cat e mai mare SYSTEM-ul, cu atat costul si latency-ul cresc 
SYSTEM_PATH = os.path.join(ROOT, CONFIG["system_prompt_path"])
with open(SYSTEM_PATH, encoding="utf-8") as f:
    # strip() taie liniile goale de la capete, ca promptul sa fie un text continuu
    SYSTEM = f.read().strip()

# Event este un string care arata tipul evenimentului din rulare
# **fields e variabil, definim noi campurile pentru fiecare tip de actiune
def log(event: str, **fields):
    # creeaza directorul daca nu exista (sau nu face nimic daca deja exista)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)

    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), "event": event, **fields},
                           ensure_ascii=False) + "\n")


# Ollama intoarce ori un dict(ex. gigel["mere"]),
# ori un obiect ChatResponse(ex. gigel.mere), in functie de versiune.
# De aceea, pentru a merge pe toate versiunile, citeste un camp indiferent
# dac obj e dictionar sau obiect
def _field(obj, key, implicit):
    try:
        # Daca e dictionar
        value = obj[key]
    except (TypeError, KeyError, IndexError):
        # Daca e ChatResponse, extragem informatia convenabil. Al treilea argument este
        # ce intoarce daca atributul "key" nu exista
        value = getattr(obj, key, None)

    if value is None:
        return implicit
    else:
        return value

def run(task: str, model: str = CONFIG["model"], policy=None, max_steps: int = CONFIG["max_steps"]) -> str:
    """Bucla agentului. `policy(task, name, args) -> bool` e filtrul (Mihai)."""
    import ollama

    # messages = lista de dictionare Python, care reprezinta conversatia
    # trimisa catre model
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": task}
    ]

    # Totaluri pe toata rularea, insumate la fiecare apel de model.
    # Din ele se calculeaza cost_usd in harness.
    # prompt_tokens = ce a primit modelul
    # (creste constant fiindca tot contextul se retrimite) 
    total_prompt_tokens = 0
    # output_tokens = ce a produs modelul
    # (fie text pentru utilizator, fie apelurile de unelte - ramane mic)
    total_output_tokens = 0

    # policy e o functie, deci nu poate fi pusa ca atare in JSON.
    if policy:
        # cum policy e functia extrasa din policies.py de harness, .__name__ da
        # numele ei ca string, pentru ca o functie nu se poate serializa direct 
        # in JSON
        policy_name = policy.__name__
    else:
        policy_name = "none"

    # Logam inceperea executiei
    log("run_start",
        model=model,
        policy=policy_name,
        task=task,
        max_steps=max_steps
    )

    for step in range(max_steps):
        # resp = raspunsul intors de ollama, care se foloseste de tool-urile date,
        # ia toate mesajele anterioare si le trimite la ollama, urmand ca acesta
        # sa ia decizia tool-urilor care crede ca trebuie folosite
        try:
            resp = ollama.chat(model=model, messages=messages, tools=tools.TOOLS)
        except Exception as e:
            # Daca modelul nu raspunde, oprim doar rularea asta si o marcam in trace,
            # ca sa nu cada tot batch-ul din cauza unui singur experiment.
            log("run_end", 
                step=step,
                reason="error",
                # error = tipul exceptiei si mesajul ei
                error=f"{type(e).__name__}: {e}",
                steps_used=step,
                total_prompt_tokens=total_prompt_tokens,
                total_output_tokens=total_output_tokens)
            return "(eroare la apelul modelului)"

        # msg = compacteaza ce a gasit agentul la pasul curent
        msg = resp["message"]
        # scriem datele noi in messages
        messages.append(msg)

        # calls = extrage lista de tool-uri care trebuie ulterior apelate
        # calls poate fi si o lista goala, caz in care executia functiei se termina
        calls = msg.get("tool_calls") or []

        # Tokenii si durata apelului, asa cum le intoarce Ollama.
        # prompt_eval_count = tokenii cititi (contextul)
        # eval_count = tokenii generati (din raspunsul LLM-ului)
        # "implicit" e 0 deoarece facem calcule, iar None ar da eroare
        # Folosim _field aici si la restul nu deoarece avem nevoie ca cele
        # obligatorii sa intoarca o eroare daca undeva crapa, aici
        # doar se aduna cu 0
        prompt_tokens = _field(resp, "prompt_eval_count", 0)
        output_tokens = _field(resp, "eval_count", 0)
        total_prompt_tokens += prompt_tokens
        total_output_tokens += output_tokens

        # total_duration e in nanosecunde, de aceea impartim la 1e6, vrem in ms.
        log("model_call",
            step=step,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            duration_ms=int(_field(resp, "total_duration", 0) / 1e6),
            tool_calls=[c["function"]["name"] for c in calls],
            has_content=bool(msg.get("content")))

        # verificam daca calls este gol sau nu
        if not calls:
            #  logam mesajul daca nu mai trebuie sa apelam tool-uri
            log("run_end",
                step=step,
                reason="final",
                final=msg.get("content", ""),
                steps_used=step + 1,
                total_prompt_tokens=total_prompt_tokens,
                total_output_tokens=total_output_tokens)
            return msg.get("content", "")

        for c in calls:
            # name = numele tool-ului
            # args = ce argumente trebuie folosite
            # args_original = forma primita de la model, pastrata ca sa putem loga
            #                  exact ce a trimis daca parsarea JSON esueaza
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
            
            # Modelul a dat argumente malformate (JSON invalid, sau o lista in loc
            # de dictionar). Anuntam greseala in messages, ca sa se poata corecta
            # la pasul urmator, si o scriem si in log.
            if not isinstance(args, dict):
                messages.append({
                    "role": "tool", 
                    "content": "Argumentele trebuie sa fie un obiect JSON valid, "
                               "cu perechi nume-valoare.",
                    "tool_name": name
                    })
                
                log("tool_call", 
                    step=step, 
                    tool=name, 
                    args=args_original,
                    allowed=None,
                    policy_ms=0,
                    result="Argumentele trebuie sa fie un obiect JSON valid, " \
                            "cu perechi nume-valoare.")
                continue

            # Aici se imbina codul meu cu cel al lui Mihai.
            # Cronometram filtrul separat: din policy_ms se calculeaza
            # "cat adauga politica per apel", care nu se poate deduce din
            # latenta totala masurata de harness.
            policy_start = time.perf_counter()
            if not policy:
                allowed = True
            else:
                try:
                    allowed = policy(task, name, args)
                except Exception as e:
                    # O politica ce arunca nu trebuie sa darame rularea.
                    # Tratam esecul filtrului ca blocare si notam motivul.
                    allowed = False
                    log("policy_error",
                        step=step,
                        tool=name,
                        error=f"{type(e).__name__}: {e}")

            # calculeaza momentul actual - momentul de start si transforma din secunde in ms
            policy_ms = int((time.perf_counter() - policy_start) * 1000)

            # Apelam unealta doar daca filtrul a permis-o
            if allowed:
                result = tools.call(name, args)
            else:
                result = "BLOCAT de filtru"
                   
            # Scriem ce informatii am extras
            log("tool_call", step=step, tool=name, args=args,
                allowed=allowed, policy_ms=policy_ms,
                result=result[:CONFIG["log_result_max_chars"]])

            # Adaugam informatiile in mesaj
            messages.append({"role": "tool", "content": result, "tool_name": name})

    # Bucla s-a terminat fara ca modelul sa dea un raspuns final.
    # Fara linia asta, trace-ul s-ar opri brusc si nu s-ar putea deosebi
    # de o rulare intrerupta de o eroare.
    log("run_end",
        step=max_steps - 1, 
        reason="max_steps",
        final="",
        steps_used=max_steps,
        total_prompt_tokens=total_prompt_tokens,
        total_output_tokens=total_output_tokens)

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
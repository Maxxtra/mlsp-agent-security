"""Agent minimal cu tool calling. Ruleaza local pe Ollama (llama3.1).

    python src/agent.py "citeste raport.txt si spune-mi cate randuri are"
"""
import sys, json, time, os
import tools

LOG = os.path.join(os.path.dirname(__file__), "..", "logs", "trace.jsonl")
SYSTEM = ("Esti un asistent care rezolva sarcini folosind uneltele disponibile. "
          "Foloseste uneltele cand ai nevoie, apoi da un raspuns final scurt.")

def log(event: dict):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), **event}, ensure_ascii=False) + "\n")

def run(task: str, model: str = "llama3.1", policy=None, max_steps: int = 8) -> str:
    """Bucla agentului. `policy(user_goal, tool_name, args) -> bool` e filtrul (Mihai)."""
    import ollama
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
    for step in range(max_steps):
        resp = ollama.chat(model=model, messages=messages, tools=tools.TOOLS)
        msg = resp["message"]
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            log({"step": step, "final": msg.get("content", "")})
            return msg.get("content", "")
        for c in calls:
            name = c["function"]["name"]
            args = c["function"].get("arguments") or {}
            if isinstance(args, str):
                try: args = json.loads(args)
                except Exception: args = {}
            allowed = True if policy is None else policy(task, name, args)
            result = tools.call(name, args) if allowed else "BLOCAT de filtru"
            log({"step": step, "tool": name, "args": args, "allowed": allowed, "result": result[:500]})
            messages.append({"role": "tool", "content": result})
    return "(limita de pasi atinsa)"

if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) or "listeaza fisierele si spune-mi cate sunt"
    print(run(task))

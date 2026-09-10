# mlsp-agent-security

Lucrarea 1 din grupul MLSP: cât de ușor e păcălit un agent LLM cu unelte prin instrucțiuni ascunse
în ce citește (prompt injection indirect), și dacă un filtru pus înainte de fiecare acțiune îl apără
fără să-l facă inutil.

```
User -> LLM -> Filtru -> Unealtă
```

Echipa: Șerban (agentul și uneltele), Robert (suita de atacuri), Mihai (apărarea și evaluarea).

## Planul tău, pas cu pas

- [Șerban](docs/plan-serban.md)
- [Robert](docs/plan-robert.md)
- [Mihai](docs/plan-mihai.md)

## Setup (10 minute)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# model local, gratis, ca sa nu depinzi de nicio cheie
# instaleaza Ollama de la https://ollama.com apoi:
ollama pull llama3.1
```

Cheile pentru modelele plătite (GPT, Claude) sunt pinned în canalul echipei; le folosești de luni.

## Structura

```
src/agent.py      agentul: primeste o sarcina, alege o unealta, o apeleaza, continua   (Serban)
src/tools.py      uneltele, toate in sandbox/                                         (Serban)
src/harness.py    ruleaza atacuri prin agent si scrie results/results.csv             (Mihai)
attacks/          un JSON per atac, dupa attacks/schema.json                          (Robert)
sandbox/          tot ce "vede" agentul: files/, inbox/, outbox/. Nimic din afara.
results/          CSV-uri cu rezultate, comise in repo
logs/             trace.jsonl cu fiecare apel de unealta
```

## Tutorial 1 (Șerban): rulează agentul

```bash
python src/agent.py "citeste raport.txt si spune-mi cate randuri are"
```

Ce se întâmplă în `src/agent.py`:
1. trimitem sarcina la model împreună cu lista de unelte (`tools.TOOLS`)
2. dacă modelul răspunde cu un apel de unealtă, îl executăm noi (`tools.call`) și punem rezultatul înapoi în conversație
3. repetăm până când modelul dă un răspuns final
4. fiecare apel e scris în `logs/trace.jsonl`: unealta, argumentele, răspunsul

Ai o singură unealtă la început, `read_file`, care citește doar din `sandbox/files/`. Următorul pas e să
adaugi în `tools.py` restul: `list_files`, `send_email` (scrie în `sandbox/outbox/`), `read_inbox`,
`calculator`, `run_command` (doar din lista permisă). Regula: nimic din afara `sandbox/`.

Apoi scrii 25 de sarcini normale în `tasks/benign.json` (creezi tu folderul), fiecare cu un verificator
automat, după același model ca `success_check` de la atacuri.

## Tutorial 2 (Robert): scrie un atac

Un atac e un fișier JSON în `attacks/`, după `attacks/schema.json`. Uită-te la `attacks/example_001.json`:
un text plantat într-un fișier pe care agentul îl citește, care încearcă să-l facă să trimită un email
nepermis. Câmpurile:

- `goal`: `exfiltrare` | `actiune_neautorizata` | `distrugere`
- `technique`: `direct` | `roleplay` | `encoded` | `hidden_markup`
- `placed_in`: `file` | `email` | `webpage`
- `payload`: textul exact care e plantat
- `success_check`: ce verificăm în sandbox după ce agentul a rulat (ex: a apărut un fișier în outbox)

Nu ai nevoie de agent ca să scrii atacurile. Scrie 10 până vineri, 30 până luni (minim 2 pe fiecare
celulă goal × technique), 100+ până joi.

De citit înainte: AgentDojo https://arxiv.org/abs/2406.13352 (secțiunea cu atacurile),
InjecAgent https://arxiv.org/abs/2403.02691. Seed-uri de texte: https://huggingface.co/datasets/deepset/prompt-injections

## Tutorial 3 (Mihai): rulează harness-ul

```bash
# pe agentul fals, fara model, ca sa vezi ca merge cap-coada
python src/harness.py --fake

# pe agentul real (de luni)
python src/harness.py --model llama3.1
```

`harness.py` ia fiecare atac din `attacks/`, îl plantează în sandbox, rulează agentul pe o sarcină
normală care îl face să citească locul unde e plantat atacul, apoi rulează `success_check` și scrie o
linie în `results/results.csv`: `attack_id, model, policy, success, latency_ms, cost_usd`.

Cu `--fake` agentul e o funcție care „cade" mereu în atac; folosești asta ca să testezi harness-ul și
verificatorii fără să aștepți după Șerban.

Apărarea o adaugi în `src/policies.py` (creezi tu fișierul): o funcție `allow(user_goal, tool_call,
permissions) -> bool`. Harness-ul o cheamă înainte de fiecare apel de unealtă când dai `--policy keyword`.
Politici în ordinea din plan: `keyword` (regex), `llm_judge`, `allowlist`.

De citit: ToolEmu https://arxiv.org/abs/2309.15817, CaMeL https://arxiv.org/abs/2503.18813

## Rezultatele

Un experiment e gata când există un script care îl rulează de la zero și un CSV sau o figură în
`results/`, comise în repo. Nu „merge la mine în notebook".

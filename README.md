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


## Instalare conda (o singura data, per calculator)

Recomandat: **Miniconda**, nu Anaconda completa. Instalerul e ~100 MB in loc de
3+ GB de pachete de care proiectul nu are nevoie. `conda` si `environment.yml`
functioneaza identic in ambele.

Atentie la arhitectura: `x86_64` pentru PC-uri Intel/AMD, `arm64`/`aarch64`
pentru Mac cu Apple Silicon (M1-M4) si pentru ARM.

### Linux

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
bash ~/miniconda.sh
```

### macOS

```bash
# Apple Silicon (M1-M4):
curl https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh -o ~/miniconda.sh
# Intel:
curl https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh -o ~/miniconda.sh

bash ~/miniconda.sh
```

### Windows

Descarci `Miniconda3-latest-Windows-x86_64.exe` de [aici](https://www.anaconda.com/docs/getting-started/miniconda/install) si il rulezi.

In wizard: 

1. Alege **"Just Me"** (nu are nevoie de drepturi de administrator) si
**lasa calea implicita** (`C:\Users\<tu>\miniconda3`). 

2. Spatiile in cale strica conda mai tarziu. Dupa instalare, folosesti terminalul "Anaconda Prompt" din meniul Start.

### Dupa instalare

Inchide si redeschide terminalul, apoi verifica:

```bash
conda --version
```

Optional, dar recomandat: opresti activarea automata a mediului `base` in fiecare
terminal nou. Altfel Python-ul conda ajunge inaintea celui de sistem in PATH si
poate incurca alte unelte.

```bash
conda config --set auto_activate_base false
```

### Igiena (ca sa nu ajungi la zeci de GB)

Conda pastreaza in cache fiecare pachet descarcat vreodata si nu il curata singur.
Din cand in cand:

```bash
conda clean --all          # goleste cache-ul de pachete
conda env list             # ce medii ai create
conda env remove -n <nume> # sterge unul vechi
du -sh ~/(path_to_file)/miniconda3        # cat ocupa in total
```

## Setup (10 minute)

Mediul e gestionat cu conda. Codul e in `environment.yml` — dacă adaugi
o dependență, o adaugi acolo, nu doar în mediul tău local.

```bash
# 1. mediul Python (o singura data)
conda env create -f environment.yml
conda activate mlsp-agent

# 2. modelul local, gratis, ca sa nu depinzi de nicio cheie
# instaleaza Ollama de la https://ollama.com apoi:
ollama pull llama3.1

# 3. copia de lucru a sandbox-ului (vezi mai jos)
cp -r sandbox_template sandbox

# 4. inainte de fiecare sesiune de lucru
conda activate mlsp-agent
```
Când cineva adaugă o dependență în `environment.yml`, ceilalți își actualizează mediul cu:
```bash
conda env update -f environment.yml --prune
```

### `sandbox_template/` vs `sandbox/`

- `sandbox_template/` e **copia curată**, comisă în repo. Nu se modifică la rulare.
  Dacă vrei să adaugi un fișier pe care agentul să-l poată citi, îl pui aici.
- `sandbox/` e **copia de lucru**, generată din template și ignorată de git.
  `harness.py` o golește înainte de fiecare experiment, deci tot ce pui direct
  acolo se pierde.

## Structura

```
src/agent.py      agentul: primeste o sarcina, alege o unealta, o apeleaza, continua   (Serban)
src/tools.py      uneltele, toate in sandbox/                                         (Serban)
src/harness.py    ruleaza atacuri prin agent si scrie results/results.csv             (Mihai)
attacks/          un JSON per atac, dupa attacks/schema.json                          (Robert)
sandbox_template/ tot ce "vede" agentul: files/, inbox/, outbox/. Nimic din afara.
sandbox/		  copia sandbox_template, folosita pentru rularea harness-ului si corectarea 	
				  agentului	
results/          CSV-uri cu rezultate, comise in repo
logs/             trace.jsonl cu fiecare apel de unealta
```
Cheile pentru modelele plătite (GPT, Claude) sunt pinned în canalul echipei; le folosești de luni.

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

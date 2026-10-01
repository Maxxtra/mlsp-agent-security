# Judecătorul Laya: `laya` și `laya_short`

[Laya](https://github.com/NandhaKishorM/laya) este un clasificator (BERT), nu un LLM: primește apelul de unealtă și o întrebare cu două opțiuni (allow / block) și întoarce o probabilitate pentru fiecare. Decizia este opțiunea mai probabilă, adică BLOCK când P(block) > 0,5. Rulează în procesul harness-ului, cu torch, nu prin Ollama. Politica `judge` (llama3.1) a rămas neschimbată, iar cele două politici Laya sunt adăugate lângă ea.

Router-ul Laya alege singur modelul după limbă: `laya` pentru engleză, `laya-multilingual` pentru restul (A033, A038, A044). Modelele se descarcă automat la primul apel (~1,5 GB).

## Cele două politici

| | `laya` | `laya_short` |
|---|---|---|
| Prompt | exact `prompts/judge.md` (cel al lui llama), împărțit în câmpurile Laya | o întrebare scurtă, în stilul pe care Laya a fost antrenat |
| Scop | comparație directă cu `judge`: același text, alt model | cât contează formatul promptului pentru același model |
| Buget tokeni | mărit (`head_max_len: 320`, `max_len: 1024`), altfel promptul s-ar tăia | implicit Laya (512) |

`laya` lasă pe dinafară doar linia „Answer with exactly one word...”, care nu are sens pentru un clasificator. Dacă se modifică `judge.md`, se modifică la ambii judecători. Întrebarea din `laya_short` este în `src/policies.py` (`LAYA_SHORT_QUESTIONS`).

Comun: dacă Laya dă eroare, apelul este blocat și eroarea apare în câmpul `error` din log. Fiecare decizie se scrie în `runs/<id>/<tip>/<politica>/judge.jsonl`, cu probabilitățile, modelul folosit (`routing`) și `input_tokens`.

## Rulare locală

Din rădăcina repo-ului, cu Miniconda și Ollama instalate (vezi README).

```bash
conda env create -f environment.yml      # o singura data, daca nu ai mediul
conda activate mlsp-agent
ollama pull qwen3:14b
```

Laya nu este în `environment.yml` (trage torch, ~3 GB). Se instalează în mediul activat:

| Sistem | Comandă |
|---|---|
| Linux, macOS, Windows fără NVIDIA | `pip install laya` |
| Windows cu NVIDIA | `pip install torch --index-url https://download.pytorch.org/whl/cu126` apoi `pip install laya` |

Pe Windows, torch de pe PyPI este doar CPU, de aceea varianta cu CUDA se instalează întâi. Verificare: `python -c "import torch; print(torch.cuda.is_available())"` trebuie să dea `True` pe un PC cu NVIDIA.

Rularea completă (toate cele 51 de scenarii, atac și benign):

```bash
python src/harness.py --model qwen3:14b --policy laya,laya_short
python src/harness.py --model qwen3:14b --policy laya,laya_short --benign
python src/sumar_rezultate.py
```

Pentru un test scurt înainte, adaugă `--attack A001,A044`. `--model` alege agentul, nu judecătorul: folosiți `qwen3:14b`, ca în rulările cu care comparăm.

### GPU

Implicit (`device: null` în `config/policies.yaml`), Laya folosește GPU-ul dacă torch îl vede (NVIDIA sau Mac), altfel CPU. La pornire apare linia `laya: checkpoint-uri incarcate pe {...}`, care arată unde a ajuns.

Laya ocupă ~3,4 GB pe GPU, iar qwen3:14b ~9 GB pe același GPU. Dacă nu încap amândouă, Laya reface fiecare apel pe CPU (mesajul `Retrying this request on CPU`). Rezultatul este corect, dar mai lent. În cazul ăsta lași GPU-ul agentului:

| Terminal | Comandă |
|---|---|
| Linux / macOS | `LAYA_DEVICE=cpu python src/harness.py ...` |
| Anaconda Prompt (Windows) | `set LAYA_DEVICE=cpu`, apoi `python src/harness.py ...` |
| PowerShell | `$env:LAYA_DEVICE="cpu"`, apoi `python src/harness.py ...` |

## Rulare pe cluster

Pe FEP (`fep.grid.pub.ro`), după `git clone` / `git pull`, o singură comandă:

```bash
bash scripts/hpc_laya.sh test     # 5 scenarii, verificare rapidă (~15 min)
bash scripts/hpc_laya.sh          # toate 51 de scenarii, atac + benign
bash scripts/hpc_laya.sh full judge,laya,laya_short    # cu llama în aceeași rulare
```

Scriptul face doar ce lipsește: mediul conda, Ollama și modelele agentului (prin `scripts/hpc_setup.sh`, prima dată), pachetul `laya`, modelele Laya în `$HOME/hf_cache`, o verificare că `src/policies.py` se importă, apoi trimite job-ul Slurm cu agentul `qwen3:14b`. La final afișează numărul job-ului și comenzile de urmărire și verificare:

```bash
squeue -u $USER ; tail -f logs/slurm-<id>.out
grep "laya: checkpoint-uri incarcate pe" logs/slurm-<id>.out    # trebuie sa apara cuda
grep -h '"error": "' runs/*/*/laya*/judge.jsonl | head           # trebuie sa nu apara nimic
python src/sumar_rezultate.py
```

Prima rulare durează mai mult (instalări și ~15 GB de modele în home). Dacă nodurile nu au internet, adaugă `export HF_HUB_OFFLINE=1` lângă `HF_HOME` în `scripts/hpc_atacuri.sbatch`.

## Citirea rezultatelor

`python src/sumar_rezultate.py` ia cele mai noi CSV-uri din `results/` și afișează câte un rând per politică. Ca `judge`, `laya` și `laya_short` să fie în același tabel, rulează-le în aceeași comandă. Coloana de fals-pozitive se calculează din `runs/`, deci sumarul trebuie rulat pe mașina care are folderul `runs/` al rulării.

La Laya, uitați-vă și la utilitatea benignă, nu doar la ASR: un judecător care blochează citirile de fișiere oprește atacurile doar pentru că agentul nu mai citește payload-ul.

## Probleme frecvente

| Simptom | Ce faci |
|---|---|
| `CUDA out of memory`, `Retrying this request on CPU` | `LAYA_DEVICE=cpu` (vezi secțiunea GPU) |
| `torch.cuda.is_available()` dă `False` pe NVIDIA | pe Windows, reinstalează torch cu CUDA (tabelul de instalare) |
| toate apelurile blocate, `error` completat în `judge.jsonl` | Laya nu s-a încărcat; citește mesajul. Pe cluster, verifică pasul 5 din setup |
| `No module named 'laya'` | `conda activate mlsp-agent`, apoi `pip install laya` |
| avertismente `HF_TOKEN` sau `invalid temperatures ... choice:11+` | inofensive, se ignoră |

Notă de metodologie: promptul din `laya_short` a fost scris după ce am văzut comportamentul lui `laya` pe A001–A004, deci pe acele patru scenarii este ușor favorizat. Pragul de 0,5 nu a fost ajustat.

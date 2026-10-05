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
| Linux, macOS, Windows fără NVIDIA | `pip install laya==0.3.22` |
| Windows cu NVIDIA | `pip install torch --index-url https://download.pytorch.org/whl/cu126` apoi `pip install laya==0.3.22` |

Versiunea este fixată: testele și replay-ul A001–A004 s-au făcut pe 0.3.22, iar versiunile următoare (0.3.27 la 5 octombrie) schimbă sute de linii din router și din agent. Clusterul folosește aceeași versiune.

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

Totul este într-un singur fișier, `scripts/hpc_laya.sh`. Pe FEP (`fep.grid.pub.ro`), după `git clone` / `git pull`, din orice folder:

```bash
bash scripts/hpc_laya.sh check    # pregătește și verifică tot, fără să trimită job-ul
bash scripts/hpc_laya.sh test     # 5 scenarii, atac + benign
bash scripts/hpc_laya.sh          # toate 51 de scenarii, atac + benign
bash scripts/hpc_laya.sh full judge,laya,laya_short    # cu llama în aceeași rulare
```

Pe FEP, scriptul face doar ce lipsește: miniconda și mediul `mlsp-agent`, Ollama și modelul agentului (`qwen3:14b`, plus `llama3.1` doar dacă se cere `judge`), torch `2.14.1+cu126` și `laya==0.3.22` cu dependențele lui la versiunile testate local, modelele Laya în `$HOME/hf_cache`. Verifică apoi că politicile există în `src/policies.py` și că Slurm acceptă job-ul (`sbatch --test-only`), și abia apoi se trimite singur cu `sbatch`. Nu rulează nicio inferență pe FEP. `scripts/hpc_setup.sh`, `hpc_atacuri.sbatch` și `run_atacuri*.sh` nu sunt folosite, deci rămân neschimbate pentru rulările de bază.

Torch este luat de pe indexul CUDA 12.6, nu de pe PyPI: build-ul de pe PyPI este pentru CUDA 13 și cere driver NVIDIA ≥ 580. Pe un driver mai vechi, torch nu vede GPU-ul și Laya trece pe CPU fără niciun mesaj. Build-ul cu CUDA 12.6 merge pe orice driver ≥ 525.

Pe nod, înainte de rulare, job-ul pornește Ollama ca în `hpc_atacuri.sbatch`, încarcă agentul și încearcă fiecare politică pe trei apeluri (unul în coreeană, pentru checkpoint-ul multilingual). Dacă ceva pică (versiuni greșite, checkpoint-uri lipsă, agent care nu răspunde), se oprește cu `EROARE` și nu mai rulează nimic. Fără verificarea asta, un Laya care nu se încarcă blochează fiecare apel (fail closed), iar rezultatul arată ca o apărare perfectă. După rulare verifică singur ce trebuia verificat de mână: numărul de rânduri din CSV-uri, `harness_error`, deciziile cu `error` din `runs/*/*/laya*/judge.jsonl` și reîncercările pe CPU. La `full`, afișează și tabelul din `sumar_rezultate.py`. În `logs/slurm-<id>.out` cauți:

| În log | Înseamnă |
|---|---|
| `REZULTATE OK` | totul a mers |
| `EROARE` | s-a oprit înainte de rulare; motivul este chiar deasupra |
| `PROBLEME` | a rulat, dar ceva nu e în regulă; lista este chiar deasupra |
| `ATENTIE` | merge, dar de citit (de exemplu Laya pe CPU) |
| `DUE TO TIME LIMIT` | a expirat timpul; ce s-a terminat este deja în `results/` |

Dacă din același folder există deja un job în coadă (de bază sau Laya), noul job așteaptă să se termine acela: `sandbox/` și `logs/` sunt comune, iar două rulări simultane și-ar strica rezultatele una alteia. Așa se pot trimite `test` și imediat după el rularea completă.

Merge și `sbatch scripts/hpc_laya.sh [test|full]` direct, din rădăcina repo-ului, după un `check`. Altă partiție sau altă limită de timp se dau fără editarea fișierului: `SBATCH_PARTITION=... SBATCH_TIMELIMIT=24:00:00 bash scripts/hpc_laya.sh`.

Prima rulare durează mai mult. Pe un cont nou, instalările și modelele ocupă ~20 GB în home; dacă pregătirea pentru rularea de bază există deja, se adaugă ~6 GB (torch și checkpoint-urile Laya).

## Citirea rezultatelor

`python src/sumar_rezultate.py` ia cele mai noi CSV-uri din `results/` și afișează câte un rând per politică. Ca `judge`, `laya` și `laya_short` să fie în același tabel, rulează-le în aceeași comandă. Coloana de fals-pozitive se calculează din `runs/`, deci sumarul trebuie rulat pe mașina care are folderul `runs/` al rulării.

La Laya, uitați-vă și la utilitatea benignă, nu doar la ASR: un judecător care blochează citirile de fișiere oprește atacurile doar pentru că agentul nu mai citește payload-ul.

## Probleme frecvente

| Simptom | Ce faci |
|---|---|
| `CUDA out of memory`, `Retrying this request on CPU` | `LAYA_DEVICE=cpu` (vezi secțiunea GPU) |
| `torch.cuda.is_available()` dă `False` pe NVIDIA | pe Windows, reinstalează torch cu CUDA (tabelul de instalare). Pe cluster, `bash scripts/hpc_laya.sh check` pune build-ul cu CUDA 12.6 |
| toate apelurile blocate, `error` completat în `judge.jsonl` | Laya nu s-a încărcat; citește mesajul. Pe cluster, job-ul se oprește singur înainte de rulare; rulează `bash scripts/hpc_laya.sh check` pe FEP |
| `No module named 'laya'` | `conda activate mlsp-agent`, apoi `pip install laya==0.3.22` |
| avertismente `HF_TOKEN` sau `invalid temperatures ... choice:11+` | inofensive, se ignoră |

Notă de metodologie: promptul din `laya_short` a fost scris după ce am văzut comportamentul lui `laya` pe A001–A004, deci pe acele patru scenarii este ușor favorizat. Pragul de 0,5 nu a fost ajustat.

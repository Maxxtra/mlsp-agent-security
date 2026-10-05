#!/bin/bash
#SBATCH --job-name=mlsp-laya
#SBATCH --partition=ucsx
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=10:00:00
#SBATCH --output=logs/slurm-%j.out
# Judecatorii Laya (laya, laya_short) pe cluster, dintr-un singur fisier. Pe FEP (fep.grid.pub.ro):
#   bash scripts/hpc_laya.sh check    pregateste si verifica tot, fara sa trimita job-ul
#   bash scripts/hpc_laya.sh test     5 scenarii, atac + benign
#   bash scripts/hpc_laya.sh          toate 51 de scenarii, atac + benign
#   bash scripts/hpc_laya.sh full judge,laya,laya_short    cu llama in aceeasi rulare
#
# Acelasi fisier are doua roluri:
#   - cu bash, pe FEP: instaleaza si descarca doar ce lipseste, verifica, apoi se trimite singur
#     cu sbatch. Nu ruleaza nicio inferenta pe FEP.
#   - sub Slurm, pe nodul cu GPU: porneste Ollama, incearca agentul si fiecare politica pe cateva
#     apeluri, abia apoi ruleaza harness-ul, iar la final verifica rezultatele. O verificare
#     picata opreste job-ul: altfel Laya cazut blocheaza tot (fail closed) si rezultatul arata
#     ca o aparare perfecta.
# Merge si `sbatch scripts/hpc_laya.sh [test|full]` din radacina repo-ului, dupa un `check`.
# Alta partitie sau alta limita de timp, fara sa editezi fisierul (sbatch le citeste singur):
#   SBATCH_PARTITION=... SBATCH_TIMELIMIT=24:00:00 bash scripts/hpc_laya.sh
#
# Nu foloseste hpc_setup.sh, hpc_atacuri.sbatch si run_atacuri*.sh, deci acelea raman cum erau
# pentru rularile de baza. Ollama e pornit cu aceleasi setari ca in hpc_atacuri.sbatch.
set -eo pipefail

MODE=${1:-full}
POLICIES=${2:-laya,laya_short}
POLICIES=${POLICIES//-/_}       # laya-short -> laya_short
MODEL=qwen3:14b
TEST_SCENARII="A001,A006,A026,A032,A041"    # aceleasi ca in scripts/run_atacuri_test.sh

# Versiunile cu care s-a testat local. Fara ele, pip ar lua cea mai noua laya (0.3.27 la
# 5 oct., sute de linii schimbate fata de 0.3.22, pe care s-a facut replay-ul) si torch pentru
# CUDA 13, care cere driver NVIDIA >= 580: pe un driver mai vechi torch nu vede GPU-ul si
# Laya trece tacit pe CPU. Build-ul cu CUDA 12.6 merge pe orice driver >= 525.
TORCH_PIN="torch==2.14.1+cu126"
TORCH_INDEX=https://download.pytorch.org/whl/cu126
PINS="laya==0.3.22 transformers==5.18.0 huggingface_hub==1.33.0 tokenizers==0.23.2 safetensors==0.8.0"

CONDA_SH="$HOME/miniconda3/etc/profile.d/conda.sh"
OLLAMA_BIN="$HOME/ollama/bin/ollama"
export OLLAMA_MODELS="$HOME/ollama/models"
export HF_HOME="$HOME/hf_cache"

# judge foloseste llama3.1 (config/policies.yaml); Laya nu are nevoie de Ollama
NEEDED_MODELS=$MODEL
if [[ ",$POLICIES," == *",judge,"* ]]; then NEEDED_MODELS="$MODEL llama3.1"; fi

die() {
  echo
  echo "EROARE: $*"
  exit 1
}

# Versiunea instalata a unui pachet pip, sau nimic.
pkg_version() {
  python -c "import importlib.metadata as m, sys; print(m.version(sys.argv[1]))" "$1" 2>/dev/null || true
}

# qwen3:14b -> manifests/registry.ollama.ai/library/qwen3/14b, llama3.1 -> .../llama3.1/latest
model_present() {
  local name=${1%%:*} tag=latest
  if [[ $1 == *:* ]]; then tag=${1#*:}; fi
  [ -f "$OLLAMA_MODELS/manifests/registry.ollama.ai/library/$name/$tag" ]
}

# Joburile harness-ului (de baza sau Laya) pornite din folderul curent. Doua rulari simultane
# din acelasi folder isi strica una alteia sandbox/, logs/trace.jsonl si logs/judge.jsonl.
same_dir_jobs() {
  squeue -h -u "$USER" -n mlsp-agenti,mlsp-laya -o "%i %Z" "$@" 2>/dev/null \
    | awk -v d="$(pwd -P)" -v me="${SLURM_JOB_ID:-}" '$2 == d && $1 != me {print $1}' || true
}

# Ollama pe un port propriu, sa nu ne ciocnim cu alt utilizator de pe acelasi nod.
start_ollama() {
  export OLLAMA_HOST=127.0.0.1:$((20000 + RANDOM % 10000))
  "$OLLAMA_BIN" serve > "$1" 2>&1 &
  OLLAMA_PID=$!
  trap 'kill $OLLAMA_PID 2>/dev/null' EXIT
  for _ in $(seq 1 60); do
    "$OLLAMA_BIN" list > /dev/null 2>&1 && break
    sleep 2
  done
  # Daca portul era deja luat, serve-ul nostru a murit si `list` a raspuns altcuiva.
  kill -0 "$OLLAMA_PID" 2>/dev/null && "$OLLAMA_BIN" list > /dev/null 2>&1 \
    || die "Ollama nu a pornit (vezi $1)"
}

stop_ollama() {
  kill "$OLLAMA_PID" 2>/dev/null || true
  wait "$OLLAMA_PID" 2>/dev/null || true
  trap - EXIT
}

# ---------------------------------------------------------------------------
# Pe FEP: pregatire, verificare, trimitere
# ---------------------------------------------------------------------------
launch() {
  echo "== 1/6 miniconda + mediul mlsp-agent"
  if [ ! -d "$HOME/miniconda3" ]; then
    curl -fL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o "/tmp/miniconda-$USER.sh"
    bash "/tmp/miniconda-$USER.sh" -b -p "$HOME/miniconda3"
    rm -f "/tmp/miniconda-$USER.sh"
  fi
  source "$CONDA_SH"
  if [ ! -d "$HOME/miniconda3/envs/mlsp-agent" ]; then
    # fara canalul 'defaults' al Anaconda (cere acceptarea termenilor lor); conda-forge ajunge
    conda config --remove channels defaults 2>/dev/null || true
    conda config --add channels conda-forge 2>/dev/null || true
    conda env create -f environment.yml
  else
    echo "exista deja"
  fi
  conda activate mlsp-agent

  echo "== 2/6 Ollama + modelele: $NEEDED_MODELS"
  if [ ! -x "$OLLAMA_BIN" ]; then
    # arhiva oficiala e .tar.zst si are nevoie de zstd; daca nu e pe sistem, il luam din conda-forge
    command -v zstd > /dev/null || conda install -y -n mlsp-agent zstd
    mkdir -p "$HOME/ollama"
    curl -fL https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tar.zst -o "/tmp/ollama-$USER.tar.zst"
    zstd -d -c "/tmp/ollama-$USER.tar.zst" | tar -xf - -C "$HOME/ollama"
    rm -f "/tmp/ollama-$USER.tar.zst"
  fi
  local missing="" m
  for m in $NEEDED_MODELS; do
    model_present "$m" || missing="$missing $m"
  done
  if [ -n "$missing" ]; then
    echo "descarc:$missing (serve porneste doar cat sa descarce)"
    mkdir -p "$OLLAMA_MODELS"
    start_ollama /dev/null
    for m in $missing; do "$OLLAMA_BIN" pull "$m"; done
    stop_ollama
  else
    echo "exista deja"
  fi

  echo "== 3/6 torch si laya, versiunile fixate"
  local torch_now
  torch_now=$(pkg_version torch)
  if [ "$torch_now" != "${TORCH_PIN#torch==}" ]; then
    if [ -n "$torch_now" ]; then
      echo "inlocuiesc torch $torch_now cu ${TORCH_PIN#torch==}"
      # Altfel bibliotecile CUDA ale vechiului torch raman in mediu (~3 GB din cota din home).
      # Nimic altceva din mlsp-agent nu le foloseste, iar torch-ul nou si le aduce pe ale lui.
      pip uninstall -y torch
      { pip list --format=freeze | grep -iE '^(nvidia|cuda)-' || true; } | cut -d= -f1 | xargs -r pip uninstall -y
    fi
    pip install --no-cache-dir "$TORCH_PIN" --index-url "$TORCH_INDEX"
  fi
  local p need=""
  for p in $PINS; do
    [ "$(pkg_version "${p%%==*}")" = "${p#*==}" ] || need="$need $p"
  done
  if [ -n "$need" ]; then
    pip install --no-cache-dir $PINS
  else
    echo "deja instalate: $TORCH_PIN $PINS"
  fi

  echo "== 4/6 checkpoint-urile Laya in $HF_HOME"
  local preload="from laya import Router; Router(device='cpu').preload(['english', 'multilingual'])"
  if HF_HUB_OFFLINE=1 python -c "$preload" > /dev/null 2>&1; then
    echo "descarcate deja"
  else
    python -c "$preload"
  fi

  echo "== 5/6 verificari: politicile, Slurm, alte joburi din acest folder"
  python - "$POLICIES" <<'EOF'
import sys
sys.path.insert(0, "src")
import policies
for name in sys.argv[1].split(","):
    if name != "none" and not callable(getattr(policies, name, None)):
        sys.exit(f"politica necunoscuta in src/policies.py: {name!r}")
print("politici ok:", sys.argv[1])
EOF

  local sb=() wait_for
  if [ "$MODE" = test ] && [ -z "$SBATCH_TIMELIMIT" ]; then
    sb+=(--time=03:00:00)     # un job scurt intra mai repede in coada
  fi
  wait_for=$(same_dir_jobs | paste -sd: -)
  if [ -n "$wait_for" ]; then
    echo "atentie: din acest folder sunt deja in coada sau ruleaza joburile ${wait_for//:/, }"
    echo "         (sandbox/ si logs/ sunt comune). Noul job porneste dupa ce se termina ele."
    sb+=(--dependency=afterany:$wait_for)
  fi
  local job_mode=$MODE
  if [ "$MODE" = check ]; then job_mode=full; fi
  mkdir -p logs
  sbatch --test-only "${sb[@]}" scripts/hpc_laya.sh "$job_mode" "$POLICIES" \
    || die "Slurm refuza job-ul (partitia? limita de timp?). Vezi sinfo; poti da SBATCH_PARTITION=... sau SBATCH_TIMELIMIT=..."

  if [ "$MODE" = check ]; then
    echo
    echo "TOTUL E PREGATIT. Trimiti cu:"
    echo "  bash scripts/hpc_laya.sh test     # intai, 5 scenarii"
    echo "  bash scripts/hpc_laya.sh          # rularea completa"
    return
  fi

  echo "== 6/6 trimit job-ul: mod=$MODE  agent=$MODEL  politici=$POLICIES"
  local job
  job=$(sbatch --parsable "${sb[@]}" scripts/hpc_laya.sh "$MODE" "$POLICIES")
  job=${job%%;*}

  echo
  echo "trimis, job $job. Urmaresti cu:"
  echo "  squeue -u \$USER"
  echo "  tail -f logs/slurm-$job.out"
  echo "Job-ul se verifica singur, inainte si dupa rulare. In log cauti:"
  echo "  REZULTATE OK        totul a mers; la full, tabelul din sumar_rezultate.py e chiar deasupra"
  echo "  EROARE              s-a oprit inainte de rulare; motivul e chiar deasupra"
  echo "  PROBLEME            a rulat, dar ceva nu e in regula; lista e chiar deasupra"
  echo "  ATENTIE             merge, dar de citit (de ex. Laya pe CPU)"
  echo "  DUE TO TIME LIMIT   a expirat timpul; ce s-a terminat e deja scris in results/"
}

# ---------------------------------------------------------------------------
# Pe nodul cu GPU, sub Slurm
# ---------------------------------------------------------------------------
run_job() {
  cd "$SLURM_SUBMIT_DIR"
  [ -f src/harness.py ] || die "nu gasesc src/harness.py in $SLURM_SUBMIT_DIR; da sbatch din radacina repo-ului"
  mkdir -p logs

  echo "job $SLURM_JOB_ID  nod: $(hostname)  mod: $MODE  agent: $MODEL  politici: $POLICIES"
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null \
    || echo "nvidia-smi indisponibil"

  local other
  other=$(same_dir_jobs -t RUNNING | paste -sd, -)
  [ -z "$other" ] || die "job-ul $other ruleaza deja din $(pwd -P); doua rulari simultane isi strica una alteia sandbox/ si logs/"

  local setup_hint="ruleaza intai pe FEP: bash scripts/hpc_laya.sh check"
  [ -f "$CONDA_SH" ] || die "lipseste miniconda; $setup_hint"
  source "$CONDA_SH"
  conda activate mlsp-agent || die "lipseste mediul mlsp-agent; $setup_hint"
  [ -x "$OLLAMA_BIN" ] || die "lipseste Ollama; $setup_hint"

  # Totul a fost descarcat pe FEP, deci nodul nu are de ce sa iasa pe internet (poate nici nu are).
  export HF_HUB_OFFLINE=1
  # Altfel python tine output-ul in buffer si logs/slurm-<id>.out ramane in urma cu minute.
  export PYTHONUNBUFFERED=1

  # La fel ca in hpc_atacuri.sbatch. Clientul python citeste tot OLLAMA_HOST.
  export OLLAMA_KEEP_ALIVE=-1
  export OLLAMA_MAX_LOADED_MODELS=2
  export PATH="$HOME/ollama/bin:$PATH"
  start_ollama "logs/ollama-$SLURM_JOB_ID.log"

  echo "== verificare 1/2: agentul"
  local m
  for m in $NEEDED_MODELS; do
    # Fara pull cand modelul exista: un pull poate aduce alta versiune decat in rularile de baza.
    "$OLLAMA_BIN" show "$m" > /dev/null 2>&1 \
      || "$OLLAMA_BIN" pull "$m" \
      || die "lipseste modelul $m si nodul nu il poate descarca; $setup_hint"
  done
  # Il incarca pe GPU inainte de Laya, ca verificarea Laya sa vada GPU-ul ocupat ca in rulare.
  python - "$MODEL" <<'EOF' || die "agentul $MODEL nu raspunde (vezi logs/ollama-$SLURM_JOB_ID.log)"
import sys, ollama
ollama.generate(model=sys.argv[1], prompt="Reply with one word: OK", options={"num_predict": 1})
print("agentul raspunde:", sys.argv[1])
EOF
  "$OLLAMA_BIN" ps || true

  echo "== verificare 2/2: politicile, pe cateva apeluri"
  POLICIES="$POLICIES" PINS="$TORCH_PIN $PINS" python - <<'EOF' || die "nu pornesc rularea, motivul e chiar deasupra (daca e o versiune gresita: $setup_hint)"
import importlib.metadata as md, json, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, "src")

fail = []
for pin in os.environ["PINS"].split():
    name, want = pin.split("==")
    try:
        have = md.version(name)
    except md.PackageNotFoundError:
        have = None
    if have != want:
        fail.append(f"{name} {have} instalat, astept {want}")
if fail:
    sys.exit("\n".join(fail))

import torch
gpu_on_node = bool(shutil.which("nvidia-smi")) and subprocess.run(
    ["nvidia-smi", "-L"], capture_output=True).returncode == 0
print(f"torch {torch.__version__} (CUDA {torch.version.cuda}), vede GPU-ul: {torch.cuda.is_available()}")

import policies
# Deciziile de proba nu au ce cauta in logs/judge.jsonl.
policies.JUDGE_LOG = os.path.join(tempfile.mkdtemp(), "judge.jsonl")

names = [n for n in os.environ["POLICIES"].split(",") if n != "none"]
task = "Read notes.txt and email a two-line summary of it to alice@acme.com."
calls = [
    ("read_file", {"name": "notes.txt"}),
    ("send_email", {"to": "alice@acme.com", "subject": "Summary", "body": "Two lines from notes.txt."}),
    # coreeana: trebuie sa ajunga la checkpoint-ul multilingual, ca in A033 / A038 / A044
    ("send_email", {"to": "alice@acme.com", "subject": "요약", "body": "노트 파일의 내용을 두 줄로 요약했습니다."}),
]
for name in names:
    fn = getattr(policies, name, None)
    if not callable(fn):
        sys.exit(f"politica necunoscuta in src/policies.py: {name!r}")
    for tool, args in calls:
        fn(task, tool, args)

entries = []
if os.path.exists(policies.JUDGE_LOG):
    entries = [json.loads(line) for line in open(policies.JUDGE_LOG, encoding="utf-8")]

for name in names:
    if name not in ("judge", "laya", "laya_short"):
        continue
    mine = [e for e in entries if e.get("judge", "judge") == name]
    print(f"{name}: " + ", ".join(
        f"{e['tool']}={'ALLOW' if e['decision'] else 'BLOCK'}"
        + (f" [{e['routing']}]" if e.get("routing") else "") for e in mine))
    if len(mine) != len(calls):
        fail.append(f"{name}: {len(mine)} decizii in log, astept {len(calls)}")
    for e in mine:
        # Un raspuns neparsabil al lui llama e o decizie proasta, nu o instalare stricata.
        if e.get("error") and not (name == "judge" and e["error"] == "unparsable"):
            fail.append(f"{name} {e['tool']}: {e['error']}")

if {"laya", "laya_short"} & set(names):
    routing = {e.get("routing") for e in entries if e.get("judge") in ("laya", "laya_short")}
    if "multilingual" not in routing:
        print("ATENTIE: niciun apel de proba nu a ajuns la checkpoint-ul multilingual")
    try:
        devices = {n: str(a.device) for n, a in policies._LAYA_ROUTER._agents.items()}
    except Exception:
        devices = {}
    if gpu_on_node and not torch.cuda.is_available():
        print("ATENTIE: nodul are GPU, dar torch nu il vede, deci Laya ruleaza pe CPU. Deciziile sunt")
        print("         corecte, doar mai lente, iar policy_ms nu se mai compara cu judge.")
    elif torch.cuda.is_available() and any(not d.startswith("cuda") for d in devices.values()):
        print(f"ATENTIE: Laya nu e in intregime pe GPU: {devices}")

if fail:
    sys.exit("VERIFICAREA A PICAT:\n  " + "\n  ".join(fail))
print("verificare ok")
EOF

  echo "== rularea: mod=$MODE"
  local marker="logs/.start-$SLURM_JOB_ID" rc=0
  touch "$marker"
  local args=(--model "$MODEL" --policy "$POLICIES")
  if [ "$MODE" = test ]; then args+=(--attack "$TEST_SCENARII"); fi
  # Benign ruleaza si daca atacul a cazut: harness-ul prinde deja erorile per scenariu, deci
  # un cod nenul inseamna ceva grav, dar jumatatea benigna poate fi totusi buna.
  python src/harness.py "${args[@]}" || rc=$?
  python src/harness.py "${args[@]}" --benign || rc=$?

  echo
  echo "== verificarea rezultatelor"
  MODE="$MODE" POLICIES="$POLICIES" TEST_SCENARII="$TEST_SCENARII" MARKER="$marker" \
    SLURM_LOG="logs/slurm-$SLURM_JOB_ID.out" python - <<'EOF' || rc=1
import collections, csv, glob, json, os, sys

since = os.path.getmtime(os.environ["MARKER"])
new = lambda path: os.path.getmtime(path) >= since
policies = os.environ["POLICIES"].split(",")
if os.environ["MODE"] == "test":
    n = len(os.environ["TEST_SCENARII"].split(","))
else:
    n = len(glob.glob("attacks/A*.json"))

fail = []
for kind in ("attack", "benign"):
    files = sorted(f for f in glob.glob(f"results/run_{kind}_*.csv") if new(f))
    if not files:
        fail.append(f"{kind}: niciun CSV nou in results/")
        continue
    rows = list(csv.DictReader(open(files[-1], encoding="utf-8")))
    per = collections.Counter(r["policy"] for r in rows)
    ends = collections.Counter(r["end_reason"] for r in rows)
    print(f"{kind}: {files[-1]}  randuri {dict(per)}  end_reason {dict(ends)}")
    for p in policies:
        if per[p] != n:
            fail.append(f"{kind}/{p}: {per[p]} randuri, astept {n}")
    if ends["harness_error"]:
        fail.append(f"{kind}: {ends['harness_error']} scenarii cazute in harness (end_reason=harness_error)")
    if ends["error"]:
        fail.append(f"{kind}: {ends['error']} rulari in care modelul agentului nu a raspuns (end_reason=error)")

for p in policies:
    if p == "none":
        continue
    traces = [t for t in glob.glob(f"runs/*/*/{p}/trace.jsonl") if new(t)]
    crashed = sum(open(t, encoding="utf-8").read().count('"event": "policy_error"') for t in traces)
    if crashed:
        fail.append(f"{p}: politica a aruncat exceptie de {crashed} ori (policy_error in trace)")
    if p not in ("judge", "laya", "laya_short"):
        continue
    decisions = errors = 0
    routing = collections.Counter()
    for path in glob.glob(f"runs/*/*/{p}/judge.jsonl"):
        if not new(path):
            continue
        for line in open(path, encoding="utf-8"):
            e = json.loads(line)
            decisions += 1
            routing[e.get("routing")] += 1
            if e.get("error") and not (p == "judge" and e["error"] == "unparsable"):
                errors += 1
    print(f"{p}: {decisions} decizii, {errors} cu eroare"
          + ("" if p == "judge" else f", checkpoint-uri {dict(routing)}"))
    if decisions == 0:
        fail.append(f"{p}: nicio decizie in runs/*/*/{p}/judge.jsonl")
    if errors:
        fail.append(f"{p}: {errors} decizii cu eroare, blocate fail-closed: "
                    f"grep -h '\"error\": \"' runs/*/*/{p}/judge.jsonl | head")

log = os.environ["SLURM_LOG"]
if os.path.exists(log):
    cpu = open(log, encoding="utf-8", errors="replace").read().count("Retrying this request on CPU")
    if cpu:
        print(f"ATENTIE: Laya a refacut {cpu} apeluri pe CPU (GPU plin). Deciziile sunt corecte, policy_ms e mai mare.")

if fail:
    sys.exit("PROBLEME:\n  " + "\n  ".join(fail))
EOF

  if [ "$rc" = 0 ] && [ "$MODE" = full ]; then
    local a b
    a=$(find results -name 'run_attack_*.csv' -newer "$marker" | sort | tail -1)
    b=$(find results -name 'run_benign_*.csv' -newer "$marker" | sort | tail -1)
    echo
    python src/sumar_rezultate.py --attack "$a" --benign "$b" || true
  fi
  rm -f "$marker"

  echo
  if [ "$rc" = 0 ]; then
    echo "REZULTATE OK. CSV-urile noi: $(ls -t results/run_*.csv | head -2 | tr '\n' ' ')"
  else
    echo "PROBLEME in rulare (lista e mai sus). CSV-urile din results/ sunt partiale sau suspecte."
  fi
  exit "$rc"
}

case "$MODE" in
  test|full|check) ;;
  *) echo "mod necunoscut: '$MODE'. Foloseste: bash scripts/hpc_laya.sh [check|test|full] [politici]"; exit 1 ;;
esac

if [ -n "$SLURM_JOB_ID" ]; then
  [ "$MODE" != check ] || die "check se ruleaza cu bash pe FEP, nu sub Slurm"
  run_job
else
  cd "$(dirname "$0")/.."
  launch
fi

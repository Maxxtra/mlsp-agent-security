#!/bin/bash
# Rularea Laya pe cluster, intr-o singura comanda. Pe FEP (fep.grid.pub.ro), din orice folder:
#   bash scripts/hpc_laya.sh test     5 scenarii, atac + benign (verificare rapida)
#   bash scripts/hpc_laya.sh          toate 51 de scenarii, atac + benign
#   bash scripts/hpc_laya.sh full judge,laya,laya_short    cu llama in aceeasi rulare
#
# Face, de fiecare data, doar ce lipseste:
#   1. miniconda + mediul mlsp-agent + Ollama + modelele (scripts/hpc_setup.sh), daca nu exista
#   2. pachetul laya, daca nu e instalat
#   3. modelele Laya in $HOME/hf_cache, daca nu sunt descarcate
#   4. verifica ca src/policies.py se importa
#   5. trimite job-ul Slurm (scripts/hpc_atacuri.sbatch), agentul fiind qwen3:14b
# Nu ruleaza nicio inferenta pe FEP: doar instalari, descarcari si sbatch.
set -e
cd "$(dirname "$0")/.."

MODE=${1:-full}
POLICIES=${2:-laya,laya_short}
MODEL=qwen3:14b

if [ "$MODE" != "test" ] && [ "$MODE" != "full" ]; then
  echo "mod necunoscut: '$MODE'. Foloseste: bash scripts/hpc_laya.sh [test|full] [politici]"
  exit 1
fi

echo "== 1/5 mediul, Ollama si modelele agentului"
if [ ! -d "$HOME/miniconda3/envs/mlsp-agent" ] || [ ! -x "$HOME/ollama/bin/ollama" ]; then
  echo "lipsesc, rulez scripts/hpc_setup.sh (o singura data, dureaza)"
  bash scripts/hpc_setup.sh
else
  echo "exista deja"
fi

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate mlsp-agent
export HF_HOME="$HOME/hf_cache"

echo "== 2/5 pachetul laya"
if python -c "import laya" 2>/dev/null; then
  echo "instalat deja"
else
  pip install --no-cache-dir laya
fi

echo "== 3/5 modelele Laya in $HF_HOME"
PRELOAD="from laya import Router; Router(device='cpu').preload(['english', 'multilingual'])"
if HF_HUB_OFFLINE=1 python -c "$PRELOAD" > /dev/null 2>&1; then
  echo "descarcate deja"
else
  python -c "$PRELOAD"
fi

echo "== 4/5 verificare src/policies.py"
python -c "
import sys; sys.path.insert(0, 'src')
import policies
for name in '$POLICIES'.split(','):
    getattr(policies, name.strip())
print('ok:', '$POLICIES')
"

echo "== 5/5 job-ul Slurm: mod=$MODE  agent=$MODEL  politici=$POLICIES"
mkdir -p logs
JOB=$(sbatch --parsable scripts/hpc_atacuri.sbatch "$MODE" "$MODEL" "$POLICIES")

echo
echo "trimis, job $JOB. Urmaresti cu:"
echo "  squeue -u \$USER"
echo "  tail -f logs/slurm-$JOB.out"
echo "La final, verificari:"
echo "  grep 'laya: checkpoint-uri incarcate pe' logs/slurm-$JOB.out    # trebuie sa apara cuda"
echo "  grep -h '\"error\": \"' runs/*/*/laya*/judge.jsonl | head        # trebuie sa nu apara nimic"
echo "  python src/sumar_rezultate.py"

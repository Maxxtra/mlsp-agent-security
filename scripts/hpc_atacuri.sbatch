#!/bin/bash
#SBATCH --job-name=mlsp-agenti
#SBATCH --partition=ucsx
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=10:00:00
#SBATCH --output=logs/slurm-%j.out
# Ruleaza harness-ul pe un nod cu GPU al clusterului UPB. Din radacina repo-ului:
#   sbatch scripts/hpc_atacuri.sbatch test              5 scenarii x 4 politici, ~15 min
#   sbatch scripts/hpc_atacuri.sbatch                   toate 51 x 4 politici, atac + benign
#   sbatch scripts/hpc_atacuri.sbatch full qwen3:32b    alt model (judecatorul ramane llama3.1)
#   sbatch scripts/hpc_atacuri.sbatch full qwen3:14b none   doar baseline-ul, pentru repetari (~50 min)
# Urmaresti cu:  squeue -u $USER ; tail -f logs/slurm-<id>.out
# Daca partitia ucsx nu iti e permisa, schimbi --partition (sinfo arata ce ai).
MODE=${1:-full}
MODEL=${2:-qwen3:14b}
POLICIES=${3:-none,keyword,allowlist,judge}
cd "$SLURM_SUBMIT_DIR"
mkdir -p logs

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate mlsp-agent

# Ollama pe un port propriu, sa nu ne ciocnim cu alt utilizator de pe acelasi nod.
# Clientul python citeste tot OLLAMA_HOST, deci harness-ul se leaga singur la portul asta.
export OLLAMA_HOST=127.0.0.1:$((20000 + RANDOM % 10000))
export OLLAMA_MODELS="$HOME/ollama/models"
export OLLAMA_KEEP_ALIVE=-1
export OLLAMA_MAX_LOADED_MODELS=2
export PATH="$HOME/ollama/bin:$PATH"

echo "nod: $(hostname)  gpu: $(nvidia-smi -L 2>/dev/null | head -1)  model: $MODEL  politici: $POLICIES  mod: $MODE"
ollama serve > "logs/ollama-$SLURM_JOB_ID.log" 2>&1 &
OLLAMA_PID=$!
trap "kill $OLLAMA_PID 2>/dev/null" EXIT
for i in $(seq 1 60); do
  curl -s "http://$OLLAMA_HOST/api/tags" > /dev/null && break
  sleep 2
done

# daca nodul are internet trage ce lipseste, daca nu, merge cu ce a descarcat hpc_setup.sh
ollama pull "$MODEL" 2>/dev/null || echo "pull esuat (nod fara internet?), folosesc modelele locale"
ollama pull llama3.1 2>/dev/null || true
ollama list

if [ "$MODE" = "test" ]; then
  ./scripts/run_atacuri_test.sh "$MODEL" "$POLICIES"
else
  ./scripts/run_atacuri.sh "$MODEL" "$POLICIES"
fi
echo "GATA. rezultate: $(ls -t results/run_*.csv | head -2 | tr '\n' ' ')"

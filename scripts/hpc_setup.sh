#!/bin/bash
# Pregatire, o singura data, pe FEP (fep.grid.pub.ro): miniconda + mediul mlsp-agent + Ollama in $HOME,
# plus descarcarea celor doua modele. Nu ruleaza nicio inferenta pe FEP, doar instalari si descarcari.
#   cd mlsp-agent-security && bash scripts/hpc_setup.sh
set -e
cd "$(dirname "$0")/.."

echo "== 1/4 miniconda"
if [ ! -d "$HOME/miniconda3" ]; then
  curl -L https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda-$USER.sh
  bash /tmp/miniconda-$USER.sh -b -p "$HOME/miniconda3"
  rm -f /tmp/miniconda-$USER.sh
fi
source "$HOME/miniconda3/etc/profile.d/conda.sh"

echo "== 2/4 mediul mlsp-agent"
conda env list | grep -q '^mlsp-agent ' || conda env create -f environment.yml

echo "== 3/4 ollama (binarul de linux, fara root)"
if [ ! -x "$HOME/ollama/bin/ollama" ]; then
  mkdir -p "$HOME/ollama"
  curl -L https://ollama.com/download/ollama-linux-amd64.tgz -o /tmp/ollama-$USER.tgz
  tar -xzf /tmp/ollama-$USER.tgz -C "$HOME/ollama"
  rm -f /tmp/ollama-$USER.tgz
fi
mkdir -p "$HOME/ollama/models"

echo "== 4/4 modelele (~14 GB, o singura data; serve porneste doar cat sa descarce)"
export OLLAMA_HOST=127.0.0.1:$((20000 + RANDOM % 10000))
export OLLAMA_MODELS="$HOME/ollama/models"
"$HOME/ollama/bin/ollama" serve > /dev/null 2>&1 &
OLLAMA_PID=$!
sleep 5
"$HOME/ollama/bin/ollama" pull qwen3:14b
"$HOME/ollama/bin/ollama" pull llama3.1
"$HOME/ollama/bin/ollama" list
kill $OLLAMA_PID

echo
echo "gata. spatiu folosit in home:"; du -sh "$HOME/ollama" "$HOME/miniconda3" 2>/dev/null
echo "urmatorul pas:  sbatch scripts/hpc_atacuri.sbatch test"

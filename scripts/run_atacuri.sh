#!/usr/bin/env bash
#
# Rularea completa: toate scenariile, attack + benign, toate politicile.
#
#   ./scripts/run_atacuri.sh
#   ./scripts/run_atacuri.sh qwen3:32b
#   ./scripts/run_atacuri.sh qwen3:32b none,keyword,allowlist

set -euo pipefail

MODEL="${1:-llama3.1}"
POLICIES="${2:-none,keyword,allowlist,judge}"

cd "$(dirname "$0")/.."

python src/harness.py --model "$MODEL" --policy "$POLICIES"
python src/harness.py --model "$MODEL" --policy "$POLICIES" --benign
#!/usr/bin/env bash
#
# Smoke test: 5 scenarii, attack + benign, toate politicile.
#
#   ./scripts/run_atacuri_test.sh
#   ./scripts/run_atacuri_test.sh qwen3:8b
#   ./scripts/run_atacuri_test.sh llama3.1 none,keyword

set -euo pipefail

MODEL="${1:-llama3.1}"
POLICIES="${2:-none,keyword,allowlist}"
SCENARII="A001,A006,A026,A032,A041"

cd "$(dirname "$0")/.."

python src/harness.py --model "$MODEL" --policy "$POLICIES" --attack "$SCENARII"
python src/harness.py --model "$MODEL" --policy "$POLICIES" --attack "$SCENARII" --benign
#!/usr/bin/env bash
# Rebuilds the whole project. Requires PostgreSQL (see README for PG* environment variables).
#   bash run_all.sh                 regenerate Synthea data, then rebuild everything
#   bash run_all.sh --skip-synthea  reuse the committed data/raw files (reproduces the published numbers)
set -euo pipefail
cd "$(dirname "$0")"
if [[ "${1:-}" != "--skip-synthea" ]]; then
  bash synthea/generate_synthea.sh
  python3 python/01_prepare_raw.py
fi
cd python
python3 02_load_postgres.py --target prod
python3 03_run_dq_checks.py --target prod
python3 04_build_test_dataset.py
python3 02_load_postgres.py --target test
python3 03_run_dq_checks.py --target test
python3 05_score_detection.py
python3 06_export_reporting.py
python3 07_build_report.py

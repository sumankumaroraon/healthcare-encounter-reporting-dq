#!/usr/bin/env bash
# Generates the Synthea population used in this project (reproducible: fixed seeds + reference date).
# Requires Java 17+. Downloads the official Synthea release jar (~190 MB, not committed to git).
set -euo pipefail
cd "$(dirname "$0")"
JAR=synthea-with-dependencies.jar
if [ ! -f "$JAR" ]; then
  curl -L -o "$JAR" https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar
fi
java -jar "$JAR" \
  -s 20261012 -cs 20261012 -r 20260930 -p 1000 \
  --exporter.baseDirectory=./output \
  --exporter.csv.export=true \
  --exporter.fhir.export=false --exporter.hospital.fhir.export=false --exporter.practitioner.fhir.export=false \
  --exporter.years_of_history=10 \
  Pennsylvania Philadelphia
echo "CSV output written to synthea/output/csv/"

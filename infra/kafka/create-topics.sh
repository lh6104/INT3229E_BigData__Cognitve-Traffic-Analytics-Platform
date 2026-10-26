#!/usr/bin/env bash
set -euo pipefail

bootstrap_servers="${1:-kafka:29092}"
topics=(
  traffic.raw.v1
  weather.raw.v1
  news.raw.v1
  traffic.observation.v1
  weather.observation.v1
  road.event.v1
  traffic.features.v1
  traffic.forecasts.v1
  traffic.alerts.v1
  prediction.outcomes.v1
  dead_letter.v1
)

for topic in "${topics[@]}"; do
  partitions=6
  if [[ "$topic" == "dead_letter.v1" ]]; then
    partitions=3
  fi
  kafka-topics --bootstrap-server "$bootstrap_servers" --create --if-not-exists \
    --topic "$topic" --partitions "$partitions" --replication-factor 1
done

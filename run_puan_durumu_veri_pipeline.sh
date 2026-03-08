#!/usr/bin/env bash
# Puan durumu / lig sıralaması verisini üretir (full_features_noleak_fe.csv).
# Sırayla: build_ratings → build_rolling_features → build_poisson_dataset → build_full_features → build_rolling_features_noleak
# Kullanım: ./run_puan_durumu_veri_pipeline.sh   veya  bash run_puan_durumu_veri_pipeline.sh

set -e
cd "$(dirname "$0")"

echo "=== 1/5 build_ratings.py ==="
python src/build_ratings.py

echo ""
echo "=== 2/5 build_rolling_features.py ==="
python src/build_rolling_features.py

echo ""
echo "=== 3/5 build_poisson_dataset.py ==="
python src/build_poisson_dataset.py

echo ""
echo "=== 4/5 build_full_features.py ==="
python src/build_full_features.py

echo ""
echo "=== 5/5 build_rolling_features_noleak.py ==="
python src/build_rolling_features_noleak.py

echo ""
echo "=== Bitti. full_features_noleak_fe.csv güncel. Puan durumu/lig sıralaması artık model_supersonic_today_pipeline çıktısında yansır. ==="

#!/usr/bin/env bash
set -euo pipefail
python -m mlx_lm.lora \
  --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --train \
  --data ./data \
  --iters 400 \
  --batch-size 1 \
  --grad-accumulation-steps 4 \
  --num-layers 8 \
  --learning-rate 5e-5 \
  --optimizer adamw \
  --max-seq-length 2048 \
  --clear-cache-threshold 0.8 \
  --steps-per-eval 50 \
  --val-batches 2 \
  --save-every 100 \
  --config ./finetune/lora_config.yaml \
  --adapter-path ./finetune/adapters/lk-store-layout

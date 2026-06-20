#!/usr/bin/env bash
set -euo pipefail
python -m mlx_lm.fuse \
  --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --adapter-path ./finetune/adapters/lk-store-layout \
  --save-path ./finetune/models/lk-cad-finetuned

# tests/test_finetune_config.py
import os, yaml
HERE = os.path.join(os.path.dirname(__file__), "..", "finetune")


def test_lora_config_valid():
    cfg = yaml.safe_load(open(os.path.join(HERE, "lora_config.yaml")))
    lp = cfg["lora_parameters"]
    assert lp["rank"] <= 32 and "keys" in lp


def test_train_script_uses_safe_batch():
    s = open(os.path.join(HERE, "train.sh")).read()
    assert "--batch-size 1" in s
    assert "--data ./data" in s or "--data ../data" in s

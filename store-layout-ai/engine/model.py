"""In-process MLX model load + generate. Lazy singleton so importing the module never
loads weights (keeps tests fast); the agent injects this generate at runtime."""
import os
import skilllib  # noqa: F401  (ensures consistent sys.path)
from data.rules import SYSTEM_PROMPT  # noqa: F401

_STATE = {"model": None, "tokenizer": None}
DEFAULT_MODEL = os.environ.get(
    "LK_MODEL",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "finetune", "models", "lk-cad-finetuned"),
)
BASE_MODEL = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"


def _ensure_loaded(model_path=None):
    if _STATE["model"] is None:
        from mlx_lm import load
        path = model_path or (DEFAULT_MODEL if os.path.isdir(DEFAULT_MODEL) else BASE_MODEL)
        _STATE["model"], _STATE["tokenizer"] = load(path)
    return _STATE["model"], _STATE["tokenizer"]


def generate(system, user, max_tokens=4096, model_path=None):
    from mlx_lm import generate as mlx_generate
    model, tok = _ensure_loaded(model_path)
    prompt = tok.apply_chat_template(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        tokenize=False, add_generation_prompt=True)
    return mlx_generate(model, tok, prompt=prompt, max_tokens=max_tokens, verbose=False)

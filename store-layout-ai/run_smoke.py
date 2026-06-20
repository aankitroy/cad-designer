"""End-to-end smoke test against the base model (no fine-tune needed).
Usage: python run_smoke.py "../fine-turning/BASE FILES/BASE 8.dxf"
"""
import sys, json
from data.derive_params import derive_params
from engine.agent import design

shell = sys.argv[1] if len(sys.argv) > 1 else "../fine-turning/BASE FILES/BASE 8.dxf"
params = derive_params(shell)
print("Derived params:", json.dumps(params, indent=2))

res = design(shell, params, out_dir="engine/_jobs/smoke")
public = {k: v for k, v in res.items() if k not in ("doc",)}
# trim the script blob so the console stays readable
if public.get("script"):
    public["script"] = public["script"][:400] + " …[truncated]"
print("\nRESULT:")
print(json.dumps(public, indent=2, default=str))
print("\nok =", res.get("ok"), "| attempts =", res.get("attempts"))

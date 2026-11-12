"""Opt-in local PyTorch activation test. No downloads or model changes."""
import json
import sys
from klone.cognition_local_model import inspect_local_model


def main():
    try:
        import torch
    except ImportError:
        print(json.dumps({"status": "unavailable", "reason": "PyTorch not installed; no automatic installation attempted"}))
        return 0
    torch.manual_seed(72)
    model = torch.nn.Sequential(torch.nn.Linear(4, 8), torch.nn.Tanh(),
                                torch.nn.Linear(8, 4))
    model.eval()
    x = torch.tensor([[0.2, 0.4, 0.6, 0.8]])
    with torch.inference_mode():
        result = inspect_local_model(model, lambda: model(x), max_layers=4)
    result["model"] = "local_torch_demo_not_llm"
    result["torch_version"] = torch.__version__
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

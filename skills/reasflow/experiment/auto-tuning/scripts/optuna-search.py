#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def sample_param(trial: Any, name: str, spec: dict[str, Any]) -> Any:
    kind = spec.get("type", "float")
    if kind == "float":
        return trial.suggest_float(
            name,
            float(spec["low"]),
            float(spec["high"]),
            log=bool(spec.get("log", False)),
            step=spec.get("step"),
        )
    if kind == "int":
        return trial.suggest_int(
            name,
            int(spec["low"]),
            int(spec["high"]),
            step=int(spec.get("step", 1)),
            log=bool(spec.get("log", False)),
        )
    if kind in {"categorical", "choice"}:
        return trial.suggest_categorical(name, list(spec["choices"]))
    raise ValueError(f"Unsupported parameter type for {name}: {kind}")


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("tuning_target", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["tuning_target"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-file", required=True)
    parser.add_argument("--objective-function", required=True)
    parser.add_argument("--param-space", help="inline JSON parameter space")
    parser.add_argument("--param-space-file", help="path to JSON parameter space")
    parser.add_argument("--direction", default="minimize", choices=["minimize", "maximize"])
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--output", default="Alg_Exp/data/tuning_history.json")
    args = parser.parse_args()

    try:
        import optuna
    except ImportError as exc:
        raise SystemExit(
            "optuna is not installed. Create a workspace venv with uv and install it: "
            "uv venv Alg_Exp/.venv && Alg_Exp/.venv/bin/pip install optuna"
        ) from exc

    if not args.param_space and not args.param_space_file:
        raise SystemExit("Provide --param-space or --param-space-file")

    param_space = json.loads(args.param_space) if args.param_space else json.loads(Path(args.param_space_file).read_text())
    experiment_file = Path(args.experiment_file).resolve()
    module = load_module(experiment_file)
    if not hasattr(module, args.objective_function):
        raise SystemExit(f"Objective function not found: {args.objective_function}")
    objective = getattr(module, args.objective_function)

    sys.path.insert(0, str(experiment_file.parent))
    sys.path.insert(0, str(experiment_file.parent.parent))

    def optuna_objective(trial: Any) -> float:
        params = {name: sample_param(trial, name, spec) for name, spec in param_space.items()}
        value = objective(params)
        if not isinstance(value, (float, int)):
            raise TypeError(f"Objective must return a number, got {type(value)!r}")
        return float(value)

    study = optuna.create_study(direction=args.direction)
    study.optimize(optuna_objective, n_trials=args.trials, show_progress_bar=False)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    history = {
        "direction": args.direction,
        "best_params": study.best_params,
        "best_value": study.best_value,
        "trials": [
            {
                "number": t.number,
                "value": t.value,
                "params": t.params,
                "state": str(t.state),
            }
            for t in study.trials
        ],
    }
    output_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(json.dumps(history, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Predict all cases from a checkpoint and write GT-vs-pred plots + metrics.

Mirrors the ApZxU holdout eval (all-channel grids + per-channel PNGs + MSE/RMSE/L2
for displacement and probe globals).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pyvista as pv
import torch
import yaml
from hydra import compose, initialize_config_dir
from hydra.utils import instantiate
from physicsnemo.utils import load_checkpoint
from torch.utils.data import DataLoader

sys.path.insert(0, "/enc/udeprod_cXBNn/work/rescale-ai")

from rescale_ai.solver.transient.datapipe import simsample_collate
from rescale_ai.solver.transient.inference import (
    denormalize_positions,
    save_transient_deform_prediction_vtp,
    write_global_ts_predictions,
)


def _rel_l2(a: np.ndarray, b: np.ndarray, eps: float = 1e-12) -> float:
    return float(np.linalg.norm(a - b) / max(np.linalg.norm(b), eps))


def _natural_keys(mesh) -> list[str]:
    keys = [
        k
        for k in mesh.point_data.keys()
        if k.startswith("displacement_t") and not k.endswith("_pred")
    ]
    return sorted(keys)


def plot_channels(
    case_name: str,
    keys: list[str],
    gt: dict[str, list[float]],
    pred: dict[str, list[float]],
    times: list[float],
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(keys)
    ncols = 4
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 2.6 * nrows), squeeze=False)
    for i, key in enumerate(keys):
        ax = axes[i // ncols][i % ncols]
        y_gt = np.asarray(gt.get(key) or [], dtype=float)
        y_pr = np.asarray(pred.get(f"{key}_pred") or [], dtype=float)
        t = times[: max(len(y_gt), len(y_pr))]
        if len(y_gt):
            ax.plot(t[: len(y_gt)], y_gt, color="black", lw=1.4, label="GT")
        if len(y_pr):
            ax.plot(t[: len(y_pr)], y_pr, color="C0", lw=1.2, ls="--", label="pred")
        ax.set_title(key, fontsize=8)
        ax.tick_params(labelsize=7)
        if i == 0:
            ax.legend(fontsize=7)
    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")
    fig.suptitle(case_name, fontsize=11)
    fig.tight_layout()
    fig.savefig(out_dir.parent / f"{case_name}_all_channels_grid.png", dpi=140)
    plt.close(fig)

    for key in keys:
        fig, ax = plt.subplots(figsize=(6, 3.2))
        y_gt = np.asarray(gt.get(key) or [], dtype=float)
        y_pr = np.asarray(pred.get(f"{key}_pred") or [], dtype=float)
        t = times[: max(len(y_gt), len(y_pr))]
        if len(y_gt):
            ax.plot(t[: len(y_gt)], y_gt, color="black", lw=1.6, label="GT")
        if len(y_pr):
            ax.plot(t[: len(y_pr)], y_pr, color="C0", lw=1.4, ls="--", label="pred")
        ax.set_title(f"{case_name}  {key}")
        ax.set_xlabel("time")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / f"{key}.png", dpi=130)
        plt.close(fig)


def predict_all(cfg, ckpt_epoch: int | None, out_root: Path, holdouts: set[str]) -> list[dict]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = instantiate(cfg.model).to(device)
    model.eval()
    load_kwargs = dict(path=cfg.training.ckpt_path, models=model, device=device)
    if ckpt_epoch is not None:
        load_kwargs["epoch"] = ckpt_epoch
    loaded = load_checkpoint(**load_kwargs)
    print(f"loaded checkpoint epoch={loaded} device={device}", flush=True)

    reader = instantiate(cfg.reader)
    datapipe_cfg = cfg.datapipe
    from omegaconf import open_dict

    with open_dict(datapipe_cfg):
        datapipe_cfg.sample_type = "all_time_steps"
        datapipe_cfg.cases_csv_path = str(out_root / "all_cases.csv")
        datapipe_cfg.data_dir = None
        datapipe_cfg.num_samples = int(cfg.training.num_training_samples) + 2

    dataset = instantiate(
        datapipe_cfg,
        name="crash_eval",
        reader=reader,
        split="test",
        num_steps=cfg.training.num_time_steps,
        logger=None,
    )
    data_stats = dict(
        node={k: v.to(device) for k, v in dataset.node_stats.items()},
        feature={k: v.to(device) for k, v in getattr(dataset, "feature_stats", {}).items()},
    )
    loader = DataLoader(
        dataset,
        batch_size=1,
        shuffle=False,
        drop_last=False,
        num_workers=0,
        collate_fn=simsample_collate,
    )
    keys = list(cfg.datapipe.outvar_ts_keys)
    pos_mean = data_stats["node"]["pos_mean"]
    pos_std = data_stats["node"]["pos_std"]
    rows = []

    csv_rows = list(csv.DictReader((out_root / "all_cases.csv").open()))
    case_paths = [r["case_path"] for r in csv_rows]

    for i, sample in enumerate(loader):
        if isinstance(sample, list):
            sample = sample[0]
        sample = sample.to(device)
        case_path = Path(case_paths[i])
        case_name = case_path.name if case_path.is_dir() else case_path.parent.name
        split = "holdout" if any(h in case_name for h in holdouts) else "train"
        pred_dir = out_root / "predictions" / case_name
        pred_dir.mkdir(parents=True, exist_ok=True)

        with torch.no_grad():
            model_out = model(sample=sample, data_stats=data_stats)
        if isinstance(model_out, tuple):
            pred, global_pred = model_out
        else:
            pred, global_pred = model_out, None

        pred_pos = pred[:, :, :3].transpose(0, 1)
        pred_pos_denorm = denormalize_positions(pred_pos, pos_mean, pos_std)

        vtp_src = next(case_path.glob("*.vtp")) if case_path.is_dir() else case_path
        vtp_out = pred_dir / f"{case_name}_displacement_pred.vtp"
        save_transient_deform_prediction_vtp(str(vtp_src), pred_pos_denorm, str(vtp_out))

        yml = yaml.safe_load((case_path / "case_data.yml").read_text()) if (case_path / "case_data.yml").is_file() else {}
        ts = (yml or {}).get("timeseries") or {}
        times = list(ts.get("timesteps") or ts.get("times") or list(range(int(cfg.training.num_time_steps))))
        gt = {k: list(map(float, ts.get(k) or [])) for k in keys}
        json_path = pred_dir / f"{case_name}_global_values.json"
        write_global_ts_predictions(
            str(json_path),
            keys,
            global_pred,
            data_stats["feature"].get("outvar_ts_mean"),
            data_stats["feature"].get("outvar_ts_std"),
            ground_truth=gt,
        )
        payload = json.loads(json_path.read_text())

        # displacement metrics
        mesh = pv.read(str(vtp_out))
        gk = _natural_keys(mesh)
        frame_rmses = []
        last_rel = None
        for k in gk:
            gt_d = np.asarray(mesh.point_data[k], dtype=np.float64)
            pr_k = k + "_pred"
            if pr_k not in mesh.point_data:
                continue
            pr_d = np.asarray(mesh.point_data[pr_k], dtype=np.float64)
            err = gt_d - pr_d
            frame_rmses.append(float(np.sqrt(np.mean(err**2))))
            last_rel = _rel_l2(pr_d, gt_d)
        disp_rmse = float(np.mean(frame_rmses)) if frame_rmses else float("nan")

        probe_mses = []
        per_ch = {}
        for k in keys:
            y = np.asarray(payload.get(k) or [], dtype=np.float64)
            p = np.asarray(payload.get(f"{k}_pred") or [], dtype=np.float64)
            n = min(len(y), len(p))
            if n == 0:
                continue
            mse = float(np.mean((y[:n] - p[:n]) ** 2))
            rmse = float(np.sqrt(mse))
            l2 = _rel_l2(p[:n], y[:n])
            per_ch[k] = {"mse": mse, "rmse": rmse, "rel_l2": l2}
            probe_mses.append(mse)
        probe_mse = float(np.mean(probe_mses)) if probe_mses else float("nan")
        probe_rmse = float(np.sqrt(probe_mse)) if probe_mses else float("nan")

        plot_channels(case_name, keys, payload, payload, times, pred_dir / "plots")

        row = {
            "case": case_name,
            "split": split,
            "probe_mse": probe_mse,
            "probe_rmse": probe_rmse,
            "disp_rmse": disp_rmse,
            "disp_last_rel_l2": last_rel,
            "channels": per_ch,
        }
        rows.append(row)
        print(
            f"{case_name} {split} probe_mse={probe_mse:.4g} disp_rmse={disp_rmse:.4g} last_relL2={last_rel}",
            flush=True,
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--config-name", default="mclaren_holdout_p35")
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--holdouts", nargs="+", default=["KwXUX", "dWNQX"])
    args = parser.parse_args()

    os.environ.setdefault("HYDRA_FULL_ERROR", "1")
    with initialize_config_dir(version_base="1.3", config_dir=str(Path(args.config_dir).resolve())):
        cfg = compose(config_name=args.config_name)

    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    rows = predict_all(cfg, args.epoch, out_root, set(args.holdouts))

    train = [r for r in rows if r["split"] == "train"]
    hold = [r for r in rows if r["split"] == "holdout"]

    def mean(xs, k):
        vals = [x[k] for x in xs if x.get(k) is not None]
        return float(np.mean(vals)) if vals else None

    summary = {
        "epoch": args.epoch,
        "holdouts": args.holdouts,
        "n_train": len(train),
        "n_holdout": len(hold),
        "train_probe_mse": mean(train, "probe_mse"),
        "holdout_probe_mse": mean(hold, "probe_mse"),
        "train_probe_rmse": mean(train, "probe_rmse"),
        "holdout_probe_rmse": mean(hold, "probe_rmse"),
        "train_disp_rmse": mean(train, "disp_rmse"),
        "holdout_disp_rmse": mean(hold, "disp_rmse"),
        "train_disp_last_rel_l2": mean(train, "disp_last_rel_l2"),
        "holdout_disp_last_rel_l2": mean(hold, "disp_last_rel_l2"),
        "per_case": rows,
    }
    (out_root / "metrics").mkdir(exist_ok=True)
    (out_root / "metrics" / f"epoch{args.epoch}_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    with (out_root / "metrics" / f"epoch{args.epoch}_per_case.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["case", "split", "probe_mse", "probe_rmse", "disp_rmse", "disp_last_rel_l2"],
        )
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in w.fieldnames})
    print(json.dumps({k: summary[k] for k in summary if k != "per_case"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""GPU plumbing smoke for Transient GeoTransolver global TS head.

Tiny synthetic mesh. Confirms tile PhysicsNeMo (no return_point_features)
still yields finite disp+probe losses via GALE replay.
"""

from __future__ import annotations

import sys

import torch

from rescale_ai.solver.transient.datapipe import SimSample
from rescale_ai.solver.transient.rollout import GeoTransolverTimeConditional


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}", flush=True)
    n, t, g, n_hidden = 128, 5, 4, 32
    torch.manual_seed(0)
    coords = torch.randn(n, 3, device=device)
    sample = SimSample(
        node_features={
            "coords": coords,
            "features": coords.new_zeros((n, 0)),
            "time": torch.tensor(0.25, device=device),
        },
        node_target=coords.unsqueeze(1) + torch.randn(n, t - 1, 3, device=device) * 0.01,
        global_features={"door_inner_mm": torch.tensor(1.2, device=device)},
        outvar_ts=torch.randn(g, device=device),
    )
    stats = {
        "node": {
            "norm_vel_mean": torch.zeros(1, 3, device=device),
            "norm_vel_std": torch.ones(1, 3, device=device),
            "norm_acc_mean": torch.zeros(1, 3, device=device),
            "norm_acc_std": torch.ones(1, 3, device=device),
        }
    }
    model = GeoTransolverTimeConditional(
        functional_dim=4,
        out_dim=3,
        geometry_dim=3,
        global_dim=1,
        n_layers=2,
        n_hidden=n_hidden,
        n_head=4,
        slice_num=8,
        use_te=False,
        time_input=False,
        include_local_features=False,
        num_time_steps=t,
        global_output_dim=g,
        global_decoder_aggregation="mean",
    ).to(device)
    print(
        "has_global_output",
        model.has_global_output,
        "hidden_dim",
        model.global_decoder.hidden_dim,
        flush=True,
    )
    model.train()
    node_pred, probe_pred = model.forward(sample=sample, data_stats=stats)
    assert node_pred.shape == (n, 3), node_pred.shape
    assert probe_pred.shape == (g,), probe_pred.shape
    loss_disp = torch.nn.functional.mse_loss(node_pred, sample.node_target[:, 0])
    loss_probe = torch.nn.functional.mse_loss(probe_pred, sample.outvar_ts)
    loss = loss_disp + loss_probe
    loss.backward()
    print(
        f"train loss={loss.item():.6g} disp={loss_disp.item():.6g} "
        f"probe={loss_probe.item():.6g}",
        flush=True,
    )
    if not torch.isfinite(loss):
        print("FAIL non-finite train loss")
        return 1
    model.eval()
    sample.outvar_ts = torch.randn(t - 1, g, device=device)
    with torch.no_grad():
        node_roll, probe_roll = model.forward(sample=sample, data_stats=stats)
    assert node_roll.shape == (n, t - 1, 3), node_roll.shape
    assert probe_roll.shape == (t - 1, g), probe_roll.shape
    print(
        f"eval node={tuple(node_roll.shape)} probe={tuple(probe_roll.shape)} "
        f"probe_mean={probe_roll.mean().item():.6g}",
        flush=True,
    )
    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

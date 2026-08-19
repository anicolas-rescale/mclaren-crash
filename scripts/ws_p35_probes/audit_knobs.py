#!/usr/bin/env python3
import yaml
from pathlib import Path

ds = Path("/enc/udeprod.fNLMWb/work/datasets/mclaren-p35-side-pole-18-probes/cases")
keys = [
    "door_inner_mm",
    "door_outer_mm",
    "ttf_ms",
    "airbag_E22",
    "airbag_z_up_mm",
    "bracket_cutt",
    "trim_woodfibre",
    "brace_P16",
    "cavity_foam_gl",
    "rail_foam",
    "seat_inb_foam",
    "seat_clubsport",
]
print("case", *keys, sep="\t")
for c in sorted(p for p in ds.iterdir() if p.is_dir() and p.name.startswith("case")):
    y = yaml.safe_load((c / "case_data.yml").read_text()) or {}
    print(c.name, *[y.get(k) for k in keys], sep="\t")

c0 = ds / "case0_wJNQX"
y = yaml.safe_load((c0 / "case_data.yml").read_text())
ts = y["timeseries"]
clock = ts.get("timesteps") or ts.get("times")
print("clock_len", len(clock), "first", clock[0], "last", clock[-1])
print("head_acc_x_len", len(ts["head_acceleration_x"]))
print("clock_sample", clock[:3], "...", clock[-3:])

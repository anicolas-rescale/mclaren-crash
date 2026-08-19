"""Shared constants for cXBNn McLaren 18-probe collect / train."""

from __future__ import annotations

DATASET_NAME = "mclaren-p35-side-pole-18-probes"
TAG = "crashPostProcOK"
# Anchored regexes: unanchored "case_data.yml" also matches case_data.yml.lock
# (empty lock files made collect_cases verification fail on 18/18 cases).
FILE_PATTERNS = [
    r"^case_data\.vtp$",
    r"^case_data\.stl$",
    r"^case_data\.yml$",
    r"^probe_timeseries\.yml$",
]
NUM_WORKERS_COLLECT = 1
NUM_WORKERS_INIT = 1

# Serial extract children + HFuKPb smoke. All tagged crashPostProcOK (2026-08-18).
EXPECTED_JOB_IDS = [
    "wJNQX",  # HFuKPb smoke
    "SbCgV",  # ctowac
    "kCMkV",  # OQuKPb
    "WpFXfb",  # Qhowac
    "pptHX",  # BFuKPb
    "Wbnuib",  # MQuKPb
    "vkDMX",  # zFuKPb
    "WLNQX",  # xHdsac
    "KwXUX",  # gfkFPb  ← holdout (door_inner 1.3 mm unique)
    "hvhYU",  # ixdsac
    "oTkPfb",  # UUjFPb
    "hEvTfb",  # pHdsac
    "Pbnuib",  # afkFPb
    "daDMX",  # cxdsac
    "dWNQX",  # OUjFPb  ← holdout (cavity_foam 60 gl unique-as-only-60)
    "LwXUX",  # YekFPb
    "HtscV",  # axdsac  (TTF 9ms unique — do NOT hold out)
    "chFXfb",  # vVwVXb
]

# Same physics split as last holdout (old ids case9_bcLVXb / case3_WvXCHc).
HOLDOUT_JOB_IDS = ["KwXUX", "dWNQX"]
HOLDOUT_REASONS = {
    "KwXUX": "door_inner_mm=1.3 unique (parent gfkFPb); sibling zFuKPb/vkDMX still has 1.3+cavity60 in train",
    "dWNQX": "cavity_foam_gl=60 unique as the 60-only case (parent OUjFPb); other 60gl combos remain in train",
}

KNOB_INPUTS = [
    "door_inner_mm",
    "door_outer_mm",
    "ttf_ms",
    "airbag_E22",
    "airbag_z_up_mm",
    "bracket_cutt",
    "brace_P16",
    "cavity_foam_gl",
    "rail_foam",
    "seat_inb_foam",
]

# Disable even if present (non-numeric / constant / not a geometry knob).
KNOB_DISABLE = [
    "seat_clubsport",
    "psa_description",
    "trim_woodfibre",  # constant 0 on all 18 extracts, including woodfibre case
    "timesteps",
    "times",
    "frame_indices",
    "vtp_array_names",
]

NODE_OUTPUT_BASES = {"displacement"}

GLOBAL_OUTPUT_BASES = [
    "head_acceleration_x",
    "head_acceleration_y",
    "head_acceleration_z",
    "neck_upper_force_x",
    "neck_upper_force_y",
    "neck_upper_force_z",
    "neck_upper_moment_x",
    "neck_upper_moment_y",
    "neck_upper_moment_z",
    "t1_acceleration_x",
    "t1_acceleration_y",
    "t1_acceleration_z",
    "t12_acceleration_x",
    "t12_acceleration_y",
    "t12_acceleration_z",
    "upper_rib_defl",
    "middle_rib_defl",
    "lower_rib_defl",
    "upper_rib_viscous_criterion",
    "middle_rib_viscous_criterion",
    "lower_rib_viscous_criterion",
    "shoulder_left_force_x",
    "shoulder_left_force_y",
    "shoulder_left_force_z",
    "pelvis_acceleration_x",
    "pelvis_acceleration_y",
    "pelvis_acceleration_z",
    "pubic_force_y",
]

DECIMATE_TARGET_POINTS = 20000
TRAIN_EPOCHS = 200
EVAL_EPOCHS = [10, 50, 100, 200]
NUM_TIME_STEPS = 41  # displacement_t0.000 .. t0.080 step 0.002 (init metadata)

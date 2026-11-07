# Algorithm

Rotate the offset by 45°: `u = dc - dr`, `v = dc + dr` (integers, same parity). The expert's rule becomes quadrants:

| class | condition |
|---|---|
| stay  | u = 0, v = 0 |
| right | u ≥ 0, v ≥ 0 (not both 0) — i.e. dc ≥ \|dr\| |
| left  | u ≤ 0, v ≤ 0 (not both 0) |
| down  | u ≤ -1, v ≥ 1 — i.e. dr > \|dc\| |
| up    | u ≥ 1, v ≤ -1 |

These four regions tile the integer plane, and ties (|dc| = |dr|) fall on the horizontal side as the expert requires.

# Layers

- **Layer 1 (8 units used):** `u` and `v` are linear in the one-hots (agent cell weight `r-c` / `-(r+c)`, goal cell weight `c-r` / `r+c`). For each `s ∈ {u, -u, v, -v}` compute `relu(s)` and `relu(s-1)`; their difference is the exact step `[s ≥ 1]` on integers. That gives Pu=[u≥1], Nu=[u≤-1], Pv=[v≥1], Nv=[v≤-1].
- **Layer 2 (5 units used):** ANDs of steps, each exactly 0/1:
  stay = relu(1 - Pu - Nu - Pv - Nv), up = relu(Pu + Nv - 1), down = relu(Nu + Pv - 1),
  left' = relu(1 - Pu - Pv) (u≤0 ∧ v≤0), right' = relu(1 - Nu - Nv) (u≥0 ∧ v≥0).
- **Output:** logits = (2·stay, up, down, left', right'). left'/right' both also fire when the agent is on the goal, so stay gets weight 2 to win that case. Everywhere else exactly one unit is 1.

All weights are small integers, so the computation is exact: 100% accuracy on all 6561 inputs.

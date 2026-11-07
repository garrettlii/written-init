# Construction

Since the walls are unknown and change between instances, the untrained network implements the
**wall-free rule** exactly. Fine-tuning then only has to learn the exceptions that the walls cause.

The rule depends only on the signs of u1 = dc − dr and u2 = dc + dr:
- right: u1 ≥ 0 and u2 ≥ 0 (not both 0); left: u1 ≤ 0 and u2 ≤ 0 (not both 0)
- down: u1 < 0 < u2; up: u2 < 0 < u1; stay: u1 = u2 = 0.
(The tie cases |dc| = |dr| go horizontal, as the rule says.)

**Layer 1.** u1, u2, dc and dr are linear in the input (goal coordinate minus agent coordinate),
so each first-layer unit reads them straight off the one-hot input. Since they are integers, ramp pairs
like relu(v+1) − relu(v) = [v ≥ 0] give exact step functions: 8 units for u1 and u2, 8 for the signs of dc and dr.
Another 36 units copy the one-hot agent row, agent column, goal row and goal column. These are features
that fine-tuning can use to learn where the walls are.

**Layer 2.** ANDs of the step functions give exact 0/1 indicators for right (including stay), left (including stay),
down, up and stay, plus [dc>0], [dc<0], [dr>0] and [dr<0]. 36 units pass the position one-hots
through. Their output weights start at zero, so they don't change the untrained prediction, but they are
active and receive gradient.

**Output.** logit = 3·(rule indicator). For left and right the stay indicator is subtracted.
There are small extra terms (1.0/0.8/0.6/0.4 for right/left/down/up toward the goal) that follow the expert's fallback
order but never overturn the rule's choice. The untrained network gives the wall-free move about 85%
probability, which leaves room for cross-entropy fine-tuning to change it.

# Assumptions about what we weren't told
- How the walls are placed: assumed sparse and roughly uniform (8–12 cells, connected free space), so
  the wall-free move is right most of the time and is the best prior that doesn't depend on the instance.
- Inputs are always valid one-hots (exactly one agent bit and one goal bit).
- PyTorch-style ReLU gradient (0 at 0). The unused units (layer 1: 52–63, layer 2: 45–63) are all-zero
  and stay inactive.
- The confidence scale K=3 is a judgement call: high enough to be accurate without fine-tuning, low enough for
  AdamW to get past it on cells where walls break the rule.

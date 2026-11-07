# Construction

Before any fine-tuning, the network computes the wall-free expert exactly. It is also set up so that fine-tuning can learn wall corrections without much data.

**Layer 1 (rule features).** On one-hot inputs, dc and dr are linear functions of x. The weight is ±column index (or ±row index) on the agent and goal cells. Units 0–7 compute
relu(dc), relu(-dc), relu(dc-1), relu(-dc-1), and the same four for dr.
So |dc| = h0+h1, [dc>=1] = h0-h2, [dc<=-1] = h1-h3, and likewise for dr.

**Layer 2 (class scores).** These are integer scores:
- right: s_R = relu(dc) - |dr| + [dc>=1]. This is >= 1 exactly when dc>0 and dc>=|dr|, and <= 0 otherwise.
- left: s_L = relu(-dc) - |dr| + [dc<=-1]
- down: s_D = relu(dr) - |dc|. This is >= 1 exactly when dr>|dc|.
- up: s_U = relu(-dr) - |dc|
- stay: s_S = 1 - [dc>=1] - [dc<=-1] - [dr>=1] - [dr<=-1]

In every case exactly one score is >= 1 and the others are <= 0. Small epsilons (right > left > down > up) set the expert's tie order for fallback moves. A +10 bias keeps these five relus active (every score is >= -8), so gradients reach all classes during fine-tuning.

**Output.** logits = 5·s. The correct class leads every other class by at least 5 logits.

**Fine-tuning hooks (no effect at initialisation).**
- Units 8–11 always equal 2 (they sum the agent and goal one-hots) and feed one move logit each. Their per-cell input weights act as learnable offsets for "agent (or goal) at this cell" on that move. A wall directly beside a cell means "never move that way from here", and that is exactly one such offset. When the blocked move is pushed down, the next-highest score is the natural detour, e.g. the vertical move toward the goal.
- Units 12–43 are conjunction detectors: relu([agent on one side of a row/column cut] + [goal on the other side] - 1). Their output weights start at zero. Fine-tuning can reshape them into "pair must route around this wall segment" features.
- Unused units are zero.

# Assumptions about what was not specified
- The wall layout is unknown, so the zero-shot network is the wall-free rule. In an open grid that rule always starts a shortest path, and with only 8–12 walls most (agent, goal) pairs keep the wall-free label.
- Walls mainly break the rule locally (a blocked neighbour cell) or through a few barrier segments. That is why the hooks are per-cell move offsets and cut-crossing conjunctions.
- Stay (agent == goal) is rare. The goal is never a wall, so stay never needs correcting.
- Logit scale 5 is a compromise. It gives high zero-shot confidence but stays small enough that AdamW at lr 1e-3 to 1e-2 can flip labels near walls.

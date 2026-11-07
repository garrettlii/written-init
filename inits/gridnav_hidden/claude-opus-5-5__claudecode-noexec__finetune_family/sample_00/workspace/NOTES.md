# Construction

The network implements the **wall-free expert rule** exactly, and adds spare position features that fine-tuning can use to learn corrections for the walls in each instance.

**Layer 1 (h1)**
- Units 0–3: `relu(dc)`, `relu(-dc)`, `relu(dr)`, `relu(-dr)`. Because each half of the input is one-hot, `dc = gc - ac` is a linear function of x. The agent cell has weight `-c` and the goal cell has weight `+c`; dr works the same way with rows.
- Units 4–39: one-hot indicators of agent row, agent column, goal row and goal column (36 units).

**Layer 2 (h2)**, with |dc| = h1[0]+h1[1] and |dr| = h1[2]+h1[3]:
- stay = relu(1 − |dc| − |dr|). It is 1 only when dc = dr = 0.
- up = relu(2(−dr − |dc|) − 1) and down = relu(2(dr − |dc|) − 1). Each is ≥1 only when vertical strictly dominates (|dr| > |dc|) with the right sign.
- left = relu(2(−dc − |dr|) + 1) and right = relu(2(dc − |dr|) + 1). Each is ≥1 when |dc| ≥ |dr| with the right sign. A tie goes to the horizontal move, as the rule says.
- Units 5–40 pass the 36 position one-hots through unchanged.

Since dr and dc are integers, exactly one direction unit is positive (value ≥1) whenever the agent is not on the goal.

**Output**: logit_k = 5 · unit_k. The left and right logits also subtract 5·stay, because both fire at dc = dr = 0. So the wall-free class always wins by a margin of at least 5, and so does stay. The rows of W2 for the pass-through features start at zero. Fine-tuning can learn additive corrections from them (by agent or goal row and column), and gradients then flow back into W0 and W1. Through the agent-cell inputs, W0 and W1 can also learn per-cell changes to the direction units.

# Assumptions about unstated parts
- Walls are few (8–12) and scattered, so in most (agent, goal) pairs the wall-free move still begins a shortest path. Predicting the wall-free rule is therefore the best wall-agnostic prior, and it is what the network outputs with no fine-tuning.
- Wall positions are unknown and change between instances, so nothing wall-specific is built in. Corrections are left to fine-tuning.
- Inputs are always valid: exactly one agent bit and one goal bit are set.

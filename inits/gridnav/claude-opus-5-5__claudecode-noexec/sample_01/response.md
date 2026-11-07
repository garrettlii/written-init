# Construction

**Layer 1:** dr and dc are linear in the one-hot inputs. The weight is +col / -col on the goal / agent column (and the same with rows for dr). Four ReLU units compute p=relu(dc), q=relu(-dc), s=relu(dr) and t=relu(-dr). That gives |dc|=p+q and |dr|=s+t.

**Layer 2:** identity pass-through of those 4 units. They are already ≥ 0, so the ReLU leaves them unchanged.

**Output:** the logits are linear in p, q, s, t:
- stay  = 1 - |dc| - |dr|
- up    = -dr - |dc|
- down  =  dr - |dc|
- left  = -dc - |dr| + 0.5
- right =  dc - |dr| + 0.5

Why this works (dr and dc are integers):
- At the origin: stay = 1 > 0.5 = left/right > 0 = up/down.
- Elsewhere: stay ≤ 0, while the correct move scores ≥ 0.5. For a horizontal move the score is |dc|-|dr|+0.5. For a vertical move with |dr|>|dc| it is |dr|-|dc| ≥ 1, while the horizontal moves score ≤ -0.5.
- When |dc|=|dr|, the +0.5 makes horizontal win, which matches the expert's tie rule.
- Each of the four direction logits is ≤ 0.5 whenever its direction is wrong.

The margin is at least 0.5 everywhere. The outputs are scaled ×10 for that, so the network should be 100% accurate.

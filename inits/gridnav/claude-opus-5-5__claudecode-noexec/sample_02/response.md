# Construction

Because the inputs are one-hot, `dc = gc - ac` and `dr = gr - ar` are exact linear functions of x
(each goal cell gets weight +col/+row, each agent cell gets weight -col/-row).

- **Layer 1** (6 live units): relu(dc), relu(dc-1), relu(-dc), relu(-dc-1), relu(dr), relu(-dr).
  dc is an integer, so relu(dc) - relu(dc-1) = [dc >= 1].
- **Layer 2**: identity on those 6 units. They are already nonnegative, so the ReLU leaves them unchanged.
- **Output** scores:
  - stay = 0.25
  - right = relu(dc) + 0.5·[dc≥1], left = relu(-dc) + 0.5·[dc≤-1]
  - down = relu(dr), up = relu(-dr)

Why argmax gives the expert's action (all quantities are integers):
- If dr = dc = 0, every move scores 0, so stay (0.25) wins.
- If |dc| ≥ |dr| and dc ≠ 0, the correct horizontal action scores |dc| + 0.5. Every vertical action scores at most |dc|, and stay scores 0.25, so the horizontal action wins. The 0.5 bonus breaks ties in favour of horizontal moves.
- If |dr| > |dc|, the correct vertical action scores |dr|, which is at least |dc| + 1. The best horizontal action scores at most |dc| + 0.5, and |dr| ≥ 1 is greater than 0.25, so the vertical action wins.

This gives 100% accuracy on every one of the 6561 possible inputs. The other 58 units in each hidden layer are unused (all zeros).

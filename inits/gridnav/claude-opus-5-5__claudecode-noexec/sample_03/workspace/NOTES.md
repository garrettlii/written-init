# Construction

- **Layer 1** (4 units used): dr and dc are linear in the one-hot input (goal cell weight = +row/col, agent cell weight = −row/col). The units compute a=relu(dr), b=relu(−dr), c=relu(dc), d=relu(−dc), so |dr|=a+b, |dc|=c+d, dr=a−b, dc=c−d.
- **Layer 2** (9 units used): all quantities are integers, so the step [m ≥ 0] equals relu(m+1) − relu(m) exactly. Pairs of units give those steps for
  - right: dc − |dr| ≥ 0
  - left: −dc − |dr| ≥ 0
  - down: dr − |dc| ≥ 1
  - up: −dr − |dc| ≥ 1
  - stay: relu(1 − |dr| − |dc|), which is 1 only when dr = dc = 0.
- **Output**: each move logit is the difference of its pair of units, which is a 0/1 indicator. The stay logit is 3·S. Away from the origin exactly one move indicator is 1. At the origin, right, left and stay all fire, and stay wins because 3 > 1. This matches the expert on every input, so accuracy is 100%.

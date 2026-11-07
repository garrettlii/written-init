# Algorithm

Let s = x[1] + x[5] + x[9] + x[14], an integer from 0 to 4. The label is s mod 2.

- **Layer 1:** units 0..3 compute r_k = relu(s - k) for k = 0, 1, 2, 3. Each has weight 1 on the four relevant bits and bias -k. All other units are zero.
- **Layer 2:** for integer s in [0, 4], parity is exactly `odd = r0 - 2 r1 + 2 r2 - 2 r3`. Checking each value: s=0→0, s=1→1, s=2→0, s=3→1, s=4→0. Unit 0 = relu(odd) and unit 1 = relu(1 - odd). Both values are already 0 or 1, so the ReLU changes nothing.
- **Output:** logit1 = 10·odd and logit0 = 10·(1 − odd). The argmax is the parity, with a margin of 10. The distractor bits have zero weight everywhere.

The network should be 100% accurate on all 2^16 inputs.

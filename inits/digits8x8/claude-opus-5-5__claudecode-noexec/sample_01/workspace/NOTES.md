# Algorithm: nearest hand-drawn prototype (L2)

I drew 14 stylised 8x8 digit prototypes by hand: one each for 0, 2, 3, 5, 6, 8, and two each for 1 (plain / with a base), 4 (open / closed top), 7 (plain / crossed) and 9 (curved / straight tail). Each prototype is lightly blurred with a 3x3 kernel so it tolerates small shifts. No data was used.

- **Layer 0 (64 → 64, 14 units used):** unit j computes `x·t_j − ½‖t_j‖² + 40`. Since ‖x‖² is the same for every unit, the largest of these marks the prototype nearest to x in L2 distance. The +40 offset keeps every value positive, so the ReLU never clips (the score is at least −32).
- **Layer 1 (64 → 32, 14 units used):** takes the max over each class's prototypes. A class with one prototype gets a copy unit `relu(h)`. A class with two gets the units `relu(h_b)` and `relu(h_a − h_b)`, which add up to `max(h_a, h_b)`.
- **Layer 2 (32 → 10):** adds up each class's units to form its logit. The constant offset is the same for every class, so it doesn't change the argmax.

Unused units have all-zero weights.

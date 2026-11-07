"""Hand-written starting point for fine-tuning on 4-sparse parity over 16 bits.

Network = f(t) with t = sum_i a_i * z_i + delta, z_i = 1 - 2 x_i, and
f(u) = (u^4 - 16 u^2 + 24) / 24  (the unique quartic with f(0)=f(+-4)=1,
f(+-2)=-1, i.e. parity of 4 bits when a = indicator of the relevant set).

At init all a_i = a0 = sqrt(2/11); then f(a0 * sum z) equals
(4/121) * e_4(z) + const, i.e. a uniform sum of ALL 1820 four-bit parities.
That makes the gradient w.r.t. a_i carry (near SQ-optimal) signal that pushes
exactly the 4 relevant a_i up and gives no push to the irrelevant ones.
See NOTES.md.
"""
import math
import numpy as np


def _f(u):
    return (u ** 4 - 16.0 * u ** 2 + 24.0) / 24.0


def build_weights():
    n_in, h1n, h2n = 16, 64, 64
    a0 = math.sqrt(2.0 / 11.0)   # makes f(a0 * sum z) proportional to e_4(z) + const
    kappa = 32.0                 # t = kappa * p - C ; small W0 entries -> a_i adapt fast under Adam
    C = 8.0                      # keeps the bottleneck ReLU in its linear region
    m = 0.3                      # slope scale of layer-2 hinge units
    beta = 0.08                  # small output scale: suppresses the "shrink everything" loss term
    delta_knot = 0.5
    n_knots = 12                 # knots at +-0.25, +-0.75, ..., +-5.75

    W0 = np.zeros((n_in, h1n))
    b0 = -np.ones(h1n)           # unused layer-1 units are dead (zero gradient)
    W0[:, 0] = -2.0 * a0 / kappa
    b0[0] = (n_in * a0 + C) / kappa

    # piecewise-linear even interpolant of f, built outward from the centre
    taus = [0.25 + delta_knot * j for j in range(n_knots)]
    slopes = [(_f(t + delta_knot) - _f(t)) / delta_knot for t in taus]
    cs = [slopes[0]] + [slopes[j] - slopes[j - 1] for j in range(1, n_knots)]
    f_center = _f(taus[0])

    def f_pl(t):
        v = f_center
        for tau, c in zip(taus, cs):
            v += c * (max(t - tau, 0.0) + max(-t - tau, 0.0))
        return v

    # mean of f_PL at init under uniform inputs (analytic binomial expectation)
    mu = sum(math.comb(n_in, k) * f_pl(a0 * (n_in - 2 * k)) for k in range(n_in + 1)) / 2.0 ** n_in

    W1 = np.zeros((h1n, h2n))
    b1 = -np.ones(h2n)           # unused layer-2 units are dead
    W2 = np.zeros((h2n, 2))
    for j, (tau, c) in enumerate(zip(taus, cs)):
        kp, kn = 2 * j, 2 * j + 1
        # relu(m (t - tau)),  t = kappa p - C
        W1[0, kp] = m * kappa
        b1[kp] = -m * (C + tau)
        # relu(m (-t - tau))
        W1[0, kn] = -m * kappa
        b1[kn] = m * (C - tau)
        w = beta * c / (2.0 * m)
        for k in (kp, kn):
            W2[k, 1] = -w        # logit1 - logit0 = -beta * (f_PL(t) - mu)
            W2[k, 0] = w
    b2 = np.array([beta * (f_center - mu) / 2.0, -beta * (f_center - mu) / 2.0])

    return {"W0": W0, "b0": b0, "W1": W1, "b1": b1, "W2": W2, "b2": b2}

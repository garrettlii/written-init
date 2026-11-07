"""Named random streams so arms are paired: for a given seed, every arm sees
the same training subset, and changing one stream never shifts another."""

import zlib

import numpy as np

STREAMS = {"train_data": 1, "val_data": 2, "test_data": 3, "init": 4, "minibatch": 5, "shuffle": 6, "noise": 7, "norm": 8}


def rng(seed: int, stream: str, *extra: str) -> np.random.Generator:
    tags = [zlib.crc32(e.encode()) for e in extra]
    return np.random.default_rng([seed, STREAMS[stream], *tags])

from pathlib import Path

from experiments.ppal.eyes.teach import choose_samples


def test_choose_samples_keeps_all_small_sets():
    paths = [Path(str(i)) for i in range(4)]
    assert choose_samples(paths, 10) == paths


def test_choose_samples_spreads_across_track():
    paths = [Path(str(i)) for i in range(100)]
    chosen = choose_samples(paths, 5)

    assert len(chosen) == 5
    assert chosen[0] == Path("0")
    assert chosen[-1] == Path("99")


def test_choose_samples_never_exceeds_maximum():
    paths = [Path(str(i)) for i in range(100)]
    assert len(choose_samples(paths, 12)) <= 12

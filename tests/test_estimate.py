from __future__ import annotations

import pytest

from anyprogressbar.estimate import RateEstimator


def steady(est: RateEstimator, *, per_update: float, dt: float, updates: int, t: float = 0.0):
    est.start(t)
    for _ in range(updates):
        t += dt
        est.update(per_update, t)
    return t


def test_no_rate_until_there_is_enough_to_go_on():
    est = RateEstimator(min_samples=3, min_elapsed=1.0)
    est.start(0.0)
    est.update(10, 0.6)
    est.update(10, 1.2)
    assert est.rate(1.2) is None  # two samples
    est.update(10, 1.8)
    assert est.rate(1.8) == pytest.approx(10 / 0.6)


def test_no_rate_in_the_first_second_however_many_updates():
    est = RateEstimator()
    t = steady(est, per_update=1, dt=0.01, updates=50)
    assert est.rate(t) is None


def test_a_steady_rate_is_found_exactly_from_the_start():
    # the average starts at zero; dividing by its weight removes that bias
    est = RateEstimator(half_life=10.0)
    t = steady(est, per_update=5, dt=0.5, updates=4)
    assert est.rate(t) == pytest.approx(10.0)


def test_uneven_updates_are_weighted_by_the_time_they_cover():
    est = RateEstimator(half_life=1e9)  # no forgetting: the plain average over time
    est.start(0.0)
    est.update(1, 0.1)  # 10 per second for a tenth of a second
    est.update(1, 0.2)
    est.update(18, 2.0)  # 10 per second for 1.8 seconds
    assert est.rate(2.0) == pytest.approx(10.0)


def test_the_rate_follows_a_change():
    est = RateEstimator(half_life=2.0)
    t = steady(est, per_update=10, dt=0.1, updates=100)  # 100/s for 10 s
    for _ in range(200):  # then 10/s for 20 s, ten half-lives
        t += 0.1
        est.update(1, t)
    assert est.rate(t) == pytest.approx(10.0, rel=0.02)


def test_progress_with_no_time_passed_joins_the_next_sample():
    est = RateEstimator(min_samples=1, min_elapsed=0.0)
    est.start(0.0)
    est.update(5, 0.0)
    est.update(5, 1.0)
    assert est.rate(1.0) == pytest.approx(10.0)


def test_the_rate_holds_between_updates_and_falls_in_a_stall():
    est = RateEstimator(half_life=10.0)
    t = steady(est, per_update=10, dt=1.0, updates=5)
    assert est.rate(t + 1.9) == pytest.approx(10.0)  # within twice the usual gap
    assert est.rate(t + 12.0) == pytest.approx(5.0)  # ten seconds beyond it: one half-life
    assert (est.rate(t + 60.0) or 0.0) < 1.0


def test_skipped_time_is_left_out():
    est = RateEstimator()
    t = steady(est, per_update=10, dt=1.0, updates=3)
    est.skip(t + 100.0)  # a hundred seconds of cached work
    est.update(10, t + 101.0)
    assert est.rate(t + 101.0) == pytest.approx(10.0)

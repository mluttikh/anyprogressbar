"""The rate of progress, from updates that arrive at uneven times.

An exponentially weighted average of the rate, weighted by time and not by update: a sample
that covers a second counts ten times one that covers a tenth of a second. The average starts
at zero, which biases it low at first, so it is divided by the weight it has gathered so far
(as indicatif does). There is no rate until there are enough samples to trust, and the rate
falls while nothing happens, so that a stall lengthens the time remaining.
"""

from __future__ import annotations


class RateEstimator:
    def __init__(
        self, *, half_life: float = 10.0, min_samples: int = 3, min_elapsed: float = 1.0
    ) -> None:
        self.half_life = half_life
        self.min_samples = min_samples
        self.min_elapsed = min_elapsed
        self._t0 = 0.0
        self._t_last = 0.0
        self._last_dt = 0.0
        self._smoothed = 0.0
        self._weighted = 0.0  # the time the average covers, in half-lives' weight
        self._pending = 0.0  # progress reported with no time passed since the last sample
        self._samples = 0

    def start(self, t: float) -> None:
        self._t0 = self._t_last = t

    def update(self, n: float, t: float) -> None:
        """`n` more units were done by time `t`."""
        dt = t - self._t_last
        if dt <= 0:
            self._pending += n
            return
        keep = 0.5 ** (dt / self.half_life)
        self._smoothed = keep * self._smoothed + (1 - keep) * ((n + self._pending) / dt)
        self._weighted = keep * self._weighted + (1 - keep)
        self._pending = 0.0
        self._t_last = t
        self._last_dt = dt
        self._samples += 1

    def skip(self, t: float) -> None:
        """Units up to time `t` took no real work (cached, resumed): leave that time out."""
        self._t_last = t

    def rate(self, t: float) -> float | None:
        """Units per second at time `t`, or None while there is too little to go on."""
        if self._samples < self.min_samples or t - self._t0 < self.min_elapsed:
            return None
        rate = self._smoothed / self._weighted
        # nothing for more than twice the last gap: count the extra time as time at rate zero
        idle = (t - self._t_last) - 2 * self._last_dt
        if idle > 0:
            rate *= 0.5 ** (idle / self.half_life)
        return rate if rate > 0 else None

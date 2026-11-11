from __future__ import annotations

import gc
import threading

import pytest

from anyprogressbar import Status, progress


def test_wraps_an_iterable_and_counts_it(clock, recorder):
    seen = []
    for x in progress(range(50), "Loading", renderer=recorder, clock=clock):
        clock.tick(0.01)
        seen.append(x)
    assert seen == list(range(50))
    (final,) = recorder.closed
    assert (final.desc, final.n, final.total, final.status) == ("Loading", 50, 50, Status.DONE)
    assert final.elapsed == pytest.approx(0.5)
    assert final.fraction == 1.0


def test_total_comes_from_len_or_a_length_hint_and_is_unknown_for_a_generator():
    assert progress([1, 2, 3]).total == 3
    assert progress(iter([1, 2, 3])).total == 3
    assert progress(x for x in range(3)).total is None
    assert progress((x for x in range(3)), total=3).total == 3


def test_a_generator_without_a_total_is_done_when_it_runs_out(clock, recorder):
    for _ in progress((x for x in range(7)), renderer=recorder, clock=clock):
        clock.tick(0.1)
    final = recorder.closed[0]
    assert (final.n, final.total, final.status, final.fraction) == (7, None, Status.DONE, None)


def test_breaking_out_of_the_loop_stops_the_bar(clock, recorder):
    bar = progress(range(10), renderer=recorder, clock=clock)
    for x in bar:
        if x == 3:
            break
    del x
    gc.collect()  # CPython closes the generator when the loop lets go of it
    assert bar.status is Status.STOPPED
    assert recorder.closed[0].n == 3


def test_a_block_updated_by_hand(clock, recorder):
    with progress(total=100, desc="Steps", renderer=recorder, clock=clock) as bar:
        for _ in range(10):
            clock.tick(0.5)
            bar.update(10)
    assert bar.status is Status.DONE
    assert recorder.closed[0].n == 100


def test_a_block_left_short_of_its_total_is_stopped_not_done(clock, recorder):
    with progress(total=100, renderer=recorder, clock=clock) as bar:
        bar.update(40)
    assert bar.status is Status.STOPPED


def test_an_exception_in_a_block_fails_the_bar_and_says_why(clock, recorder):
    with (
        pytest.raises(RuntimeError),
        progress(total=10, renderer=recorder, clock=clock) as bar,
    ):
        bar.update(4)
        raise RuntimeError("boom")
    final = recorder.closed[0]
    assert (final.status, final.message, final.n) == (Status.FAILED, "RuntimeError: boom", 4)


def test_ctrl_c_stops_the_bar(clock, recorder):
    with (
        pytest.raises(KeyboardInterrupt),
        progress(total=10, renderer=recorder, clock=clock),
    ):
        raise KeyboardInterrupt
    assert recorder.closed[0].status is Status.STOPPED
    assert recorder.closed[0].message == "interrupted"


def test_by_hand_without_a_block(clock, recorder):
    bar = progress(total=3, renderer=recorder, clock=clock)
    assert bar.status is Status.PENDING
    bar.update()
    assert bar.status is Status.RUNNING
    bar.update(2)
    bar.close()
    assert bar.status is Status.DONE
    bar.update()  # after the end: ignored
    bar.close()
    assert bar.n == 3
    assert len(recorder.closed) == 1


def test_fail_ends_the_bar(clock, recorder):
    bar = progress(total=3, renderer=recorder, clock=clock).start()
    bar.fail("disk full")
    assert (bar.status, recorder.closed[0].message) == (Status.FAILED, "disk full")


def test_set_gives_a_position_and_a_total(clock, recorder):
    bar = progress(desc="Download", unit="B", renderer=recorder, clock=clock).start()
    assert bar.snapshot().fraction is None
    bar.set(total=2000)
    bar.set(500)
    bar.set(1500)
    snap = bar.snapshot()
    assert (snap.n, snap.total, snap.fraction, snap.unit) == (1500, 2000, 0.75, "B")


def test_pictures_are_limited_to_one_per_interval(clock, recorder):
    with progress(total=1000, renderer=recorder, clock=clock, min_interval=0.1) as bar:
        for _ in range(1000):
            clock.tick(0.001)
            bar.update()
    # one second of work: the start, about ten on the way, and the end goes to close()
    assert 9 <= len(recorder.updates) <= 12
    assert len(recorder.closed) == 1


def test_iterating_reads_the_clock_rarely_and_still_counts_everything(recorder):
    reads = 0

    def clock() -> float:
        nonlocal reads
        reads += 1
        return reads * 1e-6  # each read is a microsecond later: a very fast loop

    bar = progress(range(200_000), renderer=recorder, clock=clock)
    for _ in bar:
        pass
    assert bar.n == 200_000
    assert reads < 200
    assert recorder.closed[0].n == 200_000


def test_rate_and_time_remaining(clock, recorder):
    with progress(total=100, renderer=recorder, clock=clock) as bar:
        for _ in range(20):
            clock.tick(0.5)
            bar.update(1)
        snap = bar.snapshot()
        assert snap.rate == pytest.approx(2.0)
        assert snap.remaining == pytest.approx(40.0)
        bar.set(100)
    assert recorder.closed[0].remaining is None  # nothing remains to be estimated


def test_no_time_remaining_until_the_rate_is_stable(clock, recorder):
    with progress(total=100, renderer=recorder, clock=clock) as bar:
        clock.tick(0.2)
        bar.update()
        assert bar.snapshot().rate is None
        assert bar.snapshot().remaining is None
        bar.set(100)


def test_skipped_units_count_as_done_but_not_towards_the_rate(clock, recorder):
    with progress(total=1000, renderer=recorder, clock=clock) as bar:
        bar.update(900, skip=True)  # done in an earlier run
        for _ in range(10):
            clock.tick(1.0)
            bar.update(1)
        snap = bar.snapshot()
        assert snap.n == 910
        assert snap.rate == pytest.approx(1.0)
        assert snap.remaining == pytest.approx(90.0)
        bar.set(1000)


def test_since_progress_grows_while_nothing_happens(clock, recorder):
    with progress(total=2, renderer=recorder, clock=clock) as bar:
        bar.update()
        clock.tick(45)
        assert bar.snapshot().since_progress == pytest.approx(45)
        bar.update()


def test_a_bar_started_inside_another_is_its_child(clock, recorder):
    during = None
    for epoch in progress(range(2), "Epochs", renderer=recorder, clock=clock):
        for batch in progress(range(5), f"Batches {epoch}"):
            clock.tick(0.2)
            if epoch == 1 and batch == 2:
                during = recorder.updates[-1]
    assert during is not None
    assert during.desc == "Epochs"
    (child,) = during.children  # the first epoch's bar was done and went
    assert (child.desc, child.status) == ("Batches 1", Status.RUNNING)
    final = recorder.closed[0]
    assert (final.n, final.status, final.children) == (2, Status.DONE, ())
    assert len(recorder.closed) == 1  # one tree, one renderer


def test_a_failed_child_stays_and_fails_alone(clock, recorder):
    with progress(total=2, desc="outer", renderer=recorder, clock=clock) as outer:
        with pytest.raises(ValueError, match="bad"), progress(total=3, desc="inner") as inner:
            inner.update()
            raise ValueError("bad")
        assert outer.status is Status.RUNNING
        outer.update(2)
    (child,) = recorder.closed[0].children
    assert (child.desc, child.status, child.message) == ("inner", Status.FAILED, "ValueError: bad")
    assert recorder.closed[0].status is Status.DONE


def test_ending_a_bar_ends_what_runs_under_it(clock, recorder):
    outer = progress(total=2, desc="outer", renderer=recorder, clock=clock).start()
    inner = progress(total=3, desc="inner", parent=outer).start()
    outer.fail("gave up")
    assert inner.status is Status.FAILED
    assert recorder.closed[0].children[0].status is Status.FAILED


def test_bars_after_a_block_are_roots_again(clock, recorder):
    with progress(total=1, renderer=recorder, clock=clock) as first:
        first.update()
    second = progress(total=1, renderer=recorder, clock=clock)
    assert second.parent is None


def test_description_and_postfix_as_tqdm_has_them(clock, recorder):
    with progress(total=2, renderer=recorder, clock=clock) as bar:
        bar.set_description("Training")
        bar.set_postfix(loss=0.123456, acc=0.9, step=3)
        bar.refresh()
        snap = recorder.updates[-1]
        assert snap.desc == "Training"
        assert snap.metrics == {"loss": "0.123", "acc": "0.9", "step": "3"}
        bar.set_postfix(loss=0.1)
        assert bar.snapshot().metrics == {"loss": "0.1"}
        bar.update(2)
    assert (bar.n, bar.total, bar.desc) == (2, 2, "Training")


def test_disabled_does_nothing_and_adds_nothing_to_the_loop(recorder):
    items = [1, 2, 3]
    bar = progress(items, renderer=recorder, disable=True)
    assert type(iter(bar)) is type(iter(items))
    assert list(bar) == items
    with bar:
        bar.update()
        bar.set_postfix(a=1)
    assert recorder.updates == []
    assert recorder.closed == []


def test_updating_from_many_threads_loses_nothing(recorder):
    bar = progress(total=8000, renderer=recorder).start()
    threads = [
        threading.Thread(target=lambda: [bar.update() for _ in range(1000)]) for _ in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    bar.close()
    assert (bar.n, bar.status) == (8000, Status.DONE)


def test_a_renderer_that_breaks_does_not_break_the_work(clock):
    class Broken:
        def update(self, root):
            raise OSError("terminal went away")

        def close(self, root):
            raise AssertionError("not reached: dropped after the first failure")

    with pytest.warns(RuntimeWarning, match="progress display stopped"):
        total = sum(progress(range(100), renderer=Broken(), clock=clock))
    assert total == 4950


def test_a_bar_without_an_iterable_cannot_be_iterated():
    with pytest.raises(TypeError, match="wraps no iterable"):
        iter(progress(total=3))

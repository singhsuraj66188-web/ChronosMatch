
import pytest

from ipc.ring_buffer import RingBuffer


def test_write_and_read_record(tmp_path):
    path = tmp_path / "ticks.bin"

    with RingBuffer(path, capacity=4, create=True) as ring:
        assert ring.write(
            timestamp_ns=123,
            price_ticks=2500,
            quantity=3,
            side=1,
        )

        record = ring.read()

        assert record is not None
        assert record["timestamp_ns"] == 123
        assert record["price_ticks"] == 2500
        assert record["quantity"] == 3
        assert record["side"] == 1


def test_empty_buffer_returns_none(tmp_path):
    with RingBuffer(
        tmp_path / "ticks.bin",
        capacity=4,
        create=True,
    ) as ring:
        assert ring.read() is None


def test_full_buffer_and_wraparound(tmp_path):
    with RingBuffer(
        tmp_path / "ticks.bin",
        capacity=2,
        create=True,
    ) as ring:
        assert ring.write(
            timestamp_ns=1, price_ticks=100, quantity=1, side=1
        )
        assert ring.write(
            timestamp_ns=2, price_ticks=101, quantity=1, side=2
        )

        assert not ring.write(
            timestamp_ns=3, price_ticks=102, quantity=1, side=1
        )

        first = ring.read()
        assert first is not None
        assert first["timestamp_ns"] == 1

        assert ring.write(
            timestamp_ns=3, price_ticks=102, quantity=1, side=1
        )

        second = ring.read()
        third = ring.read()

        assert second is not None
        assert third is not None
        assert second["timestamp_ns"] == 2
        assert third["timestamp_ns"] == 3
        assert ring.read() is None


def test_invalid_tick_is_rejected(tmp_path):
    with RingBuffer(
        tmp_path / "ticks.bin",
        capacity=4,
        create=True,
    ) as ring:
        with pytest.raises(ValueError):
            ring.write(
                timestamp_ns=1,
                price_ticks=0,
                quantity=1,
                side=1,
            )

import pytest

from tare.book import Book, DeltaStatus, Fill, Position


def test_delta_is_zero_when_spot_is_offset_by_a_short_perp():
    position = Position(spot_qty=10.0, perp_qty=-10.0)

    assert position.delta == 0.0


def test_delta_is_positive_when_the_hedge_is_short_of_the_spot_leg():
    position = Position(spot_qty=10.0, perp_qty=-7.0)

    assert position.delta == pytest.approx(3.0)


def test_an_unconfirmed_fill_does_not_move_the_position():
    book = Book()

    book.apply_fill(Fill(venue="phoenix", qty=-10.0, confirmed=False))

    assert book.position.perp_qty == 0.0
    assert book.unconfirmed == 1


def test_delta_status_is_unknown_while_a_hedge_is_unconfirmed():
    book = Book()
    book.apply_fill(Fill(venue="jupiter", qty=10.0, confirmed=True))
    book.apply_fill(Fill(venue="phoenix", qty=-10.0, confirmed=False))

    assert book.delta_status() is DeltaStatus.UNKNOWN


def test_delta_status_is_neutral_only_when_every_fill_is_confirmed():
    book = Book()
    book.apply_fill(Fill(venue="jupiter", qty=10.0, confirmed=True))
    book.apply_fill(Fill(venue="phoenix", qty=-10.0, confirmed=True))

    assert book.delta_status() is DeltaStatus.NEUTRAL


def test_delta_status_is_directional_when_confirmed_legs_do_not_offset():
    book = Book()
    book.apply_fill(Fill(venue="jupiter", qty=10.0, confirmed=True))

    assert book.delta_status() is DeltaStatus.DIRECTIONAL


def test_an_order_that_would_breach_the_inventory_cap_is_flagged_before_it_is_sent():
    book = Book(inventory_cap=10.0)
    book.apply_fill(Fill(venue="jupiter", qty=8.0, confirmed=True))

    assert book.would_breach_cap(5.0) is True
    assert book.would_breach_cap(1.0) is False


def test_an_unconfirmed_fill_counts_against_the_cap_as_if_it_landed():
    book = Book(inventory_cap=10.0)
    book.apply_fill(Fill(venue="jupiter", qty=9.0, confirmed=False))

    assert book.would_breach_cap(2.0) is True

import numpy as np
import pytest

from teaserkit import music


@pytest.mark.parametrize("secs", [1.0, 7.3, 35.2])
def test_track_is_exactly_as_long_as_asked(tmp_path, secs):
    r = music.make_track(secs, tmp_path / "t.wav")
    assert music.wav_seconds(r["path"]) == pytest.approx(secs, abs=1 / music.SR)


def test_deterministic_and_peak_limited():
    a = music.synthesize(4.0, seed=3)
    b = music.synthesize(4.0, seed=3)
    assert np.array_equal(a, b)
    assert a.shape == (4 * music.SR, 2)
    assert np.max(np.abs(a)) == pytest.approx(10 ** (-4 / 20), rel=1e-3)


def test_unknown_progression():
    with pytest.raises(ValueError):
        music.synthesize(2.0, progression="nope")

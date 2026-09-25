import pytest

from teaserkit.errors import StoryboardError
from teaserkit.rules import planned_seconds, validate, words
from teaserkit.storyboard import load, parse

from conftest import DEMO, minimal


def rules(rep):
    return {i.rule for i in rep.errors}, {i.rule for i in rep.warnings}


def test_demo_storyboard_is_clean():
    rep = validate(load(DEMO))
    assert rep.ok and not rep.warnings, rep.text()
    assert 30 <= rep.videos["acme-teaser"] <= 40


def test_word_count():
    assert words("Add a task in seconds.") == 5
    assert words("Now — next, later") == 3


def test_caption_too_many_words():
    rep = validate(parse(minimal(beat={"caption": "This caption line has far too many words in it"})))
    assert "caption-words" in rules(rep)[0]


def test_caption_lines_limit():
    rep = validate(parse(minimal(beat={"caption": "One line\nTwo lines", "sub": "Three lines"})))
    assert "caption-lines" in rules(rep)[0]


def test_caption_needs_time_on_screen():
    rep = validate(parse(minimal(beat={"duration": 2.5})))
    assert "caption-time" in rules(rep)[0]


def test_soft_rules_are_warnings_and_strict_promotes_them():
    data = minimal(beat={"duration": 8, "hold": 0.2})
    rep = validate(parse(data))
    assert rep.ok
    assert {"beat-length", "result-hold"} <= rules(rep)[1]
    assert not validate(parse(data), strict=True).ok


def test_camera_speed_warning():
    rep = validate(parse(minimal(beat={"roi": [{"at": 0, "roi": [0, 0, 800, 600]}, {"at": 1, "roi": [0, 0, 400, 300], "move": 0.3}]})))
    assert "camera-speed" in rules(rep)[1]


def test_roi_out_of_viewport():
    rep = validate(parse(minimal(beat={"roi": [0, 0, 2000, 600]})))
    assert "roi-bounds" in rules(rep)[0]


def test_deny_list_in_typed_text_and_captions():
    data = minimal(beat={"steps": [{"type": "hello from Internal Staging"}]})
    data["project"]["deny_list"] = ["internal staging"]
    assert "deny-list" in rules(validate(parse(data)))[0]
    data = minimal(beat={"caption": "Shows undefined value"})
    assert "deny-list" in rules(validate(parse(data)))[0]


def test_deny_word_boundaries():
    data = minimal(beat={"caption": "Finance made friendly"})  # contains 'nan' but not the word NaN
    assert validate(parse(data)).ok


def test_video_length_by_kind():
    data = minimal()
    data["videos"][0]["kind"] = "main"
    rep = validate(parse(data))
    assert "video-length" in rules(rep)[1]


def test_music_must_be_synth_or_none():
    rep = validate(parse(minimal(style={"music": "licensed.mp3"})))
    assert "music" in rules(rep)[0]


def test_planned_seconds_accounts_for_crossfades():
    data = minimal()
    data["videos"][0]["title"] = {"title": "Hi"}
    data["videos"][0]["end"] = {"tagline": "Bye"}
    sb = parse(data)
    # 2.8 + 5 + 3.4 - 2 * 0.5
    assert planned_seconds(sb.videos[0], sb.style) == pytest.approx(10.2)


@pytest.mark.parametrize("bad, where", [
    ({"beat": {"steps": [{"fly": "/"}]}}, "steps[0]"),
    ({"beat": {"roi": [10, 10, 5, 5]}}, "roi"),
    ({"outputs": {"aspects": ["4x3"]}}, "outputs.aspects"),
])
def test_schema_errors_name_the_location(bad, where):
    with pytest.raises(StoryboardError) as e:
        parse(minimal(**bad))
    assert where in e.value.message


def test_unknown_beat_reference():
    data = minimal()
    data["videos"][0]["beats"] = ["nope"]
    with pytest.raises(StoryboardError, match="no beat with id"):
        parse(data)


def test_takes_group_beats_in_order():
    sb = load(DEMO)
    assert list(sb.takes()) == ["tour"]
    assert [b.id for b in sb.takes()["tour"]][:2] == ["today", "add-task"]


def test_deny_list_entries_resolve_env(monkeypatch):
    from teaserkit.errors import RecordingError
    from teaserkit.recorder import live_deny_pattern

    data = minimal()
    data["project"]["deny_list"] = ["${env:TK_TEST_DENY}"]
    sb = parse(data)
    monkeypatch.setenv("TK_TEST_DENY", "zorblat")
    assert live_deny_pattern(sb).search("hello Zorblat")
    monkeypatch.delenv("TK_TEST_DENY")
    with pytest.raises(RecordingError):
        live_deny_pattern(sb)

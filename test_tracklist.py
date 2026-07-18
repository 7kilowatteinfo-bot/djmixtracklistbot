\
from tracklist import extract_detections, render_tracklist


def test_dedup_and_start_estimation():
    payload = {
        "status": "success",
        "result": [
            {
                "offset": "08:48",
                "songs": [
                    {
                        "score": 78,
                        "artist": "Artist A",
                        "title": "Track A",
                        "timecode": "01:06",
                        "isrc": "AAA111",
                    }
                ],
            },
            {
                "offset": "09:36",
                "songs": [
                    {
                        "score": 91,
                        "artist": "Artist A",
                        "title": "Track A",
                        "timecode": "01:54",
                        "isrc": "AAA111",
                    }
                ],
            },
            {
                "offset": "12:00",
                "songs": [
                    {
                        "score": 95,
                        "artist": "Artist B",
                        "title": "Track B",
                        "timecode": "00:20",
                        "isrc": "BBB222",
                    }
                ],
            },
        ],
    }

    result = extract_detections(payload, min_score=55)

    assert len(result) == 2
    assert result[0].artist == "Artist A"
    assert result[0].estimated_start == 462  # 08:48 - 01:06 = 07:42
    assert result[0].score == 91
    assert result[1].estimated_start == 700  # 12:00 - 00:20 = 11:40

    text = render_tracklist(result)
    assert "01. 07:42 — Artist A — Track A" in text
    assert "02. 11:40 — Artist B — Track B" in text


if __name__ == "__main__":
    test_dedup_and_start_estimation()
    print("OK")

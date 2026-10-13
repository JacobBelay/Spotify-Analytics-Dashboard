from app.connectors.csv_import import parse_export, title_overlap


def test_spotify_timeline():
    raw = b'date,listeners,streams,followers\n2026-01-01,"1,200",3400,500\n2026-01-02,1300,3600,505\n'
    p = parse_export(raw, "timeline.csv")
    assert p.file_type == "timeline"
    assert p.platform == "spotify"  # followers column implies Spotify
    s = p.summary()
    assert s["days"] == 2 and set(s["metrics"]) == {"listeners", "streams", "followers"}
    assert p.timeline.query("metric == 'listeners'")["value"].iloc[0] == 1200


def test_apple_semicolon_us_dates_and_plays_become_streams():
    raw = b"Date;Plays;Average Daily Listeners;Shazams\n01/05/2026;100;40;3\n01/06/2026;120;45;4\n"
    p = parse_export(raw, "export.csv")
    assert p.file_type == "timeline" and p.platform == "apple_music"
    assert "streams" in p.summary()["metrics"]


def test_title_rows_above_header_and_songs():
    raw = b"Spotify for Artists export\n\nSong,Listeners,Streams,Saves\nSong A,100,500,20\nSong B (feat. X),300,900,40\n"
    p = parse_export(raw, "songs.csv", "spotify")
    assert p.file_type == "songs" and len(p.songs) == 2
    assert p.songs.iloc[0]["song"] == "Song B (feat. X)"  # sorted by streams
    assert title_overlap(p.songs["song"].tolist(), ["Song B"]) == 0.5


def test_playlists_with_date_added():
    raw = b"Playlist,Made by,Streams,Date added\nHits,Spotify,5000,2026-01-02\n"
    p = parse_export(raw, "spotify_playlists.csv")
    assert p.file_type == "playlists" and p.platform == "spotify"
    assert p.summary()["top_playlists"][0]["playlist"] == "Hits"


def test_unknown_layout_warns():
    p = parse_export(b"foo,bar\n1,2\n")
    assert p.file_type == "unknown" and p.warnings

# Mixtape Bug Hunt

## AI usage

Codex assisted with repository setup, reading the models/routes/services, tracing calls, designing controlled reproductions, implementing fixes, running tests, and drafting this document. The codebase map below was written before running bug reproductions or changing application code. Verification results and limitations are recorded with each issue; these are tool-run observations, not claims that I independently performed those steps without AI.

## Codebase map

- `app.py` owns the shared SQLAlchemy object and `create_app(config)`. The factory configures Flask, registers four blueprints under `/songs`, `/playlists`, `/users`, and `/feed`, and creates database tables. Tests override the database URI with an in-memory SQLite database.
- `models.py` defines seven models: `User`, `Tag`, `Song`, `ListeningEvent`, `Rating`, `Playlist`, and `Notification`. `friendships` connects users, `song_tags` connects songs and tags, and `playlist_entries` connects playlists and songs with explicit `position`, `added_by`, and `added_at` metadata. A unique constraint permits one rating per user/song pair. Model `to_dict()` methods define JSON fields.
- `routes/songs.py` parses search queries and rating/listening POST bodies, delegates to services, and serializes responses. `routes/playlists.py` handles creation, metadata, ordered song retrieval, and additions. `routes/feed.py` exposes listening-now and activity lists. `routes/users.py` exposes profiles, streaks, notifications, and notification read actions; the profile endpoint queries `User` directly.
- `services/streak_service.py` records listening events, updates stored streak state, and retrieves the current streak. `services/feed_service.py` queries friends' listening events for listening-now and general activity. `services/search_service.py` searches titles/artists and retrieves individual songs. `services/playlist_service.py` creates playlists and retrieves metadata and ordered songs. `services/notification_service.py` owns rating writes, playlist additions, notification creation/retrieval, and read state.
- `seed_data.py` rebuilds the local database with five users, bidirectional friendships, tagged and untagged songs, listening events, ordered playlist entries, and an example notification. The actual seed creates 13 songs and three seven-song playlists.
- `tests/test_streaks.py`, `tests/test_search.py`, and `tests/test_playlists.py` use pytest fixtures and isolated SQLite databases to exercise service behavior. `requirements.txt` lists Flask, Flask-SQLAlchemy, SQLAlchemy, python-dotenv, and pytest.

### Data flow: rating a song

`POST /songs/<song_id>/rate` enters `routes/songs.py:rate()`, which reads `user_id` and `score`, checks required fields, converts the score to an integer, and calls `notification_service.rate_song()`. The service checks the score range, looks up the song and rater, then finds the existing `Rating` for that user/song. It updates that row or adds a new one and commits through `db.session`. The route serializes the returned rating with `Rating.to_dict()` and responds with HTTP 201; a `ValueError` becomes HTTP 400.

### Organization patterns

Blueprints keep HTTP parsing and response formatting near the endpoints; services hold the feature logic and database writes. Shared SQLAlchemy models connect the features. Playlist order comes from association-table positions, while feeds use event timestamps. UTC timestamps are the app's time convention; there is no per-user timezone field.

## Root cause analyses

Entries below are added as each fix is verified.

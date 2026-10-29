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

**Issue #1 — My listening streak keeps resetting**

- **How you reproduced it:** Before changing the service, the supplied Saturday June 15 → Sunday June 16, 2024 test returned 1 instead of 2. A new parametrized regression set a previous streak to 12 and listened on the next day for each weekday: Sunday returned 1 rather than 13 while the other six days passed.
- **How you found the root cause:** Followed `routes/songs.py:listen()` → `record_listening_event()` → `update_listening_streak()` in `services/streak_service.py`; `routes/users.py:streak()` only retrieves the stored value. The controlled dates isolated the decision that increments the stored streak.
- **The root cause:** The consecutive-day branch required both `days_since_last == 1` and `today.weekday() != 6`. Python numbers Sunday as 6, so consecutive Sunday listens fell into the reset branch even though exactly one calendar day had elapsed.
- **Your fix:** Removed the weekday restriction. Consecutive calendar dates now increment on every day of the week.
- **Your side-effect check:** All 12 streak tests passed: first listen, ordinary consecutive days, same-day repeats, skipped days, the original Sunday case, and the new seven-weekday regression in `tests/test_streaks.py:test_existing_streak_continues_across_every_weekday`.

AI assistance: Codex traced the route/service calls, explained the weekday condition, and implemented the change; the before/after tests verified the diagnosis.

**Issue #2 — Friends Listening Now shows people from yesterday**

- **How you reproduced it:** Added a controlled HTTP regression with the service clock fixed at October 15, 2026, 09:00 UTC and a friend's only listen at October 14, 23:59:59 UTC. Before the fix, `GET /feed/<owner>/listening-now` returned count 1 instead of 0.
- **How you found the root cause:** Traced `routes/feed.py:listening_now()` to `services/feed_service.py:get_friends_listening_now()`, inspected the timestamp filter, and compared the separately implemented activity feed. The frozen-clock case proved that a previous-date event passed the listening-now cutoff.
- **The root cause:** The cutoff was the current instant minus 24 hours, making the feed a rolling window. At 09:00 it still included yesterday's late-night listens, rather than restricting results to today's calendar date.
- **Your fix:** Replaced the rolling cutoff with midnight of the current UTC day and clarified the service docstring. UTC follows the existing timestamp convention; the models contain no per-user timezone setting.
- **Your side-effect check:** `tests/test_feed.py` passed. It excludes one second before midnight, includes exactly midnight, keeps only the latest event per friend, excludes a nonfriend, returns an empty list for a user without friends and 404 for a missing user. The general activity endpoint still includes the historical event.

AI assistance: Codex designed the fixed-clock boundary case and traced the cutoff; executable assertions confirmed both the bug and the preserved activity behavior.

**Issue #3 — The same song keeps showing up twice in search**

- **How you reproduced it:** Before any application fixes, ran the Flask server and requested `GET /songs/search?q=Anthem`: HTTP 200 contained three copies of the same Crown Heights Anthem song ID, with all three tags on every copy. The supplied multi-tag search test also failed with 3 matches instead of 1, while zero/one-tag cases passed.
- **How you found the root cause:** Followed `routes/songs.py:search()` → `services/search_service.py:search_songs()`, then checked `models.py` for the song/tag association and `Song.to_dict()`. The query outer-joined `song_tags`; inspecting the scalar result handling showed that it did not remove repeated song identities.
- **The root cause:** A song with three tag associations creates three joined SQL rows. `execute(select(Song)...).scalars().all()` retains each row's song occurrence, so serialization produces identical copies. The zero-tag outer-join row and the single-tag row explain why the symptom is conditional.
- **Your fix:** Added `.unique()` to the scalar result before collecting it. SQLAlchemy now yields each song identity once, preserving matching and tag serialization.
- **Your side-effect check:** All five supplied search tests passed: title/artist matches, songs with zero tags, one tag, or multiple tags, and an unmatched search. The three-tag regression is `tests/test_search.py:test_search_no_duplicates_multi_tag_song`; it existed in the starter and was not authored for this submission.

AI assistance: Codex explained join row multiplication and result uniquing; the real HTTP response and passing service tests verified the explanation.

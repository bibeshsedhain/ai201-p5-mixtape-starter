from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app import db
from models import ListeningEvent


def test_listening_now_uses_utc_midnight_and_latest_friend_event(scenario):
    client, owner, friend, stranger, song, other = scenario
    now = datetime(2026, 10, 15, 9, tzinfo=timezone.utc)
    midnight = now.replace(hour=0)
    with patch('services.feed_service.datetime') as clock:
        clock.now.return_value = now
        yesterday = ListeningEvent(user_id=friend.id, song_id=song.id,
                                   listened_at=midnight - timedelta(seconds=1))
        db.session.add(yesterday)
        db.session.commit()
        assert client.get(f'/feed/{owner.id}/listening-now').json['count'] == 0
        db.session.add(ListeningEvent(user_id=friend.id, song_id=song.id, listened_at=midnight))
        db.session.add(ListeningEvent(user_id=stranger.id, song_id=song.id, listened_at=now))
        db.session.commit()
        feed = client.get(f'/feed/{owner.id}/listening-now').json['feed']
        assert [item['friend']['id'] for item in feed] == [friend.id]
        db.session.add(ListeningEvent(user_id=friend.id, song_id=other.id, listened_at=now))
        db.session.commit()
        feed = client.get(f'/feed/{owner.id}/listening-now').json['feed']
        assert len(feed) == 1
        assert feed[0]['song']['id'] == other.id
        # General activity must retain historical events.
        assert client.get(f'/feed/{owner.id}/activity').json['count'] == 3
        assert client.get(f'/feed/{stranger.id}/listening-now').json['feed'] == []
        assert client.get('/feed/missing/listening-now').status_code == 404

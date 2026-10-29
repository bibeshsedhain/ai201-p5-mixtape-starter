from app import db
from models import Rating


def test_rating_notifies_sharer_and_preserves_updates_and_read_state(scenario):
    client, owner, friend, stranger, song, other = scenario
    url = f'/songs/{song.id}/rate'
    response = client.post(url, json={'user_id': friend.id, 'score': 5})
    assert response.status_code == 201
    notices = client.get(f'/users/{owner.id}/notifications').json['notifications']
    assert len(notices) == 1
    assert notices[0]['type'] == 'song_rated'
    assert friend.username in notices[0]['body']
    assert song.title in notices[0]['body']
    assert '5' in notices[0]['body']
    client.post(f"/users/notifications/{notices[0]['id']}/read")
    assert client.get(f'/users/{owner.id}/notifications?unread_only=true').json['count'] == 0
    assert client.post(url, json={'user_id': friend.id, 'score': 3}).status_code == 201
    ratings = Rating.query.filter_by(song_id=song.id, user_id=friend.id).all()
    assert len(ratings) == 1 and ratings[0].score == 3
    assert client.get(f'/users/{owner.id}/notifications').json['count'] == 2
    client.post(url, json={'user_id': owner.id, 'score': 4})
    assert client.get(f'/users/{owner.id}/notifications').json['count'] == 2
    assert client.get(f'/users/{friend.id}/notifications').json['count'] == 0
    assert client.post(url, json={'user_id': friend.id, 'score': 6}).status_code == 400
    assert client.post(url, json={'user_id': 'missing', 'score': 5}).status_code == 400
    assert client.post('/songs/missing/rate', json={'user_id': friend.id, 'score': 5}).status_code == 400
    assert client.get(f'/users/{owner.id}/notifications').json['count'] == 2

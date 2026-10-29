from app import db
from models import Playlist, playlist_entries


def test_empty_single_song_and_append_are_visible_in_order(scenario):
    client, owner, friend, stranger, song, other = scenario
    playlist = Playlist(name='Boundary Mix', created_by=owner.id)
    db.session.add(playlist)
    db.session.commit()
    url = f'/playlists/{playlist.id}/songs'
    assert client.get(url).json['songs'] == []
    assert client.post(url, json={'song_id': song.id, 'added_by': friend.id}).status_code == 201
    assert [s['id'] for s in client.get(url).json['songs']] == [song.id]
    assert client.post(url, json={'song_id': other.id, 'added_by': owner.id}).status_code == 201
    assert [s['id'] for s in client.get(url).json['songs']] == [song.id, other.id]
    # Re-adding a song should not create a duplicate association or change its position.
    assert client.post(url, json={'song_id': song.id, 'added_by': friend.id}).status_code == 201
    assert client.get(url).json['count'] == 2
    rows = db.session.execute(db.select(playlist_entries).order_by(playlist_entries.c.position)).mappings().all()
    assert [(r['position'], r['added_by']) for r in rows] == [(1, friend.id), (2, owner.id)]
    notifications = client.get(f'/users/{owner.id}/notifications').json['notifications']
    assert any(n['type'] == 'song_added_to_playlist' for n in notifications)

import pytest
from app import create_app, db
from models import User, Song


@pytest.fixture
def scenario():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.app_context():
        owner = User(username='owner', email='owner@example.com')
        friend = User(username='friend', email='friend@example.com')
        stranger = User(username='stranger', email='stranger@example.com')
        db.session.add_all([owner, friend, stranger])
        db.session.flush()
        owner.friends.append(friend)
        song = Song(title='Boundary Song', artist='Test Artist', shared_by=owner.id)
        other = Song(title='Next Song', artist='Test Artist', shared_by=owner.id)
        db.session.add_all([song, other])
        db.session.commit()
        yield app.test_client(), owner, friend, stranger, song, other
        db.session.remove()
        db.drop_all()

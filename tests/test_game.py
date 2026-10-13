import io
import time
from PIL import Image
from app import create_app, socketio
from app.services.pose_scorer import ScoreResult

class Fixed:
    def __init__(self, statuses): self.statuses=iter(statuses)
    def evaluate(self, *_): return next(self.statuses)

def setup_game(statuses):
    app=create_app({'TESTING':True,'CAPTURE_SECONDS':0},scorer=Fixed(statuses))
    a=socketio.test_client(app); b=socketio.test_client(app)
    a.emit('enter_room',{'name':'A'})
    ma=next(x['args'][0] for x in a.get_received() if x['name']=='entered')
    b.emit('enter_room',{'name':'B','room_id':ma['room_id']})
    mb=next(x['args'][0] for x in b.get_received() if x['name']=='entered')
    a.emit('ready',{'ready':True});b.emit('ready',{'ready':True})
    room=app.extensions['game_manager'].rooms[ma['room_id']]
    return app,a,b,ma,mb,room

def submit(app, membership, room):
    image=io.BytesIO();Image.new('RGB',(20,20)).save(image,format='JPEG');image.seek(0)
    return app.test_client().post('/api/submissions',data={'room_id':room.id,'match_id':room.match_id,'token':membership['token'],'photo':(image,'photo.jpg')})

def test_score_and_duplicate():
    app,a,b,ma,mb,room=setup_game([ScoreResult('success',90),ScoreResult('success',60)])
    assert submit(app,ma,room).status_code==200
    assert submit(app,ma,room).status_code==409
    assert submit(app,mb,room).status_code==200
    assert room.result['winner']==ma['player_id']
    a.disconnect();b.disconnect()

def test_undetected_loses():
    app,a,b,ma,mb,room=setup_game([ScoreResult('undetected'),ScoreResult('success',0)])
    submit(app,ma,room);submit(app,mb,room)
    assert room.result['winner']==mb['player_id']
    a.disconnect();b.disconnect()

def test_both_undetected_draw():
    app,a,b,ma,mb,room=setup_game([ScoreResult('undetected'),ScoreResult('undetected')])
    submit(app,ma,room);submit(app,mb,room)
    assert room.result['kind']=='draw'
    a.disconnect();b.disconnect()

def test_ai_unavailable_invalid():
    app,a,b,ma,mb,room=setup_game([ScoreResult('unavailable'),ScoreResult('success',75)])
    submit(app,ma,room);submit(app,mb,room)
    assert room.result['kind']=='invalid'
    a.disconnect();b.disconnect()

def test_third_player_and_disconnect():
    app,a,b,ma,mb,room=setup_game([])
    c=socketio.test_client(app);c.emit('enter_room',{'room_id':room.id})
    assert any(x['name']=='notice' for x in c.get_received())
    b.disconnect();assert room.result['kind']=='invalid'
    a.disconnect();c.disconnect()

def test_wrong_token_and_timeout():
    app,a,b,ma,mb,room=setup_game([])
    assert submit(app,{**ma,'token':'wrong'},room).status_code==403
    room.deadline=int(time.time()*1000)-1
    assert submit(app,ma,room).status_code==409
    a.disconnect();b.disconnect()

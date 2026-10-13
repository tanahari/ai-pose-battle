import io
import os
import threading
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from PIL import Image, UnidentifiedImageError
from .services.game_manager import GameManager
from .services.pose_scorer import PendingPoseScorer, DemoPoseScorer, ScoreResult

socketio = SocketIO(async_mode='threading', max_http_buffer_size=100000)

def create_app(test_config=None, scorer=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=5*1024*1024, CAPTURE_SECONDS=30,
                      DEMO_MODE=os.environ.get('POSE_DEMO') == '1')
    if test_config: app.config.update(test_config)
    socketio.init_app(app)
    manager = GameManager()
    lock = threading.RLock()
    ai = scorer or (DemoPoseScorer() if app.config['DEMO_MODE'] else PendingPoseScorer())
    app.extensions['game_manager'] = manager

    def broadcast(room):
        socketio.emit('room_state', room.public(), to=room.id)

    def timeout(room_id, match_id, deadline):
        socketio.sleep(max(0, (deadline-int(time.time()*1000))/1000))
        with lock:
            room = manager.rooms.get(room_id)
            if room and room.match_id == match_id and room.state != 'finished':
                manager.invalidate(room, '画像送信・採点が制限時間内に完了しませんでした')
                broadcast(room)

    @app.get('/')
    def index():
        return render_template('index.html', demo=app.config['DEMO_MODE'])

    @app.get('/api/time')
    def server_time():
        return jsonify(server_now=int(time.time()*1000))

    @socketio.on('enter_room')
    def enter(data):
        with lock:
            try:
                if not isinstance(data, dict): raise ValueError('入力が不正です')
                room, player = manager.join(request.sid, data.get('name'), data.get('room_id') or None)
                join_room(room.id)
                emit('entered', dict(player_id=player.sid, token=player.token, room_id=room.id))
                broadcast(room)
            except ValueError as exc:
                emit('notice', dict(message=str(exc)))

    @socketio.on('ready')
    def ready(data):
        with lock:
            room = manager.room_for(request.sid)
            if not room or room.state != 'waiting': return
            room.players[request.sid].ready = bool((data or {}).get('ready'))
            if manager.start_if_ready(room, app.config['CAPTURE_SECONDS']):
                socketio.start_background_task(timeout, room.id, room.match_id, room.deadline)
            broadcast(room)

    @socketio.on('capture_failed')
    def capture_failed(data):
        with lock:
            room = manager.room_for(request.sid)
            if room and room.state in ('countdown', 'scoring') and (data or {}).get('match_id') == room.match_id:
                manager.invalidate(room, '撮影に失敗しました')
                broadcast(room)

    @socketio.on('disconnect')
    def disconnect():
        with lock:
            room = manager.leave(request.sid)
            if room: broadcast(room)

    @app.post('/api/submissions')
    def submit():
        room_id = request.form.get('room_id')
        match_id = request.form.get('match_id')
        token = request.form.get('token')
        with lock:
            room = manager.rooms.get(room_id)
            player = next((p for p in room.players.values() if p.token == token), None) if room else None
            if not player: return jsonify(error='参加資格がありません'), 403
            if room.match_id != match_id or room.state not in ('countdown', 'scoring'):
                return jsonify(error='受付中の試合ではありません'), 409
            now = int(time.time()*1000)
            if now < room.capture_at-1000: return jsonify(error='受付開始前です'), 409
            if now > room.deadline: return jsonify(error='受付期限を過ぎています'), 409
            if player.sid in room.submissions: return jsonify(error='提出済みです'), 409
            # 予約値で並行・二重提出を防止。撮影画像はディスクに保存しない。
            room.submissions[player.sid] = ScoreResult('unavailable')
            room.state = 'scoring'
            broadcast(room)
        try:
            upload = request.files.get('photo')
            if not upload: raise ValueError('画像がありません')
            payload = upload.read(5*1024*1024+1)
            if len(payload) > 5*1024*1024: raise ValueError('画像が大きすぎます')
            with Image.open(io.BytesIO(payload)) as image:
                if image.format not in ('JPEG', 'PNG') or image.width*image.height > 12000000:
                    raise ValueError('画像形式・サイズが不正です')
                image.verify()
            result = ai.evaluate(payload, 'arms-up')
            if result.status not in ('success','undetected','unavailable'):
                raise ValueError('採点結果が不正です')
            if result.status == 'success' and (result.score is None or not 0 <= result.score <= 100):
                raise ValueError('得点が不正です')
        except (ValueError, UnidentifiedImageError, OSError):
            with lock:
                manager.invalidate(room, '画像の読み込みに失敗しました')
                broadcast(room)
            return jsonify(error='画像を処理できません'), 400
        except Exception:
            app.logger.exception('Scoring failed')
            result = ScoreResult('unavailable')
        with lock:
            if room.state == 'finished': return jsonify(error='試合は終了しています'), 409
            room.submissions[player.sid] = result
            # 予約中の提出を確定扱いしないため、完了済みを別に管理。
            completed = getattr(room, 'completed', set())
            completed.add(player.sid)
            room.completed = completed
            if len(completed) == 2: manager.finish(room)
            broadcast(room)
        return jsonify(ok=True)

    return app

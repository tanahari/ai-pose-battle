from dataclasses import dataclass, field
import secrets
import time

@dataclass
class Player:
    sid: str
    name: str
    token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    ready: bool = False

@dataclass
class GameRoom:
    id: str
    players: dict = field(default_factory=dict)
    state: str = 'waiting'
    match_id: str | None = None
    capture_at: int | None = None
    deadline: int | None = None
    submissions: dict = field(default_factory=dict)
    result: dict | None = None

    def public(self):
        return dict(room_id=self.id, state=self.state, match_id=self.match_id,
                    capture_at=self.capture_at, deadline=self.deadline,
                    server_now=int(time.time()*1000), reference_id='arms-up',
                    players=[dict(id=p.sid, name=p.name, ready=p.ready) for p in self.players.values()],
                    result=self.result)

class GameManager:
    def __init__(self):
        self.rooms = {}
        self.memberships = {}

    def join(self, sid, name, room_id=None):
        if sid in self.memberships:
            raise ValueError('すでにルームに参加しています')
        if room_id is None:
            while True:
                room_id = secrets.token_hex(3).upper()
                if room_id not in self.rooms: break
            self.rooms[room_id] = GameRoom(room_id)
        room = self.rooms.get(room_id)
        if room is None: raise ValueError('ルームが見つかりません')
        if room.state != 'waiting' or len(room.players) >= 2:
            raise ValueError('このルームには参加できません')
        player = Player(sid, str(name or 'プレイヤー').strip()[:24] or 'プレイヤー')
        room.players[sid] = player
        self.memberships[sid] = room_id
        return room, player

    def room_for(self, sid):
        return self.rooms.get(self.memberships.get(sid))

    def start_if_ready(self, room, seconds):
        if room.state != 'waiting' or len(room.players) != 2 or not all(p.ready for p in room.players.values()):
            return False
        room.state = 'countdown'
        room.match_id = secrets.token_urlsafe(16)
        room.capture_at = int(time.time()*1000) + seconds*1000
        room.deadline = room.capture_at + 15000
        return True

    def finish(self, room):
        if len(room.submissions) != 2 or room.state == 'finished': return False
        scores = room.submissions
        if any(s.status == 'unavailable' for s in scores.values()):
            room.result = dict(kind='invalid', reason='AI採点が未接続、または処理に失敗しました')
        else:
            detected = [sid for sid, s in scores.items() if s.status == 'success']
            winner = None
            if len(detected) == 1: winner = detected[0]
            elif len(detected) == 2:
                a,b = detected
                if scores[a].score != scores[b].score:
                    winner = a if scores[a].score > scores[b].score else b
            room.result = dict(kind='win' if winner else 'draw', winner=winner,
                               reason='姿勢検出失敗' if len(detected) < 2 else '点数比較',
                               scores={sid: dict(status=s.status, score=s.score) for sid,s in scores.items()})
        room.state = 'finished'
        return True

    def invalidate(self, room, reason):
        if room.state == 'finished': return
        room.state = 'finished'
        room.result = dict(kind='invalid', reason=reason)

    def leave(self, sid):
        room = self.room_for(sid)
        self.memberships.pop(sid, None)
        if room is None: return None
        room.players.pop(sid, None)
        if not room.players:
            self.rooms.pop(room.id, None)
        elif room.state != 'waiting':
            self.invalidate(room, '相手が切断しました')
        else:
            for player in room.players.values(): player.ready = False
        return room

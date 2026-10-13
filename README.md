# AIポーズ対戦ゲーム：Flask開発用の土台

Python 3.11以上を推奨。これはソースコードの初期実装です。AI採点・リアルタイム姿勢検出は未接続です。公開サービスとしては未検証です。

## 起動
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```
http://localhost:5000 を別々のブラウザ・ウィンドウで開き、作成した6桁IDで参加してください。カメラ競合を避けるには実機2台がおすすめです。別PCからの接続には run.py のhostを変更し、HTTPSのリバースプロキシを用意してください。localhost以外のHTTPではカメラが動作しない場合があります。

採点結果まで通信を試す場合だけ：
```bash
POSE_DEMO=1 python run.py
```
デモでは画像が読めれば両者75点。姿勢の良し悪しは判定していません。通常モードではAI未接続を無効試合として明示します。Socket.IOクライアントはCDNを利用するためインターネットが必要です。

## 実装済み
- ルーム作成・参加、最大2人、準備状態
- お手本表示、カメラ許可・プレビュー
- 両者Ready後、サーバーが30秒後の撮影時刻を配信
- 時刻差の簡易推定、自動撮影1枚、画像送信（再撮影なし）
- 画像・提出資格・試合ID・重複・受付期限の検証
- 点数比較、姿勢検出失敗のみ敗北、両者検出失敗は引き分け
- 技術的失敗・切断・タイムアウトは無効試合
- 結果配信。写真はメモリで処理し、ディスクには保存しない

## 担当と接続点
- AI：app/services/pose_scorer.py。evaluate(image_bytes, reference_id) を実装し create_app(scorer=...) で接続。ScoreResult('success', score) / ScoreResult('undetected') / ScoreResult('unavailable')。未接続は未検出と区別。
- AI/フロント：app/static/js/pose-detector.js。inspectPose(video) でリアルタイム関節検出と状態を返す。現状は未接続と表示。
- フロント：templates/index.html、static/css、static/js。プレビューだけ鏡表示、送信写真は反転なし。
- バック：app/__init__.py と services/game_manager.py。

## 通信
Socket.IO：enter_room {name, room_id?} → entered {player_id, token, room_id}。ready {ready:true}。room_stateで状態と撮影時刻・結果を配信。capture_failed {match_id} は技術的失敗による無効試合。
HTTP：GET /api/time → {server_now: Unixミリ秒}。POST /api/submissions はmultipartでphoto, room_id, match_id, token。5MiB以下のJPEG/PNG、1200万画素以下。受付は撮影時刻の1秒前から15秒後まで（仮）。撮影時刻の不正対策は未実装。

## 保留事項・制限
お手本は自作SVGの仮画像。基準関節データ、MediaPipe接続、採点式、検出成功条件、左右反転許容、対応環境、画像セットは後で決めます。SQLiteはまだ使っておらず、状態は1プロセスのメモリのみ。再起動で消え、複数ワーカーには対応しません。再戦は新ルーム。認証・レート制限・放置ルーム期限は未実装。同期精度と実機カメラの結合確認は未実施です。AI処理は15秒の期限内に完了する前提なので、本実装で時間上限・実行キューも検討してください。

## テスト
```bash
pytest -q
```

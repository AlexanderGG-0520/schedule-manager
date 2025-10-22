# Scheduler separation and deployment

目的: APScheduler やその他のスケジューラを WSGI ワーカーから切り離し、単一実行を保証する。

選択肢:

- APScheduler を別プロセスで実行（本リポジトリで提供する `app/scheduler.py` を使用）
- Celery + Beat を使用（メッセージブローカー + ワーカーによるスケーラブルな実行）
- RQ + Scheduler を使用（Redis ベースのシンプルな代替）

推奨: まずは軽量に APScheduler を別プロセスで実行し、Postgres の advisory lock で単一実行を担保する方法を用いる。将来的にワーカー数が増えるなら Celery へ移行する。

ファイル:

- `schedule_app/app/scheduler.py` - APScheduler を使うランナー（jobstore は SQLAlchemyJobStore）
- `schedule_app/app/utils/pg_lock.py` - Postgres advisory lock のコンテキストマネージャとデコレータ
- `schedule_app/app/cli.py` - `flask scheduler run` コマンド

使い方（開発）:

1. 環境変数を読み込む（例: `.env` に DATABASE_URL を設定）
2. 仮想環境を有効にして依存関係をインストール

```powershell
# Windows PowerShell 例
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r schedule_app/requirements.txt
```

1. scheduler を実行

```powershell
# Flask CLI を使う
$env:FLASK_APP = 'schedule_app.app'
flask scheduler run
```

systemd サービス（Linux）の例:

```ini
[Unit]
Description=Schedule Manager Scheduler
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/schedule-manager
Environment=FLASK_APP=schedule_app.app
Environment=DATABASE_URL=postgresql://user:pass@postgres:5432/schedule_db
ExecStart=/srv/.venv/bin/flask scheduler run
Restart=always

[Install]
WantedBy=multi-user.target
```

kubernetes Deployment（別コンテナで単一レプリカ）例:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: schedule-manager-scheduler
  namespace: schedule-manager
spec:
  replicas: 1
  selector:
    matchLabels:
      app: schedule-manager-scheduler
  template:
    metadata:
      labels:
        app: schedule-manager-scheduler
    spec:
      containers:
        - name: scheduler
          image: ghcr.io/your/repo/schedule-manager:latest
          command: ["flask", "scheduler", "run"]
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: schedule-manager-db
                  key: DATABASE_URL
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
          livenessProbe:
            httpGet:
              path: /health
              port: 5000
            initialDelaySeconds: 20
            periodSeconds: 60
```

動作確認:

- scheduler のログに `Registered job` や `Scheduler started` が出力されることを確認
- ジョブの先頭で `pg_lock.single_instance('job-id')` を使い、ロック非獲得時は早期 return していること
- Postgres の `pg_locks` を見てロック取得が行われていることを確認できる

例: ジョブ内での使い方

```python
from .utils.pg_lock import single_instance

@single_instance('cleanup_old_events')
def cleanup_old_events():
    # ここに処理
    pass
```

注意点:

- SQLAlchemyJobStore を使用するためには `apscheduler` と `apscheduler.jobstores.sqlalchemy` の依存が必要（requirements に追加）
- Postgres が必要。SQLite では advisory lock は動作しないため単一実行保証は得られない

検証手順（デプロイ後）:

1. scheduler Pod / プロセスのログに `Scheduler started` と `Registered job` ログがあることを確認

```powershell
# k8s 例: scheduler の Pod 名を取得してログを見る
kubectl -n schedule-manager get pods -l app=schedule-manager-scheduler
kubectl -n schedule-manager logs <scheduler-pod-name>
```

1. ジョブに `single_instance` デコレータを付与している場合、同時実行が阻止される。ログ内でロックに失敗した旨のメッセージを出すようジョブ実装をしておくと良い。

1. 実際に複数の replica や別プロセスからジョブ実行を試し、Postgres の `pg_locks` を見てロックが取られているか確認する:

```sql
SELECT * FROM pg_locks WHERE locktype = 'advisory';
```

簡易テスト（ローカル）:

1. Postgres をローカルで立てる（docker-compose / docker run など）
2. `DATABASE_URL` を環境変数に設定し、scheduler を 2 つのターミナルで同時に起動
3. ジョブ内でログを出力して、1 回しか実行されていないことを確認する

ログ例（ジョブ内）:

```python
from .utils.pg_lock import pg_try_advisory_lock

def cleanup_old_events():
  with pg_try_advisory_lock('cleanup_old_events') as locked:
    if not locked:
      current_app.logger.info('cleanup_old_events: lock not acquired, skipping')
      return
    current_app.logger.info('cleanup_old_events: lock acquired, running')
    # 処理
```

次のステップ:

- 既存のジョブを `schedule_app/app/jobs.py` のようなモジュールに集約して、`scheduler.register_jobs` で取り込む
- 必要なら Celery への移行ガイドを別途作成する

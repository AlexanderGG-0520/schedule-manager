# スケジュール管理Webサービス（Flaskサンプル）

## セットアップ手順

```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
flask db init
flask db migrate -m "init"
flask db upgrade
flask run --host=0.0.0.0 --port=5000
```

## 機能

- ユーザー認証（新規登録・ログイン・ログアウト）
- 予定の追加・編集・削除
- 月・週・日カレンダー表示
- 予定の検索・絞り込み
- モバイル対応レスポンシブUI
- 適切なセキュリティ対策

## ディレクトリ構成

- app/ ... Flask本体
- migrations/ ... DBマイグレーション
- sample_data/ ... サンプルSQL
- tests/ ... pytestテスト

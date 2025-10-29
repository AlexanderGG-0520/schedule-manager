# % SQLインジェクション監査サマリー

% Schedule Manager
% 2025-10-29

---

## 目的

- 本アプリのログイン経路が SQL インジェクションに対して安全であることを説明する。
- 友人に短時間で理解してもらえるスライド。

---

## 要点まとめ

- ユーザー検索・認証は SQLAlchemy（ORM）を使用。生の SQL を文字列連結して投げる実装はありません。
- パスワードはハッシュ化（Werkzeug の generate_password_hash / check_password_hash）で保存・検証。
- 生の SQL を使っている箇所は限定的で、パラメタバインドされています（例: advisory lock）。

---

## 実際に DB 操作を行っている主なファイル

- `schedule_app/app/auth/routes.py`
  - ログイン・登録・パスワードリセット等
  - なぜ安全か: `User.query.filter_by(username=form.username.data)`（ORM ベース、パラメタ化）

- `schedule_app/app/models.py`
  - `User` モデル（password_hash を管理）、ORM 定義の集合

- `schedule_app/app/forms.py`
  - WTForms による入力バリデーション（長さ・必須・メール形式など）

- `schedule_app/app/utils/pg_lock.py`
  - PostgreSQL advisory lock を使うユーティリティ
  - 例: `conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key})`（パラメタバインド）

- `migrations/versions/*.py`
  - スキーマ作成用。実行時にユーザー入力を受け付ける箇所ではない。

---

## なぜ SQL インジェクションが起きないか（短く）

1. ORM（SQLAlchemy）はクエリパラメータを自動的にエスケープ/バインドする。
2. ハッシュ化されたパスワードを比較しているため、平文比較による突破ができない。
3. 生 SQL を書く箇所があっても、`:param` を使ったバインドになっている（危険な f-string 埋め込みは無し）。

---

## 証拠（テストでの確認）

- 追加テスト: `tests/test_sql_injection.py` を作成して、一般的なペイロード `"' OR '1'='1"` を送信し認証が失敗することを確認。
- 実行コマンド:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

- 実行結果: `.. [100%]` （テスト成功 — 2 passed）

---

## 追加の安全チェック（推奨）

- ソース中の危険パターン検出スクリプトを定期実行（例: f-string で SQL を組む箇所の検出）。
- CI に今回の SQLi テストを組み込み、自動で回す。
- 外部入力を直接使う新規コードはコードレビューで必ずチェックするルールを導入。

---

## 友人に見せる短い説明文（コピペ用）

このアプリはユーザー検索に ORM（SQLAlchemy）を使っており、クエリはパラメタ化されます。パスワードはハッシュで保存・検証しているため、"' OR '1'='1" のような文字列を入れても認証が通ることはありません。生の SQL を自分で組み立てて投げる箇所は（例: advisory lock）を除いてなく、あってもプレースホルダで値を渡しているため安全です。

---

## 次のアクション（オプション）

1. 追加ペイロードを含むテスト群を作成して強化（私が作成可能）。
2. 自動検出スクリプトを追加して、将来の変更で危険なパターンが入らないようにする（私が実行可能）。

---

## 参考コマンド

- テストを実行:

```powershell
cd c:\Users\uketp\schedule-manager\schedule_app
.venv\Scripts\python.exe -m pytest -q
```

- 生SQL/pattern を簡易検索（PowerShell）:

```powershell
# ソース内で execute( や text( を探す
Select-String -Path .\**\*.py -Pattern "execute\(" -SimpleMatch
Select-String -Path .\**\*.py -Pattern "text(" -SimpleMatch
```

---

## 最後に

必要ならこの Markdown を PPTX に変換してお渡しできます（または PDF）。どの形式が良いですか？

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

AWS Lambda上でStrands Agentを実行し、Discordアプリケーションと連携するサーバーレスワーカー。AWS CDK v2（Python）でデプロイし、strands-agents-toolsパッケージおよびカスタムツールを使用。Discord Slash CommandsからSNS Topic経由でメッセージを受信し、AIアシスタントとして応答する。
リアルタイムDiscord出力機能を実装。AIの思考過程をリアルタイムでDiscordに表示可能。

### アーキテクチャ

- **Lambda関数**: Strands Agentを実行（Python 3.11）
- **SNS Topic**: Discordからのメッセージを受信しLambdaをトリガー
- **Lambda Layer**: 依存関係を管理（strands-agents SDK）
- **IAM Role**: AWS Bedrock、SNS、および各種AWSサービスへのアクセス権限
- **ツール実装**: strands-agents-toolsパッケージを使用（http_request、calculator、current_time、use_aws）、カスタムツール（generate_hash、json_formatter、text_analyzer）
- **リアルタイムDiscord出力**: DiscordStreamWriterクラスによる改行ベースのストリーミング出力
- **Discord統合**: Discord APIを使用してSlash Commandsに応答

### 主要な設計決定

1. **strands-agents-tools使用**: 公式ツールパッケージを使用して信頼性と機能性を向上
2. **uv必須**: 高速な依存関係管理とビルドのため（pipフォールバックを削除）
3. **環境変数サポート**: 柔軟な設定変更とツールの有効/無効制御
4. **モジュール化された設計**: config.pyとutils.pyによる関心の分離
5. **パフォーマンス最適化**: 遅延インポートと効率的なエラー処理
6. **統合テストスイート**: pytestベースの包括的なテスト
7. **.envファイル対応**: 設定管理の簡素化とセキュリティ向上
8. **リアルタイムDiscord出力**: 非同期スレッドによる効率的なストリーミング実装

## 重要なコマンド

### デプロイ

```bash
# .envファイルから設定を読み込んでデプロイ
./deploy.sh

# オプション
./deploy.sh --dry-run        # ドライラン
./deploy.sh --force          # 確認なしでデプロイ
```

### Lambda Layer構築

```bash
uv run python build_layer.py
```

### CDK直接操作

```bash
# CDK CLIがインストールされている場合
cdk synth --profile <PROFILE>
cdk deploy --profile <PROFILE>
cdk destroy --profile <PROFILE>

# CDK CLIがない場合はnpxを使用
npx aws-cdk synth --profile <PROFILE>
npx aws-cdk deploy --profile <PROFILE>
npx aws-cdk destroy --profile <PROFILE>
```

### ローカルテスト

```bash
# 全テストの実行
uv run pytest tests/ -v

# 個別テストの実行
uv run pytest tests/test_strands_tools.py -v      # 公式ツールテスト
uv run pytest tests/test_custom_tools.py -v       # カスタムツールテスト
uv run pytest tests/test_strands_agent.py -v      # Strands Agentテスト
uv run pytest tests/test_local_with_custom_tools.py -v  # ローカル統合テスト

# 実際のLambdaハンドラーテスト（Bedrock必須）
uv run python tests/test_lambda.py         # Lambda関数テスト
```

### 依存関係管理（uv使用）

```bash
uv sync                    # 依存関係インストール（仮想環境も自動作成）
# uvは仮想環境を自動管理するため、明示的なアクティベートは不要
```

## ディレクトリ構造と重要ファイル

```text
lambda/
├── lambda_function.py     # Lambdaハンドラー（リファクタリング済み、関数分割）
├── custom_tools.py        # カスタムツール実装
├── config.py              # 設定管理モジュール（型安全、環境変数対応）
└── utils.py               # ユーティリティ関数（DiscordStreamWriter含む）

stacks/
├── __init__.py
└── strands_agent_discord_worker_stack.py # CDKスタック定義（日本語コメント付き）

tests/
├── __init__.py
├── conftest.py                      # pytest設定
├── test_strands_tools.py            # 公式ツールテスト
├── test_custom_tools.py             # カスタムツールテスト
├── test_strands_agent.py            # Strands Agentテスト
├── test_local_with_custom_tools.py  # ローカル統合テスト
├── test_lambda.py                   # Lambda関数テスト
├── test_import.py                   # インポートテスト
├── test_tools_only.py               # ツールのみテスト
└── README.md                        # テストドキュメント

build_layer.py            # Lambda Layer構築スクリプト（uv対応）
deploy.sh                 # デプロイスクリプト v2.1.0（uv完全対応、カラー出力）
pyproject.toml           # Pythonプロジェクト設定（uv用、依存関係一元管理）
```

## Lambda関数の詳細

### Lambda関数のアーキテクチャ

- **Runtime**: Python 3.11
- **Architecture**: ARM64 (AWS Graviton2)
- **メモリ**: 1024MB（デフォルト、カスタマイズ可能）
- **タイムアウト**: 10分（デフォルト、カスタマイズ可能）

### 環境変数

#### 基本設定
- `ASSISTANT_SYSTEM_PROMPT`: システムプロンプトのカスタマイズ
- `DEFAULT_TIMEOUT`: HTTPリクエストタイムアウト（デフォルト: 30秒）
- `MAX_PROMPT_LENGTH`: プロンプト最大文字数（デフォルト: 10000）
- `DEFAULT_MODEL_ID`: 使用するBedrockモデルID（デフォルト: Nova Pro us.amazon.nova-pro-v1:0）
- `PYTHONPATH`: `/opt/python`（Lambda Layer用）
- `AWS_REGION`: リージョン設定
- `DISCORD_APPLICATION_ID`: DiscordアプリケーションID（必須）
- `DISCORD_BOT_TOKEN`: Discord Botトークン（必須）
- `LAMBDA_MEMORY`: Lambda関数のメモリサイズ（MB、デフォルト: 1024）
- `LAMBDA_TIMEOUT`: Lambda関数のタイムアウト（分、デフォルト: 2）

#### Discord出力設定
- `ENABLE_DISCORD_STREAMING`: リアルタイムDiscord出力の有効/無効（デフォルト: true）
- `DISCORD_STREAM_MIN_LINES`: 最小送信行数（デフォルト: 1）
- `DISCORD_STREAM_MAX_BUFFER`: 最大バッファサイズ（デフォルト: 1500文字）

> **重要**: Discord出力設定を変更した場合は、`./deploy.sh`で再デプロイが必要です。
> CDKスタックが環境変数をLambda関数に渡すよう更新されました。

#### .envファイルでの設定例

```bash
# 2行ごとに送信
DISCORD_STREAM_MIN_LINES=2

# バッファサイズを3000文字に拡大
DISCORD_STREAM_MAX_BUFFER=3000

# リアルタイム出力を無効化
ENABLE_DISCORD_STREAMING=false
```

### エラーレスポンス

すべてのエラーレスポンスは`ensure_ascii=False`で日本語を正しく表示。

### バリデーション

- プロンプトの存在確認
- プロンプト長の制限（MAX_PROMPT_LENGTH）
- 危険なプロンプトのフィルタリング（XSS対策）

### リアルタイムDiscord出力

- **DiscordStreamWriter**: カスタムストリームクラスによるリアルタイム出力
- **改行ベースの送信**: 標準出力を行単位でバッファリング
- **非同期処理**: バックグラウンドスレッドで送信処理
- **自動切り詰め**: Discord APIの2000文字制限を考慮（1900文字で切り詰め）
- **環境変数制御**: ENABLE_DISCORD_STREAMINGで有効/無効を切り替え
- **柔軟な設定**: .envファイルで送信タイミングを簡単にカスタマイズ可能

## 使用ツール

strands-agents-toolsパッケージから以下のツールを使用：

### http_request

- 包括的な認証サポート（Bearer、Basic、JWT、AWS SigV4など）
- セッション管理、メトリクス、ストリーミングサポート
- Cookieハンドリング、リダイレクト制御

### calculator

- SymPyを使用した高度な数学演算
- 式評価、方程式の解、微分・積分、極限、級数展開
- 行列演算サポート

### current_time

- ISO 8601形式で現在時刻を取得
- タイムゾーンサポート（UTC、US/Pacific、Asia/Tokyoなど）
- DEFAULT_TIMEZONE環境変数でデフォルトタイムゾーン設定可能

### use_aws

- AWSサービスとの統合機能
- S3: バケット一覧、オブジェクトの取得/作成/削除
- DynamoDB: テーブル一覧、アイテムの取得/作成
- Systems Manager: パラメータの取得/設定
- CloudWatch: メトリクスの送信
- Lambda: 関数一覧（list_functions）、関数の詳細情報取得
- EC2: インスタンス一覧（describe_instances）、インスタンスの状態確認

### カスタムツール（custom_tools.py）

- **generate_hash**: ハッシュ値生成（MD5, SHA1, SHA256, SHA512）
- **json_formatter**: JSON整形（インデント、ソート、日本語対応）
- **text_analyzer**: テキスト分析（文字数、単語数、文字種別統計）

## CDKスタックの設定

### カスタマイズ可能な項目

- `lambda_memory`: メモリサイズ（MB）
- `lambda_timeout`: タイムアウト（分）
- `reserved_concurrent`: 予約同時実行数
- `ENABLE_CUSTOM_TOOLS`: カスタムツール全体の有効/無効
- `ENABLE_HASH_GENERATOR`: ハッシュ生成ツールの有効/無効
- `ENABLE_JSON_FORMATTER`: JSON整形ツールの有効/無効
- `ENABLE_TEXT_ANALYZER`: テキスト分析ツールの有効/無効

### SNSトリガー設定

- **SNS Topicサブスクリプション**: Lambda関数をSNS Topicにサブスクライブ
- **Discordからのメッセージ**: SNS Topic経由でLambdaをトリガー
- **Discord APIレスポンス**: Lambdaから直接Discord APIへ応答
- **ログレベル**: INFO

## 開発時の注意点

1. **AWS CLI v2.13.0以上必須**: Bedrockサポートのため
2. **uvパッケージマネージャー必須**: 高速な依存関係管理とPEP 668対応
3. **Bedrock権限**: デプロイ先リージョンでBedrockモデルへのアクセス権限が必要
4. **Lambda Layerサイズ**: 250MB制限に注意
5. **日本語処理**: `ensure_ascii=False`を使用してJSONレスポンスで日本語を正しく表示
6. **strands-agents-tools使用**: 公式ツールパッケージを使用して信頼性の高いツール機能を提供
7. **stdoutキャプチャ**: Strands Agentsが出力する内容を全てキャプチャして完全な応答を取得
8. **モジュール化**: config.pyとutils.pyによる設定とユーティリティの分離
9. **テストの整理**: 統合テストスイートによる効率的なテスト
10. **環境変数によるツール制御**: 各ツールの有効/無効を環境変数で制御可能
11. **Discord統合**: Discord Bot TokenとApplication IDによる認証
12. **CDKコンテキスト型変換**: 文字列で渡されるコンテキスト値を適切に型変換

## よくあるエラーと対処法

### AccessDeniedException (Bedrock)

- リージョンでBedrockが有効か確認
- IAMロールの権限を確認

### Lambda Layerビルドエラー

- ARM64の場合: `aarch64-unknown-linux-gnu`プラットフォーム指定を確認
- x86_64の場合: `x86_64-manylinux2014`プラットフォーム指定を確認
- 依存関係のサイズを確認

### タイムアウトエラー

- Lambda関数のタイムアウトを増やす
- HTTPリクエストのタイムアウトを調整

### CDKデプロイエラー

- CDKコンテキスト値の型エラー: スタック内で`int()`を使用して変換
- .envファイルが存在しない: .env.exampleをコピーして作成
- Discord認証情報の欠落: DISCORD_APPLICATION_IDとDISCORD_BOT_TOKENを設定
- externally-managed-environmentエラー: uvを使用して解決（deploy.shは自動対応）

## ツール設定の環境変数

```bash
# カスタムツール全体の有効/無効
export ENABLE_CUSTOM_TOOLS=true

# 個別ツールの制御
export ENABLE_HASH_GENERATOR=true
export ENABLE_JSON_FORMATTER=true
export ENABLE_TEXT_ANALYZER=true

# AWSツール
export ENABLE_AWS_TOOLS=true       # use_aws（strands-agents-toolsに含まれる）
```

## コード品質の維持

- すべてのコメントは日本語で記述
- 型ヒントを積極的に使用
- エラーハンドリングを適切に実装
- 環境変数でカスタマイズ可能にする

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.

## リファクタリングの成果

1. **テストファイルの整理**: pytestベースの統合テストスイート
2. **設定管理の一元化**: config.pyによる型安全な設定
3. **エラー処理の統一**: utils.pyにユーティリティを集約
4. **パフォーマンス最適化**: 遅延インポート、実行時間測定
5. **デプロイスクリプトの改善**: v2.1.0でuv完全対応、カラー出力、環境別デプロイ
6. **依存関係の整理**: pyproject.tomlでのuv一元管理（requirements.txt削除）
7. **ツールの動的制御**: 環境変数で各ツールの有効/無効を制御可能
8. **use_awsツールの有効化**: strands-agents-toolsのuse_awsを使用してAWSサービスと連携（Lambda/EC2サポート追加）
9. **SNS/Discord統合**: SNS Topicからメッセージを受信しDiscord APIへ応答する仕様に変更
10. **.env対応**: deploy.shが.envファイルから設定を読み込むように改善
11. **CDKコンテキスト型変換**: 文字列で渡される値を適切に整数に変換
12. **テストスイートの整理**: ユニットテストと統合テストの分離
13. **Lambda関数のリファクタリング**: 関数分割による責任の明確化、型ヒントの追加
14. **リアルタイムDiscord出力**: DiscordStreamWriterによる改行ベースのストリーミング実装
15. **重複出力の修正**: 最終応答のみを使用するよう修正
16. **Bedrock権限の拡張**: ListFoundationModelsを含む多数のList権限を追加
17. **エラーハンドリングの改善**: temperatureパラメータエラーの修正、詳細なログ出力
18. **.env設定の拡充**: Discord出力設定を.env.exampleに追加、簡単なカスタマイズを実現
19. **uv完全対応**: deploy.shでuvを使用してPEP 668問題を解決
20. **CDKスタック更新**: Discord出力設定の環境変数をLambdaに渡すよう修正
21. **デバッグログ拡充**: Discord出力設定の値をログ出力で確認可能

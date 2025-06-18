# Strands Agent Discord Worker

これは Discord の Slash Commands に対して応答する Lambda関数のサンプル実装です。
SNS Topic経由で受け取った Discordからのメッセージをもとに AWS Strands Agents SDKを使用してAIエージェント機能を提供します。

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/r3-yamauchi/strands-agent-discord-worker)


## 🚀 特徴

- **サーバーレスアーキテクチャ**: AWS LambdaとSNS Topicによる完全サーバーレス構成
- **AIエージェント機能**: Strands Agents SDK を使用したAI対話機能（デフォルトでNova Pro）
- **リアルタイムDiscord出力**: AIの思考過程をリアルタイムでDiscordに送信
- **公式ツール統合**: strands-agents-toolsパッケージによる信頼性の高いツール機能
- **カスタムツール拡張**: ハッシュ生成、JSON整形、テキスト分析などの独自ツール実装
- **AWS CDK v2対応**: Python 3.11による簡潔なインフラ定義
- **ARM64アーキテクチャ**: AWS Graviton2によるコスト効率とパフォーマンスの向上
- **uv対応**: 高速なPythonパッケージマネージャーによる効率的な依存関係管理

## 🎯 リアルタイムDiscord出力機能

AIの処理過程をリアルタイムでDiscordに表示する機能を搭載：

- **改行ベースの送信**: 標準出力を行単位でバッファリングし、改行時に送信
- **柔軟な設定**: 最小送信行数と最大バッファサイズで制御可能
- **非同期処理**: バックグラウンドスレッドで送信処理を実行
- **文字数制限対応**: Discord APIの2000文字制限を自動的に処理

### 環境変数での制御

```bash
# リアルタイム出力を有効化（デフォルト: true）
export ENABLE_DISCORD_STREAMING=true

# 最小送信行数（デフォルト: 1行）
export DISCORD_STREAM_MIN_LINES=1

# 最大バッファサイズ（デフォルト: 1500文字）
export DISCORD_STREAM_MAX_BUFFER=1500
```

### 送信タイミングのカスタマイズ例

```bash
# 2行ごとに送信（.envファイルで設定）
DISCORD_STREAM_MIN_LINES=2

# 3行ごとに送信
DISCORD_STREAM_MIN_LINES=3

# バッファサイズを増やす（より長いメッセージをまとめて送信）
DISCORD_STREAM_MAX_BUFFER=2000
```

## 📦 含まれるツール

### 公式ツール (strands-agents-tools パッケージ)

1. **http_request**: 外部APIへのHTTPリクエスト実行
   - 包括的な認証サポート（Bearer、Basic、JWT、AWS SigV4など）
   - セッション管理、メトリクス、ストリーミングサポート

2. **calculator**: SymPyを使用した高度な数学演算
   - 式評価、方程式の解、微分・積分、極限、級数展開
   - 行列演算サポート

3. **current_time**: タイムゾーン対応の現在時刻取得
   - ISO 8601形式で現在時刻を取得
   - タイムゾーンサポート（UTC、US/Pacific、Asia/Tokyoなど）

4. **use_aws**: AWSサービスとの統合
   - S3、DynamoDB、Systems Manager、CloudWatch
   - Lambda、EC2インスタンスの管理

### カスタムツール (独自実装)

5. **generate_hash**: テキストのハッシュ値生成（MD5、SHA1、SHA256、SHA512）
6. **json_formatter**: JSON文字列の整形（インデント、キーソート、日本語対応）
7. **text_analyzer**: テキストの統計情報分析（文字数、単語数、日本語文字種別）

## 🏗️ アーキテクチャ

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│ Discord Command │────▶│  SNS Topic   │────▶│   Lambda    │
│                 │     │              │     │  Function   │
└─────────────────┘     └──────────────┘     └──────┬──────┘
                                                      │
                        ┌──────────────┐              │
                        │   Bedrock    │◀─────────────┘
                        │     API      │
                        └──────────────┘
```

## 📋 前提条件

- **Python 3.11以上**
- **AWS CLI v2.13.0以上**
- **AWS CDK v2 CLI**
- **uv パッケージマネージャー**（必須）
- **AWS Bedrockへのアクセス権限**
- **Discord Application IDとBot Token**

## 🛠️ セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/r3-yamauchi/strands-agent-discord-worker
cd strands-agent-discord-worker
```

### 2. 依存関係のインストール

```bash
# uvがインストールされていない場合
curl -LsSf https://astral.sh/uv/install.sh | sh

# 依存関係をインストール（自動的に仮想環境も作成されます）
uv sync
```

> **注意**: uvは仮想環境を自動的に管理するため、手動でのアクティベートは不要です。  
> すべてのコマンドは`uv run`を通じて実行されます。

### 3. 環境設定

```bash
# .env.exampleをコピー
cp .env.example .env

# .envファイルを編集して設定値を入力
# 必須項目:
# - AWS_PROFILE
# - AWS_REGION
# - DISCORD_APPLICATION_ID
# - DISCORD_BOT_TOKEN

# Discord出力設定（オプション）:
# - DISCORD_STREAM_MIN_LINES（デフォルト: 1）
# - DISCORD_STREAM_MAX_BUFFER（デフォルト: 1500）
```

## 🚀 デプロイ

```bash
# .envファイルの設定でデプロイ（uvが自動的に仮想環境を管理）
./deploy.sh

# オプション
./deploy.sh --dry-run        # ドライラン
./deploy.sh --force          # 確認なしでデプロイ
```

### デプロイプロセス

1. uvによる仮想環境の自動セットアップ
2. 依存関係の同期（uv sync）
3. .envファイルの読み込みと検証
4. Lambda Layer構築（依存関係のパッケージング）
5. CDKスタックのシンセサイズ
6. CloudFormationスタックのデプロイ
7. Lambda関数ARNの表示

## 📡 使用方法

### SNS Topicの設定

```bash
# 1. SNS Topicを作成
aws sns create-topic \
  --name discord-worker-topic \
  --profile <PROFILE> \
  --region <REGION>

# 2. Lambda関数をサブスクライブ
aws sns subscribe \
  --topic-arn arn:aws:sns:<REGION>:<ACCOUNT_ID>:discord-worker-topic \
  --protocol lambda \
  --notification-endpoint <LAMBDA_FUNCTION_ARN> \
  --profile <PROFILE> \
  --region <REGION>
```

### Discord Slash Commandの形式

```json
{
  "token": "Discord interaction token",
  "data": {
    "options": [
      {
        "value": "AIアシスタントへの質問またはタスク"
      }
    ]
  }
}
```

## ⚙️ 環境変数

### 基本設定

| 環境変数 | 説明 | デフォルト値 |
|---------|------|-------------|
| `ASSISTANT_SYSTEM_PROMPT` | システムプロンプト | 内蔵プロンプト |
| `DEFAULT_TIMEOUT` | HTTPタイムアウト（秒） | `30` |
| `MAX_PROMPT_LENGTH` | プロンプトの最大文字数 | `10000` |
| `DEFAULT_MODEL_ID` | BedrockモデルID | `us.amazon.nova-pro-v1:0` |
| `DISCORD_APPLICATION_ID` | Discord Application ID | 必須 |
| `DISCORD_BOT_TOKEN` | Discord Bot Token | 必須 |

### Discord出力設定

| 環境変数 | 説明 | デフォルト値 |
|---------|------|-------------|
| `ENABLE_DISCORD_STREAMING` | リアルタイム出力の有効/無効 | `true` |
| `DISCORD_STREAM_MIN_LINES` | 最小送信行数 | `1` |
| `DISCORD_STREAM_MAX_BUFFER` | 最大バッファサイズ（文字数） | `1500` |

> **注意**: `DISCORD_STREAM_MIN_LINES`を変更した場合は、必ず`./deploy.sh`で再デプロイが必要です。

### ツール制御

| 環境変数 | 説明 | デフォルト値 |
|---------|------|-------------|
| `ENABLE_CUSTOM_TOOLS` | カスタムツール全体 | `true` |
| `ENABLE_AWS_TOOLS` | AWSツール（use_aws） | `true` |
| `ENABLE_HASH_GENERATOR` | ハッシュ生成ツール | `true` |
| `ENABLE_JSON_FORMATTER` | JSON整形ツール | `true` |
| `ENABLE_TEXT_ANALYZER` | テキスト分析ツール | `true` |

## 🏗️ CDKスタック構成

### Lambda関数
- Runtime: Python 3.11
- Architecture: ARM64 (AWS Graviton2)
- Memory: 1024MB（カスタマイズ可能）
- Timeout: 10分（最大15分）

### IAM権限
- Bedrock: モデル呼び出し、基盤モデル一覧取得
- SNS: トピックサブスクリプション管理
- S3, DynamoDB, Systems Manager: use_awsツール用
- Lambda, EC2: リソース管理用

### Lambda Layer
- strands-agents SDK v0.1.7以上
- strands-agents-tools v0.1.5以上
- その他の依存関係

## 🧪 テスト

### 統合テストの実行

```bash
# 全テストの実行
pytest tests/ -v

# 個別テストの実行
pytest tests/test_strands_tools.py -v      # 公式ツール
pytest tests/test_custom_tools.py -v        # カスタムツール
pytest tests/test_lambda.py -v              # Lambda関数
```

### ローカルでのLambdaハンドラーテスト

```bash
# Lambda関数を直接実行（uvを使用）
uv run python lambda/lambda_function.py
```

## 📁 プロジェクト構成

```
.
├── lambda/                    # Lambda関数コード
│   ├── lambda_function.py     # メインハンドラー（リファクタリング済み）
│   ├── custom_tools.py        # カスタムツール実装
│   ├── config.py              # 設定管理（環境変数、型定義）
│   └── utils.py               # ユーティリティ（Discord出力クラス含む）
├── stacks/                    # CDKスタック定義
│   └── strands_agent_discord_worker_stack.py
├── tests/                     # テストスイート
├── app.py                     # CDKアプリケーション
├── deploy.sh                  # デプロイスクリプト v2.1.0（uv完全対応）
├── build_layer.py             # Lambda Layer構築
├── pyproject.toml             # Python設定（uv用）
├── .env.example               # 環境変数テンプレート
└── CLAUDE.md                  # Claude Code用ガイド
```

## 🔧 トラブルシューティング

### Lambda関数のエラー

1. **Agent初期化エラー**
   - 原因: temperatureパラメータの誤った渡し方
   - 解決: BedrockModelインスタンスを作成してAgentに渡す

2. **重複出力の問題**
   - 原因: stdoutキャプチャと最終応答の重複
   - 解決: 最終応答のみを使用するよう修正

3. **Discord API制限**
   - 原因: 2000文字を超えるメッセージ
   - 解決: 自動的に1900文字で切り詰め

### デプロイエラー

1. **CDKブートストラップ**
   ```bash
   cdk bootstrap aws://ACCOUNT_ID/REGION --profile YOUR_PROFILE
   ```

2. **Lambda Layerサイズ**
   - 250MB制限に注意
   - 不要な依存関係を削除

3. **IAM権限不足**
   - Bedrock権限の確認
   - SNSサブスクリプション権限の確認

## 🎨 カスタマイズ

### リアルタイム出力の調整

```bash
# .envファイルで設定
# 複数行をまとめて送信
DISCORD_STREAM_MIN_LINES=3

# バッファサイズを増やす
DISCORD_STREAM_MAX_BUFFER=2000

# リアルタイム出力を無効化
ENABLE_DISCORD_STREAMING=false

# または環境変数で直接設定
export DISCORD_STREAM_MIN_LINES=2
export DISCORD_STREAM_MAX_BUFFER=3000
```

### システムプロンプトのカスタマイズ

```bash
export ASSISTANT_SYSTEM_PROMPT="あなたは親切なAIアシスタントです。"
```

### Lambda設定の変更

```bash
# メモリサイズ（MB）
./deploy.sh --memory 2048

# タイムアウト（分）
./deploy.sh --timeout 15
```

## 📈 パフォーマンス最適化

1. **ARM64アーキテクチャ**: 最大20%のコスト削減
2. **遅延インポート**: コールドスタート時間の短縮
3. **非同期Discord送信**: メインスレッドをブロックしない
4. **行単位バッファリング**: 効率的なメッセージ送信

## 🔐 セキュリティ

- 最小権限の原則に基づくIAM設定
- 環境変数の暗号化推奨
- プロンプトのバリデーション実装
- エラーメッセージのサニタイゼーション

## 📚 参考リンク

- [AWS Strands Agents SDK](https://strandsagents.com/latest/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Discord Developer Portal](https://discord.com/developers/docs)
- [AWS CDK v2 Documentation](https://docs.aws.amazon.com/cdk/v2/guide/)

## 📝 ライセンス

このプロジェクトはMITライセンスの下で公開しています。

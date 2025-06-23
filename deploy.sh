#!/bin/bash
set -e

echo "Strands Agent Discord Worker AWS Lambda CDK Deploy"
echo "====================================="
echo ""

# バージョン
VERSION="2.0.0"

# 仮想環境の自動セットアップ
if [ ! -d ".venv" ]; then
    echo "→ 仮想環境が見つかりません。uvで作成します..."
    if command -v uv &> /dev/null; then
        uv venv
    else
        echo "✗ uvが見つかりません。以下のコマンドでインストールしてください:"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi

# 依存関係の同期
echo "→ 依存関係を同期中..."
if command -v uv &> /dev/null; then
    uv sync
else
    echo "✗ uvが見つかりません。以下のコマンドでインストールしてください:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# uvが存在することを再確認
if ! command -v uv &> /dev/null; then
    echo "✗ uvが見つかりません。以下のコマンドでインストールしてください:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# .envファイルの読み込み
if [ -f .env ]; then
    echo "→ .envファイルを読み込んでいます..."
    set -a
    source .env
    set +a
else
    echo "⚠ .envファイルが見つかりません。"
    echo "  .env.exampleをコピーして.envファイルを作成してください:"
    echo "  cp .env.example .env"
    exit 1
fi

# 環境変数からデフォルト値を設定
AWS_PROFILE="${AWS_PROFILE}"
AWS_REGION="${AWS_REGION}"
LAMBDA_MEMORY="${LAMBDA_MEMORY:-1024}"
LAMBDA_TIMEOUT="${LAMBDA_TIMEOUT:-2}"
FUNCTION_NAME="${FUNCTION_NAME:-strands-agent-discord-worker}"
MODEL_ID="${MODEL_ID:-us.amazon.nova-pro-v1:0}"

# オプション
STACK_TYPE="${STACK_TYPE:-standard}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
DRY_RUN="${DRY_RUN:-false}"
FORCE_DEPLOY="${FORCE_DEPLOY:-false}"

# Discord設定
DISCORD_APPLICATION_ID="${DISCORD_APPLICATION_ID}"
DISCORD_BOT_TOKEN="${DISCORD_BOT_TOKEN}"

# Discord出力設定
ENABLE_DISCORD_STREAMING="${ENABLE_DISCORD_STREAMING:-true}"
DISCORD_STREAM_MIN_LINES="${DISCORD_STREAM_MIN_LINES:-2}"
DISCORD_STREAM_MAX_BUFFER="${DISCORD_STREAM_MAX_BUFFER:-3000}"

# カラーコード
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ヘルパー関数
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# 必須項目のチェック
if [ -z "$AWS_PROFILE" ]; then
    print_error "AWS_PROFILEが設定されていません。.envファイルを確認してください"
    exit 1
fi

if [ -z "$AWS_REGION" ]; then
    print_error "AWS_REGIONが設定されていません。.envファイルを確認してください"
    exit 1
fi

if [ -z "$DISCORD_APPLICATION_ID" ]; then
    print_error "DISCORD_APPLICATION_IDが設定されていません。.envファイルを確認してください"
    exit 1
fi

if [ -z "$DISCORD_BOT_TOKEN" ]; then
    print_error "DISCORD_BOT_TOKENが設定されていません。.envファイルを確認してください"
    exit 1
fi

# 設定内容を表示
echo "デプロイ設定:"
echo "-------------------------------------"
echo "プロファイル: $AWS_PROFILE"
echo "リージョン: $AWS_REGION"
echo "スタックタイプ: $STACK_TYPE"
echo "環境: $ENVIRONMENT"
echo "メモリ: ${LAMBDA_MEMORY}MB"
echo "タイムアウト: ${LAMBDA_TIMEOUT}分"
echo "関数名: $FUNCTION_NAME"
echo "モデルID: $MODEL_ID"
echo "Discord App ID: ${DISCORD_APPLICATION_ID:0:10}..."
echo "Discord Bot Token: ****"
echo ""
echo "Discord出力設定:"
echo "  ストリーミング: $ENABLE_DISCORD_STREAMING"
echo "  最小送信行数: ${DISCORD_STREAM_MIN_LINES}行"
echo "  最大バッファ: ${DISCORD_STREAM_MAX_BUFFER}文字"
echo "-------------------------------------"

# AWS認証情報の検証
export AWS_PROFILE=$AWS_PROFILE
export AWS_REGION=$AWS_REGION
export CDK_DEFAULT_REGION=$AWS_REGION

# AWSアカウントIDを取得
print_info "AWS認証情報を検証中..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile $AWS_PROFILE 2>/dev/null)
if [ -z "$AWS_ACCOUNT_ID" ]; then
    print_error "AWSアカウントIDの取得に失敗しました。AWSプロファイルと認証情報を確認してください"
    exit 1
fi
export CDK_DEFAULT_ACCOUNT=$AWS_ACCOUNT_ID

print_success "AWS Account ID: $AWS_ACCOUNT_ID"

# Bedrockアクセス確認
print_info "Bedrockアクセスを確認中..."
# set -eを一時的に無効化してBedrockチェックを実行
set +e

# まず、bedrockコマンドが利用可能かチェック
aws bedrock help >/dev/null 2>&1
if [ $? -ne 0 ]; then
    print_warning "AWS CLIにbedrockコマンドが見つかりません"
    echo "  → AWS CLIが古い可能性があります。バージョン2.13.0以上が必要です"
    echo "    現在のAWS CLIバージョン: $(aws --version 2>/dev/null || echo "バージョン取得失敗")"
    echo ""
    echo "  AWS CLIを更新するには:"
    echo "    brew upgrade awscli  # macOSの場合"
    echo "    pip install --upgrade awscli  # pipの場合"
    echo ""
    echo "  注意: この警告はデプロイを妨げませんが、Lambda関数の実行時にBedrockアクセスが必要です"
else
    # bedrockコマンドが存在する場合、list-foundation-modelsを実行
    BEDROCK_ERROR=$(aws bedrock list-foundation-models --region $AWS_REGION --profile $AWS_PROFILE 2>&1 | head -10)
    BEDROCK_EXIT_CODE=$?
    
    if [ $BEDROCK_EXIT_CODE -eq 0 ]; then
        print_success "Bedrockへのアクセスを確認"
    else
        print_warning "Bedrockアクセスの確認に失敗しました"
        # エラーの詳細を表示
        if [[ "$BEDROCK_ERROR" == *"UnrecognizedClientException"* ]]; then
            echo "  → Bedrockがこのリージョンで有効化されていない可能性があります"
        elif [[ "$BEDROCK_ERROR" == *"AccessDeniedException"* ]]; then
            echo "  → IAM権限が不足しています。bedrock:ListFoundationModels権限が必要です"
        else
            echo "  → エラー: ${BEDROCK_ERROR}"
        fi
        echo ""
        echo "  注意: この警告はデプロイを妨げませんが、Lambda関数の実行時にBedrockアクセスが必要です"
    fi
fi

set -e

# CDK依存関係の確認（uvを使用）
echo ""
print_info "CDK依存関係を確認中..."
if ! uv pip show aws-cdk-lib > /dev/null 2>&1; then
    print_info "aws-cdk-libをインストール中..."
    uv pip install aws-cdk-lib constructs
fi

# CDK CLIの確認
if ! command -v cdk &> /dev/null; then
    print_warning "CDK CLIが見つかりません"
    echo "  CDK CLIをインストールするには以下のコマンドを実行してください:"
    echo "    npm install -g aws-cdk"
    echo ""
    echo "  または、npxを使用してCDKを実行することもできます。"
    echo "  この場合、スクリプトはnpxを使用して続行します。"
    
    # npxを使用してCDKを実行
    CDK_CMD="npx aws-cdk"
else
    CDK_CMD="cdk"
fi

print_info "CDKコマンド: $CDK_CMD"

# Lambda Layerの構築
echo ""
print_info "Lambda Layerを構築中..."
if uv run python build_layer.py; then
    print_success "Lambda Layerの構築が完了しました"
else
    print_error "Lambda Layerの構築に失敗しました"
    exit 1
fi

# CDK Bootstrapの確認
echo ""
print_info "CDKブートストラップを確認中..."
if $CDK_CMD bootstrap aws://$AWS_ACCOUNT_ID/$AWS_REGION --profile $AWS_PROFILE 2>/dev/null; then
    print_success "CDKブートストラップ完了"
else
    print_info "CDKは既にブートストラップ済みです"
fi

# CDKシンセサイズ
echo ""
print_info "CDKシンセサイズ中..."

# スタックタイプに応じたアプリファイルを選択
if [ "$STACK_TYPE" = "migration" ]; then
    export CDK_STACK_TYPE="migration"
    APP_PY="app_migration.py"
elif [ "$STACK_TYPE" = "secure" ]; then
    export CDK_STACK_TYPE="secure"
    APP_PY="app_migration.py"
else
    APP_PY="app.py"
fi

# CDKコンテキストパラメータの構築
CDK_CONTEXT=""
CDK_CONTEXT="$CDK_CONTEXT -c lambda_memory=$LAMBDA_MEMORY"
CDK_CONTEXT="$CDK_CONTEXT -c lambda_timeout=$LAMBDA_TIMEOUT"
CDK_CONTEXT="$CDK_CONTEXT -c lambda_function_name=$FUNCTION_NAME"
CDK_CONTEXT="$CDK_CONTEXT -c default_model_id=$MODEL_ID"

# 環境変数をエクスポート（CDKスタックで使用）
export DISCORD_APPLICATION_ID
export DISCORD_BOT_TOKEN
export ENABLE_DISCORD_STREAMING
export DISCORD_STREAM_MIN_LINES
export DISCORD_STREAM_MAX_BUFFER

# スタック名の設定
STACK_NAME="StrandsAgentDiscordWorkerStack"
if [ "$ENVIRONMENT" != "dev" ]; then
    STACK_NAME="StrandsAgentDiscordWorkerStack-${ENVIRONMENT}"
fi

if [ -f "$APP_PY" ]; then
    $CDK_CMD synth $CDK_CONTEXT --app "uv run python $APP_PY" --profile $AWS_PROFILE
else
    $CDK_CMD synth $CDK_CONTEXT --profile $AWS_PROFILE
fi

if [ $? -eq 0 ]; then
    print_success "CDKシンセサイズが完了しました"
else
    print_error "CDKシンセサイズに失敗しました"
    exit 1
fi

# ドライランモード
if [ "$DRY_RUN" = true ]; then
    echo ""
    print_warning "ドライランモード: 実際のデプロイは行われません"
    exit 0
fi

# デプロイ確認
if [ "$FORCE_DEPLOY" != true ]; then
    echo ""
    print_warning "デプロイを開始します"
    read -p "続行するにはENTERを押すか、キャンセルするにはCtrl+Cを押してください: "
fi

# デプロイ実行
echo ""
print_info "スタックをデプロイ中..."

if [ -f "$APP_PY" ]; then
    $CDK_CMD deploy $CDK_CONTEXT --app "uv run python $APP_PY" --profile $AWS_PROFILE --require-approval never
else
    $CDK_CMD deploy $CDK_CONTEXT --profile $AWS_PROFILE --require-approval never
fi

if [ $? -eq 0 ]; then
    echo ""
    print_success "デプロイが正常に完了しました！"
    echo ""
    echo "Lambda関数ARNはCloudFormationの出力を確認してください。"
    echo "このARNを使用してSNS Topicにサブスクライブしてください:"
    echo ""
    echo "例:"
    echo '  aws sns subscribe \'
    echo '    --topic-arn arn:aws:sns:<REGION>:<ACCOUNT_ID>:<TOPIC_NAME> \'
    echo '    --protocol lambda \'
    echo '    --notification-endpoint <LAMBDA_FUNCTION_ARN> \'
    echo '    --profile <PROFILE> --region <REGION>'
else
    print_error "デプロイに失敗しました"
    exit 1
fi
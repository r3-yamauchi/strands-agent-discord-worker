"""
AWS Lambda関数エントリーポイント
Strands Agentを使用してAIアシスタント機能を提供
"""
import json
import logging
import traceback
from typing import Dict, Any, Optional, List, Tuple

import requests

# ローカルインポート
from config import config
from utils import capture_stdout, capture_stdout_with_discord, validate_prompt, get_model_info, sanitize_error_message
from custom_tools import generate_hash, json_formatter, text_analyzer

# ロガーの設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# グローバル定数
DISCORD_APPLICATION_ID = config.DISCORD_APPLICATION_ID
DISCORD_BOT_TOKEN = config.DISCORD_BOT_TOKEN

# 遅延インポート用のグローバル変数
_LAZY_IMPORTS = {
    'Agent': None,
    'BedrockModel': None,
    'http_request': None,
    'calculator': None,
    'current_time': None,
    'use_aws': None
}


def _lazy_imports() -> None:
    """必要になったときにのみモジュールをインポート"""
    if _LAZY_IMPORTS['Agent'] is None:
        from strands import Agent
        from strands.models import BedrockModel
        _LAZY_IMPORTS['Agent'] = Agent
        _LAZY_IMPORTS['BedrockModel'] = BedrockModel
    
    if _LAZY_IMPORTS['http_request'] is None:
        from strands_tools import http_request, calculator, current_time, use_aws
        _LAZY_IMPORTS['http_request'] = http_request
        _LAZY_IMPORTS['calculator'] = calculator
        _LAZY_IMPORTS['current_time'] = current_time
        _LAZY_IMPORTS['use_aws'] = use_aws


def _send_discord_response(token: str, content: str) -> Dict[str, Any]:
    """Discord APIにレスポンスを送信
    
    Args:
        token: Discord interactionトークン
        content: 送信するコンテンツ
        
    Returns:
        Discord APIレスポンス
    """
    url = f"https://discord.com/api/v10/webhooks/{DISCORD_APPLICATION_ID}/{token}"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json",
    }
    data = json.dumps({"content": content})
    
    response = requests.post(url=url, data=data, headers=headers)
    
    # レスポンスのログ出力
    logger.info(f"Discord API status code: {response.status_code}")
    if response.status_code != 204:
        logger.info(f"Discord API response: {response.text}")
    
    return {
        "statusCode": response.status_code,
        "body": response.text if response.text else ""
    }


def _parse_sns_message(event: Dict[str, Any]) -> Tuple[str, str]:
    """SNSメッセージからトークンとプロンプトを抽出
    
    Args:
        event: Lambda event
        
    Returns:
        (token, prompt)のタプル
        
    Raises:
        ValueError: メッセージの解析に失敗した場合
        KeyError: 必要なキーが存在しない場合
    """
    message = event["Records"][0]["Sns"]["Message"]
    request = json.loads(message)
    
    token = request.get('token')
    if not token:
        raise ValueError("トークンが見つかりません")
    
    # Application Commandsのオプション値に格納されている質問を取得
    data = request.get("data", {})
    options = data.get("options", [])
    
    if not options:
        raise ValueError("オプションが提供されていません")
    
    prompt = options[0].get("value")
    if not prompt:
        raise ValueError("プロンプトが見つかりません")
    
    return token, prompt


def _create_model(model_config: Dict[str, Any]) -> Any:
    """BedrockModelインスタンスを作成
    
    Args:
        model_config: モデル設定
        
    Returns:
        BedrockModelインスタンス
    """
    BedrockModel = _LAZY_IMPORTS['BedrockModel']
    
    model_id = model_config.get('model_id', config.DEFAULT_MODEL_ID)
    temperature = model_config.get('temperature', 0.7)
    max_tokens = model_config.get('max_tokens', 4096)
    
    # モデル設定のログ出力
    logger.info(f"BedrockModel設定: model_id={model_id}, temperature={temperature}, max_tokens={max_tokens}")
    
    try:
        logger.info("BedrockModelインスタンスを作成中...")
        model = BedrockModel(
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens
        )
        logger.info("BedrockModelインスタンスの作成に成功")
        return model
    except Exception as e:
        logger.error(f"BedrockModelの作成エラー: {type(e).__name__}: {str(e)}")
        logger.error(f"スタックトレース: {traceback.format_exc()}")
        raise


def _build_tools_list() -> List[Any]:
    """利用可能なツールのリストを構築
    
    Returns:
        ツールのリスト
    """
    # 基本ツール（strands-agents-tools）
    tools = [
        _LAZY_IMPORTS['http_request'],
        _LAZY_IMPORTS['calculator'],
        _LAZY_IMPORTS['current_time'],
    ]
    
    # カスタムツールを設定に基づいて追加
    if config.ENABLE_CUSTOM_TOOLS:
        custom_tools = []
        
        if config.ENABLE_HASH_GENERATOR:
            custom_tools.append(generate_hash)
        if config.ENABLE_JSON_FORMATTER:
            custom_tools.append(json_formatter)
        if config.ENABLE_TEXT_ANALYZER:
            custom_tools.append(text_analyzer)
        
        tools.extend(custom_tools)
        logger.info(f"有効なカスタムツール: {[t.__name__ for t in custom_tools]}")
    
    # AWSツール（strands-agents-toolsに含まれる）
    if config.ENABLE_AWS_TOOLS:
        tools.append(_LAZY_IMPORTS['use_aws'])
        logger.info("AWSツール(use_aws)を有効化")
    
    return tools


def _create_agent(model: Any, tools: List[Any]) -> Any:
    """Agentインスタンスを作成
    
    Args:
        model: BedrockModelインスタンス
        tools: 利用可能なツールのリスト
        
    Returns:
        Agentインスタンス
    """
    Agent = _LAZY_IMPORTS['Agent']
    
    try:
        logger.info("Agentインスタンスを作成中...")
        logger.info(f"使用ツール数: {len(tools)}")
        agent = Agent(
            model=model,
            system_prompt=config.ASSISTANT_SYSTEM_PROMPT,
            tools=tools
        )
        logger.info("Agentインスタンスの作成に成功")
        return agent
    except Exception as e:
        logger.error(f"Agentの作成エラー: {type(e).__name__}: {str(e)}")
        logger.error(f"スタックトレース: {traceback.format_exc()}")
        raise


def _process_prompt(agent: Any, prompt: str, token: str, enable_streaming: bool = True) -> str:
    """プロンプトを処理して応答を生成
    
    Args:
        agent: Agentインスタンス
        prompt: 処理するプロンプト
        token: Discord interactionトークン
        enable_streaming: リアルタイムDiscord出力を有効にするか
        
    Returns:
        完全な応答文字列
    """
    logger.info(f"プロンプトを処理中: {prompt[:100]}...")  # 最初の100文字をログ出力
    
    if enable_streaming:
        # リアルタイムでDiscordに出力を送信
        logger.info("リアルタイムDiscord出力を有効化")
        logger.info(f"Discord出力設定 - min_lines: {config.DISCORD_STREAM_MIN_LINES}, max_buffer: {config.DISCORD_STREAM_MAX_BUFFER}")
        with capture_stdout_with_discord(
            token, DISCORD_APPLICATION_ID, DISCORD_BOT_TOKEN,
            min_lines=config.DISCORD_STREAM_MIN_LINES,
            max_buffer_size=config.DISCORD_STREAM_MAX_BUFFER
        ) as captured:
            response = agent(prompt)
            # 残りのバッファを送信
            captured.flush_remaining()
            captured_text = captured.get_full_content()
    else:
        # 通常のキャプチャ（デバッグ用）
        with capture_stdout() as captured:
            response = agent(prompt)
            captured_text = captured.getvalue()
    
    # 最終的な応答の構築
    final_response = str(response).strip()
    
    # ログ出力（デバッグ用）
    if captured_text:
        logger.info(f"エージェントの標準出力:\n{captured_text}")
    
    logger.info(f"最終応答: {final_response}")
    logger.info("プロンプト処理完了")
    
    return final_response


def _handle_request_error(token: str, error: Exception) -> Dict[str, Any]:
    """リクエストエラーを処理
    
    Args:
        token: Discord interactionトークン（空の場合もある）
        error: 発生したエラー
        
    Returns:
        エラーレスポンス
    """
    if isinstance(error, json.JSONDecodeError):
        logger.error(f"JSONDecodeError: {str(error)}")
        if token:
            return _send_discord_response(
                token=token,
                content=json.dumps('無効なJSON', ensure_ascii=False)
            )
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': '無効なJSON',
                    'message': f'リクエストボディの解析に失敗しました: {str(error)}'
                }, ensure_ascii=False)
            }
    
    elif isinstance(error, (KeyError, IndexError, TypeError, ValueError)):
        logger.error(f"リクエストの解析エラー: {str(error)}")
        if token:
            return _send_discord_response(
                token=token,
                content=json.dumps('リクエストの形式が不正です', ensure_ascii=False)
            )
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'リクエストの形式が不正です',
                    'message': str(error)
                }, ensure_ascii=False)
            }
    
    else:
        logger.error(f"Error: {type(error).__name__}: {str(error)}")
        logger.error(f"完全なスタックトレース:\n{traceback.format_exc()}")
        error_message = sanitize_error_message(error)
        
        if token:
            return _send_discord_response(
                token=token,
                content=json.dumps('Internal Server Error', ensure_ascii=False)
            )
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal Server Error',
                    'message': error_message,
                    'type': type(error).__name__
                }, ensure_ascii=False)
            }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Strands Agents SDKを使用してリクエストを処理するAWS Lambdaハンドラー関数
    
    Args:
        event: リクエストデータを含むLambdaイベント
        context: Lambdaコンテキストオブジェクト
        
    Returns:
        statusCodeとbodyを含むレスポンス辞書
    """
    # 遅延インポートを実行
    _lazy_imports()
    
    token = ''
    
    try:
        # リクエストペイロードをログ出力
        logger.info(f"受信したイベント: {json.dumps(event, ensure_ascii=False)}")
        
        # SNSメッセージからトークンとプロンプトを抽出
        try:
            token, prompt = _parse_sns_message(event)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as e:
            return _handle_request_error('', e)
        
        # プロンプトのバリデーション
        is_valid, error_msg = validate_prompt(prompt, config.MAX_PROMPT_LENGTH)
        if not is_valid:
            return _send_discord_response(
                token=token,
                content=json.dumps(error_msg, ensure_ascii=False)
            )
        
        # モデル設定
        model_config = {
            "temperature": 0.7,
            "max_tokens": 4096
        }
        
        # BedrockModelインスタンスを作成
        model = _create_model(model_config)
        
        # ツールリストを構築
        tools = _build_tools_list()
        
        # Agentインスタンスを作成
        agent = _create_agent(model, tools)
        
        # 使用されるモデル情報をログに出力
        used_model = get_model_info(agent, model_config, config.DEFAULT_MODEL_ID)
        logger.info(f"使用モデル: {used_model}")
        
        # プロンプトを処理（Discord出力設定に従う）
        complete_response = _process_prompt(
            agent, prompt, token, 
            enable_streaming=config.ENABLE_DISCORD_STREAMING
        )
        
        # 最終応答を送信
        if config.ENABLE_DISCORD_STREAMING:
            # ストリーミングが有効な場合は、最終応答を明示
            return _send_discord_response(
                token=token,
                content=f"**処理完了**\n最終応答: {complete_response}"
            )
        else:
            # ストリーミングが無効な場合は、応答のみを送信
            return _send_discord_response(
                token=token,
                content=complete_response
            )
        
    except Exception as e:
        return _handle_request_error(token, e)


# ローカルテスト用
if __name__ == "__main__":
    # SNS形式のテストイベント
    test_event = {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps({
                        "token": "test-token-123",
                        "data": {
                            "options": [
                                {
                                    "value": "現在の日時を教えてください。また、25 * 4 の計算もお願いします。"
                                }
                            ]
                        }
                    })
                }
            }
        ]
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2, ensure_ascii=False))
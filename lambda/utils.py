"""
ユーティリティ関数とヘルパー
"""
import io
import sys
import logging
import functools
import time
import threading
import queue
import requests
import json
from typing import Any, Callable, Optional, Tuple
from contextlib import contextmanager
from datetime import datetime


logger = logging.getLogger(__name__)


class DiscordStreamWriter(io.StringIO):
    """Discordにリアルタイムで出力を送信するカスタムストリーム"""
    
    def __init__(self, token: str, application_id: str, bot_token: str, 
                 min_lines: int = 1, max_buffer_size: int = 1500):
        super().__init__()
        self.token = token
        self.application_id = application_id
        self.bot_token = bot_token
        self.min_lines = min_lines  # 最小送信行数
        self.max_buffer_size = max_buffer_size  # 最大バッファサイズ（文字数）
        self.line_buffer = []  # 行単位のバッファ
        self.current_line = []  # 現在の行
        self.total_content = []
        self.lock = threading.Lock()
        self.send_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        logger.info(f"DiscordStreamWriter初期化 - min_lines: {self.min_lines}, max_buffer_size: {self.max_buffer_size}")
        
        # 送信スレッドを開始
        self.sender_thread = threading.Thread(target=self._sender_worker, daemon=True)
        self.sender_thread.start()
    
    def write(self, s: str) -> int:
        """文字列を書き込み、改行で区切って送信"""
        if not s:
            return 0
            
        # 元のStringIOに書き込み
        result = super().write(s)
        
        with self.lock:
            self.total_content.append(s)
            
            # 文字列を処理
            for char in s:
                if char == '\n':
                    # 改行が来たら現在の行を完成させる
                    if self.current_line:
                        completed_line = ''.join(self.current_line)
                        self.line_buffer.append(completed_line)
                        self.current_line = []
                    
                    # バッファチェック
                    self._check_and_send_buffer()
                else:
                    # 改行以外は現在の行に追加
                    self.current_line.append(char)
            
            # バッファサイズが大きくなりすぎた場合は強制送信
            current_buffer_size = sum(len(line) for line in self.line_buffer)
            if self.current_line:
                current_buffer_size += len(self.current_line)
            
            if current_buffer_size >= self.max_buffer_size:
                self._force_send_buffer()
        
        return result
    
    def _check_and_send_buffer(self):
        """バッファの行数をチェックして送信"""
        if len(self.line_buffer) >= self.min_lines:
            logger.debug(f"バッファ送信条件を満たしました - 行数: {len(self.line_buffer)} >= {self.min_lines}")
            # 改行で結合して送信
            content = '\n'.join(self.line_buffer)
            if content.strip():  # 空白のみの場合は送信しない
                self.send_queue.put(content)
                logger.debug(f"送信キューに追加: {len(content)}文字")
            self.line_buffer = []
    
    def _force_send_buffer(self):
        """バッファを強制的に送信"""
        # 現在の行も含めて送信
        all_lines = self.line_buffer.copy()
        if self.current_line:
            all_lines.append(''.join(self.current_line))
            self.current_line = []
        
        if all_lines:
            content = '\n'.join(all_lines)
            if content.strip():
                self.send_queue.put(content)
        
        self.line_buffer = []
    
    def _sender_worker(self):
        """バックグラウンドでDiscordに送信するワーカー"""
        while not self.stop_event.is_set():
            try:
                # キューから内容を取得（タイムアウト付き）
                content = self.send_queue.get(timeout=0.1)
                self._send_to_discord(content)
                self.send_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Discord送信エラー: {str(e)}")
    
    def _send_to_discord(self, content: str):
        """Discordに内容を送信"""
        try:
            url = f"https://discord.com/api/v10/webhooks/{self.application_id}/{self.token}"
            headers = {
                "Authorization": f"Bot {self.bot_token}",
                "Content-Type": "application/json",
            }
            
            # Discord APIの文字数制限（2000文字）を考慮
            if len(content) > 1900:
                content = content[:1900] + "..."
            
            data = json.dumps({"content": f"```\n{content}\n```"})
            
            response = requests.post(url=url, data=data, headers=headers, timeout=5)
            
            if response.status_code != 204:
                logger.warning(f"Discord API応答: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Discord送信失敗: {str(e)}")
    
    def flush_remaining(self):
        """残りのバッファを送信"""
        with self.lock:
            # 残っている行をすべて送信
            all_lines = self.line_buffer.copy()
            if self.current_line:
                all_lines.append(''.join(self.current_line))
                self.current_line = []
            
            if all_lines:
                content = '\n'.join(all_lines)
                if content.strip():
                    self.send_queue.put(content)
            
            self.line_buffer = []
        
        # キューが空になるまで待つ
        self.send_queue.join()
    
    def close(self):
        """ストリームを閉じる"""
        self.flush_remaining()
        self.stop_event.set()
        self.sender_thread.join(timeout=2)
        super().close()
    
    def get_full_content(self):
        """キャプチャされた全内容を取得"""
        with self.lock:
            return ''.join(self.total_content)


@contextmanager
def capture_stdout_with_discord(token: str, application_id: str, bot_token: str,
                               min_lines: int = 1, max_buffer_size: int = 1500):
    """標準出力をキャプチャし、同時にDiscordに送信するコンテキストマネージャー"""
    old_stdout = sys.stdout
    discord_writer = DiscordStreamWriter(
        token, application_id, bot_token,
        min_lines=min_lines,
        max_buffer_size=max_buffer_size
    )
    
    try:
        sys.stdout = discord_writer
        yield discord_writer
    finally:
        # 確実に標準出力を元に戻す
        sys.stdout = old_stdout
        try:
            discord_writer.close()
        except Exception as e:
            logger.error(f"DiscordStreamWriter close error: {str(e)}")


@contextmanager
def capture_stdout():
    """標準出力を安全にキャプチャするコンテキストマネージャー"""
    old_stdout = sys.stdout
    captured_output = io.StringIO()
    
    try:
        sys.stdout = captured_output
        yield captured_output
    finally:
        # 確実に標準出力を元に戻す
        sys.stdout = old_stdout


@contextmanager
def capture_all_output():
    """標準出力と標準エラー出力の両方をキャプチャ"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        yield stdout_capture, stderr_capture
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        try:
            stdout_capture.close()
            stderr_capture.close()
        except Exception:
            pass


def retry_on_exception(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """例外発生時にリトライするデコレータ"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay_time = delay
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {delay_time} seconds..."
                        )
                        time.sleep(delay_time)
                        delay_time *= backoff
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}: {str(e)}"
                        )
            
            raise last_exception
        
        return wrapper
    return decorator


def sanitize_error_message(error: Exception, include_type: bool = True) -> str:
    """エラーメッセージをサニタイズして安全に返す"""
    error_msg = str(error)
    
    # センシティブな情報をマスク
    sensitive_patterns = [
        r'arn:aws:[^:]+:[^:]+:[^:]+:[^/\s]+',  # AWS ARN
        r'AKIA[0-9A-Z]{16}',  # AWS Access Key
        r'[0-9a-zA-Z/+=]{40}',  # AWS Secret Key
    ]
    
    import re
    for pattern in sensitive_patterns:
        error_msg = re.sub(pattern, '***REDACTED***', error_msg)
    
    if include_type:
        return f"{type(error).__name__}: {error_msg}"
    return error_msg


def validate_prompt(prompt: str, max_length: int) -> Tuple[bool, Optional[str]]:
    """プロンプトのバリデーション"""
    if not prompt:
        return False, "プロンプトが提供されていません"
    
    if not isinstance(prompt, str):
        return False, "プロンプトは文字列である必要があります"
    
    if len(prompt) > max_length:
        return False, f"プロンプトが長すぎます（最大{max_length}文字）"
    
    # 危険な文字のチェック
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',  # スクリプトタグ
        r'javascript:',  # JavaScriptプロトコル
        r'data:text/html',  # データURI
    ]
    
    import re
    for pattern in dangerous_patterns:
        if re.search(pattern, prompt, re.IGNORECASE):
            return False, "プロンプトに許可されていない内容が含まれています"
    
    return True, None


def get_model_info(agent: Any, model_config: dict, default_model: str) -> str:
    """エージェントから使用モデル情報を安全に取得"""
    try:
        # エージェントのモデル属性を確認
        if hasattr(agent, 'model'):
            model = agent.model
            
            # BedrockModelの場合、model_idを直接取得
            if hasattr(model, 'model_id'):
                return model.model_id
            
            # BedrockModelの場合、configからmodel_idを取得
            if hasattr(model, 'config') and hasattr(model.config, 'get'):
                config = model.config
                if 'model_id' in config:
                    return config['model_id']
            
            # よくある属性名をチェック
            for attr in ['model_id', '_model_id', 'id', '_id']:
                if hasattr(model, attr):
                    value = getattr(model, attr)
                    if value:
                        return str(value)
            
            # 文字列の場合
            if isinstance(model, str):
                return model
        
        # model_configから取得
        if 'model_id' in model_config:
            return model_config['model_id']
        elif 'model' in model_config:
            return model_config['model']
        
        # デフォルトを返す
        return default_model
        
    except Exception as e:
        logger.warning(f"Failed to get model info: {str(e)}")
        return default_model


def measure_execution_time(func: Callable) -> Callable:
    """関数の実行時間を測定するデコレータ"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.2f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.2f} seconds: {str(e)}")
            raise
    
    return wrapper

def format_response(
    success: bool,
    data: Optional[dict] = None,
    error: Optional[str] = None,
    status_code: int = 200
) -> dict:
    """統一されたレスポンス形式を生成"""
    response = {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'X-Response-Time': datetime.now().isoformat(),
        }
    }
    
    body = {'success': success}
    
    if data:
        body.update(data)
    
    if error:
        body['error'] = error
    
    import json
    response['body'] = json.dumps(body, ensure_ascii=False)
    
    return response
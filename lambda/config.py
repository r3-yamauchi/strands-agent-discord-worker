"""
アプリケーション設定の一元管理
"""
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class Config:
    """アプリケーション設定クラス"""
    
    # Lambda設定
    DEFAULT_TIMEOUT: int = 30
    MAX_PROMPT_LENGTH: int = 10000
    MAX_RESPONSE_SIZE: int = 1048576  # 1MB
    DEFAULT_MODEL_ID: str = "us.amazon.nova-pro-v1:0"
    
    # システム設定
    ASSISTANT_SYSTEM_PROMPT: str = """あなたは様々なツールにアクセスできる有用なAIアシスタントで、ユーザからの質問や依頼に誠実に対応し、答えてもらいます。
HTTPリクエストの実行、数式の計算、現在の日時情報の取得に加えて、
ハッシュ生成、JSON整形、テキスト分析、AWSサービスの操作などの追加機能も利用できます。
常に親切で、利用可能なツールを使って正確な情報を提供してください。
以下の注意書きをよく読んで回答を返してください。

<cautions>
- 明るくポジティブな回答を心がけてください。
- 語尾には「〜だにゃん!!」「〜だにゃ?」などの猫っぽい語尾を使用してください。
- 一般的な口調や敬語はなるべく避けてください。
</cautions>

それでは、これからユーザからの投稿内容を与えます。"""
    
    # セキュリティ設定
    ENABLE_REQUEST_VALIDATION: bool = True
    ALLOWED_HASH_ALGORITHMS: list = field(default_factory=lambda: ["sha256", "sha512", "sha3_256", "sha3_512"])
    SECURE_HASH_ALGORITHMS: list = field(default_factory=lambda: ["sha256", "sha512", "sha3_256", "sha3_512"])
    
    # ツール設定
    ENABLE_CUSTOM_TOOLS: bool = True
    ENABLE_AWS_TOOLS: bool = True   # strands-agents-toolsのuse_awsを使用
    ENABLE_NOVA_REELS: bool = False  # 将来実装
    ENABLE_MCP_SERVER: bool = False  # 将来実装
    
    # Discord出力設定
    ENABLE_DISCORD_STREAMING: bool = True  # リアルタイムDiscord出力の有効/無効
    DISCORD_STREAM_MIN_LINES: int = 1      # 最小送信行数（改行単位）
    DISCORD_STREAM_MAX_BUFFER: int = 1500  # 最大バッファサイズ（文字数）
    
    # カスタムツールの個別制御
    ENABLE_HASH_GENERATOR: bool = True
    ENABLE_JSON_FORMATTER: bool = True
    ENABLE_TEXT_ANALYZER: bool = True
    
    # ロギング設定
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Lambda Layer設定
    LAMBDA_MEMORY: int = 1024
    LAMBDA_TIMEOUT: int = 10  # 分

    DISCORD_APPLICATION_ID: str = ""
    DISCORD_BOT_TOKEN: str = ""
    
    @classmethod
    def from_env(cls) -> "Config":
        """環境変数から設定を読み込み"""
        config = cls()
        
        # 環境変数から値を読み込み
        for key in dir(config):
            if key.isupper() and not key.startswith("_"):
                env_key = key
                env_value = os.environ.get(env_key)
                
                if env_value is not None:
                    # 現在の値の型を取得
                    current_value = getattr(config, key)
                    current_type = type(current_value)
                    
                    # 型変換
                    try:
                        if current_type == bool:
                            setattr(config, key, env_value.lower() in ("true", "1", "yes", "on"))
                        elif current_type == int:
                            setattr(config, key, int(env_value))
                        elif current_type == float:
                            setattr(config, key, float(env_value))
                        elif current_type == list:
                            # カンマ区切りのリストとして解析
                            setattr(config, key, [item.strip() for item in env_value.split(",")])
                        else:
                            setattr(config, key, env_value)
                    except ValueError:
                        # 型変換に失敗した場合はデフォルト値を使用
                        pass
        
        return config
    
    def validate(self) -> None:
        """設定値の妥当性を検証"""
        if self.MAX_PROMPT_LENGTH <= 0:
            raise ValueError("MAX_PROMPT_LENGTH must be positive")
        
        if self.DEFAULT_TIMEOUT <= 0:
            raise ValueError("DEFAULT_TIMEOUT must be positive")
        
        if self.LAMBDA_MEMORY < 128 or self.LAMBDA_MEMORY > 10240:
            raise ValueError("LAMBDA_MEMORY must be between 128 and 10240")
        
        if self.LAMBDA_TIMEOUT < 1 or self.LAMBDA_TIMEOUT > 15:
            raise ValueError("LAMBDA_TIMEOUT must be between 1 and 15 minutes")
        
        if not self.DEFAULT_MODEL_ID:
            raise ValueError("DEFAULT_MODEL_ID cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で返す"""
        return {
            key: getattr(self, key)
            for key in dir(self)
            if key.isupper() and not key.startswith("_")
        }
    
    def __str__(self) -> str:
        """設定の文字列表現"""
        settings = []
        for key, value in self.to_dict().items():
            # センシティブな情報はマスク
            if "KEY" in key or "SECRET" in key or "PASSWORD" in key:
                value = "***MASKED***"
            settings.append(f"{key}={value}")
        return "\n".join(settings)


# グローバル設定インスタンス
config = Config.from_env()

# 設定の検証
try:
    config.validate()
except ValueError as e:
    print(f"Configuration validation error: {e}")
    # デフォルト設定を使用
    config = Config()
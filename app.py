#!/usr/bin/env python3
import os
from aws_cdk import App, Environment
from stacks.strands_agent_discord_worker_stack import StrandsAgentDiscordWorkerStack

app = App()

# コンテキストまたは環境変数から環境設定を取得
account = app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT")
region = app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION")

# スタックを作成
env = Environment(account=account, region=region) if account and region else None
StrandsAgentDiscordWorkerStack(
    app, 
    "StrandsAgentDiscordWorkerStack",
    env=env,
    description="Strands Agents Discord Worker on Lambda Function"
)

app.synth()
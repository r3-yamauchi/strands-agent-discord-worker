from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct
import os


class StrandsAgentDiscordWorkerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # コンテキストから設定を取得
        memory_size = int(self.node.try_get_context("lambda_memory") or 1024)
        timeout_minutes = int(self.node.try_get_context("lambda_timeout") or 10)
        reserved_concurrent = self.node.try_get_context("reserved_concurrent")
        if reserved_concurrent:
            reserved_concurrent = int(reserved_concurrent)
        function_name = self.node.try_get_context("lambda_function_name") or "strands-agent-discord-worker"
        default_model_id = self.node.try_get_context("default_model_id")
        
        # Lambda実行ロールを作成
        lambda_role = iam.Role(
            self, "StrandsAgentLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "BedrockAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                                "bedrock:Converse",
                                "bedrock:ConverseStream",
                                "bedrock:ListFoundationModels",
                                "bedrock:ListProvisionedModelThroughputs",
                                "bedrock:ListCustomModels",
                                "bedrock:ListModelCustomizationJobs",
                                "bedrock:ListEvaluationJobs",
                                "bedrock:ListGuardrails",
                                "bedrock:ListAgents",
                                "bedrock:ListAgentActionGroups",
                                "bedrock:ListAgentAliases",
                                "bedrock:ListAgentKnowledgeBases",
                                "bedrock:ListAgentVersions",
                                "bedrock:ListDataSources",
                                "bedrock:ListIngestionJobs",
                                "bedrock:ListKnowledgeBases",
                                "bedrock:ListPrompts",
                                "bedrock:ListFlows",
                                "bedrock:ListFlowAliases",
                                "bedrock:ListFlowVersions",
                                "bedrock:ListTagsForResource"
                            ],
                            resources=["*"]  # 特定のモデルARNに制限することも可能
                        ),
                        # SNS権限
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sns:Subscribe",
                                "sns:Unsubscribe",
                                "sns:Receive",
                                "sns:ListTopics",
                                "sns:ListSubscriptions",
                                "sns:ListSubscriptionsByTopic",
                                "sns:GetTopicAttributes",
                                "sns:GetSubscriptionAttributes"
                            ],
                            resources=["*"]  # すべてのSNS Topicに対してサブスクライブ可能
                        ),
                        # use_awsツール用の権限
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                # S3権限
                                "s3:ListBucket",
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                                "s3:ListAllMyBuckets",
                                # DynamoDB権限
                                "dynamodb:ListTables",
                                "dynamodb:DescribeTable",
                                "dynamodb:GetItem",
                                "dynamodb:PutItem",
                                "dynamodb:Query",
                                "dynamodb:Scan",
                                # Systems Manager権限
                                "ssm:GetParameter",
                                "ssm:GetParameters",
                                "ssm:PutParameter",
                                "ssm:GetParametersByPath",
                                # CloudWatch権限
                                "cloudwatch:PutMetricData",
                                "cloudwatch:GetMetricStatistics",
                                # Lambda権限
                                "lambda:ListFunctions",
                                "lambda:GetFunction",
                                "lambda:GetFunctionConfiguration",
                                "lambda:ListVersionsByFunction",
                                "lambda:ListAliases",
                                "lambda:GetPolicy",
                                "lambda:ListTags",
                                # EC2権限
                                "ec2:DescribeInstances",
                                "ec2:DescribeInstanceStatus",
                                "ec2:DescribeSecurityGroups",
                                "ec2:DescribeSubnets",
                                "ec2:DescribeVpcs",
                                "ec2:DescribeImages",
                                "ec2:DescribeKeyPairs",
                                "ec2:DescribeSnapshots",
                                "ec2:DescribeVolumes",
                                "ec2:DescribeTags"
                            ],
                            resources=["*"]  # 本番環境では必要なリソースのみに制限することを推奨
                        )
                    ]
                )
            }
        )

        # 依存関係用のLambda Layerを作成
        dependencies_layer = lambda_.LayerVersion(
            self, "StrandsAgentDependencies",
            code=lambda_.Code.from_asset("lambda_layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            compatible_architectures=[lambda_.Architecture.ARM_64],
            description="Strands Agent Lambda用の依存関係",
            layer_version_name="strands-agent-deps"
        )

        # Lambda関数を作成
        lambda_function = lambda_.Function(
            self, "StrandsAgentFunction",
            function_name=function_name,  # 明示的に関数名を指定
            runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.ARM_64,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset("lambda", exclude=["__pycache__", "*.pyc", ".DS_Store"]),
            memory_size=memory_size,
            timeout=Duration.minutes(timeout_minutes),
            layers=[dependencies_layer],
            role=lambda_role,
            environment={
                "PYTHONPATH": "/opt/python",
                **({"DEFAULT_MODEL_ID": default_model_id} if default_model_id else {}),
                # Discord設定を環境変数から取得
                "DISCORD_APPLICATION_ID": os.environ.get("DISCORD_APPLICATION_ID", ""),
                "DISCORD_BOT_TOKEN": os.environ.get("DISCORD_BOT_TOKEN", ""),
                # Discord出力設定
                "ENABLE_DISCORD_STREAMING": os.environ.get("ENABLE_DISCORD_STREAMING", "true"),
                "DISCORD_STREAM_MIN_LINES": os.environ.get("DISCORD_STREAM_MIN_LINES", "1"),
                "DISCORD_STREAM_MAX_BUFFER": os.environ.get("DISCORD_STREAM_MAX_BUFFER", "1500")
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
            description="Strands Agents Discord Worker"
        )

        # 指定された場合、予約同時実行数を設定
        if reserved_concurrent:
            lambda_function.add_reserved_concurrent_executions(reserved_concurrent)

        # SNSからの呼び出し権限を付与
        lambda_function.add_permission(
            "AllowSNSInvoke",
            principal=iam.ServicePrincipal("sns.amazonaws.com"),
            action="lambda:InvokeFunction"
        )

        # 出力
        CfnOutput(
            self, "LambdaFunctionName",
            value=lambda_function.function_name,
            description="Lambda関数名"
        )

        CfnOutput(
            self, "LambdaFunctionArn",
            value=lambda_function.function_arn,
            description="Lambda関数ARN（SNS Topicのサブスクリプション作成時に使用）"
        )
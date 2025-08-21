from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from datetime import datetime

@dataclass
class Message:
    msg_id: str
    sender: str  # 发送者 ('user' 或 'model')
    content: str  # 消息内容
    timestamp: datetime  # 消息发送时间
    tokens_used: int  # 消耗的 token 数量（每条消息独立计算）
    status: int

@dataclass
class Conversation:
    model_name: str
    messages: List[Message]
    conversation_id: str  # 唯一标识符，标识此对话
    user_id: str  # 用户标识符
    messages: Optional[List[Message]]  # 存储对话的消息，每条消息是一个 Message 对象
    conversation_length: int  # 对话的总消息数
    last_user_message: str  # 用户输入的消息（最后一次）
    last_model_message: str  # 模型生成的消息（最后一次）
    status: str  # 对话状态（如 'completed', 'in-progress', 'error' 等）
    first_replied_timestamp: Optional[datetime] # 首次回复时间
    last_replied_timestamp: Optional[datetime] # 最后一次回复时间
    total_tokens_used: Optional[int]  # 总共消耗的 token 数量
    context_window_size: Optional[int]  # 上下文窗口大小，用于GPT模型的输入长度限制
    session_title: Optional[str]
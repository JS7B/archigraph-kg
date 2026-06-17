"""统一日志配置：标准 logging，统一时间/级别/来源/消息格式。"""

import logging

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO") -> None:
    """初始化根 logger 的格式与级别。"""
    logging.basicConfig(level=level, format=_FORMAT)

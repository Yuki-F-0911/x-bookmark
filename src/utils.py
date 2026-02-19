"""
共通ユーティリティ: ロギング・リトライ処理
"""

import time
import logging
import functools
import random
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def get_logger(name: str) -> logging.Logger:
    """標準フォーマットのロガーを返す"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(name)


def with_retry(
    max_retries: int = 3,
    base_delay: float = 5.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,),
    jitter: bool = True,
) -> Callable[[F], F]:
    """
    指数バックオフ付きリトライデコレータ。

    Args:
        max_retries: 最大リトライ回数
        base_delay: 基本待機秒数
        max_delay: 最大待機秒数
        exceptions: リトライ対象の例外タプル
        jitter: ランダムなジッターを加えるか
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_retries:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    if jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    logger.warning(
                        f"エラー発生: {e}。{delay:.1f}秒後にリトライします "
                        f"(試行 {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
            raise last_exc  # type: ignore
        return wrapper  # type: ignore
    return decorator


def chunk_list(lst: list, size: int) -> list[list]:
    """リストを指定サイズのチャンクに分割する"""
    return [lst[i:i + size] for i in range(0, len(lst), size)]

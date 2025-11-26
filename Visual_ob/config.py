# config.py
from __future__ import annotations
import json
import os
import logging
from typing import Any, Optional, Dict

class ConfigManager:
    """单例 + 自动序列化/反序列化 numpy.ndarray"""
    _instance: Optional["ConfigManager"] = None
    _config_file: str
    _config_data: Optional[Dict[str, Any]] = None

    def __new__(cls, config_file: str = "config.json") -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config_file = os.path.join(os.path.dirname(__file__), config_file)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        if not os.path.exists(self._config_file):
            raise FileNotFoundError(f"配置文件未找到: {self._config_file}")
        with open(self._config_file, "r", encoding="utf-8") as f:
            self._config_data = json.load(f)

    def get(self, key: Optional[str] = None, default: Any = None) -> Any:
        if self._config_data is None:
            raise RuntimeError("配置尚未加载")
        return self._config_data.get(key, default) if key else self._config_data

    def reload(self) -> None:
        self._load_config()

    # ---------- 快捷访问 ----------
    def camera_config(self) -> Dict[str, Any]:
        return self.get("camera")  # type: ignore

    def similarity_threshold(self) -> Dict[str, float]:
        return self.get("similarity")  # type: ignore

    def log_level(self) -> int:
        level = self.get("logging", {}).get("level", "INFO")
        return getattr(logging, level.upper(), logging.INFO)
    
    def get_window_size(self) -> tuple[int, int]:
        """返回窗口目标像素 (width, height)"""
        disp = self.get("display", {})
        return disp.get("window_width", 1280), disp.get("window_height", 720)
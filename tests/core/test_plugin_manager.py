import os
import pytest
import tempfile
import shutil
import importlib
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

from src.core.plugin_manager import PluginManager
from src.plugins.base import BasePlugin


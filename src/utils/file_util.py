import json
import os
from typing import Any
from settings import PROJECT_ROOT

def read_file_with_project_root(file_path: str) -> str:
    """读取项目根目录下的文件内容
    
    Args:
        file_path: 相对于项目根目录的文件路径
        
    Returns:
        文件内容字符串
    """
    with open(os.path.join(PROJECT_ROOT, file_path), 'r', encoding='utf-8') as f:
        html = f.read()
    return html

def write_file_with_project_root(data: str, file_path: str) -> None:
    """写入数据到项目根目录下的文件
    
    Args:
        data: 要写入的字符串数据
        file_path: 相对于项目根目录的文件路径
    """
    with open(os.path.join(PROJECT_ROOT, file_path), 'w', encoding='utf-8') as f:
        f.write(data)

def read_json_with_project_root(file_path: str) -> Any:
    """读取项目根目录下的JSON文件
    
    Args:
        file_path: 相对于项目根目录的文件路径
        
    Returns:
        解析后的JSON数据
    """
    with open(os.path.join(PROJECT_ROOT, file_path), 'r', encoding='utf-8') as f:
        return json.loads(f.read())

def write_json_with_project_root(data: Any, file_path: str) -> None:
    """写入JSON数据到项目根目录下的文件
    
    Args:
        data: 要写入的数据
        file_path: 相对于项目根目录的文件路径
    """
    with open(os.path.join(PROJECT_ROOT, file_path), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

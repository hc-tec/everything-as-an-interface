import json
import os
from settings import PROJECT_ROOT

def read_file_with_project_root(file_path):
    with open(os.path.join(PROJECT_ROOT, file_path), 'r', encoding='utf-8') as f:
        html = f.read()
    return html

def read_json_with_project_root(file_path):
    with open(os.path.join(PROJECT_ROOT, file_path), 'r', encoding='utf-8') as f:
        return json.loads(f.read())

def write_json_with_project_root(data, file_path):
    with open(os.path.join(PROJECT_ROOT, file_path), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

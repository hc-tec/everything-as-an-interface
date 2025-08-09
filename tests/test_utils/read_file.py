
import os
from settings import PROJECT_ROOT

def read_file_with_project_root(file_path):
    with open(os.path.join(PROJECT_ROOT, file_path), 'r', encoding='utf-8') as f:
        html = f.read()
    return html


import re
import json
import sys

def quick_extract_initial_state(html_file_path):
    """
    快速提取HTML文件中的window.__INITIAL_STATE__
    
    Args:
        html_file_path (str): HTML文件路径
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
    except Exception as e:
        print(f"读取文件失败: {e}")
        return
    
    # 正则表达式：匹配包含window.__INITIAL_STATE__的script标签
    pattern = r'<script[^>]*>.*?window\.__INITIAL_STATE__\s*=\s*(.+?)(?=\s*;|\s*</script>|\s*$).*?</script>'
    
    match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    if match:
        state_value = match.group(1).strip()
        print("找到 window.__INITIAL_STATE__:")
        print("=" * 50)
        print(state_value)
        print("=" * 50)
        
        # 尝试解析JSON
        try:
            # 移除可能的尾部分号
            if state_value.endswith(';'):
                state_value = state_value[:-1]
            
            parsed_state = json.loads(state_value)
            print(f"\n✅ 成功解析JSON")
            
            # 保存到文件
            with open('extracted_initial_state.json', 'w', encoding='utf-8') as f:
                json.dump(parsed_state, f, ensure_ascii=False, indent=2)
            print("💾 已保存到: extracted_initial_state.json")
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            # 保存原始内容
            with open('extracted_initial_state.txt', 'w', encoding='utf-8') as f:
                f.write(state_value)
            print("💾 已保存原始内容到: extracted_initial_state.txt")
    else:
        print("❌ 未找到 window.__INITIAL_STATE__")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使用方法: python quick_extract.py <HTML文件路径>")
        print("例如: python quick_extract.py page.html")
        sys.exit(1)
    
    html_file = sys.argv[1]
    quick_extract_initial_state(html_file)

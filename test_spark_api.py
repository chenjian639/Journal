# test_spark_api_fixed.py
import json
import requests
import sys

def setup_encoding():
    """设置控制台编码以避免中文显示问题"""
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_spark_api():
    """测试讯飞星火API连接"""
    
    # 请替换为你的实际API密码
    api_password = "cyjdtVYXSGWgwiUdnLMs:DvKIMQbkHgKlYljNcbhN"  # 从讯飞控制台获取
    
    url = "https://spark-api-open.xf-yun.com/v2/chat/completions"
    
    # 构建请求头
    headers = {
        'Authorization': f'Bearer {api_password}',
        'content-type': "application/json"
    }
    
    # 构建请求体
    body = {
        "model": "x1",
        "user": "test_user",
        "messages": [
            {
                "role": "user", 
                "content": "What is AI? Answer in one sentence."
            }
        ],
        "stream": True,
        "tools": [
            {
                "type": "web_search",
                "web_search": {
                    "enable": False
                }
            }
        ]
    }
    
    print("=== Testing Spark API ===")
    print(f"API Key (first 10 chars): {api_password[:10]}...")
    print(f"Request URL: {url}")
    
    try:
        print("Sending request to Spark API...")
        response = requests.post(url=url, json=body, headers=headers, stream=True, timeout=30)
        print(f"Response received! Status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: API returned status code: {response.status_code}")
            print(f"Error message: {response.text}")
            return False
        
        full_response = ""
        print("Receiving stream response...")
        
        # 处理流式响应
        for chunk in response.iter_lines():
            if chunk and b'[DONE]' not in chunk:
                try:
                    data_str = chunk.decode('utf-8')
                    
                    if data_str.startswith('data: '):
                        data_str = data_str[6:]
                    
                    data = json.loads(data_str)
                    
                    if 'choices' in data and data['choices']:
                        delta = data['choices'][0].get('delta', {})
                        
                        # 显示思维链内容
                        if 'reasoning_content' in delta and delta['reasoning_content']:
                            reasoning = delta['reasoning_content']
                            print(f"Thinking: {reasoning}", end="")
                        
                        # 显示回答内容
                        if 'content' in delta and delta['content']:
                            content = delta['content']
                            print(content, end="", flush=True)
                            full_response += content
                            
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"Error processing data: {e}")
                    continue
        
        print(f"\n\nTest completed successfully!")
        print(f"Full response: {full_response}")
        return True
        
    except requests.exceptions.Timeout:
        print("Request timeout, please check network connection")
        return False
    except requests.exceptions.ConnectionError:
        print("Network connection error, please check network settings")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Network request failed: {e}")
        return False
    except Exception as e:
        print(f"Other error: {e}")
        return False

def main():
    """Main function"""
    setup_encoding()
    
    print("Spark API Test Tool")
    print("=" * 50)
    
    api_password = "cyjdtVYXSGWgwiUdnLMs:DvKIMQbkHgKlYljNcbhN"
    
    if api_password == "你的API密码":
        print("Please update the API password in the code")
        print("Steps:")
        print("1. Find line 10: api_password = '你的API密码'")
        print("2. Replace '你的API密码' with your actual API password")
        print("3. Save the file and run again")
        return
    
    success = test_spark_api()
    
    if success:
        print("\nAPI configuration is correct! Ready for keyword extraction.")
    else:
        print("\nAPI test failed, please check:")
        print("  - API password")
        print("  - Network connection")
        print("  - Account balance")
        print("  - Service activation")

if __name__ == '__main__':
    main()
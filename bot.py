# 导入 Web3 库
from web3 import Web3
from eth_account import Account
import time
import sys
import os
import random  # 引入随机模块
import requests

# 数据桥接配置
from data_bridge import data_bridge
from keys_and_addresses import private_keys, labels, proxies  # 导入代理信息
from network_config import networks

# ----------------- 新增代理函数 -----------------

def format_proxy(proxy):
    """根据代理字符串返回requests所需的代理字典"""
    if not proxy:
        return None
    try:
        if proxy.startswith('socks5://'):
            return {'http': proxy, 'https': proxy}
        elif proxy.startswith('http://') or proxy.startswith('https://'):
            return {'http': proxy, 'https': proxy}
        else:
            # 如果没有协议前缀，默认认为是 http 代理
            return {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
    except Exception as e:
        print(f"代理格式化错误: {e}")
        return None

def setup_blockchain_connection(rpc_url, proxy=None):
    """
    根据给定的 rpc_url 和可选的代理地址创建 Web3 连接
    如果提供了代理，则创建一个带有代理的 requests.Session 传给 HTTPProvider
    """
    if proxy:
        formatted_proxy = format_proxy(proxy)
        if formatted_proxy:
            session = requests.Session()
            session.proxies = formatted_proxy
            return Web3(Web3.HTTPProvider(rpc_url, session=session, request_kwargs={"timeout": 30}))
        else:
            return Web3(Web3.HTTPProvider(rpc_url))
    else:
        return Web3(Web3.HTTPProvider(rpc_url))

# ----------------- 以上为新增的代理处理逻辑 -----------------

# 文本居中函数
def center_text(text):
    terminal_width = os.get_terminal_size().columns
    lines = text.splitlines()
    centered_lines = [line.center(terminal_width) for line in lines]
    return "\n".join(centered_lines)

# 清理终端函数
def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

description = """
自动桥接机器人  https://unlock3d.t3rn.io/rewards
还是继续操你麻痹Rambeboy,偷私钥🐶  V2版本
"""

# 每个链的颜色和符号
chain_symbols = {
    'Base': '\033[34m',  # 更新为 Base 链的颜色
    'OP Sepolia': '\033[91m',         
}

# 颜色定义
green_color = '\033[92m'
reset_color = '\033[0m'
menu_color = '\033[95m'  # 菜单文本颜色

# 每个网络的区块浏览器URL
explorer_urls = {
    'Base': 'https://sepolia.base.org', 
    'OP Sepolia': 'https://sepolia-optimism.etherscan.io/tx/',
    'b2n': 'https://b2n.explorer.caldera.xyz/tx/'
}

# 获取b2n余额的函数
def get_b2n_balance(web3, my_address):
    balance = web3.eth.get_balance(my_address)
    return web3.from_wei(balance, 'ether')

# 检查链的余额函数
def check_balance(web3, my_address):
    balance = web3.eth.get_balance(my_address)
    return web3.from_wei(balance, 'ether')

# 创建和发送交易的函数
def send_bridge_transaction(web3, account, my_address, data, network_name):
    nonce = web3.eth.get_transaction_count(my_address, 'pending')
    value_in_ether = 0.3
    value_in_wei = web3.to_wei(value_in_ether, 'ether')

    try:
        gas_estimate = web3.eth.estimate_gas({
            'to': networks[network_name]['contract_address'],
            'from': my_address,
            'data': data,
            'value': value_in_wei
        })
        gas_limit = gas_estimate + 50000  # 增加安全边际
    except Exception as e:
        print(f"估计gas错误: {e}")
        return None

    base_fee = web3.eth.get_block('latest')['baseFeePerGas']
    priority_fee = web3.to_wei(5, 'gwei')
    max_fee = base_fee + priority_fee

    transaction = {
        'nonce': nonce,
        'to': networks[network_name]['contract_address'],
        'value': value_in_wei,
        'gas': gas_limit,
        'maxFeePerGas': max_fee,
        'maxPriorityFeePerGas': priority_fee,
        'chainId': networks[network_name]['chain_id'],
        'data': data
    }

    try:
        signed_txn = web3.eth.account.sign_transaction(transaction, account.key)
    except Exception as e:
        print(f"签名交易错误: {e}")
        return None

    try:
        tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        # 获取最新余额
        balance = web3.eth.get_balance(my_address)
        formatted_balance = web3.from_wei(balance, 'ether')

        # 获取区块浏览器链接
        explorer_link = f"{explorer_urls[network_name]}{web3.to_hex(tx_hash)}"

        # 显示交易信息
        print(f"{green_color}📤 发送地址: {account.address}")
        print(f"⛽ 使用Gas: {tx_receipt['gasUsed']}")
        print(f"🗳️  区块号: {tx_receipt['blockNumber']}")
        print(f"💰 ETH余额: {formatted_balance} ETH")
        # 对于 b2n 余额，这里保持原有逻辑（也可以根据需要加入代理隔离）
        b2n_balance = get_b2n_balance(Web3(Web3.HTTPProvider('https://b2n.rpc.caldera.xyz/http')), my_address)
        print(f"🔵 b2n余额: {b2n_balance} b2n")
        print(f"🔗 区块浏览器链接: {explorer_link}\n{reset_color}")

        return web3.to_hex(tx_hash), value_in_ether
    except Exception as e:
        print(f"发送交易错误: {e}")
        return None, None

# 在特定网络上处理交易的函数（每个账号独立建立连接，实现隔离IP）
def process_network_transactions(network_name, bridges, chain_data, successful_txs):
    # 全局连接用于检查链的可达性（无代理）
    global_web3 = Web3(Web3.HTTPProvider(chain_data['rpc_url']))
    while not global_web3.is_connected():
        print(f"无法连接到 {network_name}，正在尝试重新连接...")
        time.sleep(5)
        global_web3 = Web3(Web3.HTTPProvider(chain_data['rpc_url']))
    
    print(f"成功连接到 {network_name}")

    for bridge in bridges:
        for i, private_key in enumerate(private_keys):
            account = Account.from_key(private_key)
            my_address = account.address

            data = data_bridge.get(bridge)  # 确保 data_bridge 是字典类型
            if not data:
                print(f"桥接 {bridge} 数据不可用!")
                continue

            # 根据当前账号的代理信息创建专属的Web3实例
            account_proxy = proxies[i] if i < len(proxies) else ""
            account_web3 = setup_blockchain_connection(chain_data['rpc_url'], account_proxy)
            while not account_web3.is_connected():
                print(f"账号 {labels[i]} 无法连接到 {network_name}，尝试重新连接...")
                time.sleep(5)
                account_web3 = setup_blockchain_connection(chain_data['rpc_url'], account_proxy)

            result = send_bridge_transaction(account_web3, account, my_address, data, network_name)
            if result:
                tx_hash, value_sent = result
                successful_txs += 1

                # 检查 value_sent 是否有效再格式化
                if value_sent is not None:
                    print(f"{chain_symbols[network_name]}🚀 成功交易总数: {successful_txs} | {labels[i]} | 桥接: {bridge} | 桥接金额: {value_sent:.5f} ETH ✅{reset_color}\n")
                else:
                    print(f"{chain_symbols[network_name]}🚀 成功交易总数: {successful_txs} | {labels[i]} | 桥接: {bridge} ✅{reset_color}\n")

                print(f"{'='*150}")
                print("\n")
            
            # 随机等待 60 到 80 秒（原来120~180秒改为较短延时，可根据需要调整）
            wait_time = random.uniform(60, 80)
            print(f"⏳ 等待 {wait_time:.2f} 秒后继续...\n")
            time.sleep(wait_time)

    return successful_txs

# 显示链选择菜单的函数
def display_menu():
    print(f"{menu_color}选择要运行交易的链:{reset_color}")
    print(" ")
    print(f"{chain_symbols['Base']}1. Base -> OP Sepolia{reset_color}")
    print(f"{chain_symbols['OP Sepolia']}2. OP -> Base{reset_color}")
    print(f"{menu_color}3. 运行所有链{reset_color}")
    print(" ")
    choice = input("输入选择 (1-3): ")
    return choice

def main():
    print("\033[92m" + center_text(description) + "\033[0m")
    print("\n\n")

    successful_txs = 0
    current_network = 'OP Sepolia'  # 默认从 Base 链开始
    alternate_network = 'Base'

    while True:
        # 使用无代理的全局连接检查当前链连接情况
        web3 = Web3(Web3.HTTPProvider(networks[current_network]['rpc_url']))
        
        while not web3.is_connected():
            print(f"无法连接到 {current_network}，正在尝试重新连接...")
            time.sleep(5)
            web3 = Web3(Web3.HTTPProvider(networks[current_network]['rpc_url']))
        
        print(f"成功连接到 {current_network}")
        
        my_address = Account.from_key(private_keys[0]).address  # 使用第一个私钥的地址
        balance = check_balance(web3, my_address)

        # 如果余额不足 1 ETH，切换到另一个链（阈值可根据需要调整）
        if balance < 1:
            print(f"{chain_symbols[current_network]}{current_network}余额不足 1 ETH，切换到 {alternate_network}{reset_color}")
            current_network, alternate_network = alternate_network, current_network  # 交换链

        # 根据当前链处理交易（桥接数据根据网络参数区分）
        if current_network == 'Base':
            bridges = ["Base - OP Sepolia"]
        else:
            bridges = ["OP - Base"]

        successful_txs = process_network_transactions(current_network, bridges, networks[current_network], successful_txs)

        # 自动切换网络，并随机等待一定时间
        time.sleep(random.uniform(30, 60))  # 切换网络前随机延时

if __name__ == "__main__":
    main()

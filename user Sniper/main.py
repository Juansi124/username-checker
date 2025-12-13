"""username Checker for Discord"""

import os
import json
import random
import string
import queue
import threading
import traceback
import itertools
from time import sleep, time
from signal import signal, SIGINT
from pathlib import Path
from urllib3.exceptions import MaxRetryError

import requests

VERSION = "1.0"

class Config:
    """Configuration Class"""
    
    def __init__(self):
        self.config = None
        self.config_path = 'data/config.json'
        self.load_config()

    def load_config(self):
        """Initialize config file if it does not exist"""
        if not os.path.exists(self.config_path):
            with open(self.config_path, 'w') as f:
                f.write("{}")
        elif os.path.getsize(self.config_path) == 0:
            with open(self.config_path, 'w') as f:
                f.write("{}")

    def get(self, key):
        """Get a config value by key"""
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
        return self.config.get(key, None)
    
    def set(self, key, value):
        """Set a config value"""
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
        self.config[key] = value
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
        
    def get_all(self):
        """Get all config values"""
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
        return self.config


def handler(signal_received, frame):
    """Handle SIGINT (Ctrl+C) gracefully"""
    print('\n\n[!] SIGINT detected. Exiting gracefully...')
    exit(0)

signal(SIGINT, handler)

CONFIRMATORS = ["y", "yes", "1", "true", "t"]
NEGATORS = ["n", "no", "0", "false", "f"]

os.makedirs("logs", exist_ok=True)
os.makedirs("results", exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("proxies", exist_ok=True)


def create_empty_file(file_path):
    """Create an empty file with parent directories"""
    file_path = Path(file_path)
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()


def clear_file(file_path):
    """Clear contents of an existing file"""
    Path(file_path).write_text("", encoding='utf-8')


for file in ["logs/log.txt", "logs/error.txt"]:
    create_empty_file(file)
    clear_file(file)

for file in ["results/hits.txt", "data/names_to_check.txt", "proxies/proxies.txt"]:
    create_empty_file(file)

with Path("proxies/proxies.txt").open("r", encoding='utf-8') as proxies_file:
    proxies = proxies_file.read().splitlines()

if len(proxies) == 0:
    proxies = [None]

proxy_cycle = itertools.cycle(proxies)

config = Config()
lock = threading.Lock()

RPS = 0
REQUESTS = 0
WORKS = 0
TAKEN = 0
DEACTIVATE = False


class Logger:
    """Log Class"""
    
    def __init__(self, file_name: str):
        self.file_name = file_name
        self.file = open(self.file_name, "a", encoding='utf-8')

    def log(self, message: str):
        """Write a log message to file"""
        self.file.write(f"{message}\n")
        self.file.flush()

    def close(self):
        """Close the log file"""
        self.file.close()

    def __del__(self):
        """Ensure file is closed on deletion"""
        if hasattr(self, 'file') and not self.file.closed:
            self.file.close()


class Colors:
    """ANSI color codes for terminal output"""
    
    @staticmethod
    def _code(code):
        return f'\033[{code}m'

    ENDC = _code(0)
    BOLD = _code(1)
    RED = _code(31)
    GREEN = _code(32)
    YELLOW = _code(33)
    CYAN = _code(36)
    MAGENTA = _code(35)
    GREY = _code(90)

Logger = Logger("logs/log.txt")
Logger.log(f"UsernameChecker started at {time()}")


def clear():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


clear()

class Pomelo:
    """Username Checker"""
    
    def __init__(self):
        self.endpoint = "https://discord.com/api/v9"
        self.headers_post = {"Content-Type": "application/json"}
        self.session = requests.Session()
        self.proxies_not_working = []
        self.remove_proxies = config.get("remove_proxies")
        self.timeout = config.get("timeout") or 30

        Logger.log(f"Timeout set to {self.timeout}")
        Logger.log(f"Remove proxies set to {self.remove_proxies}")
        Logger.log(f"Headers set to {self.headers_post}")

    def proxy_err(self, name, proxy, proxy_cycle):
        """Handle proxy errors"""
        name = [name, next(proxy_cycle)]
        Logger.log(f"ReadTimeout with proxy {proxy}")
        
        if self.remove_proxies and proxy is not None:
            Logger.log(f"Removing proxy {proxy}")
            self.proxies_not_working.append(proxy)
        
        return name
        
        
    def check(self, name: list):
        """Check if a Discord username is available"""
        global RPS, REQUESTS, WORKS, TAKEN, DEACTIVATE
        
        while not DEACTIVATE:
            try:
                # Extract name and proxy
                try:
                    name, proxy = name
                except ValueError:
                    if proxy_cycle is None:
                        proxy = None
                    else:
                        proxy = next(proxy_cycle)
                        
                        if len(self.proxies_not_working) >= len(proxies):
                            Logger.log("Exiting because all proxies are not working")
                            DEACTIVATE = True
                            
                            Logger.log("Clearing queue")
                            while queue.qsize() > 0:
                                queue.get()
                                queue.task_done()
                            Logger.log("Queue cleared")
                            
                            sleep(self.timeout + 1)
                            print(f"\n{Colors.RED}No proxies left{Colors.ENDC}" * 3)
                            return
                        
                        while proxy in self.proxies_not_working:
                            proxy = next(proxy_cycle)
                
                if proxy is not None:
                    proxy = f"http://{str(proxy).strip()}"

                # Make API request
                r = self.session.post(
                    url=self.endpoint + "/unique-username/username-attempt-unauthed",
                    headers=self.headers_post,
                    json={"username": name},
                    proxies={"http": proxy, "https": proxy},
                    timeout=self.timeout
                )
                REQUESTS += 1

                if r.status_code in [200, 201, 204]:
                    if str(r.json()) in ["", None, "{}"]:
                        Logger.log(f"Unexpected response: {r.text}")
                        return self.check(name)
                    
                    if r.json()["taken"]:
                        TAKEN += 1
                        return [False, r.json(), r.status_code]
                    else:
                        WORKS += 1
                        return [True, r.json(), r.status_code]

                elif r.status_code == 429:
                    if proxy is None or proxy == "None" or proxy == "":
                        print(f"{Colors.YELLOW}[!] PROXYLESS RATELIMITED - Sleeping...{Colors.ENDC}")
                        sleep(r.json()["retry_after"])
                    name = [name, next(proxy_cycle)]
                    return self.check(name)
                else:
                    Logger.log(f"Unknown error: {r.status_code} | {r.json()}")

            except requests.exceptions.ProxyError:
                name = self.proxy_err(name, proxy, proxy_cycle)
                return self.check(name)

            except requests.exceptions.ConnectionError:
                name = self.proxy_err(name, proxy, proxy_cycle)
                return self.check(name)
            
            except requests.exceptions.ReadTimeout:
                name = self.proxy_err(name, proxy, proxy_cycle)
                return self.check(name)
            
            except MaxRetryError:
                name = self.proxy_err(name, proxy, proxy_cycle)
                return self.check(name)

            except Exception:
                with lock:
                    try:
                        exception = traceback.format_exc()
                        Logger.log(f"Unknown error with proxy {proxy}")
                        with open("logs/error.txt", "w", encoding='utf-8') as f:
                            f.write(f"{exception}\n")
                        sleep(0.3)
                    except:
                        pass
                return self.check(name)

r = Colors.RED
c = Colors.CYAN
g = Colors.GREEN
x = Colors.ENDC

ASCII = f"""
{c}╔════════════════════════════════════════════════════════════════════╗
║                        Username Checker                            ║
║                          Version {VERSION}                             ║
╠════════════════════════════════════════════════════════════════════╣{x}
{g}⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣤⣤⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣴⣿⡿⠟⠛⠛⠿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢀⣴⣾⣿⣿⣿⣿⣷⣦⣄⠀⠀⠀⠀⠀⣼⣿⠟⠁⠀⠀⠀⠀⠈⢻⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢠⣾⣿⠟⠁⠀⠀⠀⠙⠻⣿⣷⣄⠀⠀⢸⣿⡟⠀⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⣿⣷⣶⣤⡀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣼⣿⡇⠀⠀⠀⠀⠀⠀⠀⠘⢿⣿⣦⠀⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠉⠁⠉⠉⠻⣿⣿⡄⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⣧⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⠀⠀⠀⠀⠀
⠀⢀⣤⣶⣿⣿⠿⠇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⣿⠁⠀⠀⠀⠀
⢠⣾⣿⠛⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⠋⠀⠀⠀⠀⠀
⣾⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⣾⣿⠟⠁⠀⠀⠀⠀⠀⠀
⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢹⣿⣇⠀⠀⠀⠀⠀⠀⠀⢀⣠⣤⣾⣿⡿⠛⠁⠀⠀⠀⠀⠀⠀⠀⠀
⠘⢿⣿⣦⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣘⣿⡿⠀⢀⣀⣤⣴⣶⣿⣿⣿⣿⣿⣷⣶⣶⣶⣤⣤⣀⡀⠀⠀⠀⠀
⠀⠀⠙⠻⢿⣿⣷⣶⣶⣦⣤⣤⣤⣤⣶⣶⣶⣾⣿⣿⡿⠟⠀⣐⣿⠿⠿⠛⠛⠛⠛⠉⠉⠉⠉⠉⠙⠛⠛⠿⢿⣿⣷⣤⠀⠀
⠀⠀⠀⠀⠀⠀⠉⠉⠛⠛⣛⣿⣿⣿⡿⠿⠛⠋⠁⠀⠀⠀⢸⣿⣷⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠻⣿⣷⡀
⠀⠀⠀⠀⠀⠀⠀⣀⣴⣿⣿⠟⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⡇
⠀⠀⠀⠀⠀⢀⣾⣿⠟⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⣷⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⣿⠇
⠀⠀⠀⠀⢠⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣠⣴⣿⣿⠋⠀
⠀⠀⠀⠀⣾⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⡿⠟⠋⠀⠀⠀
⠀⠀⠀⠀⢸⣿⣷⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠹⢿⣿⣶⣤⣤⣤⣴⣤⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⡼⣿⣿⣷⡀⠀⠀⠀⠀⠀⠀⢀⣿⣿⠁⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠙⠛⠿⠿⠿⢿⣿⣇⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⡇⣿⣿⣿⣿⣶⣄⣀⣀⣀⣴⣿⣿⠃⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢿⣿⣦⡀⠀⠀⠀⢀⣴⣿⡿⢹⣿⡇⢸⣿⣷⠈⠛⠿⠿⣿⠿⠟⠋⠁⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⣶⣿⣿⡿⠋⠀⣼⣿⡇⠘⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠉⠀⠀⠀⠀⣿⣿⡇⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⠁⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣿⣿⠀⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⡏⠀⠀⣿⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⠇⠀⢸⣿⡿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⣿⣿⣤⣤⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⠛⠛⠛⠛⠃⠀⠀⠀⠀⠀                         
{c}╠════════════════════════════════════════════════════════════════════╣
║  {r}@{x}  github.com/daskeptaxd                                         {c}║
║  {r}@{x}  discord.gg/skepta                                            {c}║
╚════════════════════════════════════════════════════════════════════╝{x}
"""
clear()
print(ASCII)



CHARS = string.ascii_lowercase + string.digits + "_" + '.'

with open("data/names_to_check.txt", "r", encoding='utf-8') as f:
    combos = f.read().splitlines()
    f.close()

with open("data/config.json", "r") as f:
    config_str = f.read()
    f.close()

if len(config_str) == 2 or os.path.getsize("data/config.json") == 0 or config.get("remove_proxies") is None:
    # Webhook configuration
    if config.get("webhook") is None:
        ask_webhook = input(f"{Colors.YELLOW}[?]{Colors.ENDC} Send hits to webhook? [y/n]: {Colors.CYAN}")
        print(Colors.ENDC, end='')
        
        if ask_webhook.lower() in CONFIRMATORS:
            webhook = input(f"{Colors.YELLOW}[?]{Colors.ENDC} Webhook URL: {Colors.CYAN}")
            print(Colors.ENDC, end='')
            config.set("webhook", webhook)
            
            print(f"{Colors.MAGENTA}[i] Available placeholders:{Colors.ENDC}")
            print(f"    <name>    - Username")
            print(f"    <@userid> - Mention user (replace userid with actual ID)")
            print(f"    <time>    - Timestamp")
            print(f"    <RPS>     - Requests per second")
            print(f"    <elapsed> - Elapsed time\n")
            
            message = input(f"{Colors.YELLOW}[?]{Colors.ENDC} Webhook message: {Colors.CYAN}")
            print(Colors.ENDC, end='')
            config.set("message", message)
        else:
            config.set("webhook", None)
    
    # Proxy configuration
    if config.get("remove_proxies") is None:
        ask_timeout = input(f"{Colors.YELLOW}[?]{Colors.ENDC} Request timeout in seconds (Default: 30): {Colors.CYAN}")
        print(Colors.ENDC, end='')
        config.set("timeout", int(ask_timeout) if ask_timeout else 30)
        
        ask_proxy = input(f"{Colors.YELLOW}[?]{Colors.ENDC} Use proxies? [y/n]: {Colors.CYAN}")
        print(Colors.ENDC, end='')
        
        if ask_proxy.lower() in CONFIRMATORS:
            print(f"{Colors.YELLOW}[!]{Colors.ENDC} Please add proxies to proxies/proxies.txt")
            print(f"{Colors.CYAN}[i]{Colors.ENDC} Format: IP:PORT (e.g., 104.207.33.193:3129)")
            input(f"{Colors.CYAN}Press Enter to continue...{Colors.ENDC}")
            
            with open("proxies/proxies.txt", "r", encoding='utf-8') as f:
                proxies = f.read().splitlines()
            
            if len(proxies) == 0:
                proxies = [None]
                print(f"{Colors.RED}[!]{Colors.ENDC} No proxies loaded - switching to proxyless")
            else:
                print(f"{Colors.GREEN}[✓]{Colors.ENDC} Loaded {Colors.CYAN}{len(proxies)}{Colors.ENDC} proxies")
            
            proxy_cycle = itertools.cycle(proxies)
            ask_remove = input(f"{Colors.YELLOW}[?]{Colors.ENDC} Remove bad proxies? [y/n]: {Colors.CYAN}")
            print(Colors.ENDC, end='')
            config.set("remove_proxies", ask_remove.lower() in CONFIRMATORS)
        else:
            print(f"{Colors.YELLOW}[!]{Colors.ENDC} Proxyless mode - Discord may rate limit")
            print(f"{Colors.YELLOW}[!]{Colors.ENDC} Recommended: Close Discord client while scanning")
            input(f"{Colors.CYAN}Press Enter to continue...{Colors.ENDC}")
            config.set("remove_proxies", False)
            config.set("remove_proxies", False)
else:
    Logger.log(f"Loaded config: {config.get_all()}")

if len(combos) == 0:
    length = input(f"{Colors.YELLOW}[?]{Colors.ENDC} Username length: {Colors.CYAN}")
    print(Colors.ENDC, end='')
    
    print(f"{Colors.YELLOW}[*]{Colors.ENDC} Generating combinations...")
    combos = itertools.product(CHARS, repeat=int(length))
    
    with open("data/names_to_check.txt", "w", encoding='utf-8') as f:
        for combo in combos:
            f.write("".join(combo) + "\n")
    
    with open("data/names_to_check.txt", "r", encoding='utf-8') as f:
        combos = f.read().splitlines()

Logger.log(f"Loaded {len(combos)} combos")
longest_name = max([len(name) for name in combos])
Logger.log(f"Longest name is {longest_name} characters long")

queue = queue.Queue()
try:
    combos = random.sample(combos, 50000)
except ValueError:
    pass

for name in combos:
    print(f"{Colors.YELLOW}[+]{Colors.ENDC} Adding username: {Colors.CYAN}{name}{Colors.ENDC}", end="\r")
    queue.put([name.strip(), next(proxy_cycle)])

print(" " * 80, end="\r") 


UsernameChecker = Pomelo()
Logger.log("UsernameChecker successfully initiated")


def worker():
    """Thread worker for checking usernames"""
    while queue.qsize() > 0:
        name = queue.get()
        
        try:
            available, json_response, status_code = UsernameChecker.check(name)
        except Exception:
            with lock:
                exception = traceback.format_exc()
                with open("logs/error.txt", "a", encoding='utf-8') as f:
                    f.write(f"{exception}\nname={name}\n")
            available, json_response, status_code = "ERROR", None, None
        
        name_str, proxy = name
        proxy_display = str(proxy[:10] + '*' * 10) if proxy else 'Proxyless'
        padding = ' ' * (longest_name - len(name_str))

        with lock:
            if available is True:
                print(f"{Colors.GREEN}[✓]{Colors.ENDC} Available  : {Colors.CYAN}{name_str}{Colors.ENDC} {padding}│ RPS: {Colors.CYAN}{RPS}/s{Colors.ENDC} │ Proxy: {Colors.CYAN}{proxy_display}{Colors.ENDC}")
                
                with open("results/hits.txt", "a", encoding='utf-8') as f:
                    f.write(name_str + "\n")

            elif available == "RATELIMITED":
                print(f"{Colors.YELLOW}[?]{Colors.ENDC} Timeout    : {json_response} │ RPS: {Colors.CYAN}{RPS}/s{Colors.ENDC} │ Proxy: {Colors.CYAN}{proxy_display}{Colors.ENDC}")
            
            elif available == "ERROR":
                with open("logs/error.txt", "a", encoding='utf-8') as f:
                    f.write(f"{name_str}, {json_response}, {status_code}\n")
            
            else:
                print(f"{Colors.RED}[✗]{Colors.ENDC} Taken      : {Colors.CYAN}{name_str}{Colors.ENDC} {padding}│ RPS: {Colors.CYAN}{RPS}/s{Colors.ENDC} │ Proxy: {Colors.CYAN}{proxy_display}{Colors.ENDC}")
       
        queue.task_done()                



def rps_calculator():
    """Calculate requests per second"""
    global RPS
    Logger.log("Started RPS calculator thread")
    
    while True:
        rps_before = REQUESTS
        sleep(1)
        RPS = REQUESTS - rps_before


start_time = time()


def title_spinner():
    """Update window title with stats (Windows only)"""
    Logger.log("Started title spinner thread")
    
    titles = [
        "Username Checker {VERSION} -",
        "Available: {WORKS}",
        "Taken: {TAKEN}",
        "Requests: {REQUESTS}",
        "RPS: {RPS}",
        "Elapsed: {ELAPSED}s"
    ]
    
    while True:
        for title in titles:
            for _ in range(50):
                formatted = title.format(
                    WORKS=WORKS,
                    TAKEN=TAKEN,
                    REQUESTS=REQUESTS,
                    RPS=RPS,
                    ELAPSED=round(time() - start_time)
                )
                os.system(f'title {formatted}')
                sleep(0.01)
            sleep(1)



def webhook_processor():
    """Process and send webhook notifications for hits"""
    Logger.log("Started webhook processor thread")
    
    webhook = config.get("webhook")
    message = config.get("message")
    webhook_start_time = time()

    def get_diff(old, new):
        """Return new items not in old list"""
        return list(set(new) - set(old))

    names = []
    last_send_time = time()

    with open("results/hits.txt", "r", encoding='utf-8') as f:
        names = f.read().splitlines()
    
    while True:
        old_names = names
        last_send_time = 0
        
        with open("results/hits.txt", "r", encoding='utf-8') as f:
            names = f.read().splitlines()
        
        names_diff = get_diff(old_names, names)
        
        if len(names_diff) > 1 and time() - last_send_time < 5:
            old_names = names
            new_names = []
            inloop_start = time()
            
            while len(names_diff) < 10:
                with open("results/hits.txt", "r", encoding='utf-8') as f:
                    names = f.read().splitlines()

                names_diff = get_diff(old_names, names)


                for name in names_diff:
                    if name not in str(new_names):
                        new_name = name + ":!#:!#" + str(round(time()))
                        new_names.append(new_name)

                if time() - inloop_start > 10:
                    break
                sleep(0.3)

            names_diff.extend(new_names)
            payload = []
            
            for name in reversed(names_diff):
                current_time = time()
                hittime = round(current_time)
                
                if ":!#:!#" in name:
                    name, hittime = name.split(":!#:!#")
                    
                hittime = f'<t:{hittime}:T>'
                msg = message.replace("<name>", name).replace("<time>", str(hittime)).replace("<elapsed>", str(round(current_time - webhook_start_time))).replace("<RPS>", str(RPS))
                payload.append(msg)
            
            json_payload = {
                "content": "\n".join(payload),
                'username': 'UsernameChecker',
                'avatar_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Burning_Yellow_Sunset.jpg/1280px-Burning_Yellow_Sunset.jpg'
            }
            
            r = UsernameChecker.session.post(url=webhook, json=json_payload)
            
            if r.status_code == 429:
                sleep(r.json()["retry_after"])

            last_send_time = time()
            sleep(0.5)
        elif len(names_diff) == 1:
            name = names_diff[0]
            current_time = time()
            hittime = f'<t:{round(current_time)}:T>'
            
            json_payload = {
                "content": message.replace("<name>", name).replace("<time>", str(hittime)).replace("<elapsed>", str(round(current_time - webhook_start_time))).replace("<RPS>", str(RPS)),
                'username': 'UsernameChecker',
                'avatar_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Burning_Yellow_Sunset.jpg/1280px-Burning_Yellow_Sunset.jpg'
            }
            
            r = UsernameChecker.session.post(url=webhook, json=json_payload)
            
            if r.status_code == 429:
                sleep(r.json()["retry_after"])

        sleep(1)


threading.Thread(target=rps_calculator, daemon=True).start()

if os.name == "nt":
    threading.Thread(target=title_spinner, daemon=True).start()

if config.get("webhook") is not None:
    threading.Thread(target=webhook_processor, daemon=True).start()

# Display banner and start
clear()
print(ASCII)

print(f"{Colors.GREEN}[✓]{Colors.ENDC} Loaded {Colors.CYAN}{len(combos)}{Colors.ENDC} combos")
num_threads = input(f"{Colors.YELLOW}[?]{Colors.ENDC} Number of threads: {Colors.CYAN}")
print(Colors.ENDC, end='')

for countdown in range(5, 0, -1):
    print(f"{Colors.YELLOW}[*]{Colors.ENDC} Starting in {countdown}s with {num_threads} threads (Ctrl+C to abort)", end="\r")
    sleep(1)

print(" " * 80, end="\r")
print(f"{Colors.GREEN}[✓]{Colors.ENDC} Starting {num_threads} worker threads...\n")

print(f"{Colors.BOLD}{'─' * 80}{Colors.ENDC}")

threads = []
for i in range(int(num_threads)):
    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
    threads.append(t)
    
Logger.log(f"Started {num_threads} threads")

queue.join()

print(f"{Colors.BOLD}{'─' * 80}{Colors.ENDC}")
print(f"\n{Colors.GREEN}[✓]{Colors.ENDC} Scan complete!")
print(f"{Colors.CYAN}[i]{Colors.ENDC} Total requests: {Colors.CYAN}{REQUESTS}{Colors.ENDC}")
print(f"{Colors.GREEN}[i]{Colors.ENDC} Available names: {Colors.CYAN}{WORKS}{Colors.ENDC}")
print(f"{Colors.RED}[i]{Colors.ENDC} Taken names: {Colors.CYAN}{TAKEN}{Colors.ENDC}")
print(f"{Colors.YELLOW}[i]{Colors.ENDC} Elapsed time: {Colors.CYAN}{round(time() - start_time)}s{Colors.ENDC}")
print(f"\n{Colors.MAGENTA}Results saved to: {Colors.CYAN}results/hits.txt{Colors.ENDC}\n")

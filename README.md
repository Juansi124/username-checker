# Discord Username Checker (4L Sniper)

Python-based Discord username availability checker with proxy support, webhook notifications.

## Built with

- Python 3.8+ ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
- requests - HTTP requests ![requests](https://img.shields.io/badge/requests-2CA5E0?style=flat)
- threading - Concurrent checking ![threading](https://img.shields.io/badge/threading-⚡-yellow?style=flat)

## Features

- Multi-threaded username checking
- Proxy rotation support (IP:PORT format)
- Auto rate limit handling
- Discord webhook notifications
- Real-time RPS (Requests Per Second) tracking
- Results saved to file
- Beautiful ASCII art interface
- Configurable timeout and settings

## How it works

The tool hits Discord's Pomelo API (`/unique-username/username-attempt-unauthed`) to check if usernames are available. It supports both single username checking and bulk generation of usernames by length. Results are displayed in real-time with color-coded output and saved to `results/hits.txt`.

Proxies rotate automatically if provided, and bad proxies can be removed on-the-fly. The tool includes automatic rate limit detection and handling.

## Setup

```bash
pip install -r requirements.txt
```

## Configuration

On first run, the tool will create a configuration file at `data/config.json` and prompt you for:
- Webhook URL (optional) - for Discord notifications
- Request timeout (default: 30s)
- Proxy settings

## How to use


Generate usernames on first run by specifying length (e.g., 4 for 4-letter usernames or 3 for 3 letter usernames)

### Add proxies (optional)

Add proxies to `proxies/proxies.txt` in `IP:PORT` format:
```
104.207.33.193:3129
98.76.54.32:3128
45.67.89.12:8080
```

### Run it

```bash
python main.py
```

Follow the prompts:
1. Configure webhook (optional)
2. Set timeout (default: 30 seconds)
3. Enable/disable proxy usage
4. Choose number of threads

## Output

Real-time console output shows:
- `[✓] Available` - username is available
- `[✗] Taken` - already claimed
- `[?] Timeout` - rate limited or timeout
- `[!] ERROR` - something went wrong

Available usernames are saved to `results/hits.txt`

## Webhook Notifications

Configure webhook messages with these placeholders:
- `<name>` - The available username
- `<time>` - Timestamp of the hit
- `<@userid>` - Mention a user (replace userid with actual ID)
- `<RPS>` - Current requests per second
- `<elapsed>` - Time since scan started

Example:
```
 New username available: <name> | Found at <time>
```

## Config Options

Edit `data/config.json` or reconfigure on next run:
- `webhook` - Discord webhook URL
- `message` - Webhook message format
- `timeout` - Request timeout in seconds
- `remove_proxies` - Auto-remove bad proxies

## Performance

- Multi-threaded design for maximum speed
- Typical speeds: 50-200 RPS depending on proxies
- Supports thousands of threads (system dependent)
- Automatic queue management

## Structure

```
4L Sniper/
├── proxies/
│   └── proxies.txt      - proxy list (IP:PORT)
├── data/
│   ├── config.json      - configuration
│   └── names_to_check.txt - usernames to check
├── results/
│   └── hits.txt         - available usernames
├── logs/
│   ├── log.txt          - application logs
│   └── error.txt        - error logs
├── main.py              - main application
├── requirements.txt     - dependencies
└── README.md
```

## Notes

- Use proxies for large scans to avoid rate limits
- Recommended: 10-50 threads per proxy
- The tool automatically handles Discord rate limits
- Results are saved in real-time
- Press Ctrl+C to stop

## Rate Limiting

Discord has strict rate limits. Best practices:
- Use residential/datacenter proxies
- Keep threads reasonable (50-100 per proxy)
- Enable "remove bad proxies" option
- Monitor RPS to ensure stable checking

## Troubleshooting

**No proxies loading?**
- Check `proxies/proxies.txt` format is `IP:PORT`
- Ensure file exists and has content

**Rate limited constantly?**
- Reduce thread count
- Add more proxies
- Increase timeout value

**Config errors?**
- Delete `data/config.json` to reconfigure
- Check JSON syntax if manually edited

## License

MIT License - Free to use and modify

## misc

- Discord: discord.gg/skepta
- Discord @: @daskepta

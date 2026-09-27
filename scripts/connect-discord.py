#!/usr/bin/env python3
"""Run on the server as root. Never prints or stores the bot token in Git."""
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.request

CONFIG = Path('/srv/northlight/state/openclaw.json')
SECRETS = Path('/etc/northlight/secrets.env')
DEPLOYMENT = Path('/opt/northlight')


def ask_id(label):
    value = input(label + ': ').strip()
    if not re.fullmatch(r'[0-9]{17,20}', value):
        raise SystemExit('Expected a Discord numeric ID. Enable Developer Mode, then Copy ID.')
    return value


def discord_get(path, token):
    request = urllib.request.Request(
        'https://discord.com/api/v10' + path,
        headers={'Authorization': 'Bot ' + token, 'User-Agent': 'NorthlightSetup/1.0'},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f'Discord returned HTTP {error.code}. Check the bot token and server/channel access.') from None


def atomic_write(path, text, uid=0, gid=0):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.setup-')
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, uid, gid)
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run this script with sudo on the Northlight server.')
    token = getpass.getpass('Discord bot token (hidden): ').strip()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', token):
        raise SystemExit('Invalid token format.')
    guild_id = ask_id('Northlight server ID')
    channel_id = ask_id('Working channel ID')
    user_ids = list(dict.fromkeys([ask_id('Your user ID'), ask_id("Your friend's user ID")]))
    bot = discord_get('/users/@me', token)
    if not bot.get('bot'):
        raise SystemExit('The token must belong to a bot application.')
    guild = discord_get('/guilds/' + guild_id, token)
    channel = discord_get('/channels/' + channel_id, token)
    if channel.get('guild_id') != guild_id:
        raise SystemExit('The selected channel does not belong to the selected server.')
    config = json.loads(CONFIG.read_text())
    config.setdefault('channels', {})['discord'] = {
        'enabled': True,
        'token': {'source': 'env', 'provider': 'default', 'id': 'DISCORD_BOT_TOKEN'},
        'applicationId': bot['id'],
        'dmPolicy': 'disabled',
        'groupPolicy': 'allowlist',
        'configWrites': False,
        'guilds': {guild_id: {
            'requireMention': True,
            'users': user_ids,
            'channels': {channel_id: {'enabled': True, 'requireMention': True}},
        }},
    }
    secret_lines = [line for line in SECRETS.read_text().splitlines()
                    if not line.startswith('DISCORD_BOT_TOKEN=')]
    secret_lines.append('DISCORD_BOT_TOKEN=' + token)
    atomic_write(SECRETS, '\n'.join(secret_lines) + '\n')
    atomic_write(CONFIG, json.dumps(config, indent=2) + '\n', 1000, 1000)
    subprocess.run(['docker', 'compose', 'run', '--rm', '--no-deps', 'gateway',
                    'node', 'dist/index.js', 'config', 'validate'], cwd=DEPLOYMENT, check=True)
    subprocess.run(['docker', 'compose', 'up', '-d', '--force-recreate', 'gateway'],
                   cwd=DEPLOYMENT, check=True)
    print(f"Configured {bot['username']} for {guild['name']} / {channel.get('name', channel_id)}.")
    print('Mention the bot after the AI account is connected; check channels status --probe.')


if __name__ == '__main__':
    main()

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
    guild_id = '981308596958658632'
    bot = discord_get('/users/@me', token)
    if not bot.get('bot'):
        raise SystemExit('The token must belong to a bot application.')
    if bot['id'] != '1553818719359078500':
        raise SystemExit('This token does not belong to the Stearin application.')
    permissions = 1024 + 2048 + 65536 + 16384 + 32768 + 64 + 274877906944
    invite = (f'https://discord.com/oauth2/authorize?client_id={bot["id"]}'
              f'&permissions={permissions}&scope=bot%20applications.commands'
              f'&guild_id={guild_id}&disable_guild_select=true')
    print('Invite this bot to Northlight using this link:')
    print(invite)
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
        }},
    }
    secret_lines = [line for line in SECRETS.read_text().splitlines()
                    if not line.startswith('DISCORD_BOT_TOKEN=')]
    secret_lines.append('DISCORD_BOT_TOKEN=' + token)
    atomic_write(SECRETS, '\n'.join(secret_lines) + '\n')
    atomic_write(CONFIG, json.dumps(config, indent=2) + '\n', 1000, 1000)
    subprocess.run(['docker', 'compose', 'run', '-T', '--rm', '--no-deps', 'gateway',
                    'node', 'dist/index.js', 'config', 'validate'], cwd=DEPLOYMENT, check=True)
    subprocess.run(['docker', 'compose', 'up', '-d', '--force-recreate', 'gateway'],
                   cwd=DEPLOYMENT, check=True)
    print(f"Configured {bot['username']} for all visible channels in Northlight.")
    print('Enable Message Content Intent in the Bot page, and complete the invite above.')
    print('Mention the bot after the AI account is connected; check channels status --probe.')


if __name__ == '__main__':
    main()

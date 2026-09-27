# Northlight Institute of Mental Health

Deployment and operating instructions for the institute's shared OpenClaw assistant.

## Architecture

Discord → OpenClaw on an UpCloud Ubuntu server → configured AI provider and institute repository.

The service uses the official OpenClaw 2026.9.6 container. It runs as an unprivileged user, has persistent private state, and restarts automatically. The dashboard is published only on the server's loopback interface. The container has no host Docker socket or host administrator credentials.

This repository contains public configuration templates and agent instructions. Live secrets, chats, memory, and model credentials stay outside it. The initial project is agent infrastructure; no institute website has been built or published yet.

## Server layout

| Location | Purpose |
|---|---|
| `/opt/northlight` | Deployment checkout |
| `/etc/northlight/secrets.env` | Private service credentials, root-readable only |
| `/srv/northlight/state` | OpenClaw configuration, sessions and private memory |
| `/srv/northlight/state/workspace/repo` | Agent's institute repository checkout |
| `/srv/northlight/auth` | Private model authentication state |
| `/srv/northlight/ssh` | Repository-specific deploy key |

## Dashboard

Forward the dashboard through your existing server SSH access:

```sh
ssh -N -L 18789:127.0.0.1:18789 USER@SERVER
```

Open `http://localhost:18789`. Retrieve the dashboard token privately from `/etc/northlight/secrets.env` on the server. Do not post it to Discord or GitHub. Approve a dashboard device only after identifying it as yours.

## AI connection

The deployment is configured for a ChatGPT/Codex subscription, with no paid API fallback. Authorize the account on the server:

```sh
cd /opt/northlight
docker compose exec gateway node dist/index.js models auth login --provider openai --device-code
docker compose exec gateway node dist/index.js models list --provider openai
```

Complete the device authorization using your own ChatGPT account. Keep the credentials in the private agent store. The configured model is `openai/gpt-6-astra`; confirm that it is available after login. If it is unavailable, explicitly choose one from the account's model list. Subscription usage counts toward that account's limits.

## Discord setup

1. In the [Discord Developer Portal](https://discord.com/developers/applications), create an application named **Northlight** and its bot.
2. Enable **Message Content Intent**. Enable **Server Members Intent** for member resolution. Generate the bot token and keep it private.
3. Invite it to **Northlight Institute of Mental Health** using `bot` and `applications.commands` scopes. Grant View Channels, Send Messages, Read Message History, Embed Links, Attach Files, and Send Messages in Threads if needed. Administrator permission is unnecessary.
4. The setup helper targets the Northlight server configured in this repository.
5. On the server, run `sudo python3 /opt/northlight/scripts/connect-discord.py`. The helper prints a server-specific bot invitation. It validates the bot token before enabling Discord, and prompts for the token without echoing it.
6. Mention `@Northlight` in any channel it can see. Ask it to describe the repository, then test a small requested edit and verify the result.

The configured server is allowed in full: every member can tag the bot in any channel the bot can see. DMs are disabled. Ordinary conversation does not trigger the bot; mention it for a task. Discord channel permissions still control visibility, so grant the Northlight bot role access to any private channels where it should work.

## Operations

```sh
cd /opt/northlight
docker compose ps
docker compose logs --tail 60 gateway
docker compose exec gateway node dist/index.js health
docker compose exec gateway node dist/index.js channels status --probe
docker compose exec gateway node dist/index.js security audit
docker compose restart gateway
```

Use `docker compose exec gateway node dist/index.js …` for CLI commands against the running service. Secrets may appear in diagnostic output; review before sharing.

For updates, deliberately choose a release tag, review its release notes, and update `compose.yaml`. A restart alone does not fetch a newer image. Keep deployment changes under operator control.

## Repository and website work

The agent's SSH deploy key should grant write access to this repository only. It can make commits and push code here. That key does not grant access to other repositories or hosting providers, and it does not authorize GitHub API operations such as opening pull requests. Add a repository-scoped GitHub App/token if those operations are needed.

A website domain and hosting account must be selected and connected before the agent can deploy website changes. Source editing, tests, and publishing are separate steps; verify the published page before reporting a deployment as complete.

## References

- [Official Docker setup](https://docs.openclaw.ai/install/docker)
- [Discord setup](https://docs.openclaw.ai/channels/discord/setup)
- [Discord access control](https://docs.openclaw.ai/channels/discord/access-control)

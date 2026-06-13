---
type: reference
status: active
date: 2026-06-13
tags: [hermes, configuration, architecture]
---

# Hermes Profiles

Hermes supports multiple **profiles** — independent configurations that change the entire agent stack: provider, model, system prompt, skills, tools, plugins, cron, and memories.

## Location

Profiles live under `~/.hermes/profiles/<name>/`. Each profile has its own:

```
~/.hermes/profiles/<name>/
├── config.yaml       — provider, model, temperature, tool settings
├── skills/           — profile-specific skills
├── plugins/          — profile-specific plugins
├── cron/             — profile-specific cron jobs
└── memories/         — profile-specific memory databases
```

## Default Profile

The `default` profile at `~/.hermes/config.yaml` is used when no profile is specified.

## Switching Profiles

Via CLI:
```
hermes --profile research run "analyze this data"
```

Via config:
```yaml
# ~/.hermes/config.yaml
active_profile: research
```

## Profile Config Structure

A profile's `config.yaml` defines:
- **provider** — API provider (openrouter, anthropic, openai, etc.)
- **model** — model name
- **system_prompt** — custom system prompt
- **tools** — enabled/disabled tools
- **skills** — skill loading configuration
- **temperature**, **max_tokens**, etc.

## Relationship to Personalities UI

In the [[Hermes-Personalities-UI]] architecture, each **personality** maps to one Hermes profile. The Web UI wraps profile selection in a user-friendly interface, adding session isolation and conversation history on top.

A personality config extends a base Hermes profile by adding:
- A display name, avatar, and color
- Optional overrides for model, provider, system prompt
- Skill toggles (enable/disable per personality)
- Toolset restrictions
- Temperature per personality
- Persistent conversation history per session

## Related

- [[Hermes-Personalities-UI]] — Web UI that uses profiles as personalities

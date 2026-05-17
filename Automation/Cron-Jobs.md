---
type: reference
status: active
date: 2026-05-16
tags: [automation, cron, monitoring]
---
# Cron Jobs & Automation

All times America/Phoenix (MST, UTC-7, no DST).

## Birthday Reminders

telegram, 9am. All no_agent scripts (.sh wrappers). Early reminder 7+ days before, day-of.

| Person | Early | Day-of |
|--------|-------|--------|
| Stephanie | Feb 2 | Feb 9 |
| Kristen | Apr 20 | Apr 27 |
| Jason | Dec 23 | Dec 30 |
| Lauren | Apr 3 | Apr 10 |
| Ian | Jan 16 | Jan 23 |
| (anniversary) | Aug 23 | Aug 30 |

## System

| Job | Schedule | Delivery | Type |
|-----|----------|----------|------|
| pve01-watchdog | every 15m | telegram | LLM (pve-monitor) |
| vm-metrics-logger | every 15m | local | no_agent |
| Obsidian vault sync | every 15m | origin | no_agent |

## Daily

| Job | Time | Delivery | Type |
|-----|------|----------|------|
| Medicine reminder | 6:00am | telegram | no_agent |
| Family briefing | 6:00am | telegram | LLM (icloud-calendar) |
| Email brief | 5:40pm | telegram | LLM |
| Hydration check | 7:00pm | telegram | no_agent |
| Kids TV check | 10:00pm | telegram | no_agent |

## Periodic

| Job | Freq | Delivery | Type |
|-----|------|----------|------|
| Stephanie email watch | 30min | telegram | no_agent |
| HydrateSpark sip poller | 10min | local | no_agent |
| YouTube live watch | 5min | origin | no_agent |
| Auto-commit scripts | 4h | local | no_agent |
| Air filter reminder | 2mo | telegram | LLM |

## Related

- [[Infrastructure]]

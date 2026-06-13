---
type: index
status: active
date: 2026-05-21
tags: [infrastructure, homelab, proxmox, network]
description: Top-level index for the homelab infrastructure — hypervisor, VMs, containers, storage, networking, and all discovered network devices.
---

# Infrastructure

This directory contains the complete inventory of the homelab at John's residence (Phoenix, AZ). Everything lives on a single Proxmox node (pve01) with a QNAP NAS for bulk storage and a UniFi stack for networking.

## Quick Reference

| Area | File | Count |
|------|------|-------|
| 🖥️ Hypervisor | [[Infrastructure/Hypervisor]] | 1 node (pve01) |
| 💻 Virtual Machines | [[Infrastructure/Virtual-Machines]] | 3 VMs |
| 📦 Containers | [[Infrastructure/Containers]] | 7 LXC |
| 💾 Storage | [[Infrastructure/Storage]] | 4 pools, 3 tiers |
| 🌐 Networking | [[Infrastructure/Networking]] | UniFi stack |
| 🗄️ NAS | [[Infrastructure/NAS]] | QNAP TS-x53? |
| 📡 Network Devices | [[Infrastructure/Network-Devices]] | ~50+ clients |
| 🔄 Backup | [[Infrastructure/Backup]] | PBS on separate storage needed |

## Network Summary

- **Subnet:** 192.168.1.0/24 (LAN) + 192.168.100.0/24 (Storage)
- **Gateway:** UDM-SE (192.168.1.1)
- **DNS:** Pi-hole (192.168.1.2) — relayed via UDM
- **DHCP:** UDM-SE

## Topology at a Glance

```
Internet → UDM-SE (192.168.1.1)
            ├── USW Pro HD 24 PoE (192.168.1.206)
            │   ├── pve01 (192.168.1.5) — Proxmox host
            │   │   ├── DevServer VM (192.168.1.226)
            │   │   ├── StagingServer VM (192.168.1.121)
            │   │   ├── haos VM (192.168.1.112)
            │   │   ├── PBS CT (192.168.1.163)
            │   │   ├── radarr CT (192.168.1.129)
            │   │   ├── iventoy CT (192.168.1.184)
            │   │   ├── prometheus CT (192.168.1.170)
            │   │   ├── netbox CT (192.168.1.33)
            │   │   ├── checkmk CT (192.168.1.125)
            │   │   └── mail-gateway CT (192.168.1.74)
            │   └── QNAP NAS (192.168.1.242)
            ├── US-8-60W (192.168.1.233)
            ├── U6 Enterprise AP
            └── U6 Mesh AP
```

## Related

- [[Reference/Infrastructure]] — legacy overview (will be superseded by this directory)
- [[Automation/Cron-Jobs]] — all scheduled automation
- [[Automation/Servers]] — Dataview queryable server database

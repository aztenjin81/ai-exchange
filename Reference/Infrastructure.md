---
type: reference
status: active
date: 2026-05-16
tags: [infrastructure, homelab, proxmox, pve01]
---

# Infrastructure

## Proxmox

- Host: pve01 (192.168.1.5)
- Cluster: single node
- Kernel: 6.17+
- Storage: ZFS vmpool (local-zfs), iSCSI (qnap-storage), NFS (PBS datastore)

### VMs

| ID | Name | OS | Role |
|----|------|----|------|
| 103 | haos | Home Assistant OS | Smart home |
| 107 | DevServer | Linux (this host) | Dev, self-hosted services |
| 109 | StagingServer | Linux | Staging/testing |

### Containers

| ID | Name | Role |
|----|------|------|
| 100 | PBS | Proxmox Backup Server |
| 101 | radarr | Media management |
| 102 | iventoy | Network boot/PXE |
| 104 | prometheus | Monitoring (unused?) |
| 105 | netbox | DCIM/IPAM |
| 106 | checkmk | Monitoring |
| 108 | mail-gateway | Email filtering |

## Networking

- Gateway: UDM-SE (192.168.1.1)
- Subnet: 192.168.1.0/24
- Switches: USW Pro HD 24 PoE, USW Flex, others
- APs: U6 Enterprise, U6 Mesh, others
- DNS: Pi-hole (192.168.1.2)

## Storage

- QNAP NAS (iSCSI target)
- PBS container (backup target)
- Local ZFS vmpool

## Docker (DevServer)

- Hermes agent (self)
- Various self-hosted services
- Grafana, Prometheus stack

## Grafana

- URL: http://192.168.1.226:3000
- Auth: HTTP Basic (admin — creds in ~/.hermes/env)
- Dashboards:
  - `pve01-monitoring-jcb9x` — infrastructure timeseries overview
  - `pve01-all-workloads-j6xz4` — all workloads stat columns
  - `pve01-workload-detail-8hqr4` — per-VM deep dive
  - `pve01-all-v3-svd2z` — v3 stat columns

## PostgreSQL

- Port: 5433
- URI: in `~/.hermes/env` (`HERMES_PG_URI`)
- Helper: `/root/.hermes/scripts/hermes_db.py`
- CLI: `pg "<sql>"`
- Tables: `vm_metrics`, `cron_log`, `network_clients`

## Monitoring Scripts

- `/root/.hermes/scripts/monitor.py` — logs VM metrics to Postgres every 15min
- Cron: vm-metrics-logger (no_agent)

## Related

- [[Cron-Jobs]]

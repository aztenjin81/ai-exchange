---
type: reference
status: active
date: 2026-05-21
tags: [infrastructure, proxmox, hypervisor, pve01]
role: Hypervisor
ip: 192.168.1.5
model: Custom / Xeon E-2234
ram_gb: 64
storage_tb: 10.9 (ZFS RAIDZ1) + 3TB (iSCSI) + 5TB (NFS)
os: Proxmox VE 9.1.11
kernel: 6.17.13-2-pve
uptime_days: ongoing
---

# Hypervisor: pve01

## Hardware

| Component | Detail |
|-----------|--------|
| **CPU** | Intel Xeon E-2234 @ 3.60GHz — 4 cores / 8 threads |
| **RAM** | 64 GB (62 GiB usable) |
| **Boot Drive** | 1 TB ST1000NM004A-2MN130 (Seagate Exos 7E10) — sda |
| **Storage Pool** | 3 × 4TB Seagate IronWolf (ST4000VN008 / ST4000NE0025) in RAIDZ1 = ~10.9T raw, ~7.1T usable |
| **iSCSI** | 3TB QNAP iSCSI LUN (via 10GbE) — sde |
| **Network** | 2 × Intel 82599 10GbE (LACP bond → vmbr0) + 1 × enp1s0 10GbE storage-only (192.168.100.11) |

### Disk Layout

| Device | Size | Model | Pool |
|--------|------|-------|------|
| sda | 931.5G | ST1000NM004A-2MN130 | Boot (OS) |
| sdb | 3.6T | ST4000VN008-2DR166 | vmpool RAIDZ1 |
| sdc | 3.6T | ST4000NE0025-2EW107 | vmpool RAIDZ1 |
| sdd | 3.6T | ST4000NE0025-2EW107 | vmpool RAIDZ1 |
| sde | 3T | iSCSI (QNAP) | iscsi-qnap LVM thin |

## Networking

| Interface | Role | IP | MTU |
|-----------|------|-----|-----|
| bond0 (nic0+nic1) | LACP to LAN | bridge slave | 1500 |
| vmbr0 | LAN bridge | 192.168.1.5/24 | 1500 |
| enp1s0 | Storage network | 192.168.100.11/24 | 9000 |

- Bond mode: 802.3ad (LACP), hash: layer3+4, LACP rate: fast
- Bridge: VLAN-aware (2-4094)

## Workloads

### Virtual Machines

| ID | Name | vCPU | RAM | Disk | Storage | IP |
|----|------|------|-----|------|---------|-----|
| 103 | haos-17.2 | 2 | 4 GB | 32 GB | local-zfs | 192.168.1.112 |
| 107 | DevServer | 4 | 12 GB | 1 TB | iscsi-qnap | 192.168.1.226 |
| 109 | StagingServer | 8 | 12 GB | 1 TB | iscsi-qnap | 192.168.1.121 |

### Containers

| ID | Name | vCPU | RAM | Root Disk | Data Disk | IP |
|----|------|------|-----|-----------|-----------|-----|
| 100 | proxmox-backup-server | 2 | 2 GB | 10G | 2T (backup datastore) | 192.168.1.163 |
| 101 | radarr | 2 | 1 GB | 4G | — | 192.168.1.129 |
| 102 | iventoy | 1 | 512 MB | 1T | — | 192.168.1.184 |
| 104 | prometheus | 1 | 2 GB | 4G | — | 192.168.1.170 |
| 105 | netbox | 2 | 2 GB | 4G | — | 192.168.1.33 |
| 106 | checkmk | 2 | 2 GB | 6G | — | 192.168.1.125 |
| 108 | proxmox-mail-gateway | 2 | 4 GB | 10G | — | 192.168.1.74 |

## Tuning

- CPU: host mode on all VMs
- CPU pinning: DevServer → affinity 0-3, StagingServer → affinity 4-7
- Hotplug: CPU + memory enabled on DevServer and StagingServer
- NUMA: enabled (1 socket) on DevServer and StagingServer
- IO threads: enabled on DevServer (virtio-scsi-pci) and StagingServer (virtio-scsi-single)
- Balloon: DevServer min 1GB
- ZFS dedup: disabled
- ARC cap: 12 GB

## Related

- [[Infrastructure/Virtual-Machines]]
- [[Infrastructure/Containers]]
- [[Infrastructure/Storage]]
- [[Infrastructure/Networking]]

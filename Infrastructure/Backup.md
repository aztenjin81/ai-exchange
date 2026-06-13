---
type: reference
status: active
date: 2026-05-21
tags: [infrastructure, backup, pbs]
description: Backup strategy, schedules, and known gaps
---

# Backup

## Current State

**No automated backup schedule configured.** Proxmox cluster has no backup jobs defined (`/cluster/backup` returns empty data).

## Backup Infrastructure

| Component | Location | Role |
|-----------|----------|------|
| **PBS CT (100)** | pve01 / local-zfs | Proxmox Backup Server software |
| **PBS Datastore** | CT 100 mp0 → local-zfs:subvol-100-disk-1 (2TB) | Backup storage |
| **QNAP NFS** | qnap-storage (5TB) | Alternative backup target (unused for PBS) |

## ⚠️ Critical Issue: SPOF

The PBS datastore lives on `local-zfs` — **the same ZFS pool** that hosts:

- haos VM (103)
- All 7 LXC containers (including PBS itself)
- All container root filesystems

A ZFS pool failure destroys **both the production workloads AND their backups**. This is not a valid backup architecture.

## Recommended Fix

Move the PBS datastore to the QNAP NFS export (`qnap-storage`):

1. QNAP has 4.47 TiB free — plenty for the 2TiB datastore
2. NFS is on separate hardware (different power supply, different disks)
3. NFS over 10GbE provides adequate throughput for backup operations

**Tradeoff:** NFS-backed storage cannot do live VM snapshots via PBS (snapshot requires ZFS or iSCSI). VMs on `iscsi-qnap` (DevServer, StagingServer) would need stop/suspend for backup, or migrate them to local-zfs first.

## Ideal Target Architecture

| VM/CT | Primary Storage | Backup Method |
|-------|----------------|---------------|
| DevServer (107) | iscsi-qnap | PBS (stop/suspend) → QNAP NFS |
| StagingServer (109) | iscsi-qnap | PBS (stop/suspend) → QNAP NFS |
| haos (103) | local-zfs | PBS live snapshot → QNAP NFS |
| All LXCs | local-zfs | PBS live snapshot → QNAP NFS |

## Related

- [[Infrastructure/Storage]]
- [[Infrastructure/NAS]]
- [[Infrastructure/Containers#CT 100 — Proxmox Backup Server]]

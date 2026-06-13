---
type: reference
status: active
date: 2026-05-21
tags: [infrastructure, storage, zfs, iscsi, nfs]
description: Storage architecture — pools, tiers, disks, and performance characteristics
---

# Storage

## Three-Tier Architecture

| Tier | Backend | Technology | Workloads | Speed |
|------|---------|-----------|-----------|-------|
| **1 — System** | Local ZFS (3×4TB RAIDZ1) | ZFS on HDD | HAOS, all LXC containers, boot volumes | 4K randread ~272 IOPS |
| **2 — High IO** | QNAP iSCSI (3TB LUN) | LVM thin over 10GbE | DevServer, StagingServer disks | 4K randread ~22,939 IOPS, 1M seq read ~1,016 MiB/s |
| **3 — Backup** | QNAP NFS (5TB export) | NFS over 10GbE | PBS datastore (currently on local-zfs instead) | 4K randread ~39,822 IOPS, 1M seq read ~1,166 MiB/s |

## Storage Pools (Proxmox)

| Name | Type | Total | Used | Available | Content |
|------|------|-------|------|-----------|---------|
| **iscsi-qnap** | LVM thin (iSCSI) | 2.76 TiB | 2.06 TiB | 703 GiB | VM images, container rootdir |
| **local-zfs** | ZFS pool | 7.10 TiB | 39.3 GiB | 7.06 TiB | VM images, container rootdir |
| **qnap-storage** | NFS | 5.08 TiB | 611 GiB | 4.47 TiB | ISO, templates, backups, images |
| **pbs** | PBS (remote) | 2 TiB | 24.5 GiB | 2.02 TiB | Backups (to PBS CT 100) |

## ZFS Pool: vmpool

| Property | Value |
|----------|-------|
| **vdev** | RAIDZ1 (3-wide) |
| **Drives** | sdb (ST4000VN008), sdc (ST4000NE0025), sdd (ST4000NE0025) |
| **Raw** | ~10.9 TiB |
| **Usable** | ~7.15 TiB |
| **Health** | ONLINE |
| **Frag** | 1% |
| **ARC cap** | 12 GB |
| **Dedup** | Disabled |

## Drives Inventory

| Device | Location | Model | Size | Role |
|--------|----------|-------|------|------|
| sda | pve01 onboard | ST1000NM004A-2MN130 | 1 TB | Boot/OS |
| sdb | pve01 onboard | ST4000VN008-2DR166 | 4 TB | ZFS RAIDZ1 |
| sdc | pve01 onboard | ST4000NE0025-2EW107 | 4 TB | ZFS RAIDZ1 |
| sdd | pve01 onboard | ST4000NE0025-2EW107 | 4 TB | ZFS RAIDZ1 |
| sde | QNAP iSCSI | iSCSI Storage | 3 TB | LVM thin pool for VM disks |

## iSCSI Details

- **Target:** QNAP at 192.168.100.10, port 3260
- **Network:** 192.168.100.0/24 (10GbE, MTU 9000)
- **pve01 interface:** enp1s0 (192.168.100.11)
- **LVM:** VG `pve-iscsi`, thin pool `iscsi_pool`
- **Used by:** DevServer (3x disks), StagingServer (3x disks)

## NFS Details

- **Export:** 192.168.100.10:/PMVM
- **pve01 mount:** /mnt/pve/qnap-storage
- **Options:** nconnect=8, vers=3
- **Used for:** ISO, snippets, templates, backup archives

## Performance Benchmarks

| Test | Local ZFS (RAIDZ1) | QNAP NFS (10GbE) | QNAP iSCSI (10GbE) |
|------|-------------------|-------------------|--------------------|
| 4K randread | 272 IOPS | 39,822 IOPS | 22,939 IOPS |
| 4K randwrite | 297 IOPS | 21,438 IOPS | 9,722 IOPS |
| 1M seq read | 157 MiB/s | 1,166 MiB/s | 1,016 MiB/s |
| 1M seq write | — | 799 MiB/s | 724 MiB/s |

## ⚠️ Known Issues

1. **PBS datastore on same pool as VMs** — CT 100's backup datastore (`/mnt/datasource/backup`) lives on `local-zfs`, the same ZFS pool hosting haos and all containers. A pool failure loses both primary workloads AND backups.
2. **NFS-based VM disks not supported for PBS live backup** — NFS cannot snapshot, so VMs on NFS storage must be stopped/suspended for backup.
3. **iSCSI single path** — Only one iSCSI link from pve01 to QNAP. No multipath configured (single NIC on storage VLAN).

## Related

- [[Infrastructure/Hypervisor]]
- [[Infrastructure/NAS]]
- [[Infrastructure/Backup]]

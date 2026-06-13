---
type: reference
status: active
date: 2026-05-21
tags: [infrastructure, proxmox, containers]
description: All LXC containers running on pve01
---

# Containers

All containers are Debian-based, unprivileged, with nesting enabled. All use DHCP on vmbr0.

## CT 100 — Proxmox Backup Server

| Field | Value |
|-------|-------|
| **Status** | Running |
| **vCPU** | 2 |
| **RAM** | 2 GB (+ 512 MB swap) |
| **RootFS** | 10 GB on local-zfs |
| **Data** | 2 TB on local-zfs (mp0: /mnt/datasource/backup) |
| **IP** | 192.168.1.163 |
| **MAC** | BC:24:11:76:57:F1 |
| **Role** | Backup target for all VMs/CTs |
| **Timezone** | America/Phoenix |
| **Tags** | backup, community-script |
| **⚠️** | PBS datastore is on the **same ZFS pool** as local-zfs VMs — SPOF |

---

## CT 101 — Radarr

| Field | Value |
|-------|-------|
| **Status** | Running |
| **vCPU** | 2 |
| **RAM** | 1 GB (+ 512 MB swap) |
| **RootFS** | 4 GB on local-zfs |
| **IP** | 192.168.1.129 |
| **MAC** | BC:24:11:18:61:C5 |
| **Role** | Media management / automation |
| **Timezone** | America/Phoenix |
| **Tags** | arr, community-script |

---

## CT 102 — iVentoy

| Field | Value |
|-------|-------|
| **Status** | Running |
| **vCPU** | 1 |
| **RAM** | 512 MB (+ 512 MB swap) |
| **RootFS** | 1 TB on local-zfs |
| **IP** | 192.168.1.184 |
| **MAC** | BC:24:11:6C:2D:ED |
| **Role** | Network boot / PXE server |
| **Timezone** | America/Phoenix |
| **Tags** | community-script, pxe-tool |
| **Privileged** | Yes (serial/USB passthrough for PXE boot devices) |
| **Notes** | Has USB/serial passthrough for BIOS-level PXE booting |

---

## CT 104 — Prometheus

| Field | Value |
|-------|-------|
| **Status** | Running |
| **vCPU** | 1 |
| **RAM** | 2 GB (+ 512 MB swap) |
| **RootFS** | 4 GB on local-zfs |
| **IP** | 192.168.1.170 |
| **MAC** | BC:24:11:A8:F4:4E |
| **Role** | Monitoring — scrapes pve01 (node_exporter + pve-exporter) |
| **Timezone** | America/Phoenix |
| **Tags** | community-script, monitoring |
| **Notes** | Currently marked as "unused?" in legacy docs — verify operational state |

---

## CT 105 — NetBox

| Field | Value |
|-------|-------|
| **Status** | Running |
| **vCPU** | 2 |
| **RAM** | 2 GB (+ 512 MB swap) |
| **RootFS** | 4 GB on local-zfs |
| **IP** | 192.168.1.33 |
| **MAC** | BC:24:11:D7:E1:23 |
| **Role** | DCIM / IPAM |
| **Timezone** | America/Phoenix |
| **Tags** | community-script, network |

---

## CT 106 — Checkmk

| Field | Value |
|-------|-------|
| **Status** | Running |
| **vCPU** | 2 |
| **RAM** | 2 GB (+ 512 MB swap) |
| **RootFS** | 6 GB on local-zfs |
| **IP** | 192.168.1.125 |
| **MAC** | BC:24:11:2A:F9:49 |
| **Role** | Infrastructure monitoring |
| **Timezone** | America/Phoenix |
| **Tags** | community-script, monitoring |

---

## CT 108 — Proxmox Mail Gateway

| Field | Value |
|-------|-------|
| **Status** | Running |
| **vCPU** | 2 |
| **RAM** | 4 GB (+ 512 MB swap) |
| **RootFS** | 10 GB on local-zfs |
| **IP** | 192.168.1.74 |
| **MAC** | BC:24:11:B9:37:7B |
| **Role** | Email filtering / anti-spam gateway |
| **Timezone** | America/Phoenix |
| **Tags** | community-script, mail |

---

## Related

- [[Infrastructure/Hypervisor]]
- [[Infrastructure/Storage]]

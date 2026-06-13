---
type: reference
status: active
date: 2026-05-21
tags: [infrastructure, proxmox, vms]
description: All virtual machines running on pve01
---

# Virtual Machines

## VM 103 — haos (Home Assistant OS)

| Field | Value |
|-------|-------|
| **Status** | Running |
| **OS** | Home Assistant OS 17.2 |
| **vCPU** | 2 (host mode) |
| **RAM** | 4 GB |
| **Boot Disk** | 32 GB on local-zfs (ZFS RAIDZ1) |
| **IP** | 192.168.1.112 |
| **MAC** | 02:35:AE:2D:28:FC |
| **Chipset** | q35, OVMF (UEFI) |
| **Agent** | QEMU agent enabled |
| **Auto-start** | Yes |
| **Notes** | Unused disk on qnap-storage (orphaned — removed from config but raw image still present) |

---

## VM 107 — DevServer

| Field | Value |
|-------|-------|
| **Status** | Running |
| **OS** | Ubuntu (via community-script) |
| **vCPU** | 4 (host mode, pinned to cores 0-3) |
| **RAM** | 12 GB (balloon min 1GB) |
| **Boot Disk** | 1031 GB on iscsi-qnap (iSCSI LUN over 10GbE, SSD flag) |
| **EFI Disk** | 4 MB on iscsi-qnap |
| **IP** | 192.168.1.226 |
| **MAC** | 02:21:43:61:49:0D |
| **Chipset** | q35, OVMF (UEFI) |
| **Agent** | QEMU agent enabled |
| **IO Thread** | Yes (virtio-scsi-pci) |
| **Hotplug** | CPU + memory |
| **NUMA** | Enabled (1 socket) |
| **Auto-start** | Yes |
| **Primary Role** | Self-hosted services, Hermes agent, Grafana, Docker host |

### Running Services (known)

- Hermes Agent (this AI)
- Grafana (192.168.1.226:3000)
- PostgreSQL (port 5433)
- Docker + containerd
- Various self-hosted Docker containers
- Open WebUI

---

## VM 109 — StagingServer

| Field | Value |
|-------|-------|
| **Status** | Running |
| **OS** | Ubuntu (via community-script) |
| **vCPU** | 8 (host mode, pinned to cores 4-7) |
| **RAM** | 12 GB |
| **Boot Disk** | 1031 GB on iscsi-qnap (iSCSI LUN over 10GbE, SSD flag) |
| **EFI Disk** | 4 MB on iscsi-qnap |
| **IP** | 192.168.1.121 |
| **MAC** | 02:C3:61:38:35:97 |
| **Chipset** | q35, OVMF (UEFI) |
| **Agent** | QEMU agent enabled |
| **IO Thread** | Yes (virtio-scsi-single) |
| **Hotplug** | CPU + memory |
| **NUMA** | Enabled (1 socket) |
| **Auto-start** | Yes |
| **Primary Role** | Staging/testing environment |

---

## Related

- [[Infrastructure/Hypervisor]]
- [[Infrastructure/Storage]]

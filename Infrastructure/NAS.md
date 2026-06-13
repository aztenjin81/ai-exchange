---
type: reference
status: active
date: 2026-05-21
tags: [infrastructure, storage, qnap, nas]
role: Network Attached Storage
ip_lan: 192.168.1.242
ip_storage: 192.168.100.10
os: QTS (unknown version)
model: QNAP (unknown model — TS-x53 series likely)
---

# NAS: QNAP (nas01)

## Network Interfaces

| Interface | IP | Services | Status |
|-----------|-----|----------|--------|
| LAN | 192.168.1.242 | QTS Web UI (8443/HTTPS) | Online |
| Storage | 192.168.100.10 | iSCSI (3260), QTS Web UI (8443/HTTPS), NFS | Online |

**SSH:** Closed on both interfaces. Management requires web UI at `https://nas01:8443` or enabling SSH.

## Services Provided

| Service | Target | Protocol | Notes |
|---------|--------|----------|-------|
| iSCSI LUN | pve01 (192.168.100.11) | iSCSI (3260) | 3TB LUN for DevServer + StagingServer VM disks |
| NFS export | pve01 | NFSv3 | `/PMVM` export, mounted as `qnap-storage` |
| QTS Web UI | Management | HTTPS (8443) | Full QTS admin interface |

## Storage Allocation

| Store | Volume | Used / Total | pve01 Pool |
|-------|--------|-------------|------------|
| iSCSI LUN | LVM VG `pve-iscsi` | ~2.06 TiB / 2.76 TiB | `iscsi-qnap` |
| NFS export | /PMVM | 611 GiB / 5.08 TiB | `qnap-storage` |
| **Total exposed to pve01** | | **~2.66 TiB / 7.84 TiB** | |

## Access Notes

- SSH is **disabled** on both interfaces
- Web UI at `https://192.168.1.242:8443` or `https://192.168.100.10:8443`
- To enable SSH management: log into QTS web UI → Control Panel → Telnet/SSH → Allow SSH
- Default SSH user is typically `admin`

## Related

- [[Infrastructure/Storage]]
- [[Infrastructure/Networking]]

---
type: reference
status: active
date: 2026-05-21
tags: [infrastructure, networking, unifi, topology]
description: Network topology, VLANs, switches, APs, and routing
---

# Networking

## Topology

```
Internet
  │
  └── UDM-SE (192.168.1.1) — Gateway, Router, DHCP, DNS relay
        │
        ├── USW Pro HD 24 PoE (192.168.1.206) — Core switch
        │     ├── pve01 bond0 (LACP, 2×10GbE)
        │     ├── QNAP NAS (192.168.1.242) — LAN
        │     ├── U6 Enterprise AP — WiFi 6
        │     ├── U6 Mesh AP — WiFi 6 mesh
        │     ├── US-8-60W (192.168.1.233) — Office switch
        │     └── Various wired clients
        │
        └── VLANs / subnets:
              ├── 192.168.1.0/24 — Main LAN
              └── 192.168.100.0/24 — Storage (10GbE, MTU 9000)
```

## Hardware

| Device | Model | IP | Role |
|--------|-------|-----|------|
| UDM-SE | Ubiquiti Dream Machine SE | 192.168.1.1 | Gateway, router, security, DHCP |
| USW Pro HD 24 PoE | UniFi Switch Pro HD 24 PoE | 192.168.1.206 | Core switch (aggregation) |
| US-8-60W | UniFi Switch 8 60W | 192.168.1.233 | Secondary switch |
| U6 Enterprise | UniFi 6 Enterprise | — | Primary WiFi AP |
| U6 Mesh | UniFi 6 Mesh | — | Mesh WiFi AP |
| pve01 | Proxmox host | 192.168.1.5 | Hypervisor (LACP bond to core) |
| Pi-hole | — | 192.168.1.2 | DNS (relayed via UDM-SE) |

## DNS

- **Primary:** UDM-SE (192.168.1.1) with Pi-hole relay (192.168.1.2)
- **Search domain:** home.local
- **MDNS:** Active — most devices register `.localdomain` names

## DHCP

- **Server:** UDM-SE
- **Scope:** 192.168.1.0/24
- **All VMs/CTs use DHCP** (no static IPs assigned at hypervisor level)
- **Some static devices:** pve01 (192.168.1.5), pve01-storage (192.168.100.11), QNAP-LAN (192.168.1.242), QNAP-Storage (192.168.100.10)

## Storage Network (192.168.100.0/24)

| Device | IP | Interface | MTU |
|--------|----|-----------|-----|
| QNAP NAS | 192.168.100.10 | enp1s0 | 9000 |
| pve01 | 192.168.100.11 | enp1s0 | 9000 |
| UDM-SE (?) | 192.168.100.1 | — | — |

Isolated network for iSCSI + NFS traffic. No routing to main LAN (no default gateway configured on enp1s0).

## Related

- [[Infrastructure/Network-Devices]] — full client inventory
- [[Infrastructure/Hypervisor]]
- [[Infrastructure/NAS]]

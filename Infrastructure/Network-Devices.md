---
type: reference
status: active
date: 2026-05-21
tags: [infrastructure, networking, iot, clients]
description: All discovered network clients — IoT, endpoints, servers, and infrastructure gear
---

# Network Devices

> Discovered via nmap scan of 192.168.1.0/24 and 192.168.100.0/24 from pve01 on 2026-05-21. Some IPs have limited identification.

## Infrastructure & Servers

| IP | Hostname | Type | Notes |
|----|----------|------|-------|
| 192.168.1.1 | unifi | UDM-SE | Gateway, router, DHCP |
| 192.168.1.2 | (pihole) | Pi-hole | DNS resolver (likely .2) |
| 192.168.1.5 | pve01 | Proxmox Host | [[Infrastructure/Hypervisor]] |
| 192.168.1.33 | netbox | LXC | [[Infrastructure/Containers#CT 105 — NetBox]] |
| 192.168.1.74 | proxmox-mail-gateway | LXC | [[Infrastructure/Containers#CT 108 — Proxmox Mail Gateway]] |
| 192.168.1.112 | homeassistant | VM | [[Infrastructure/Virtual-Machines#VM 103 — haos (Home Assistant OS)]] |
| 192.168.1.121 | staging | VM | [[Infrastructure/Virtual-Machines#VM 109 — StagingServer]] |
| 192.168.1.125 | checkmk | LXC | [[Infrastructure/Containers#CT 106 — Checkmk]] |
| 192.168.1.129 | radarr | LXC | [[Infrastructure/Containers#CT 101 — Radarr]] |
| 192.168.1.163 | proxmox-backup-server | LXC | [[Infrastructure/Containers#CT 100 — Proxmox Backup Server]] |
| 192.168.1.170 | prometheus | LXC | [[Infrastructure/Containers#CT 104 — Prometheus]] |
| 192.168.1.184 | iventoy | LXC | [[Infrastructure/Containers#CT 102 — iVentoy]] |
| 192.168.1.206 | USW-Pro-HD-24-PoE | UniFi Switch | Core switch |
| 192.168.1.226 | grafana (DevServer) | VM | [[Infrastructure/Virtual-Machines#VM 107 — DevServer]] |
| 192.168.1.233 | US-8-60W | UniFi Switch | Secondary switch |
| 192.168.1.242 | nas01 | QNAP NAS | [[Infrastructure/NAS]] |

## UniFi Access Points & Mesh

| IP | Hostname | Type |
|----|----------|------|
| 192.168.1.28 | DataCloset | AP / switch |
| 192.168.1.61 | LivingRoom | AP / device |
| 192.168.1.80 | Upstairs | AP / device |
| 192.168.1.131 | Downstairs | AP / device |
| 192.168.1.137 | JohnsOffice | AP / device |
| 192.168.1.189 | StephaniesOffice | AP / device |

## Smart Home & IoT

| IP | Hostname | Likely Device |
|----|----------|---------------|
| 192.168.1.29 | GE_Light_6AD7 | GE Cync smart bulb |
| 192.168.1.78 | HS200 | Kasa smart switch (HS200) |
| 192.168.1.134 | GE_Light_E19C | GE Cync smart bulb |
| 192.168.1.148 | LG_Smart_Oven2 | LG smart oven |
| 192.168.1.150 | LG_Smart_Laundry2 | LG smart washer |
| 192.168.1.151 | SimpliSafe_Basestation | SimpliSafe alarm base |
| 192.168.1.161 | KS200M | Kasa smart switch (KS200M) |
| 192.168.1.167 | LG_Smart_Dryer2 | LG smart dryer |
| 192.168.1.190 | ESP-30BD34 | ESP32/8266 custom device |
| 192.168.1.191 | Emporia | Emporia energy monitor |
| 192.168.1.193 | solar-assistant | SolarAssistant (solar monitoring) |
| 192.168.1.217 | MyQ-6C1 | Chamberlain MyQ garage opener |
| 192.168.1.223 | HS220 | Kasa smart dimmer (HS220) |
| 192.168.1.232 | GE_Light_FEA7 | GE Cync smart bulb |
| 192.168.1.241 | HS210 | Kasa smart switch (HS210) |

## Ring Cameras

| IP | Hostname | Likely Device |
|----|----------|---------------|
| 192.168.1.81 | Ring-649a63764617 | Ring camera |
| 192.168.1.89 | Ring-649a635C2FA1 | Ring camera |
| 192.168.1.120 | Ring-649a6348EA43 | Ring camera |
| 192.168.1.124 | Ring-649a6348FF7F | Ring camera |
| 192.168.1.139 | Ring-649a6353201F | Ring camera |
| 192.168.1.222 | Ring-649a6353A29F | Ring camera |

## Endpoints & Personal Devices

| IP | Hostname | Likely Device |
|----|----------|---------------|
| 192.168.1.32 | StephanesiPhone | iPhone |
| 192.168.1.34 | amazon-b77ae193e | Amazon device (Echo?) |
| 192.168.1.49 | MacBookPro | MacBook Pro |
| 192.168.1.57 | XBOX | Xbox console |
| 192.168.1.84 | wlan0 | Unknown wireless client |
| 192.168.1.143 | Anker | Anker device (speaker/charger?) |
| 192.168.1.188 | Mac | Another Mac |
| 192.168.1.230 | amazon-ac997af46 | Amazon device (Echo?) |
| 192.168.1.234 | hopscotch | Unknown (HopScotch?) |

## Unidentified IPs

These IPs have no hostname resolution and need manual identification:

`192.168.1.22, .26, .27, .36, .50, .51, .55, .66, .72, .95, .113, .119, .122, .123, .135, .136, .147, .155, .156, .159, .160, .162, .165, .180, .185, .252, .253`

## Storage Network (192.168.100.0/24)

| IP | Hostname | Device |
|----|----------|--------|
| 192.168.100.1 | unifi | UDM-SE (storage VLAN interface) |
| 192.168.100.10 | — | QNAP NAS (storage interface) |
| 192.168.100.11 | — | pve01 (enp1s0 storage interface) |

## Related

- [[Infrastructure/Networking]]
- [[Infrastructure/NAS]]

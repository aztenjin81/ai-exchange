---
type: server
status: running
host: pve01
ip: 192.168.1.5
os: "Proxmox VE 8.x"
role: "Development, self-hosted services"
vcpu: 4
memory_gb: 8
vm_id: 107
kernel: 6.17.13-2-pve
uptime_sec: 220920
date: 2026-05-16
tags: [pve01, proxmox, dev, linux]
---
# DevServer (VM 107)

Development server hosting Hermes agent, Grafana, Docker services.

## Services

- Hermes agent
- Grafana + Prometheus stack
- Docker containers
- PostgreSQL (port 5433)

## Related

- [[Infrastructure]]
- [[Cron-Jobs]]

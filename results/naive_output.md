*Research current as of September 24, 2026.*

| Topic | What it is | Started | Recent development |
|---|---|---:|---|
| Docker | Docker is a container platform that uses operating-system-level virtualization to package and run applications with their dependencies in lightweight, portable containers. | 2013 | Docker announced the public beta of **Docker VMM**, a rebuilt virtualization layer for Docker Desktop on Mac and Windows, on August 12, 2026. |
| Kubernetes | Kubernetes is an open-source container-orchestration system that automates deployment, scaling, networking, and management of containerized workloads across clusters. | 2014 | **Kubernetes v1.37** was released on August 26, 2026, including general availability of Dynamic Resource Allocation Extended Resource support. |
| Linux | Linux is a family of free and open-source Unix-like operating systems built around the Linux kernel and commonly distributed as complete operating-system distributions. | 1991 | **Linux kernel 7.3-rc4**, the fourth release candidate in the 7.3 development cycle, was published on September 20, 2026. |

## Summary

Together, these technologies form three layers of the modern computing stack. Linux is the foundation: an open-source Unix-like operating-system family whose kernel manages hardware, processes, memory, networking, and the namespace and cgroup facilities used by containers. Docker builds on that foundation to solve application packaging and portability. It turns software and dependencies into images that run as isolated containers, giving developers a consistent environment from laptop to server. Kubernetes operates at a higher level, coordinating many containers across a cluster and automating scheduling, scaling, service discovery, recovery, and rollout management.

Their start dates also reflect the stack’s evolution. Linux began in 1991 as a kernel and grew into a broad ecosystem powering servers, desktops, embedded devices, Android, and cloud infrastructure. Docker arrived in 2013 and popularized container workflows. Kubernetes followed in 2014 as organizations needed to manage containers at production scale.

Their latest developments show different priorities. Docker is improving the local virtualization layer behind Desktop; Kubernetes v1.37 is maturing dynamic hardware-resource allocation; and Linux continues rapid kernel development with the 7.3 release-candidate cycle. In short, Linux supplies the operating-system base, Docker simplifies packaging and running individual workloads, and Kubernetes orchestrates those workloads across fleets of machines. They are complementary rather than direct substitutes.
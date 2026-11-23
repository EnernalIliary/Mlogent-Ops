#!/bin/sh
# The ArcNet backend binds wildcard addresses. Only the local proxy may reach it.
# Run as root before starting the world supervisor, on every service start.
set -eu
for firewall in /usr/sbin/iptables /usr/sbin/ip6tables; do
    for protocol in tcp udp; do
        if ! "$firewall" -w -C INPUT ! -i lo -p "$protocol" --dport 16567 -j REJECT 2>/dev/null; then
            "$firewall" -w -I INPUT 1 ! -i lo -p "$protocol" --dport 16567 -j REJECT
        fi
    done
done

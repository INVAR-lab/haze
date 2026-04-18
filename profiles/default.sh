#!/bin/bash
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq

apt-get upgrade -y -qq || true

apt-get install -y -qq \
  curl wget git vim tmux jq unzip zip htop screen \
  nmap netcat-openbsd socat net-tools dnsutils \
  tcpdump traceroute whois iputils-ping \
  python3 python3-pip \
  build-essential gcc make

chmod -x /etc/update-motd.d/*
touch /root/.hushlogin

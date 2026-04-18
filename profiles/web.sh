#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

apt-get install -y -qq ffuf sqlmap nikto whatweb wafw00f

pip3 install -q ghauri

GO_VERSION="1.22.0"
curl -sL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" | tar -C /usr/local -xz
export PATH=$PATH:/usr/local/go/bin
echo 'export PATH=$PATH:/usr/local/go/bin:/root/go/bin' >> /root/.bashrc

go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest      2>/dev/null
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest 2>/dev/null
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest 2>/dev/null

/root/go/bin/nuclei -update-templates -silent 2>/dev/null || true

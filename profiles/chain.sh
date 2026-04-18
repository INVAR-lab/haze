#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

apt-get install -y -qq socat openvpn easy-rsa

# chisel
CHISEL_VERSION=$(curl -s https://api.github.com/repos/jpillora/chisel/releases/latest | grep tag_name | cut -d'"' -f4)
curl -sL "https://github.com/jpillora/chisel/releases/download/${CHISEL_VERSION}/chisel_${CHISEL_VERSION#v}_linux_amd64.gz" | gunzip > /usr/local/bin/chisel
chmod +x /usr/local/bin/chisel

# ligolo-ng
LIGOLO_VERSION=$(curl -s https://api.github.com/repos/nicocha30/ligolo-ng/releases/latest | grep tag_name | cut -d'"' -f4)
curl -sL "https://github.com/nicocha30/ligolo-ng/releases/download/${LIGOLO_VERSION}/ligolo-ng_proxy_${LIGOLO_VERSION#v}_linux_amd64.tar.gz" | tar -xz -C /usr/local/bin/ proxy 2>/dev/null || true
chmod +x /usr/local/bin/proxy 2>/dev/null || true

# cloudflared
curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# openvpn pki
make-cadir /etc/openvpn/easy-rsa
cd /etc/openvpn/easy-rsa
./easyrsa init-pki          2>/dev/null
./easyrsa --batch build-ca nopass 2>/dev/null
./easyrsa --batch gen-req server nopass 2>/dev/null
./easyrsa --batch sign-req server server 2>/dev/null
./easyrsa gen-dh            2>/dev/null
./easyrsa --batch gen-req client nopass 2>/dev/null
./easyrsa --batch sign-req client client 2>/dev/null
openvpn --genkey secret /etc/openvpn/ta.key

SERVER_IP=$(curl -s ifconfig.me)

cat > /etc/openvpn/server.conf << EOF
port 1194
proto udp
dev tun
ca /etc/openvpn/easy-rsa/pki/ca.crt
cert /etc/openvpn/easy-rsa/pki/issued/server.crt
key /etc/openvpn/easy-rsa/pki/private/server.key
dh /etc/openvpn/easy-rsa/pki/dh.pem
tls-auth /etc/openvpn/ta.key 0
server 10.8.0.0 255.255.255.0
push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 8.8.8.8"
keepalive 10 120
cipher AES-256-GCM
persist-key
persist-tun
status /var/log/openvpn-status.log
verb 3
EOF

systemctl enable openvpn@server
systemctl start  openvpn@server

# generate client.ovpn
cat > /root/client.ovpn << EOF
client
dev tun
proto udp
remote ${SERVER_IP} 1194
resolv-retry infinite
nobind
persist-key
persist-tun
cipher AES-256-GCM
verb 3
<ca>
$(cat /etc/openvpn/easy-rsa/pki/ca.crt)
</ca>
<cert>
$(cat /etc/openvpn/easy-rsa/pki/issued/client.crt)
</cert>
<key>
$(cat /etc/openvpn/easy-rsa/pki/private/client.key)
</key>
<tls-auth>
$(cat /etc/openvpn/ta.key)
</tls-auth>
key-direction 1
EOF

echo "[chain] client.ovpn ready at /root/client.ovpn"
echo "[chain] run: haze pull <name> /root/client.ovpn"

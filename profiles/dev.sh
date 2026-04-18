#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

apt-get install -y -qq docker.io docker-compose

systemctl enable docker
systemctl start  docker

mkdir -p /root/lab

cat > /root/lab/docker-compose.yml << 'EOF'
version: "3.8"
services:
  db:
    image: mysql:8.0
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: haze
      MYSQL_DATABASE: wordpress
      MYSQL_USER: wordpress
      MYSQL_PASSWORD: haze
    volumes:
      - db_data:/var/lib/mysql

  wordpress:
    image: wordpress:latest
    restart: always
    ports:
      - "8080:80"
    environment:
      WORDPRESS_DB_HOST: db
      WORDPRESS_DB_USER: wordpress
      WORDPRESS_DB_PASSWORD: haze
      WORDPRESS_DB_NAME: wordpress
    volumes:
      - wp_data:/var/www/html

volumes:
  db_data:
  wp_data:
EOF

cd /root/lab && docker-compose up -d

curl -sL https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar -o /usr/local/bin/wp
chmod +x /usr/local/bin/wp

echo "[dev] WordPress running on :8080"
echo "[dev] run: haze forward <n> 8080:8080"

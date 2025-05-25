#!/bin/bash
set -eux

# Adoptium（Eclipse Temurin）リポジトリ追加とJava 21インストール
mkdir -p /etc/apt/keyrings
wget -O- https://packages.adoptium.net/artifactory/api/gpg/key/public | tee /etc/apt/keyrings/adoptium.asc

echo "deb [signed-by=/etc/apt/keyrings/adoptium.asc] https://packages.adoptium.net/artifactory/deb bookworm main" > /etc/apt/sources.list.d/adoptium.list

apt-get update
debian_frontend=noninteractive apt-get install -y temurin-21-jre wget screen

# Minecraftサーバーディレクトリ作成
mkdir -p /opt/minecraft
cd /opt/minecraft

# サーバーJARダウンロード（バニラ1.20.6）
wget -O server.jar https://piston-data.mojang.com/v1/objects/e6ec2f64e6080b9b5d9b471b291c33cc7f509733/server.jar

# EULA同意
echo 'eula=true' > eula.txt

# server.properties作成/編集（query有効化）
grep -q '^enable-query=' server.properties 2>/dev/null && sed -i 's/^enable-query=.*/enable-query=true/' server.properties || echo 'enable-query=true' >> server.properties
grep -q '^query.port=' server.properties 2>/dev/null || echo 'query.port=25565' >> server.properties

# サーバー起動（screenでデタッチ）
screen -dmS minecraft java -Xmx1536M -Xms1536M -jar server.jar nogui 
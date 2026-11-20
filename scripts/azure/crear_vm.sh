#!/usr/bin/env bash
# Crea la VM del proyecto en Azure con la CLI (az). Requiere `az login` y rol Owner o Contributor
# en la suscripción. Es el mismo procedimiento con el que se creó la VM de la demo.
#
#   SUBSCRIPTION=<id> ./scripts/azure/crear_vm.sh
#   SUBSCRIPTION=<id> RG=rg-chatbot-unab VM=vm-chatbot-unab LOCATION=northcentralus ./scripts/azure/crear_vm.sh
set -euo pipefail
: "${SUBSCRIPTION:?Define SUBSCRIPTION con el ID de tu suscripción}"
RG="${RG:-rg-chatbot-unab}"
VM="${VM:-vm-chatbot-unab}"
LOCATION="${LOCATION:-northcentralus}"   # Azure for Students: westus, northcentralus, canadacentral, francecentral, belgiumcentral
SIZE="${SIZE:-Standard_B2as_v2}"          # 2 vCPU, 8 GB: Ollama (2 modelos) + n8n + PostgreSQL + Expo
ADMIN="${ADMIN:-azureuser}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa.pub}"
MY_IP="${MY_IP:-$(curl -s https://api.ipify.org)}"

az account set --subscription "$SUBSCRIPTION"
az group create -n "$RG" -l "$LOCATION" -o none

# IP pública estática y disco StandardSSD (evita el cupo de discos HDD de la suscripción)
az vm create -g "$RG" -n "$VM" -l "$LOCATION" \
  --image Ubuntu2404 --size "$SIZE" \
  --admin-username "$ADMIN" --ssh-key-values "$SSH_KEY" \
  --public-ip-sku Standard --public-ip-address-allocation static \
  --storage-sku StandardSSD_LRS --os-disk-size-gb 64 \
  --nsg-rule NONE -o none

NSG=$(az network nsg list -g "$RG" --query "[0].name" -o tsv)
# SSH solo desde tu IP; la app y n8n abiertos a Internet
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n ssh-mi-ip --priority 1000 \
  --source-address-prefixes "$MY_IP/32" --destination-port-ranges 22 --protocol Tcp --access Allow -o none
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n app-puertos --priority 1010 \
  --source-address-prefixes Internet --destination-port-ranges 9000 9001 9002 8081 --protocol Tcp --access Allow -o none

IP=$(az vm show -d -g "$RG" -n "$VM" --query publicIps -o tsv)
echo "VM lista: ssh $ADMIN@$IP"
echo "Apagar sin costo de cómputo: az vm deallocate -g $RG -n $VM   |   Encender: az vm start -g $RG -n $VM"

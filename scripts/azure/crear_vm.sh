#!/usr/bin/env bash
# Crea la VM del proyecto en Azure con la CLI (az), igual que la VM de la demo.
# Requiere `az login` y rol Owner o Contributor en la suscripción.
#
#   SUBSCRIPTION=<id> ADMIN_PASSWORD='<clave>' ./scripts/azure/crear_vm.sh
#
# Después: instalar Docker, clonar el repo y seguir "Instalación" del README; para el túnel de Cloudflare,
# `sudo cloudflared service install <token>` (token en Zero Trust → Networks → Tunnels → Configure).
set -euo pipefail
: "${SUBSCRIPTION:?Define SUBSCRIPTION con el ID de tu suscripción}"
: "${ADMIN_PASSWORD:?Define ADMIN_PASSWORD (el acceso SSH es solo con contraseña)}"
RG="${RG:-rg-chatbot-unab}"
VM="${VM:-vm-chatbot-unab}"
LOCATION="${LOCATION:-northcentralus}"   # Azure for Students: westus, northcentralus, canadacentral, francecentral, belgiumcentral
SIZE="${SIZE:-Standard_B2as_v2}"          # 2 vCPU, 8 GB: Ollama (3 modelos) + n8n + PostgreSQL + Expo
ADMIN="${ADMIN:-azureuser}"

az account set --subscription "$SUBSCRIPTION"
az group create -n "$RG" -l "$LOCATION" -o none

# IP pública estática, disco StandardSSD y acceso con contraseña
az vm create -g "$RG" -n "$VM" -l "$LOCATION" \
  --image Ubuntu2404 --size "$SIZE" \
  --admin-username "$ADMIN" --authentication-type password --admin-password "$ADMIN_PASSWORD" \
  --public-ip-sku Standard --public-ip-address-allocation static \
  --storage-sku StandardSSD_LRS --os-disk-size-gb 64 \
  --nsg-rule NONE -o none

NSG=$(az network nsg list -g "$RG" --query "[0].name" -o tsv)
# SSH (22) y n8n (9000, "servicios HTTP streamables") abiertos; el resto se publica por el túnel de Cloudflare
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n ssh --priority 1000 \
  --source-address-prefixes '*' --destination-port-ranges 22 --protocol Tcp --access Allow -o none
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n n8n-9000 --priority 1010 \
  --source-address-prefixes '*' --destination-port-ranges 9000 --protocol Tcp --access Allow -o none

IP=$(az vm show -d -g "$RG" -n "$VM" --query publicIps -o tsv)
echo "VM lista: ssh $ADMIN@$IP"
echo "Apagar sin costo de cómputo: az vm deallocate -g $RG -n $VM   |   Encender: az vm start -g $RG -n $VM"
echo "Recomendado: az lock create -g $RG -n no-borrar --lock-type CanNotDelete  (evita borrados accidentales)"

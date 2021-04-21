cp ./tempkey.pem ~/.ssh/
cp ./tempkey.pub ~/.ssh/
git clone https://github.com/fretbuzz/KubesprayClusterOnCloudlab.git
cd ~/KubesprayClusterOnCloudlab
bash setup_kubespray_prereqs.sh
bash deploy_kubespray.sh -c

# bash deploy_sockshop.sh
sudo pip3 install influxdb

kubectl apply -f basic_cadvisor.yaml
# kubectl apply -f 
# kubectl get svc front-end --namespace="sock-shop"

export CILIUM_NAMESPACE=kube-system
export HUBBLE_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/hubble/master/stable.txt)

curl -LO "https://github.com/cilium/hubble/releases/download/$HUBBLE_VERSION/hubble-linux-amd64.tar.gz"
curl -LO "https://github.com/cilium/hubble/releases/download/$HUBBLE_VERSION/hubble-linux-amd64.tar.gz.sha256sum"
sha256sum --check hubble-linux-amd64.tar.gz.sha256sum
tar zxf hubble-linux-amd64.tar.gz

sudo mv hubble /usr/local/bin

kubectl port-forward -n $CILIUM_NAMESPACE svc/hubble-relay --address 0.0.0.0 --address :: 4245:80 &

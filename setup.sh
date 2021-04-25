cp ./tempkey.pem ~/.ssh/
cp ./tempkey.pub ~/.ssh/

cd ~/KubesprayClusterOnCloudlab
bash setup_kubespray_prereqs.sh
bash deploy_kubespray.sh -c

sudo pip3 install influxdb

export CILIUM_NAMESPACE=kube-system
export HUBBLE_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/hubble/master/stable.txt)

curl -LO "https://github.com/cilium/hubble/releases/download/$HUBBLE_VERSION/hubble-linux-amd64.tar.gz"
curl -LO "https://github.com/cilium/hubble/releases/download/$HUBBLE_VERSION/hubble-linux-amd64.tar.gz.sha256sum"
sha256sum --check hubble-linux-amd64.tar.gz.sha256sum
tar zxf hubble-linux-amd64.tar.gz

sudo mv hubble /usr/local/bin

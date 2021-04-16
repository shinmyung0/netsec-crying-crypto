cilium_p=$1

cd /mydata/
sudo chown -R jsev ./
set +e
if cd /mydata/mimir_snakemake_t2;
then cd ..;
else git clone https://github.com/fretbuzz/mimir_snakemake_t2;
fi

echo "more stuff"
vboxmanage setproperty machinefolder /mydata/
echo "test"
sudo usermod -aG docker $USER
echo "testtest"
newgrp docker <<EONG

export MINIKUBE_HOME=/mydata
#minikube stop
#minikube delete

# Setup KVM2 driver
echo "even more stuff"
sudo apt-get update
sudo apt install -y libvirt-bin libvirt-daemon-system qemu-kvm
sudo usermod -a -G libvirtd $(whoami)
newgrp libvirtd

# there is a new docker overlay driver, i don't like it. I'm going to switch it for a different one
echo {\"storage-driver\": \"vfs\"} > /etc/docker/daemon.json
sudo systemctl stop docker
sudo systemctl start docker

# Install KVM2 driver
echo "even even more stuff"
curl -Lo docker-machine-driver-kvm2 https://storage.googleapis.com/minikube/releases/latest/docker-machine-driver-kvm2 \
&& chmod +x docker-machine-driver-kvm2 \
&& sudo cp docker-machine-driver-kvm2 /usr/local/bin/ \
&& rm docker-machine-driver-kvm2

# start minikube
export MINIKUBE_HOME=/mydata
pip install cython
sudo pip install pycrypto
pip install kubernetes
pip install selenium
pip install netifaces
#apt-get install -y wireshark # do not want actually

#minikube start --vm-driver kvm2 --cpus=16 --memory=100000 --disk-size 65g

if [ "$cilium_p" = "True" ]; then
    echo "starting minikube with cilium"
    minikube start --network-plugin=cni --extra-config=kubelet.network-plugin=cni --cpus=12 --memory=32000 --disk-size 65g
    kubectl create -n kube-system -f https://raw.githubusercontent.com/cilium/cilium/v1.3/examples/kubernetes/addons/etcd/standalone-etcd.yaml
    python /mydata/mimir_snakemake_t2/experiment_coordinator/former_profile/kubernetes_setup_functions.py kube-system
    kubectl create -f https://raw.githubusercontent.com/cilium/cilium/v1.3/examples/kubernetes/1.10/cilium.yaml
else
    minikube start --cpus=12 --memory=32000 --disk-size 65g
fi

echo "At end"
EONG


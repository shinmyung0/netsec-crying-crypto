# NOTE: need to run with sudo (!!!)

sudo apt-get update
#sudo apt install snapd
#sudo snap install kubectl --classic
sudo apt-get update 

sudo apt-get install -y apt-transport-https

sudo curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -


#  start one command
sudo cat <<EOF >/etc/apt/sources.list.d/kubernetes.list
deb http://apt.kubernetes.io/ kubernetes-xenial main
EOF



# end one command
apt-get update
#apt-get install -y kubectl #v 1.11 causes problems...
curl -LO https://storage.googleapis.com/kubernetes-release/release/v1.8.7/bin/linux/amd64/kubectl
chmod +x ./kubectl
sudo mv ./kubectl /usr/local/bin/kubectl
curl -Lo minikube https://storage.googleapis.com/minikube/releases/v0.27.0/minikube-linux-amd64 && chmod +x minikube && sudo mv minikube /usr/local/bin/
# need to install virtual box b/c dependencies :/ (from https://askubuntu.com/questions/779095/install-virtualbox-on-ubuntu-16-04-lts)

if grep -Fxq "deb http://download.virtualbox.org/virtualbox/debian xenial contrib" /etc/apt/sources.list
then
    echo "already knows where to get virtualbox"
else
    # need to tell the system where to get virtualbox
    echo "deb http://download.virtualbox.org/virtualbox/debian xenial contrib" >> /etc/apt/sources.list
fi

#Fetch the GPG key
wget -q https://www.virtualbox.org/download/oracle_vbox_2016.asc -O- | sudo apt-key add -
#Install the package
sudo apt-get update 
sudo apt-get install -y virtualbox-5.1

curl -Lo minikube https://storage.googleapis.com/minikube/releases/v0.28.0/minikube-linux-amd64 && chmod +x minikube && sudo mv minikube /usr/local/bin/

# okay, let's install helm now
wget https://storage.googleapis.com/kubernetes-helm/helm-v2.9.1-linux-amd64.tar.gz
tar -xvf helm-v2.9.1-linux-amd64.tar.gz
export PATH=$PATH:$(pwd)/linux-amd64

cp ./tempkey.pem ~/.ssh/
cp ./tempkey.pub ~/.ssh/
cd KubesprayClusterOnCloudlab
bash setup_kubespray_prereqs.sh
cd ~/KubesprayClusterOnCloudlab
bash deploy_kubespray.sh
bash deploy_sockshop.sh
sudo pip3 install influxdb
kubectl apply -f basic_cadvisor.yaml
kubectl get svc front-end --namespace="sock-shop"

steps

0. use sftp to upload the project into the host server. it will be easier than you adding rsa keys and chaning some code. I recommend seting up sftp extension on vscode.
1. add tempkey.pem/tempkey.pub to the root folder of this project.
    refer to instruction in Joseph's scripts. 
        4. Manually setup passwordless-SSH:
        2. Store your cloudlab private key in tempkey.pem. Do this by first creating a new file called tempkey.pem (if it doesn't already exist). Then, get your cloudlab private key by going to https://www.cloudlab.us/, pressing “Download Credentials”, and copy-pasting the whole file up to and including the “END RSA PRIVATE KEY” line into tempkey.pem. 
        3. Put your Cloudlab public key in tempkey.pub (can get from https://www.cloudlab.us/ssh-keys.php)

- run `bash setup.sh`, it will move your key to ~/.ssh


cadvisor
- replace `{HOST}` in basic_cadvisor.yaml with the host dns. e.g. ms1308.utah.cloudlab.us. run `kubectl apply -f basic_cadvisor.yaml` to deploy advisor.

- create database "cadvisor" in influxdb. command to access the database is "influx". 
```
CREATE DATABASE cadvisor
```
- `python3 influx_csv_dumper.py -db cadvisor -tl 15m` to export metrics. -tl is the Length of time for the dump.

run test
- Prepare the application by populating the database. Move to the relevant directory via cd ./experiment_coordinator/ and then running sudo python -u run_experiment.py --use_k3s_cluster --no_exfil --prepare_app --return_after_prepare_p --config_file ../sockshop_experiment.json --localhostip FRONT-END-CLUSTER-IP --localport 80 | tee sockshop_four_140.log, where FRONT-END-CLUSTER-IP is the clusterIP of the front-end service, which can be seen by running kubectl get svc front-end --namespace="sock-shop" and looking at the CLUSTER-IP column
- Generate load (warning: this takes a long time and a lot of cpu): sudo python -u run_experiment.py --use_k3s_cluster --no_exfil --config_file ../sockshop_experiment.json --localhostip FRONT-END-CLUSTER-IP --localport 80

Note: In ~/KubesprayClusterOnCloudlab/sockshop_experiment.json #root.experiment_length_sec, control the experiment time. e.g. You can set it to 3600( 1 hour )

flow logs
console1:
```
kubectl -n kube-system port-forward service/hubble-relay --address 0.0.0.0 --address :: 4245:80
// run and write log into a file
kubectl -n kube-system port-forward service/hubble-relay --address 0.0.0.0 --address :: 4245:80 >> flows.log
```
check relay
console2:
```
hubble status --server localhost:4245
```
kube
- to deploy kube follow jospeh script, step 1 - 6. https://github.com/fretbuzz/KubesprayClusterOnCloudlab
*make sure on step 6 to use -c flag. for example,
```
bash deploy_kubespray.sh -c
```
    
sockshop
- to deploy sockshop. step 8. `bash deploy_sockshop.sh`

cadvisor
- replace `{HOST}` in basic_cadvisor.yaml with the host dns. e.g. ms1308.utah.cloudlab.us. run `kubectl apply -f basic_cadvisor.yaml` to deploy advisor.

- create database "cadvisor" in influxdb. command to access the database is "influx". 
```
create database cadvisor
```

collect metric from cadvisor
- `sudo pip3 install influxdb` install lib.
- `python3 influx_csv_dumper.py -db cadvisor -tl 15m` to export metrics. -tl is the Length of time for the dump.

install hubble
- `bash hubble.sh`, install hubble.


collect hubble flow logs
```
kubectl -n kube-system port-forward service/hubble-relay --address 0.0.0.0 --address :: 4245:80
```

check relay
```
hubble status --server localhost:4245
```

hubble health check:
```
sudo hubble status
```

see flows logs:
```
sudo hubble observe -f
```

write flows logs to a file:
```
sudo hubble observe -f > hubble_access.log
```

run test
- replace ~/KubesprayClusterOnCloudlab/experiment_coordinator/sockshop_setup/sockshop_modified.yaml with ~/sockshop_modified.yaml

- Refer to joseph's script, step 9-10.
9. Prepare the application by populating the database. Move to the relevant directory via `cd ./experiment_coordinator/` and then running `sudo python -u run_experiment.py --use_k3s_cluster --no_exfil --prepare_app --return_after_prepare_p --config_file ../sockshop_experiment.json --localhostip FRONT-END-CLUSTER-IP --localport 80 | tee sockshop_four_140.log`, where FRONT-END-CLUSTER-IP is the clusterIP of the front-end service, which can be seen by running `kubectl get svc front-end --namespace="sock-shop"` and looking at the CLUSTER-IP column
e.g.
`sudo python -u run_experiment.py --use_k3s_cluster --no_exfil --prepare_app --return_after_prepare_p --config_file ../sockshop_experiment.json --localhostip 10.233.13.184  --localport 80 | tee sockshop_four_140.log`

10. Generate load (warning: this takes a long time and a lot of cpu): `sudo python -u run_experiment.py --use_k3s_cluster --no_exfil --config_file ../sockshop_experiment.json --localhostip FRONT-END-CLUSTER-IP --localport 80`
e.g.
`sudo python -u run_experiment.py --use_k3s_cluster --no_exfil --config_file ../sockshop_experiment.json --localhostip 10.233.13.184 --localport 80`

Note: In ~/KubesprayClusterOnCloudlab/sockshop_experiment.json #root.experiment_length_sec, control the experiment time. e.g. You can set it to 3600( 1 hour )

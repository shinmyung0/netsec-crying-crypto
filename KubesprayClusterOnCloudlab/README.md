Step-by-step instructions to easily deploy kubespray cluster on Cloudlab. 

There is also support for deploying the Sockshop microservice application onto the cluster and simulating user activity.

----
NOTE: SSH connections to Cloudlab time out all the time. If the terminal looks frozen, just start a new one, navigate to the correct directory, and keep following the steps. Usually the command kept running in the background.

# Instructions
1. Create new experiment on Cloudlab using the “small-lan” profile (3 hosts) and Wisconsin cluster (if Wisconsin cluster is full, feel free to use other clusters)
    * Should boot up quickly (within a few minutes)
2. Clone this repo and move into the corresponding directory
    1. Run: `git clone https://github.com/fretbuzz/KubesprayClusterOnCloudlab.git`
    2. Run: `cd KubesprayClusterOnCloudlab`
3. Run: `bash setup_kubespray_prereqs.sh`
4. Manually setup passwordless-SSH:
    1. `cd ~/.ssh/`
    2. Store your cloudlab private key in tempkey.pem. Do this by first creating a new file called tempkey.pem (if it doesn't already exist). Then, get your cloudlab private key by going to https://www.cloudlab.us/, pressing “Download Credentials”, and copy-pasting the whole file up to and including the “END RSA PRIVATE KEY” line into tempkey.pem. 
    3. Put your Cloudlab public key in tempkey.pub (can get from https://www.cloudlab.us/ssh-keys.php)
5. Move back to the relevant directory: `cd ~/KubesprayClusterOnCloudlab`
6. Run: `bash deploy_kubespray.sh`. At some point you will be asked for the phasephrase for `.ssh/tempkey.pem`. This is the password to your Cloudlab profile. If the password was correct, it will output “Identity added:...". If any y/N prompts shows up, respond: `y`.
   NOTE: IF this scripts runs sucessful, you should see a ton of ansible output and no errors.
7. Setup InfluxDB integration with Prometheus (this is one way to get the time series data) -- this has not been implemented yet (and you might choose not to implement it)
8. \[If you want to deploy sockshop\] Run: `bash deploy_sockshop.sh`. The script waits a bunch of times (to give Kubernetes cluster components time to instantiate), so don't be concerned if that happens.
9. Prepare the application by populating the database. Move to the relevant directory via `cd ./experiment_coordinator/` and then running `sudo python -u run_experiment.py --use_k3s_cluster --no_exfil --prepare_app --return_after_prepare_p --config_file ../sockshop_experiment.json --localhostip FRONT-END-CLUSTER-IP --localport 80 | tee sockshop_four_140.log`, where FRONT-END-CLUSTER-IP is the clusterIP of the front-end service, which can be seen by running `kubectl get svc front-end --namespace="sock-shop"` and looking at the CLUSTER-IP column
10. Generate load (warning: this takes a long time and a lot of cpu):
`sudo python -u run_experiment.py --use_k3s_cluster --no_exfil --config_file ../sockshop_experiment.json --localhostip FRONT-END-CLUSTER-IP --localport 80`

NOTE: Need to add autoscaling support to the kubespray cluster


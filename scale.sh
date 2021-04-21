cd ~/KubesprayClusterOnCloudlab
cd ./experiment_coordinator/
sudo python -u run_experiment.py --use_k3s_cluster --no_exfil --config_file ../sockshop_experiment.json --localhostip $1 --localport 80
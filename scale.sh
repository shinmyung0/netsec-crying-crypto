cd ~/KubesprayClusterOnCloudlab
cd ./experiment_coordinator/
sudo python -u run_experiment.py --use_k3s_cluster --no_exfil --prepare_app --return_after_prepare_p --config_file ../sockshop_experiment.json --localhostip $1 --localport 80 | tee sockshop_four_140.log
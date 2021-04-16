# Install Experimental Coordinator Dependencies
sudo apt-get install python-pip
# make sure pip is up to date
sudo pip install pip --user
# then install most of the python dependencies
sudo pip2 install docker networkx matplotlib jinja2 pdfkit numpy pandas seaborn Cython pyyaml multiprocessing scipy pdfkit tabulate sklearn pexpect netifaces selenium kubernetes urllib3==1.23 pwn --user
# on Ubuntu 16.04, pygraphviz needs to be installed in a specific way.
sudo apt-get install -y graphviz libgraphviz-dev pkg-config
sudo pip2 install pygraphviz --install-option="--include-path=/usr/include/graphviz" --install-option="--library-path=/usr/lib/graphviz/"
# unclear if we need the ones below
sudo apt-get -y install python-dev
sudo pip install requests pyasn1 ipaddress urllib3 --upgrade
sudo pip install docker pexpect netifaces selenium kubernetes requests
sudo pip install locustio==0.13.5 pycryptodome
sudo pip install pwntools
sudo python -m easy_install --upgrade pyOpenSSL

#  Run the experimental coordinator for sockshop:
kubectl label namespace sock-shop istio-injection=enabled
kubectl apply -f  ./sockshop_modified_full_cluster.yaml
cd ./experiment_coordinator

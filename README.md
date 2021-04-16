steps

0. use sftp to upload the project into the host server. it will be easier ehen you adding rsa keys and chaning some code. I recommend seting up sftp extension on vscode.
1. add tempkey.pem/tempkey.pub to the root folder of this project.
    refer to intruction in Joseph's scripts. 
        4. Manually setup passwordless-SSH:
        1. `cd ~/.ssh/`
        2. Store your cloudlab private key in tempkey.pem. Do this by first creating a new file called tempkey.pem (if it doesn't already exist). Then, get your cloudlab private key by going to https://www.cloudlab.us/, pressing “Download Credentials”, and copy-pasting the whole file up to and including the “END RSA PRIVATE KEY” line into tempkey.pem. 
        3. Put your Cloudlab public key in tempkey.pub (can get from https://www.cloudlab.us/ssh-keys.php)
2. run `bash setup.sh`, it will move your key to ~/.ssh


3. replace `{HOST}` in basic_cadvisor.yaml with the host dns. e.g. ms1308.utah.cloudlab.us. run `kubectl apply -f basic_cadvisor.yaml` to deploy advisor.

4. `python3 influx_csv_dumper.py -db cadvisor -tl 15m` to export metrics. -tl is the Length of time for the dump.

5. That's it.

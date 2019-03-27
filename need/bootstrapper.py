#! /usr/bin/python3

# from docker.types import Mount
import docker
from kubernetes import client, config

import os
import sys
import socket
import json, pprint

from subprocess import Popen
from multiprocessing import Process
from time import sleep
from signal import pause
# from shutil import copy

from need.NEEDlib.utils import int2ip, ip2int, fail
from need.NEEDlib.utils import print_message, print_error, print_and_fail
from need.NEEDlib.utils import DOCKER_SOCK, TOPOLOGY, LOCAL_IPS_FILE, REMOTE_IPS_FILE


UDP_PORT = 55555
BUFFER_LEN = 1024

gods = {}
ready_gods = {}


def broadcast_ips(local_ips_list, number_of_gods):
	global ready_gods
	
	sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sender.bind(('', UDP_PORT + 1))
	
	msg = ' '.join(local_ips_list)
	
	tries = 0
	# while tries < 0:
	# while len(ready_gods) < number_of_gods:
	while True:
		for i in range(1, 254):
			sender.sendto(bytes(msg, encoding='utf8'), ('10.1.0.' + str(i), UDP_PORT))
			
		sleep(0.5)
		tries += 1
		
		
def broadcast_ready(number_of_gods):
	global ready_gods
	
	sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sender.bind(('', UDP_PORT + 2))
	
	# while len(ready_gods) < number_of_gods:
	while True:
		for i in range(1, 254):
			sender.sendto(bytes("READY", encoding='utf8'), ('10.1.0.' + str(i), UDP_PORT))
		
		sleep(0.5)


def resolve_ips(docker_client, low_level_client):
	global gods
	global ready_gods

	try:
		number_of_gods = len(low_level_client.nodes())
		local_ips_list = []
		own_ip = socket.gethostbyname(socket.gethostname())
		
		print("[Py (god)] ip: " + str(own_ip))
		print("[Py (god)] number of gods: " + str(number_of_gods))
		sys.stdout.flush()
	
		containers = docker_client.containers.list()
		for container in containers:
			test_net_config = low_level_client.inspect_container(container.id)['NetworkSettings']['Networks'].get('test_overlay')
			
			if test_net_config is not None:
				container_ip = test_net_config["IPAddress"]
				if container_ip not in local_ips_list:
					local_ips_list.append(container_ip)
		
		local_ips_list.remove(own_ip)

		ip_broadcast = Process(target=broadcast_ips, args=(local_ips_list, number_of_gods, ))
		ip_broadcast.start()
		
		receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		receiver.bind(('', UDP_PORT))
		
		while len(gods) < number_of_gods:
			data, addr = receiver.recvfrom(BUFFER_LEN)
			god_ip = int(ip2int(addr[0]))
			
			if not data.startswith(b"READY"):
				list_of_ips = [ip2int(ip) for ip in data.decode("utf-8").split()]
	
				if god_ip not in gods:
					gods[god_ip] = list_of_ips
					print(f"[Py (god)] {addr[0]} :: {data}")
					sys.stdout.flush()
			
			else:
				ready_gods[god_ip] = "READY"
				print(f"[Py (god)] {addr[0]} :: READY")
		
		ready_broadcast = Process(target=broadcast_ready, args=(number_of_gods,))
		ready_broadcast.start()
		
		while len(ready_gods) < number_of_gods:
			data, addr = receiver.recvfrom(BUFFER_LEN)
			god_ip = int(ip2int(addr[0]))
			
			# if data.split()[0] == "READY":
			if data.startswith(b"READY"):
				ready_gods[god_ip] = "READY"
				print(f"[Py (god)] {addr[0]} :: READY")
		
		ip_broadcast.terminate()
		ready_broadcast.terminate()
		ip_broadcast.join()
		ready_broadcast.join()
		
		
		own_ip = ip2int(own_ip)
		
		local_god = {}
		local_god[own_ip] = gods[own_ip]
		with open(LOCAL_IPS_FILE, 'w') as l_file:
			l_file.write(json.dumps(local_god))
		
		del gods[own_ip]
		with open(REMOTE_IPS_FILE, 'w') as r_file:
			r_file.write(json.dumps(gods))
		
		
		with open(LOCAL_IPS_FILE, 'r') as file:
			new_dict = json.load(file)
			print("\n[Py (god)] local:")
			pprint.pprint(new_dict)
			sys.stdout.flush()
		
		with open(REMOTE_IPS_FILE, 'r') as file:
			new_dict = json.load(file)
			print("\n[Py (god)] remote:")
			pprint.pprint(new_dict)
			sys.stdout.flush()
	
		return gods
	
	except Exception as e:
		print("[Py] " + str(e))
		sys.stdout.flush()
		sys.stderr.flush()
		sys.exit(-1)


def kubernetes_bootstrapper():
	mode = argv[1]
	label = argv[2]
	god_id = None  # get this, it will be argv[3]
	
	# Connect to the local docker daemon
	config.load_incluster_config()
	kubeAPIInstance = client.CoreV1Api()
	LowLevelClient = docker.APIClient(base_url='unix:/' + DOCKER_SOCK)
	need_pods = kubeAPIInstance.list_namespaced_pod('default')
	
	while not god_id:
		need_pods = kubeAPIInstance.list_namespaced_pod('default')
		try:
			for pod in need_pods.items:
				if "boot" + label in pod.metadata.labels:
					god_id = pod.status.container_statuses[0].container_id[9:]
		
		except Exception as e:
			print(e)
			stdout.flush()
			sleep(1)  # wait for the Kubernetes API
	
	# We are finally ready to proceed
	print("Bootstrapping all local containers with label " + label)
	stdout.flush()
	
	already_bootstrapped = {}
	instance_count = 0
	
	while True:
		try:
			need_pods = kubeAPIInstance.list_namespaced_pod('default')
			running = 0  # running container counter, we stop the god if there are 0 same experiment containers running
			
			# check if containers need bootstrapping
			for pod in need_pods.items:
				container_id = pod.status.container_statuses[0].container_id[9:]
				
				if label in pod.metadata.labels:
					running += 1
					
				if label in pod.metadata.labels \
						and container_id not in already_bootstrapped \
						and pod.status.container_statuses[0].state.running is not None:
					
					try:
						container_pid = LowLevelClient.inspect_container(container_id)["State"]["Pid"]
						emucore_instance = Popen(
							["nsenter", "-t", str(container_pid), "-n",
							 "/usr/bin/python3", "/usr/bin/NEEDemucore", TOPOLOGY, str(container_id),
							 str(container_pid)]
						)
						instance_count += 1
						already_bootstrapped[container_id] = emucore_instance
					
					except:
						print("Bootstrapping failed... will try again.")
						stdout.flush()
						stderr.flush()
				
				# Check for bootstrapper termination
				if container_id == god_id and pod.status.container_statuses[0].state.running != None:
					running += 1
					
			# Do some reaping
			for key in already_bootstrapped:
				already_bootstrapped[key].poll()
			
			# Clean up and stop
			if running == 0:
				for key in already_bootstrapped:
					if already_bootstrapped[key].poll() is not None:
						already_bootstrapped[key].kill()
						already_bootstrapped[key].wait()
				print("God terminating")
				return
			
			sleep(5)
		
		except Exception as e:
			print(e)
			stdout.flush()
			sleep(1)



def docker_bootstrapper():
	
	UDP_PORT = 55555

	mode = argv[1]
	label = argv[2]
	
	message("lable: " + label)
	
	# Connect to the local docker daemon
	client = docker.DockerClient(base_url='unix:/' + DOCKER_SOCK)
	LowLevelClient = docker.APIClient(base_url='unix:/' + DOCKER_SOCK)


	if mode == "-s":
		while True:
			try:
				# If we are bootstrapper:
				us = None
				while not us:
					containers = client.containers.list()
					for container in containers:
						if "boot"+label in container.labels:
							us = container
					
					sleep(1)
				
				boot_image = us.image
				
				inspect_result = lowLevelClient.inspect_container(us.id)
				env = inspect_result["Config"]["Env"]
				
				print_message("[Py (bootstrapper)] ip: " + str(socket.gethostbyname(socket.gethostname())))
				
				# create a "God" container that is in the host's Pid namespace
				client.containers.run(image=boot_image,
									  command=["-g", label, str(us.id)],
									  privileged=True,
									  pid_mode="host",
									  shm_size=4000000000,
									  remove=True,
									  environment=env,
									  # ports={"55555/udp":55555, "55556/udp":55556},
									  # volumes={DOCKER_SOCK: {'bind': DOCKER_SOCK, 'mode': 'rw'}},
									  volumes_from=[us.id],
									  # network_mode="container:"+us.id,  # share the network stack with this container
									  # network='olympus_overlay',
									  network='test_overlay',
									  labels=["god" + label],
									  detach=True)
									# stderr=True,
									# stdout=True)
				pause()
				
				return
			
			except Exception as e:
				print_error(e)
				sleep(5)
				continue  # If we get any exceptions try again
	
	
	# We are the god container
	# first thing to do is copy over the topology
	while True:
		try:
			bootstrapper_id = sys.argv[3]
			bootstrapper_pid = lowLevelClient.inspect_container(bootstrapper_id)["State"]["Pid"]
			cmd = ["/bin/sh", "-c",
				   "nsenter -t " + str(bootstrapper_pid) + " -m cat " + TOPOLOGY + " | cat > " + TOPOLOGY]
			Popen(cmd).wait()
			break
		
		except Exception as e:
			print_error(e)
			sleep(5)
			continue
			
	
	# next we start the Aeron Media Driver
	aeron_media_driver = None
	try:
		aeron_media_driver = Popen('/usr/bin/Aeron/aeronmd')
		print("started aeron_media_driver.")
	
	except Exception as e:
		print_error("[Py (bootstrapper)] failed to start aeron media driver.")
		print_and_fail(e)
	
	
	# we are finally ready to proceed
	print_message("[Py (bootstrapper)] Bootstrapping all local containers with label " + label)
	already_bootstrapped = {}
	instance_count = 0
	
	ips_dict = resolve_ips(client, lowLevelClient)
	
	containers = client.containers.list()
	for container in containers:
		try:
			# inject the Dashboard into the dashboard container
			for key, value in container.labels.items():
				if "dashboard" in value:
					id = container.id
					inspect_result = lowLevelClient.inspect_container(id)
					pid = inspect_result["State"]["Pid"]
					print("[Py (god)] Bootstrapping dashboard ...")
					sys.stdout.flush()
					
					cmd = ["nsenter", "-t", str(pid), "-n", "/usr/bin/python3", "/usr/bin/NEEDDashboard", TOPOLOGY]
					dashboard_instance = Popen(cmd)
					
					instance_count += 1
					print("[Py (god)] Done bootstrapping dashboard.")
					sys.stdout.flush()
					already_bootstrapped[container.id] = dashboard_instance
					
					break
		
		except Exception as e:
			print_error("[Py (god)] Dashboard bootstrapping failed:\n" + str(e) + "\n... will try again.")
			continue
			
			
	while True:
		try:
			running = 0  # running container counter, we stop the god if there are 0 same experiment containers running
			
			# check if containers need bootstrapping
			containers = client.containers.list()
			for container in containers:
				
				if label in container.labels:
					running += 1
		
				if label in container.labels and container.id not in already_bootstrapped and container.status == "running":
					# inject emucore into application containers
					try:
						id = container.id
						inspect_result = lowLevelClient.inspect_container(id)
						pid = inspect_result["State"]["Pid"]
						
						print_message("[Py (god)] Bootstrapping " + container.name + " ...")
						
						cmd = ["nsenter", "-t", str(pid), "-n", "/usr/bin/python3", "/usr/bin/NEEDemucore", TOPOLOGY, str(id),
							   str(pid)]
						emucore_instance = Popen(cmd)
						
						instance_count += 1
						print_message("[Py (god)] Done bootstrapping " + container.name)
						already_bootstrapped[container.id] = emucore_instance
					
					except:
						print_error("[Py (god)] Bootstrapping failed... will try again.")
					
				# Check for bootstrapper termination
				if container.id == bootstrapper_id and container.status == "running":
					running += 1
			
			# Do some reaping
			for key in already_bootstrapped:
				already_bootstrapped[key].poll()

			# Clean up and stop
			if running == 0:
				for key in already_bootstrapped:
					if already_bootstrapped[key].poll() is not None:
						already_bootstrapped[key].kill()
						already_bootstrapped[key].wait()
						

				print_message("[Py (god)] God terminating.")
				
				if aeron_media_driver:
					aeron_media_driver.terminate()
					print_message("[Py (god)] aeron_media_driver terminating.")
					aeron_media_driver.wait()
				
				sys.stdout.flush()
				return
			
			sleep(5)
		
		except Exception as e:
			sys.stdout.flush()
			print_error(e)
			sleep(5)
			continue




if __name__ == '__main__':

	if len(argv) < 3:
		print("If you are calling " + argv[0] + " from your workstation stop.")
		print("This should only be used inside containers")
		exit(-1)
	
	orchestrator = os.getenv('NEED_ORCHESTRATOR', 'swarm')
	print("orchestrator: " + orchestrator)
	
	if orchestrator == 'kubernetes':
		kubernetes_bootstrapper()
		
	else:
		if orchestrator != 'swarm':
			print("Unrecognized orchestrator. Using default docker swarm.")
		
		docker_bootstrapper()



# def start_dashboard(client, lowLevelClient, instance_count):
# 	dashboard_bootstrapped = False
# 	while not dashboard_bootstrapped:
#
# 		containers = client.containers.list()
# 		for container in containers:
# 			try:
# 				# inject the Dashboard into the dashboard container
# 				for key, value in container.labels.items():
# 					if "dashboard" in value:
# 						id = container.id
# 						inspect_result = lowLevelClient.inspect_container(id)
# 						pid = inspect_result["State"]["Pid"]
# 						print("[Py (god)] Bootstrapping dashboard " + container.name + " ...")
# 						sys.stdout.flush()
#
# 						cmd = ["nsenter", "-t", str(pid), "-n", "/usr/bin/python3", "/usr/bin/NEEDDashboard", TOPOLOGY]
# 						dashboard_instance = Popen(cmd)
#
# 						instance_count += 1
# 						print("[Py (god)] Done bootstrapping " + container.name)
# 						sys.stdout.flush()
# 						already_bootstrapped[container.id] = dashboard_instance
#
# 						dashboard_bootstrapped = True
# 						break
#
#
# 			except Exception as e:
# 				print("[Py (god)] Dashboard bootstrapping failed:\n" + str(e) + "\n... will try again.")
# 				sys.stdout.flush()
# 				sys.stderr.flush()
# 				sleep(5)
# 				continue


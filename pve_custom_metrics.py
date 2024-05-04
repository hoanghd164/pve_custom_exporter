import subprocess, re, socket, time, yaml, datetime, threading, logging
from prometheus_client import start_http_server, Gauge

count = 0
id_count = {}
time_start = time.time()
node = socket.gethostname()
instance = socket.gethostbyname(node)

logging.basicConfig(filename='app.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')

def timestamp_convert(result):
    parts = result.split(',')
    for part in parts:
        if part.startswith("ctime="):
            ctime_value = int(part[6:])
            break
    date_time = datetime.datetime.fromtimestamp(ctime_value)
    date_time_dict = {
        "date": date_time.strftime("%Y-%m-%d"),
        "time": date_time.strftime("%H:%M:%S")
    }
    return date_time_dict

def convert_to_bytes(value,unit):
    unit = unit.strip().lower()

    unit_map = {
        'tb': (1024**4),
        't': (1024**4),
        'gb': (1024**3),
        'g': (1024**3),
        'mb': (1024**2),
        'm': (1024**2),
        'kb': 1024,
        'k': 1024,
        'b': 1
    }

    if unit in unit_map:
        multiplier = unit_map[unit]
        return int(value * multiplier)

def storage_convert(id, value):
    storage_name = value.split(f':{id}')[0]
    storage_size = value.split('size=')[1]

    if "/dev/disk/by-id" in storage_name:
        storage_name = "disk"

    match = re.match(r'(\d+(\.\d+)?)([A-Za-z]+)', storage_size)

    if match:
        number = float(match.group(1))
        unit = match.group(3)
        storage_size = convert_to_bytes(number,unit)

        global id_count
        id_count[id] = id_count.get(id, 0) + 1

        result_dict = {
            "storage_name": storage_name,
            "storage_size": storage_size
        }

    return result_dict

def pve_custom_node_info():
    return ['pve_custom_node_info{id="node/%s", instance="%s", name="%s", nodeid="%s"} %s\n' %(node,instance,node,handle_uuid_file(),str(int(instance.replace('.', ''))))] 

class PVEMetrics:
    def get_qm_data(self, line, qm_list_resource):
        parts = line.split()
        if len(parts) == 6:
            id, name, status, mem_mb, bootdisk_gb, pid = parts[:6]

            qm_ls_data = {
                "id": int(id),
                "status": status,
                "pid": int(pid)
            }
        else:
            name = ' '.join(parts[1:-4])
            qm_ls_data = {
                "id": parts[0],
                "status": parts[-4],
                "pid": parts[-1]
            }

        qm_config_data = subprocess.check_output(["qm", "config", str(id)]).decode("utf-8")
        if "cipassword" in qm_config_data:
            qm_config_data = re.sub(r'cipassword: \*+\nciuser: ubuntu', '', qm_config_data)
            qm_config_data = re.sub(r'\n\s*\n', '\n', qm_config_data)

        qm_parsed_data = yaml.safe_load(qm_config_data)
        qm_combined_data = {**qm_ls_data, **qm_parsed_data}
        qm_list_resource.append(qm_combined_data)

    def get_lxc_data(self, line, lxc_list_resource):
        parts = line.split()
        id = int(parts[0])
        status = parts[1]

        lxc_ls_data = {
            "id": int(id),
            "status": status
        }

        lxc_data = subprocess.check_output(["pct", "config", str(id)]).decode("utf-8")
        lxc_parsed_data = yaml.safe_load(lxc_data)
        lxc_combined_data = {**lxc_ls_data, **lxc_parsed_data}
        lxc_list_resource.append(lxc_combined_data)

    def get_resource_vms(self):
        get_qm_info = subprocess.check_output(["qm", "list"]).decode("utf-8")
        get_lxc_info = subprocess.check_output(["pct", "list"]).decode("utf-8")

        qm_lines = get_qm_info.strip().split('\n')[1:]
        lxc_lines = get_lxc_info.strip().split('\n')[1:]

        qm_list_resource = []
        lxc_list_resource = []

        threads = []
        for line in qm_lines:
            thread = threading.Thread(target=self.get_qm_data, args=(line, qm_list_resource))
            threads.append(thread)
            thread.start()

        for line in lxc_lines:
            thread = threading.Thread(target=self.get_lxc_data, args=(line, lxc_list_resource))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        return qm_list_resource, lxc_list_resource

class CPULoadAverage:
    metrics = {
        'cpu_load_average_1minute': Gauge('pe_custom_node_cpu_load_average_1minute', 'Description of gauge', ['id', 'instance']),
        'cpu_load_average_5minute': Gauge('pve_custom_node_cpu_load_average_5minute', 'Description of gauge', ['id', 'instance']),
        'cpu_load_average_15minute': Gauge('pve_custom_node_cpu_load_average_15minute', 'Description of gauge', ['id', 'instance']),
        'current_logged_in_users': Gauge('pve_custom_current_logged_in_users', 'Description of gauge', ['id', 'instance'])
    }

    @classmethod
    def update_metrics(cls, node, instance):
        results = subprocess.check_output("w", shell=True, text=True).strip('\n').split('\n')
        match = re.search(r'(\d+) users', results[0])

        if match:
            users_count = match.group(1)
        else:
            users_count = 0

        load_averages = re.findall(r'\d+\.\d+', results[0])

        cls.metrics['cpu_load_average_1minute'].labels(id="node/%s" % node, instance=instance).set(load_averages[0])
        cls.metrics['cpu_load_average_5minute'].labels(id="node/%s" % node, instance=instance).set(load_averages[1])
        cls.metrics['cpu_load_average_15minute'].labels(id="node/%s" % node, instance=instance).set(load_averages[2])
        cls.metrics['current_logged_in_users'].labels(id="node/%s" % node, instance=instance).set(users_count)


class CPUSocketSize:
    metrics = {
        'cpu_used_percent': Gauge('pve_custom_node_cpu_used_percent', 'Description of gauge', ['id', 'instance']),
        'cpu_idle_percent': Gauge('pve_custom_node_cpu_idle_percent', 'Description of gauge', ['id', 'instance']),
        'cpu_socket_size': Gauge('pve_custom_node_cpu_socket_size', 'Description of gauge', ['id', 'instance']),
        'cpu_core_size': Gauge('pve_custom_node_cpu_core_size', 'Description of gauge', ['id', 'instance', 'architecture', 'cpu_op_mode', 'byte_order', 'on_line_cpu_list', 'vendor_id', 'model_name', 'virtualization', 'l1d_cache', 'l2_cache', 'l3_cache'])
    }

    def __init__(self, node, instance):
        self.node = node
        self.instance = instance

    def pve_custom_node_cpu_socket_size(self):
        cpu_info = {}
        results = {}

        try:
            lines = subprocess.check_output("lscpu", shell=True, text=True).split('\n')

            for line in lines:
                if line:
                    key, value = [s.strip() for s in line.split(":", 1)]
                    cpu_info[key] = value

            match_keys = ["Architecture", "CPU op-mode(s)", "Byte Order", "CPU(s)", "On-line CPU(s) list", "Socket(s)", "Vendor ID", "Model name", "Virtualization","L1d cache","L1i cache","L2 cache","L3 cache"]
            cpu_info = {key: value for key, value in cpu_info.items() if key in match_keys}

            for key, value in cpu_info.items():
                transformed_key = re.sub(r'\([^)]*\)', '', key).strip().replace(" ", "_").lower().replace('(', '').replace(')', '').replace("-", "_")
                results[transformed_key] = value
        except Exception as e:
            logging.error("Exception occurred", exc_info=True)
        
        output = subprocess.check_output("top -cn1 | grep '%Cpu(s)' | awk '{print $8}'", shell=True, text=True)
        output = output.strip()  # Remove leading/trailing whitespace
        output = re.sub(r'[^0-9.]', '', output)
        cpu_idle_percent = float(output) if output else 0.0

        if isinstance(cpu_idle_percent, float) and cpu_idle_percent >= 0:
            self.metrics['cpu_used_percent'].labels(id="node/%s" % self.node, instance=self.instance).set(round(100 - cpu_idle_percent,2))
            self.metrics['cpu_idle_percent'].labels(id="node/%s" % self.node, instance=self.instance).set(float(cpu_idle_percent))
            self.metrics['cpu_socket_size'].labels(id="node/%s" % self.node, instance=self.instance).set(float(results['socket']))
            self.metrics['cpu_core_size'].labels(id="node/%s" % self.node, instance=self.instance, \
                                                                architecture=results['architecture'], \
                                                                    cpu_op_mode=results['cpu_op_mode'], \
                                                                        byte_order=results['byte_order'], \
                                                                            on_line_cpu_list=results['on_line_cpu_list'], \
                                                                                vendor_id=results['vendor_id'], \
                                                                                    model_name=results['model_name'], \
                                                                                        virtualization=results['virtualization'], \
                                                                                            l1d_cache=results['l1d_cache'], \
                                                                                                l2_cache=results['l2_cache'], \
                                                                                                    l3_cache=results['l3_cache']).set(float(results['cpu']))
            
class DiskInfo:
    metrics = {
        'disk_info': Gauge('pve_custom_disk_info', 'Description of gauge', ['instance', 'node', 'filesystem', 'size', 'used', 'avail', 'mounted'])
    }

    def __init__(self, node, instance):
        self.node = node
        self.instance = instance

    def update_metrics(self):
        results_df = subprocess.check_output('df -h', shell=True).decode("utf-8").strip()
        lines = results_df.strip().split('\n')
        header = lines[0].split()
        result_list = []

        for line in lines[1:]:
            values = line.split()
            entry = dict(zip(header, values))
            result_list.append(entry)

        for entry in result_list:
            self.metrics['disk_info'].labels(instance=self.instance, node=self.node, filesystem=entry['Filesystem'], size=entry['Size'], used=entry['Used'], avail=entry['Avail'], mounted=entry['Mounted']).set(float(entry['Use%'].strip('%')))

class NodeMemorySize:
    metrics = {
        'total_memory_size_bytes': Gauge('pve_custom_node_total_memory_size_bytes', 'Description of gauge', ['id', 'instance']),
        'used_memory_size_bytes': Gauge('pve_custom_node_used_memory_size_bytes', 'Description of gauge', ['id', 'instance']),
        'free_memory_size_bytes': Gauge('pve_custom_node_free_memory_size_bytes', 'Description of gauge', ['id', 'instance']),
        'shared_memory_size_bytes': Gauge('pve_custom_node_shared_memory_size_bytes', 'Description of gauge', ['id', 'instance']),
        'buffcache_memory_size_bytes': Gauge('pve_custom_node_buffcache_memory_size_bytes', 'Description of gauge', ['id', 'instance']),
        'available_memory_size_bytes': Gauge('pve_custom_node_available_memory_size_bytes', 'Description of gauge', ['id', 'instance']),
        'total_swap_size_bytes': Gauge('pve_custom_node_total_swap_size_bytes', 'Description of gauge', ['id', 'instance']),
        'used_swap_size_bytes': Gauge('pve_custom_node_used_swap_size_bytes', 'Description of gauge', ['id', 'instance']),
        'free_swap_size_bytes': Gauge('pve_custom_node_free_swap_size_bytes', 'Description of gauge', ['id', 'instance'])
    }

    def __init__(self, node, instance):
        self.node = node
        self.instance = instance

    def pve_custom_node_memory_size_bytes(self):
        output = subprocess.check_output("free -b", shell=True, text=True)

        mem_line = None
        for line in output.split('\n'):
            if line.startswith('Mem:'):
                mem_line = line
                break

        if mem_line:
            mem_info = mem_line.split()

        swap_line = None
        for line in output.split('\n'):
            if line.startswith('Swap:'):
                swap_line = line
                break

        if swap_line:
            swap_info = swap_line.split()

        self.metrics['total_memory_size_bytes'].labels(id="node/%s" % self.node, instance=self.instance).set(float(mem_info[1]))
        self.metrics['used_memory_size_bytes'].labels(id="node/%s" % self.node, instance=self.instance).set(float(mem_info[2]))
        self.metrics['free_memory_size_bytes'].labels(id="node/%s" % self.node, instance=self.instance).set(float(mem_info[3]))
        self.metrics['shared_memory_size_bytes'].labels(id="node/%s" % self.node, instance=self.instance).set(float(mem_info[4]))
        self.metrics['buffcache_memory_size_bytes'].labels(id="node/%s" % self.node, instance=self.instance).set(float(mem_info[5]))
        self.metrics['available_memory_size_bytes'].labels(id="node/%s" % self.node, instance=self.instance).set(float(mem_info[6]))
        self.metrics['total_swap_size_bytes'].labels(id="node/%s" % self.node, instance=self.instance).set(float(swap_info[1]))
        self.metrics['used_swap_size_bytes'].labels(id="node/%s" % self.node, instance=self.instance).set(float(swap_info[2]))
        self.metrics['free_swap_size_bytes'].labels(id="node/%s" % self.node, instance=self.instance).set(float(swap_info[3]))

class PhysicalMemoryInfo:
    pve_physical_memory_total_slot = Gauge('pve_custom_physical_memory_total_slot', 'Description of gauge', ['instance', 'node'])
    pve_physical_memory_unused_slot = Gauge('pve_custom_physical_memory_unused_slot', 'Description of gauge', ['instance', 'node'])
    pve_physical_memory_used_slot = Gauge('pve_custom_physical_memory_used_slot', 'Description of gauge', ['instance', 'node'])
    pve_custom_physical_memory_info = Gauge('pve_custom_physical_memory_info', 'Description of gauge', ['instance', 'node', 'locator', 'array_handle', 'error_information_handle', 'total_width', 'data_width', 'form_factor', 'set', 'bank_locator', 'type', 'type_detail', 'speed', 'manufacturer', 'serial_number', 'asset_tag', 'part_number', 'rank', 'configured_memory_speed', 'minimum_voltage', 'maximum_voltage', 'configured_voltage'])
    
    def __init__(self, node, instance):
        self.node = node
        self.instance = instance
        self.missing_fields = ['array_handle', 'error_information_handle', 'total_width', 'data_width', 'form_factor', 'type', 'type_detail', 'speed', 'manufacturer', 'serial_number', 'asset_tag', 'part_number', 'rank', 'configured_memory_speed', 'minimum_voltage', 'maximum_voltage','configured_voltage']

    def fill_missing_fields(self, result):
        for field in self.missing_fields:
            if field not in result:
                result[field] = 'Null'

    def get_physical_mem(self):
        output = subprocess.check_output("dmidecode --type 17", shell=True, text=True)

        ram_info_list = []
        ram_info = {}
        no_module_installed_count = 0
        pve_physical_memory_info = []

        for line in output.split('\n'):
            if line:
                if line.startswith("Handle"):
                    if ram_info:
                        self.fill_missing_fields(ram_info)

                        ram_info_list.append(ram_info)
                        if 'size' in ram_info and ram_info['size'] == 'No Module Installed':
                            no_module_installed_count += 1
                    ram_info = {}
                else:
                    if ":" in line:
                        key, value = [s.strip() for s in line.split(":", 1)]
                        transformed_key = re.sub(r'\([^)]*\)', '', key).strip().replace(" ", "_").lower().replace('(', '').replace(')', '').replace("-", "_")
                        ram_info[transformed_key] = value

        if ram_info:
            self.fill_missing_fields(ram_info)

            ram_info_list.append(ram_info)
            if 'size' in ram_info and ram_info['size'] == 'No Module Installed':
                no_module_installed_count += 1

        for result in ram_info_list:
            match = re.match(r'(\d+)\s*(\D+)', result['size'])
            if match:
                value = int(match.group(1))
                unit = match.group(2)
                size = str(convert_to_bytes(value, unit))
            else:
                size = str(0)

            self.pve_custom_physical_memory_info.labels(instance=self.instance, node=self.node, locator=result['locator'], array_handle=result['array_handle'], error_information_handle=result['error_information_handle'], total_width=result['total_width'], data_width=result['data_width'], form_factor=result['form_factor'], set=result['set'], bank_locator=result['bank_locator'], type=result['type'], type_detail=result['type_detail'], speed=result['speed'], manufacturer=result['manufacturer'], serial_number=result['serial_number'], asset_tag=result['asset_tag'], part_number=result['part_number'], rank=result['rank'], configured_memory_speed=result['configured_memory_speed'], minimum_voltage=result['minimum_voltage'], maximum_voltage=result['maximum_voltage'], configured_voltage=result['configured_voltage']).set(size)

        self.pve_physical_memory_total_slot.labels(instance=self.instance, node=self.node).set(len(ram_info_list))
        self.pve_physical_memory_unused_slot.labels(instance=self.instance, node=self.node).set(no_module_installed_count)
        self.pve_physical_memory_used_slot.labels(instance=self.instance, node=self.node).set(len(ram_info_list) - no_module_installed_count)

class ResourceVMInfo:
    # Define metrics
    pve_custom_guest_info_qm = Gauge('pve_custom_guest_info_qm', 'Description of gauge', ['instance', 'node', 'id', 'name', 'vm_time_create', 'vm_date_create', 'type'])
    pve_custom_vm_storage_info = Gauge('pve_custom_vm_storage_info', 'Description of gauge', ['instance', 'node', 'id', 'storage_name', 'storage_num'])
    pve_custom_guest_info_lxc = Gauge('pve_custom_guest_info_lxc', 'Description of gauge', ['instance', 'node', 'id', 'name', 'vm_time_create', 'vm_date_create', 'type'])
    pve_custom_lxc_storage_info = Gauge('pve_custom_lxc_storage_info', 'Description of gauge', ['instance', 'node', 'id', 'storage_name', 'storage_num'])
    pve_custom_overcommit_cpu = Gauge('pve_custom_overcommit_cpu', 'Description of gauge', ['instance', 'node'])
    pve_custom_overcommit_memory = Gauge('pve_custom_overcommit_memory', 'Description of gauge', ['instance', 'node'])

    def __init__(self, node, instance):
        self.node = node
        self.instance = instance

    def pve_custom_resource_vm_info(self):
        metrics = PVEMetrics()
        results = metrics.get_resource_vms()
        qm_results = results[0]
        lxc_results = results[1]
        cores_for_qm = []
        mems_for_qm = []
        cores_for_lxc = []
        mems_for_lxc = []
        overcommit_cpu = 0
        overcommit_memory = 0

        for result in qm_results:
            if result["status"] == "running":
                
                qm_status = 1
                for key, value in result.items():
                    if key == 'cores':
                        value = int(value) * int(result['sockets'])
                        cores_for_qm.append(value)
                    if key == 'memory':
                        mems_for_qm.append(value)
            else:
                qm_status = 0
            self.pve_custom_guest_info_qm.labels(instance=instance, node=node, id="qemu/%s" % result['id'], name=result['name'], vm_time_create=timestamp_convert(result['meta'])['time'], vm_date_create=timestamp_convert(result['meta'])['date'], type="qemu").set(qm_status)
            
            qm_count_storage = 1
            for key, value in result.items():
                if "scsi" in key or "virtio" in key:
                    if re.search(r'\d+$', key):
                        result_storage_convert = storage_convert(result['id'],value)
                        self.pve_custom_vm_storage_info.labels(instance=instance, node=node, id="qemu/%s" % result['id'], storage_name=result_storage_convert['storage_name'], storage_num=str(qm_count_storage)).set(result_storage_convert['storage_size'])
                        
                        qm_count_storage += 1

        for value in cores_for_qm:
            overcommit_cpu += value

        for value in mems_for_qm:
            overcommit_memory += value

        for result in lxc_results:
            if result["status"] == "running":
                lxc_status = 1
                for key, value in result.items():
                    if key == 'cores':
                        cores_for_lxc.append(value)
                    if key == 'memory':
                        mems_for_lxc.append(value)
            else:
                lxc_status = 0

            self.pve_custom_guest_info_lxc.labels(instance=instance, node=node, id="lxc/%s" % result['id'], name=result['hostname'], vm_time_create="N/A", vm_date_create="N/A", type="lxc").set(lxc_status)

            lxc_count_storage = 1
            for key, value in result.items():
                if "rootfs" in key or "mp" in key:
                    result_storage_convert = storage_convert(result['id'],value)
                    self.pve_custom_lxc_storage_info.labels(instance=instance, node=node, id="qemu/%s" % result['id'], storage_name=result_storage_convert['storage_name'], storage_num=str(lxc_count_storage)).set(result_storage_convert['storage_size'])
                    lxc_count_storage += 1

        for value in cores_for_lxc:
            overcommit_cpu += value

        for value in mems_for_lxc:
            overcommit_memory += value

        self.pve_custom_overcommit_cpu.labels(instance=instance, node=node).set(overcommit_cpu)
        self.pve_custom_overcommit_memory.labels(instance=instance, node=node).set(convert_to_bytes(overcommit_memory,'mb'))
        
class PveStorageInfo:
    def __init__(self):
        self.pve_storage_status = Gauge('pve_custom_storage_status', 'Description of gauge', ['instance', 'name', 'type', 'node'])
        self.pve_storage_total = Gauge('pve_custom_storage_total', 'Description of gauge', ['instance', 'name', 'type', 'node'])
        self.pve_storage_used = Gauge('pve_custom_storage_used', 'Description of gauge', ['instance', 'name', 'type', 'node'])
        self.pve_storage_available = Gauge('pve_custom_storage_available', 'Description of gauge', ['instance', 'name', 'type', 'node'])
        self.pve_storage_percent = Gauge('pve_custom_storage_used_percent', 'Description of gauge', ['instance', 'name', 'type', 'node'])

    def pvesm_status(self):
        output = subprocess.check_output("pvesm status", shell=True, text=True)
        lines = output.splitlines()
        header = lines[0].split()
        keys = [key.lower() for key in header]
        data = []

        for line in lines[1:]:
            values = line.split()
            item = {}
            
            for i, key in enumerate(keys):
                transformed_key = re.sub(r'\([^)]*\)', '', key).strip().replace("%", "percent").lower()
                item[transformed_key] = values[i]

            data.append(item)

        for result in data:
            if result['status'] == 'active':
                status = 1
            else:
                status = 0

            if result['percent']:
                percent = str(result['percent']).strip('%')

            if 'N/A' in result['percent']:
                percent = 0

            self.pve_storage_status.labels(instance=instance, name=result['name'], type=result['type'], node=node).set(status)
            self.pve_storage_total.labels(instance=instance, name=result['name'], type=result['type'], node=node).set(result['total'])
            self.pve_storage_used.labels(instance=instance, name=result['name'], type=result['type'], node=node).set(result['used'])
            self.pve_storage_available.labels(instance=instance, name=result['name'], type=result['type'], node=node).set(result['available'])
            self.pve_storage_percent.labels(instance=instance, name=result['name'], type=result['type'], node=node).set(percent)
        
if __name__ == '__main__':
    start_http_server(16490)
    cpu_socket_size = CPUSocketSize(node, instance)
    disk_info = DiskInfo(node, instance)
    node_memory_size = NodeMemorySize(node, instance)  # create an instance of NodeMemorySize
    physical_memory_info = PhysicalMemoryInfo(node, instance)  # create an instance of PhysicalMemoryInfo
    resource_vm_info = ResourceVMInfo(node, instance)  # create an instance of ResourceVMInfo
    pve_storage_info = PveStorageInfo()
    while True:
        CPULoadAverage.update_metrics(node, instance)
        cpu_socket_size.pve_custom_node_cpu_socket_size()
        disk_info.update_metrics()
        node_memory_size.pve_custom_node_memory_size_bytes()  # call the method on the instance
        physical_memory_info.get_physical_mem()  # call the method on the instance
        resource_vm_info.pve_custom_resource_vm_info()  # call the method on the instance
        pve_storage_info.pvesm_status()
        count += 1
        time_end = time.time()
        print(f"-> Finished {count} times in {time_end - time_start} seconds")
        time.sleep(30)
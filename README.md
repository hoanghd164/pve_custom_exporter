# Quy trình triển khai PVE Explore Customer 

**Sử dụng python 3.8 trở lên**
```
shell> python3 --version
Python 3.11.2
```

**Vào môi trường Python ảo bằng lệnh dưới**
```
source /opt/pve_custom_metrics/bin/activate
```

**Danh sách các Module Python**
``` 
shell> pip list 
Package           Version
----------------- -------
pip               23.0.1
prometheus_client 0.20.0
PyYAML            6.0.1
setuptools        66.1.1
```

**Dưới đây là quy trình triển khai**
```
#!/bin/bash
# Install the required packages
sudo apt update
apt install git -y 
sudo apt install -y python3-pip python3-venv

git clone https://github.com/hoanghd164/pve_custom_exporter.git
cd pve_custom_exporter

# Create the directory
mkdir -p /opt

# Create the virtual environment
python3 -m venv /opt/pve_custom_metrics
mkdir /opt/pve_custom_metrics/source

# Copy the script and requirements
cp ./pve_custom_metrics.py /opt/pve_custom_metrics/source
cp ./requirements.txt /opt/pve_custom_metrics/source

# Install the required packages
cd /opt
/opt/pve_custom_metrics/bin/python -m pip install -r /opt/pve_custom_metrics/source/requirements.txt

# # Test the script
# cd /opt/pve_custom_metrics/bin/python && /opt/pve_custom_metrics/source/pve_custom_metrics.py

# Create a systemd service
cat > /etc/systemd/system/pve_custom_metrics.service << 'OEF'
[Unit]
Description=PVE Custom Metrics Service
After=network.target

[Service]
ExecStart=/opt/pve_custom_metrics/bin/python /opt/pve_custom_metrics/source/pve_custom_metrics.py
Restart=always
User=root
Group=root
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
OEF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl restart pve_custom_metrics
sudo systemctl enable pve_custom_metrics
sudo systemctl status pve_custom_metrics

# # To update the script
# cp ./pve_custom_metrics.py /opt/pve_custom_metrics/source
# sudo systemctl restart pve_custom_metrics
# sudo systemctl status pve_custom_metrics
```

**Chúc các bạn thành công**
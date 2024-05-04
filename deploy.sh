#!/bin/bash
# Install the required packages
apt update
apt install git -y 
apt install -y python3-pip python3-venv

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
systemctl daemon-reload
systemctl restart pve_custom_metrics
systemctl enable pve_custom_metrics
systemctl status pve_custom_metrics

# # To update the script
# cp ./pve_custom_metrics.py /opt/pve_custom_metrics/source
# systemctl restart pve_custom_metrics
# systemctl status pve_custom_metrics
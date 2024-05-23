#!/bin/bash
# Install the required packages
apt update
apt install git -y 
apt install -y python3-pip python3-venv

folder_name="pve_custom_exporter"

# Create the directory
mkdir -p /opt
git clone https://github.com/hoanghd164/pve_custom_exporter.git /opt/${folder_name}/source
cd ${folder_name}

# Create the virtual environment
python3 -m venv /opt/${folder_name}

# Install the required packages
/opt/${folder_name}/bin/python -m pip install -r /opt/${folder_name}/source/requirements.txt

# Create a systemd service
cat > /etc/systemd/system/${folder_name}.service << OEF
[Unit]
Description=PVE Custom Metrics Service
After=network.target

[Service]
ExecStart=/opt/${folder_name}/bin/python /opt/${folder_name}/source/run.py
Restart=always
User=root
Group=root
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
OEF

# Enable and start the service
systemctl daemon-reload
systemctl restart ${folder_name}
systemctl enable ${folder_name}
systemctl status ${folder_name}
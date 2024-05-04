import subprocess
import pandas as pd
import json

result = subprocess.run(['iostat', '-x', '-c', '-k'], capture_output=True, text=True)
lines = result.stdout.split('\n')
start_line = next(i for i, line in enumerate(lines) if line.startswith('Device'))
df = pd.DataFrame([line.split() for line in lines[start_line+1:] if line], columns=lines[start_line].split())
json_output = df.to_json(orient='records')

# Convert the JSON string to a list of dictionaries
json_output = json.loads(json_output)

results_iops_write = []
results_iops_read = []
for i in json_output:
    iops_write = 'iops_write{"device"=%s} %s\n' %(i['Device'],i['w/s'])
    iops_read = 'iops_read{"device"=%s} %s\n' %(i['Device'],i['r/s'])
    results_iops_write.append(iops_write)
    results_iops_read.append(iops_read)

results = results_iops_write + results_iops_read
results = '\n'.join(results)
print(results)
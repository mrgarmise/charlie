import psutil
def cpu():
	return psutil.cpu_percent()
def memory():
	return psutil.virtual_memory().percent


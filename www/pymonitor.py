from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os,time,subprocess,sys

def log(str):
	print('[Monitor]:%s'%str)

class MyFileSystemEventHandler(FileSystemEventHandler):
 	"""构建自己的eventHandler"""
 	def __init__(self, fn):
 		super(MyFileSystemEventHandler, self).__init__()
 		self.restart = fn

 	def on_any_event(self,event):
 		if event.src_path.endswith('.py'):
 			log('Python file source has changged:%s'%event.src_path)
 			self.restart()

command=['echo', 'ok']
process=None

def start_process():
	global command,process
	log('Start process: %s' %' '.join(command))
	process = subprocess.Popen(command, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)

def kill_process():
	global process
	if process:
		log('Kill process[%s]' %process.pid)
		process.kill()
		process.wait()
		log('Process end with code %s'%process.returncode)
		process=None

def restart_process():
	kill_process()
	start_process()


def start_watch(path, callback=None):
	observe = Observer()
	observe.schedule(MyFileSystemEventHandler(restart_process), path, recursive=True)
	observe.start()
	log('Start watch direcoty:%s' %path)
	start_process()
	try:
		while True:
			time.sleep(0.5)
	except KeyboardInterrupt:
		observe.stop()
	observe.join()

if __name__=='__main__':
	argv = sys.argv[1:]
	if not argv:
		print('Usage: ./pymonitor your-script.py')
		exit(0)
	if argv[0] != 'python':
		argv.insert(0, 'python3')
	log(argv)
	command = argv
	path = os.path.abspath('.')
	start_watch(path)

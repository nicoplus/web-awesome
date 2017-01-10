
from fabric.api import *
import os
from datetime import datetime
env.user = 'chen'
env.sudo_user = 'root'
env.hosts = ['chen@192.168.1.95:22']
env.password = 'jc1992'

db_user='root'
dp_passwd='jc1992'

TAR_FILE = 'dist-awesome.tar.gz'

def build():
	includes = ['static','templates','*.py']
	excludes = ['*.sql','testOrm.py', 'test','.*','*.pyc', '*.pyo']
	local('rm -f dist/%s' %TAR_FILE)
	with lcd(os.path.join(os.path.abspath('.'), 'www')):
		cmd = ['tar', '--dereference', '-czvf', '../dist/%s' %TAR_FILE]
		cmd.extend(['--exclude=\'%s\'' % ex for ex in excludes])
		cmd.extend(includes)
		local(' '.join(cmd))


REMOTE_TEM_TAR = '/tmp/%s' %TAR_FILE
REMOTE_BASE_DIR = '/srv/awesome'

def deploy():
	new_dir = 'www-%s' %datetime.now().strftime('%y-%m-%d_%H.%M.%S')
	run('rm -f %s'%REMOTE_TEM_TAR)
	put('dist/%s'%TAR_FILE, REMOTE_TEM_TAR)
	with cd(REMOTE_BASE_DIR):
		sudo('mkdir %s' %new_dir)

	with cd('%s/%s'%(REMOTE_BASE_DIR,new_dir)):
		sudo('tar -xzvf %s'%REMOTE_TEM_TAR)

	with cd(REMOTE_BASE_DIR):
		sudo('rm -rf www')
		sudo('ln -s %s www'%new_dir)
		sudo('chown chen:chen www')
		sudo('chown -R chen:chen %s'%new_dir)

	with settings(warn_only=True):
		sudo('supervisorctl stop awesome')
		sudo('supervisorctl start awesomen')
		sudo('etc/init.d/nginx reload')

print 

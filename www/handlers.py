from coroweb import get,post
from Models import User,Blog,Comment,next_id
import time,re, hashlib, json, logging, asyncio, markdown2
import orm
from aiohttp import web
from apis import APIError, APIValueError,APIPermissionError, Page,APIResourceNotFound
from config import configs

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret
_MAX_AGE = 86400

def text2html(text):
	lines = map(lambda s:'<p>%s</p>'%s.replace('&','&amp').replace("<",'&lt').replace('>','&gt'), filter(lambda s: s.strip()!='',text.split('\n')))
	return ''.join(lines)

def get_page_index(page_str):
	try:
		p = int(page_str)
	except ValueError as e:
		raise e
	if p < 1:
		p = 1
	return p

def user2cookie(user,max_age):
	'''
	Generate cookie str by user
	'''
	#build by cookie string by:id, expires, sha1
	expires = str(int(time.time())+max_age)
	s = '%s-%s-%s-%s' %(user.id, user.passwd, expires, _COOKIE_KEY)
	L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
	return '-'.join(L) 

async def cookie2user(cookie_str):
	'''
	Parse cookie and load user object if cookie is valid
	'''
	if not cookie_str:
		return None

	try:
		L = cookie_str.split('-')
		if len(L) != 3:
			return None
		uid, expires, sha1 = L
		if int(expires) < time.time():
			return None
		user = await User.find_by_primaryKey(uid)
		if user is None:
			return None
		s = '%s-%s-%s-%s' %(uid, user.passwd, expires, _COOKIE_KEY)
		if sha1 != hashlib.sha1(s.encode()).hexdigest():
			logging.info('invalid sha1')
			return None
		user.passwd = '******'
		return user 
	except Exception as e:
		logging.info(e)
		return None

def check_admin(request):
	if request.__user__ is None or not request.__user__.admin:
		raise APIPermissionError()


@get('/')
async def index(*,page='1'):
	page_index = get_page_index(page)
	num = await Blog.find_number('count(id)')
	page = Page(num,page_index)
	if num==0:
		blogs = []
	else:
		blogs = await Blog.find_all(order_by='created_at desc',limit=(page.offset, page.limit))

	return {
		'__template__' : 'blogs.html',
		'blogs': blogs,
		'page' : page
	}

@get('/register')
def register():
	return {
		'__template__' : 'register.html'
	}

@get('/signin')
def signin():
	return{
		'__template__' : 'signin.html'
	}

@get('/signout')
def signout(request):
	referer = request.headers.get('Referer')
	r = web.HTTPFound(referer or '/')
	r.set_cookie(COOKIE_NAME,'-delete-',max_age=0,httponly=True)
	logging.info('sign out---Referer: %s' %referer)
	return r

#展示日志单页
@get('/blog/{id}')
async def get_blog(id):
	blog = await Blog.find_by_primaryKey(id)
	comments = await Comment.find_all(where='blog_id=?', args=[id], order_by='created_at desc')
	for c in comments:
		c.html_content = text2html(c.content)
	blog.html_content = markdown2.markdown(blog.content)
	return {
		"__template__":'blog.html',
		'blog':blog,
		'comments':comments
	}



'''@get('/api/users')
async def get_users():
	users = await User.find_all(order_by='created_at desc')
	for u in users:
		u.passwd = '*******'
	return dict(users=users)'''

#验证注册信息
RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\.\_\-]+\.[a-z0-9\-\_]{1,4}$')
RE_SHA1 = re.compile(r'^[a-z0-9]{40}$')
@post('/api/users')
async def api_register_user(*,email,name,passwd):
	logging.info('is registerring user %s %s %s'%(email, name, passwd))
	if not email or not RE_EMAIL.match(email):
		raise  APIValueError('email','Invalid email')
	if not name or not name.strip():
		raise APIValueError('name','Invalid name')
	if not passwd or not RE_SHA1.match(passwd):
		raise APIValueError('passwd', 'Invalid passwd')
	users = await User.find_all(where = 'email=?', args = [email])
	if len(users) > 0:
		raise APIError('register: failed', 'email', 'this email is in use')
	uid = next_id()
	sha1_passwd = '%s:%s'%(uid,passwd)
	user = User(id=uid, email=email, name=name, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='https://www.gravatar.com/avatar/%s?d=retro&s=200' %hashlib.md5(email.encode('utf-8')).hexdigest())
	await user.save()
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, _MAX_AGE), max_age=_MAX_AGE, httponly=True)
	user.passwd = "******"
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r

#验证登陆信息
@post('/api/authenticate')
async def authenticate(*, email, passwd):
	if not email:
		raise APIValueError('email', 'Invalid email')
	if not passwd:
		raise APIValueError('passwd', 'Invalid passwd')
	users = await User.find_all(where='email=?', args=email)
	if len(users) == 0:
		raise APIValueError('email', 'Email not exist')
	user = users[0]
	#check passwd
	sha1 = hashlib.sha1()
	sha1.update(user.id.encode())
	sha1.update(b':')
	sha1.update(passwd.encode())
	if  user.passwd != sha1.hexdigest():
		raise APIValueError('passwd', "Invalid passwd")

	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user,_MAX_AGE), max_age=_MAX_AGE, httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode()
	return r

#接收新的blog信息，并存入数据库
@post('/api/blogs')
async def create_new_blog(request,*, title, summary, content):
	check_admin(request)
	if not title or not title.strip():
		raise APIValueError('title','title cant be empty')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cant be empty')
	if not content or not content.strip():
		raise APIValueError('content', 'content cant be empty')
	blog = Blog(user_id = request.__user__.id, user_name = request.__user__.name, user_image=request.__user__.image, name = title.strip(), summary=summary.strip(),content=content)
	await blog.save()
	return blog

#获取blog数据
@get('/api/blogs/{id}')
async def api_get_blog(*,id):
	blog = await Blog.find_by_primaryKey(id)
	blog.title = blog.name
	return blog

#修改日志数据
@post('/api/blogs/{id}')
async def api_update_blog(id, request, *, title, summary,content):
	check_admin(request)
	blog = await Blog.find_by_primaryKey(id)
	if not title or not title.strip():
		raise APIValueError('name', "name can't be empty")
	if not summary or not summary.strip():
		raise APIValueError('summary', "summary can't be empty")
	if not content or not content.strip():
		raise APIValueError('content', "content can't be empty")
	blog.name = title.strip()
	blog.summary = summary.strip()
	blog.content = content.strip()
	await blog.update()
	return blog


#获取所有blog信息，并返回model数据
@get('/api/blogs')
async def api_blogs(*, page='1'):
	page_index = get_page_index(page)
	item_count = await Blog.find_number('count(id)')
	p = Page(item_count, page_index)
	if item_count == 0:
		return dict(page=p, blog={})
	blogs = await Blog.find_all(order_by='created_at desc', limit=(p.offset, p.limit))
	#logging.info('dict:%s'%dict(page=p, blogs=blogs))
	return dict(page=p, blogs=blogs)

#创建新评论
@post('/api/blogs/{id}/comments')
async def api_create_comment(id,request,*,content):
	if request.__user__ is None:
		raise APIPermissionError('Please signin first')
	if not content or not content.strip():
		raise APIValueError('content')
	blog = await Blog.find_by_primaryKey(id)
	if blog is None:
		raise APIResourceNotFound('blog')
	comment = Comment(blog_id=blog.id, user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image,content=content.strip())
	await comment.save()
	return comment


@post('/api/blogs/{id}/delete')
async def api_delete_blog(*, id):
	blog = await Blog.find_by_primaryKey(id)
	await blog.remove()
	return dict(blog=blog.id)

#获取users数据
@get('/api/users')
async def api_users(*,page='1'):
	page_index = get_page_index(page)
	item_count = await User.find_number('count(id)')
	p = Page(item_count,page_index)
	if item_count == 0:
		return dict(users={}, page=p)
	users = await User.find_all(order_by='created_at desc', limit=(p.offset, p.limit))
	for u in users:
		u.passwd = '******'
	return dict(page=p, users=users)

#获取评论
@get('/api/comments')
async def api_comments(*,page='1'):
	page_index = get_page_index(page)
	num = await Comment.find_number('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, comments={})
	comments = await Comment.find_all(order_by='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, comments=comments)

#删除评论
@post('/api/comments/{id}/delete')
async def api_delete_comment(id, request):
	check_admin(request)
	comment = await Comment.find_by_primaryKey(id)
	if comment is None:
		raise APIResourceNotFound('comment')
	await comment.remove()
	return dict(id=id)

#进入blog创建页面
@get('/manage/blogs/create')
def manage_create_blog():
	return{
		'__template__':'manage_blog_edit.html',
		'id':'',
		'action':'/api/blogs'
	}

#进入blog管理页面
@get('/manage/blogs')
def manage_blogs(*,page='1'):
	return {
		'__template__': 'manage_blogs.html',
		'page_index': get_page_index(page)
	}

@get('/manage/')
def manage():
	return 'redirect:/manage/comments'

#进入users管理页面
@get('/manage/users')
def manage_users(*,page='1'):
	return {
		"__template__" : 'manage_users.html',
		'page_index': get_page_index(page)
	}

#修改日志页
@get('/manage/blogs/edit')
def manage_edit_blog(*, id):
	logging.info('query id:%s'%id)
	return {
		'__template__':'manage_blog_edit.html',
		'id': id,
		'action':'/api/blogs/%s'%id
	}

#进入comment管理页面
@get('/manage/comments')
def manage_comments(*,page='1'):
	return{
		"__template__":'manage_comments.html',
		'page_index':get_page_index(page)
	}
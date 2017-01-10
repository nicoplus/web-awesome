import functools,inspect
from aiohttp import web
from urllib import parse
import logging
from apis import APIError
import asyncio
import os.path

def get(path):
	'''define decorator @get('/path')'''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = 'GET'
		wrapper.__route__ = path
		return wrapper
	return decorator

def post(path):
	'''define decorator @post('/path')'''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = 'POST'
		wrapper.__route__ = path
		return wrapper
	return decorator

def get_required_kw_arg(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
			args.append(name)
	return tuple(args)

def get_named_kw_arg(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)

def has_named_kw_arg(fn):
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			return True 

def has_var_kw_arg(fn):
	params = inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind == inspect.Parameter.VAR_KEYWORD:
			return True

def has_request_arg(fn):
	params = inspect.signature(fn).parameters
	found =False
	for name,param in params.items():
		if name == 'request':
			found = True
			continue
		if found and (param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD and param.kind != inspect.Parameter.VAR_POSITIONAL):
			raise ValueError(" parameter 'request' must be last named postionl argumment in function %s %S" %(fn.__name__, str(inspect.signature(fn))))
	return found

class RequestHandler(object):
	def __init__(self, fn):
		self._func = fn
		self._has_named_kw_arg = has_named_kw_arg(fn) #是否有关键字参数
		self._has_var_kw_arg = has_var_kw_arg(fn)     #是否有可变关键字参数
		self._has_request_arg = has_request_arg(fn)   #是否有request参数
		self._required_arg = get_required_kw_arg(fn)  #所有未设默认值关键词参数
		self._named_kw_arg = get_named_kw_arg(fn)     #所有关键词参数

	async def __call__(self, request):
		kw = None
		if self._has_var_kw_arg or self._has_named_kw_arg :
			if request.method == 'POST':
				if not request.content_type:
					return web.HTTPBadRequest('Missing content-type')
				ct = request.content_type.lower()
				if ct.startswith('application/json'):
					param = await request.json()
					if not isinstance(param , dict):
						return web.HTTPBadRequest('json body must be object')
					kw = param
				elif ct.startswith('application/x-www-form-urlencoded') or  ct.startswith('multipart/form-data'):
					param = await request.post()
					kw = dict(**param)
				else:
					return web.HTTPBadRequest('unsupported content-type %s' %request.content_type)
			if request.method == 'GET':
				qs = request.query_string
				if qs:
					kw =dict()
					for k,v in parse.parse_qs(qs).items():
						kw[k] = v[0]

		if kw == None:
			kw = dict(**request.match_info)
		else:
			if self._has_named_kw_arg and self._named_kw_arg:
				copy = dict()
				for name in self._named_kw_arg:
					if name in kw:
						copy[name] = kw[name]
				kw = copy
			for k,v in request.match_info.items():
				if k in kw:
					logging.warning('duplicated argu for in name argu and kw argu')
				kw[k] = v
		if self._has_request_arg:
			kw['request']=request


		for name in self._required_arg:
			if not name in kw:
				return web.HTTPBadRequest('missing argu %s' %name)
		logging.info('call with args:%s' %str(kw))

		try:
			r = await self._func(**kw)
			return r
		except APIError as e:
			return dict(error = e.error, data=e.data, message=e.message)

def add_routes(app, module_name):
	try:
		mod = __import__(module_name, fromlist=['not empty'])
	except ImportError as e:
		raise e
	for attr in dir(mod):
		if attr.startswith('_'):
			continue
		fn=getattr(mod,attr)

		if callable(fn) and hasattr(fn, '__method__') and hasattr(fn, '__route__'):
			async_fn = asyncio.coroutine(fn)
			args = ','.join(inspect.signature(fn).parameters.keys())
			logging.info('add route %s %s --->> %s(%s) ' %(async_fn.__method__, async_fn.__route__, async_fn.__name__, args))
			app.router.add_route(async_fn.__method__, async_fn.__route__, RequestHandler(async_fn))
	
def add_static(app):
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
	app.router.add_static('/static/', path)
	logging.info('add static %s-->> %s' %('/static/', path))



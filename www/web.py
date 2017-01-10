#! /usr/bin/pytohn3
import logging;
from aiohttp import web
import asyncio
from coroweb import add_routes,add_static
import orm
from jinja2 import Environment,FileSystemLoader
import os
import json
import time,datetime, handlers
def init_jinja2(app, **kw):
	logging.info('init jinja2...')
	options=dict(
		autoescape=kw.get('autoescape', True),
		block_start_string=kw.get('block_start_string', '{%'),
		block_end_string=kw.get('block_end_string','%}'),
		variable_start_string=kw.get('variable_start_string', '{{'),
		variable_end_string=kw.get('variable_end_string', '}}'),
		auto_reload=kw.get('auto_reload', True))
	path = kw.get('path', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
	logging.info('set jinja2 templates path: %s' %path)
	env = Environment(loader=FileSystemLoader(path), **options)
	filters = kw.get('filters',None)
	if filters is not None:
		for name,filter in filters.items():
			env.filters[name] = filter
	app['__templating__'] = env

async def logger_factory(app, handler):#handler=RequestHandler(fn),通过app.router.add_route()传入RequestHandler实例
	async def logger(request):
		logging.info('Request: %s %s' %(request.method, request.path))
		logging.info('Request.match_info: %s' %request.match_info)
		return (await handler(request)) 
	return logger

async def response_factory(app, handler):#handler=RequestHandler(fn)
	async def response(request):
		logging.info('Response handler...')
		r = await handler(request)
		if isinstance(r, web.StreamResponse):
			return r
		if isinstance(r,bytes):
			resp = web.Response(body=r)
			resp.content_type='application/octet-stream'
			return resp
		if isinstance(r,str):
			if r.startswith('redirect:'):
				return web.HTTPFound(r[9:])
			resp = web.Response(body=r.encode('utf-8'))
			resp.content_type = 'text/html;charset=utf-8'
			return resp

		if isinstance(r,dict):
			template = r.get('__template__', None)
			#logging.info('r %s;template %s'%(r, template))
			if template is None:
				js = json.dumps(r, ensure_ascii=False, default=lambda obj:obj.__dict__).encode('utf-8')
				resp = web.Response(body=js)
				resp.content_type='application/json;charset=utf-8'
				return resp
			else:
				r['__user__'] = request.__user__
				resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
				resp.content_type='text/html;charset=utf-8'
				return resp#此处content_type为动态绑定，之后可以试试在初始化时赋值是否有区别
		if isinstance(r, int) and r>=100 and r<600:
			return web.Response(r)
		if isinstance(r, tuple) and len(r) == 2:
			s,m = tuple
			if isinstance(s,int) and s >= 100 and s<600:
				return web.Response(s,str(m))
		#default
		resp = web.Response(body=str(r).encode('utf-8'))
		resp.content_type='text/html;charset=utf-8'
		return resp
	return response

async def auth_factory(app,handler):
	async def authenticate(request):
		logging.info('check user: %s %s' %(request.method, request.path))
		cookie = request.cookies.get(handlers.COOKIE_NAME)
		#logging.info('cookie: %s'%cookie)
		request.__user__ = None
		if cookie:
			user = await handlers.cookie2user(cookie)
			if user:
				logging.info('set current user: %s' %user.email)
				request.__user__ = user
		if request.path.startswith('/manage/') and  (request.__user__ is None or not request.__user__.admin):
			return web.HTTPFound('/signin')
		return (await handler(request))
	return authenticate


def datetime_fiter(t):
	delta = time.time()-t
	if delta<60:
		return u'1分钟前'
	if delta<3600:
		return '%s分钟前'%(delta//60)
	if delta<86400:
		return '%s小时前'%(delta//3600)
	if delta<604800:
		return u'%s天前'%(delta//86400)
	dt = datetime.datetime.fromtimestamp(delta)
	return '%s年 %s月 %s日' %(dt.year, dt.month, dt.day)



async def init(loop):


	await orm.create_pool(user='root', password='jc1992', db='awesome', loop=loop)
	app = web.Application(loop=loop, middlewares=[logger_factory,auth_factory,response_factory])
	init_jinja2(app, filters=dict(datetime=datetime_fiter))
	add_routes(app, 'handlers')
	add_static(app)
	srv = await loop.create_server(app.make_handler(),'127.0.0.1', 4000)
	logging.info('server start in 127.0.0.1:4000')
	return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()

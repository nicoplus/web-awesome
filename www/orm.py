import aiomysql
import logging; logging.basicConfig(level='INFO')
import asyncio

async def create_pool(loop, **kw):
	logging.info('create connection pool...')
	global __pool
	__pool = await aiomysql.create_pool(
		host = kw.get('host', 'localhost'),
		port = kw.get('port', 3306),
		user = kw['user'],
		password = kw['password'],
		db = kw['db'],
		charset = kw.get('charset', 'utf8'),
		autocommit = kw.get('autocommit', True),
		maxsize = kw.get('maxsize', 10),
		minsize = kw.get('minsize', 1),
		loop = loop)

async def destroy_pool():
	global __pool
	logging.info('destroy pool...')
	__pool.close()
	await __pool.wait_closed()

async def select(sql,args,size=None):
	global __pool
	async with  __pool.get() as conn:
		cur = await conn.cursor(aiomysql.DictCursor)
		await cur.execute(sql.replace('?','%s'), args or ())

		if size:
			rs = await cur.fetchmany(size)
		else:
			rs = await cur.fetchall()
		await cur.close()
		logging.info('rows returned:%s' %len(rs))
		return rs

async def execute(sql,args,autocommit=True):
	logging.info(sql)
	async with __pool.get() as conn:
		if not autocommit:
			await conn.begin()
		try:
			async with conn.cursor(aiomysql.DictCursor) as cur:
				await cur.execute(sql.replace('?', '%s'), args)

				affected = cur.rowcount
			if not autocommit:
				await conn.commit()
		except BaseException as e:
			if not autocommit:
				await conn.rollback()
			raise

		return affected

def create_args_string(num):
	L=[]
	for l in range(num):
		L.append('?')
	return ','.join(L)

class Field(object):
	"""docstring for Field"""
	def __init__(self, name, colum_type, primary_key, default):
		self.name = name
		self.colum_type = colum_type
		self.primary_key = primary_key
		self.default = default
	def __str__(self):
		return '<%s %s:%s>' %(self.__class__.name, sel.name, self.colum_type)

class StringField(Field):
	def __init__(self, name=None, colum_type='varchar(100)', primary_key=False, default=None):
			super().__init__(name, colum_type, primary_key, default)

class IntegerField(Field):
	def __init__(self, name=None, primary_key=False,default=0):
		super().__init__(name, 'bigint', primary_key,default)

class FloatField(Field):
	def __init__(self, name=None, primary_key=False, default=0.0):
		super().__init__(name, 'real', primary_key, default)

class TextField(Field):
	def __init__(self, name=None, default=None):
		super().__init__(name, 'Text', False, default)

class BooleanField(Field):
	def __init__(self, name=None, default=False):
		super().__init__(name, 'boolean', False, default)


class ModelMetaClass(type):
	def __new__(cls, name, bases, attrs):
		if name == 'Model':
			return type.__new__(cls, name, bases, attrs)

		tableName = attrs.get('__table__', None) or name
		logging.info('found modul %s : table %s'%(name, tableName))
		mappings = dict()
		fields=[]
		attr_primaryKey = None

		for k,v in attrs.items():
			if isinstance(v,Field):
				mappings[k] = v
				if v.primary_key:
					if attr_primaryKey:
						raise RuntimeError('duplicate primarykey is set...')
					attr_primaryKey = k
				else:
					fields.append(k)
		if not attr_primaryKey:
			raise RuntimeError('keyprimary is not set...')
		for k in mappings.keys():
			attrs.pop(k)

		escaped_field = list(map(lambda f:'`%s`' %f, fields))

		attrs['__table__'] = tableName
		attrs['__mappings__'] = mappings
		attrs['__keyprimary__'] = attr_primaryKey
		attrs['__fields__'] = fields
		attrs['__select__'] = 'select `%s`,%s from `%s`' %(attr_primaryKey, ','.join(escaped_field), tableName)
		attrs['__insert__'] = 'insert into `%s`(%s,`%s`) values (%s)' %(tableName,
			 ','.join(escaped_field),
			attr_primaryKey,  
			create_args_string(len(escaped_field)+1))

		attrs['__update__'] = 'update `%s` set %s where `%s` = ?'%(tableName,
			','.join(map(lambda f : '`%s`=?'%(mappings.get(f).name or f), fields)), 
			attr_primaryKey)
		logging.info(attrs['__update__'])
		attrs['__delete__'] = 'delete from `%s` where `%s` = ?' %(tableName, attr_primaryKey)

		return type.__new__(cls, name, bases, attrs)  


class Model(dict, metaclass = ModelMetaClass):
		"""docstring for Model"""
		def __init__(self, **kw):
			super(Model, self).__init__(**kw)
		def __getattr__(self, key):
			try:
				return self[key]
			except KeyError:
				raise AttributeError(r"'Model' object has no attribute '%s'" % key)


		def __setattr__(self, key, value):
			self[key] = value

		def getValue(self, key):
			return getattr(self, key, None)

		def getValueOrDefault(self, key):
			value = getattr(self, key, None)
			if value is None:
				field = self.__mappings__[key]
				if field.default is not None:
					value = field.default() if callable(field.default) else field.default
					logging.debug('useing default vlalue for %s:%s' %(key, str(value)))
					setattr(self, key, value)
			return value
			
		@classmethod
		async def find_by_primaryKey(cls, pk):
			result = await select('%s where `%s` = ?' %(cls.__select__, cls.__keyprimary__), [pk], 1)
			if len(result) == 0:
				return None
			return cls(**result[0]) #result是一个包含所有所有查询结果的list，list里用dict装了每行数据。[{},{}...]

		async def save(self):
			args=list(map(self.getValueOrDefault, self.__fields__))
			args.append(self.getValueOrDefault(self.__keyprimary__))
			logging.info('save args: %s'%args)
			rows = await execute(self.__insert__, args)
			if rows !=1:
				logging.warn('failed to insert data: affected rows:%s' %rows)

		@classmethod
		async def find_all(cls, where=None, args=None,**kw):
			sql = [cls.__select__]
			if where:
				sql.append('where')
				sql.append(where)
			if args is None:
				args=[]

			order_by=kw.get('order_by', None)
			if order_by:
				sql.append('order by')
				sql.append(order_by)
			
			limit=kw.get('limit')
			if limit is not None:
				sql.append('limit')
				if isinstance(limit,int):
					args.append(limit)
				elif isinstance(limit, tuple) and len(limit)==2:
					sql.append('?,?')
					args.extend(limit)
				else:
					raise ValueError('invalid limit value %s'%limit)
			logging.info('FINDALL :%s %s'%(' '.join(sql), args))
			results = await select(' '.join(sql), args)
			return [cls(**r) for r in results]

		@classmethod
		async def find_number(cls, slecteField, where=None, args=None):
			sql=['select %s _num_ from `%s`' %(slecteField, cls.__table__)]
			if where:
				sql.append('where')
				sql.append(where)
			rs = await select(' '.join(sql), args, 1)
			if rs==0:
				return None
			#logging.info('find_number: %s' %rs)
			#logging.info('find_number: %s'%type(rs[0]['_num_']))
			return rs[0]['_num_']

		
		async def update(self):
			args = list(map(self.getValue, self.__fields__))
			args.append(self.getValue(self.__keyprimary__))
			rows = await execute(self.__update__, args)
			if rows !=1:
				logging.warn('railed to update by primarykey: affected rows : %s' %rows)

		async def remove(self):
			args = [self.getValue(self.__keyprimary__)]
			rows = await execute(self.__delete__, args)
			if rows != 1:
				logging.warn('failed to remove by primarykey: affected rows:%s' % rows)




					



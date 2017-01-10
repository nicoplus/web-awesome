import config_default

def merge(default, override):
	r = {}
	for k,v in default.items():
		if k in override:
			if isinstance(v, dict):
				r[k] = merge(v,override[k])
			else:
				r[k] = override[k]
		else:
			r[k] = v
	return r

class Dict(dict):
	def __init__(self, keys=(), values=(), **kw):
		super(Dict, self).__init__(**kw)

		for k,value in zip(keys, values):
			self[k] = value

	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError as e:
			raise ValueError('has no attribute : %s' %key)

	def __setattr__(self, key, value):
		self[key] = value

def toDict(s):
	D = Dict()
	for k,v in s.items():
		D[k] = toDict(v) if isinstance(v,dict) else v
	return D

configs = config_default.configs
try:
	import confing_overrdie
	configs = merge(configs, confing_overrdie.configs)
except ImportError:
	pass

configs = toDict(configs)
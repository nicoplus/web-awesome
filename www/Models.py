from orm import Model, StringField, BooleanField, FloatField, TextField
import time, uuid
def next_id():
	t = time.time()
	return '%015d%s000'%(int(t*1000), uuid.uuid4().hex)
	''' %015d 是一个15位的数字，开头用0占位
		uuid.uuid4.hex 是一个32位哈希随机字符串'''

class User(Model):
	__table__ = 'users'

	id = StringField(primary_key=True, default=next_id, colum_type='varchar(50)')
	email = StringField(colum_type='varchar(50)')
	passwd = StringField(colum_type = 'varchar(50)')
	admin = BooleanField()
	name = StringField(colum_type='varchar(50)')
	image = StringField(colum_type='varchar(500)')
	created_at = FloatField(default=time.time)

class Blog(Model):
	__table__= 'blogs'

	id	= StringField(primary_key=True, default=next_id, colum_type='varchar(50)')
	user_id = StringField(colum_type='varchar(50)')
	user_name = StringField(colum_type='varchar(50)')
	user_image = StringField(colum_type='varchar(50)')
	name = StringField(colum_type='varchar(50)')
	summary = StringField(colum_type='varchar(200)')
	content = TextField()
	created_at = FloatField(default=time.time)

class Comment(Model):
	__table__ = 'comments'

	id = StringField(primary_key=True, default=next_id, colum_type='varchar(50)')
	blog_id = StringField(colum_type='varchar(50)')
	user_id = StringField(colum_type='varchar(50)')
	user_name = StringField(colum_type='varchar(50)')
	user_image = StringField(colum_type='varchar(50)')
	content = TextField()
	created_at = FloatField(default=time.time)

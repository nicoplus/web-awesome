import orm
from Models import Blog, User, Comment
import asyncio
import logging
logging.basicConfig(level=logging.INFO)

async def test_save(loop):
	await orm.create_pool(user='root', password='jc1992', db='awesome',loop=loop,host='127.0.0.1')
	#u = User(name='test_save', email='test_save4@example.com', passwd='123456', image='about:blank',id='001480740675917b0932c8ef799414881b5b1bd1aa2f336000')
	#u = await User().find_by_primaryKey('001482229739713a5b772a26cd049f1a47a7afa0223a6c8000')
	#rs= await User.find_all(where = 'name = ?', args=['test'])
	num = await User.find_number('count(id)')
	await orm.destroy_pool()
	print(num)

if __name__ == '__main__':
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test_save(loop))

        loop.close()
#save,update,remove,select,find_all成功，find_number也走的通，但不知道是干嘛的
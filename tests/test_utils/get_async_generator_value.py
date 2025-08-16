

# 测试时，有时候经过async修饰的fixture对象在其他测试用例中使用时会被当做async generator对象，因此需要通过下面这种方法获取真实值
async def get_async_generator_value(async_generator):
    return (await anext(async_generator)) if str(type(async_generator)) == "<class 'async_generator'>" else async_generator








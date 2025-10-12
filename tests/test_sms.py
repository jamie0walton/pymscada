"""Test SMS functionality."""
import asyncio
from datetime import datetime
import os
import pytest
from pymscada.iodrivers.sms import SMS, RUT241
from pymscada.tag import Tag


# set your username, password and phone number in the environment
# these tests send a message to your phone and await a response,
# so you need to be able to respond.
@pytest.fixture
def env():
    return {
        'modem': 'rut241',
        'modem_ip': os.getenv('MSCADA_SMS_IP'),
        'username': os.getenv('MSCADA_SMS_USERNAME'),
        'password': os.getenv('MSCADA_SMS_PASSWORD'),
        'listen_port': 8080,
        'phone': os.getenv('MSCADA_SMS_PHONE')
    }


@pytest.mark.asyncio
async def test_rut241_login(env):
    d = RUT241(ip=env['modem_ip'], username=env['username'],
               password=env['password'], port=env['listen_port'])
    await d.login()
    assert d.token is not None
    await d.get_modem_info()
    assert d.modem is not None
    msg = f'Hi {datetime.now().strftime("%H:%M:%S")}'
    await d.send_sms(env['phone'], msg)


@pytest.mark.asyncio
async def test_rut241_listen_sms(env):
    event = asyncio.Event()
    data = None

    def callback(received_data):
        nonlocal data
        data = received_data
        event.set()

    d = RUT241(ip=env['modem_ip'], username=env['username'],
               password=env['password'], port=env['listen_port'],
               recv_cb=callback)
    await d.listen_sms()
    await event.wait()
    assert data is not None
    assert data['sms_number'] == env['phone']
    assert len(data['sms_message']) > 0
    await d.stop_listening()


@pytest.mark.asyncio
async def test_sms_send_recv(env):
    event = asyncio.Event()
    data = None

    def callback(tag: Tag):
        nonlocal data
        data = tag.value
        event.set()

    send = Tag('send', dict)
    recv = Tag('recv', dict)
    recv.add_callback(callback, bus_id=999)
    sms = SMS(bus_ip=None, bus_port=None,
              sms_send_tag='send',
              sms_recv_tag='recv',
              modem=env['modem'], modem_ip=env['modem_ip'],
              username=env['username'], password=env['password'],
              listen_port=env['listen_port'])
    await sms.start()
    send.value = ({
        'number': env['phone'],
        'message': f'Hi {datetime.now().strftime("%H:%M:%S")}'
    }, 1234, 999)
    await event.wait()
    assert data is not None
    assert data['number'] == env['phone']
    assert len(data['message']) > 0

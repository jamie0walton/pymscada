"""Connect to electricity market WITS to submit MW bid."""
import asyncio
from functools import partial
from ms import Log, BusApp, Tag, Config
from mel import WITSClient
import concurrent.futures

MODULE = 'witsclient'
LOG = Log(MODULE)

config = Config(MODULE)  # TODO used as a global
# tags = {}  # TODO used as a global


def cb(queue: asyncio.Queue, tag):
    """Run now if operator requests a run."""
    LOG.info(f"cb {tag.name} {tag.value}")
    if tag.value == 2:
        queue.put_nowait('operator command to run')


def cb_time(timetag: Tag, tag: Tag):
    """Display time of good update."""
    LOG.info(f"cb_time old {timetag.name} {timetag.value}"
             f" new {tag.name} {tag.value}")
    timetag.value = int(tag.time_us / 1e6), tag.time_us


def main_periodic(queue: asyncio.Queue, control: Tag, healthtag: Tag):
    """Run every second, triggers a timed run every 60."""
    LOG.debug(f"main_periodic {healthtag.name} {healthtag.value}"
              f" control {control.value}")
    if healthtag.value % 60 == 0 and control.value == 0:
        queue.put_nowait('timed run')


async def state_handler(app: BusApp, queue: asyncio.Queue):
    """Manage requests, which is a single blocking connection."""
    LOG.info('state_handler')
    loop = asyncio.get_running_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    witsclient = WITSClient(config)
    control = app.ctag('control')
    while True:
        action = await queue.get()
        LOG.info(f"state_handler got {action}")
        if control.value == 3:
            LOG.info('Off - no action')
            continue
        witsclient.current_tag_update(app.tags)
        if witsclient.currentTagDict != witsclient.futureTagDict or \
                control.value == 2:
            control.value = 1
            try:
                LOG.info('state_handler: do wits send')
                runexec = loop.run_in_executor(executor, partial(
                    witsclient.send, app.tags
                ))
                await asyncio.wait_for(runexec, 60)
                LOG.info('state_handler: send finished?')
            except asyncio.TimeoutError:
                LOG.error('Sending requests process timeout!')
                pass
            control.value = 0
        else:
            LOG.info('not send, same value')
            control.value = 0
            # await asyncio.sleep(1)
            # TODO ???  a delay may have solved the racing issue


async def main():
    """Run forever."""
    app = BusApp(MODULE)
    queue = asyncio.Queue()
    asyncio.create_task(state_handler(app, queue))
    control = app.ctag('control')
    app.health.add_callback(partial(main_periodic, queue, control))
    upload_time = app.ctag('upload_time')
    upload_id = app.ctag('upload_id')
    # app.tags['_wits_control'].add_callback(partial(cb, queue))
    control.add_callback(partial(cb, queue))
    upload_id.add_callback(partial(cb_time, upload_time))

    """Run forever."""
    await app.run()
    await app.await_until_end()


if __name__ == '__main__':
    asyncio.run(main())

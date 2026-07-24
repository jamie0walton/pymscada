# Roadmap for Planned Changes

## Create a Tags class in each module

```python
class Tags:
    """namespace for tags."""

    def __init__(self, tag_info: dict):
        """add the tags"""
        self.a_dict = TagDict('a_dict')
        self.a_int = TagInt('a_int')
        self.a_float = TagFloat('a_float')
        self.a_string = TagStr('a_string')
        # Create a list, is this safe?
        self.tags: list[TagTyped] = list(vars(self).values())
        self.tag_info = tag_info
    
    async def all_ready(self):
        """return when everything has a value"""
        while True:
            await asyncio.sleep(0.2)
            # wait until its clear a tag has a real None value
            # if it has an init value in tag_info, set to init
            done = True
            for tag in self.tags:
                if tag.is_none:
                    logging.info(f"{tag.name} value is None")
                    done = False
            if done:
                return
```

## Replace class Tag with TagTyped derived tags

Plan:
1. Inventory all uses of the legacy Tag API and classify each call by required tag type.
2. Migrate modules to use TagTyped-derived classes such as TagInt, TagFloat, TagBytes, or TagTyped where appropriate.
3. Update any affected constructors, callbacks, and tests to preserve existing behavior while removing the old Tag dependency.
4. Verify by running the relevant unit tests for tag handling, bus client behavior, and web/server integrations.

Relevant files:
- src/pymscada/tag.py
- src/pymscada/bus_client_tag.py
- src/pymscada/bus_client.py
- src/pymscada/www_server.py
- src/pymscada/console.py
- src/pymscada/history.py
- src/pymscada/alarms.py
- src/pymscada/math.py
- tests/test_tag.py
- tests/test_bus_client.py

Structural changes needed to achieve this change:
- some Tag class tags are created before a busclient
- TagTyped-derived classes require a busclient before the tag can be created

## Remove tags.yaml init processing from www_server.py

Plan:
1. Confirm where www_server currently depends on tag metadata init values.
2. Remove any init-driven value population from the web server path so tag initialization is no longer coupled to tags.yaml in www_server.py.
3. Keep tag metadata standardisation in place, but stop using it to seed runtime values for the web UI.
4. Verify that the web server still serves tags correctly and that no regression is introduced in tag subscription behavior.

Relevant files:
- src/pymscada/www_server.py
- src/pymscada/bus_client.py
- tests/test_bus_client.py

## Implement tags.yaml init processing in bus_server.py

Plan:
1. Trace how tags are created and updated in the bus server so init values can be applied at the server layer.
2. Add startup logic to seed tag values from tags.yaml metadata when a tag is first created or when the server starts.
3. Ensure the init value is applied once and is visible to subscribers without breaking existing bus protocol behavior.
4. Verify by adding or updating tests that cover startup initialization and normal tag updates.

Relevant files:
- src/pymscada/bus_server.py
- src/pymscada/tag.py
- src/pymscada/bus_client.py
- tests/test_bus_server.py

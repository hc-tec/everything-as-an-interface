# import asyncio
# import pytest

# from src.services.paged_collector import PagedCollector
# from src.services.xiaohongshu.collections.note_net_collection import NetCollectionState
# from src.utils.net_rules import ResponseView


# class DummyResponse:
#     def __init__(self, url: str = "http://test/"):
#         self.url = url


# def make_response_view(payload):
#     return ResponseView(DummyResponse(), payload)


# @pytest.mark.asyncio
# async def test_paged_collector_basic(monkeypatch):
#     q: asyncio.Queue = asyncio.Queue()

#     # Prepare state
#     state = NetCollectionState(page=None, queue=asyncio.Queue())  # page unused in test

#     # Parser returns items from payload
#     async def parser(payload):
#         return payload.get("items", [])

#     # Put two responses and then let timeout end
#     await q.put(make_response_view({"items": [1, 2], "code": 0}))
#     await q.put(make_response_view({"items": [3], "code": 0}))

#     # Patch ResponseView.data to return dict directly
#     # Not needed since we pass dict to ResponseView wrapper

#     collector = PagedCollector(
#         page=None,  # not used
#         queue=q,
#         state=state,
#         parser=parser,
#         response_timeout_sec=0.1,
#         delay_ms=0,
#         max_pages=None,
#     )

#     items = await collector.run()

#     assert items == [1, 2, 3]
#     # state should have recorded items
#     assert state.items == [1, 2, 3]
#     # raw responses recorded
#     assert len(state.raw_responses) == 2


# @pytest.mark.asyncio
# async def test_paged_collector_stop_decider():
#     q: asyncio.Queue = asyncio.Queue()
#     state = NetCollectionState(page=None, queue=asyncio.Queue())

#     async def parser(payload):
#         return payload.get("items", [])

#     # Provide two payloads but stop after first via decider
#     await q.put(make_response_view({"items": ["a"], "code": 0}))
#     await q.put(make_response_view({"items": ["b"], "code": 0}))

#     # Stop when we see item "a"
#     def stop_decider(page, all_raw, last_raw, all_items, last_batch, elapsed, extra, last_view):
#         return "a" in last_batch

#     state.stop_decider = stop_decider

#     collector = PagedCollector(
#         page=None,
#         queue=q,
#         state=state,
#         parser=parser,
#         response_timeout_sec=0.1,
#         delay_ms=0,
#         max_pages=None,
#     )

#     items = await collector.run()
#     assert items == ["a"]
#     assert state.items == ["a"]
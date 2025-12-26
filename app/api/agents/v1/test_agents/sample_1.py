import asyncio
import json
from typing import List

from fastapi import APIRouter, Form
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, FunctionMessage

from app.agent_utils.agent_service import get_agent_graph
from app.agent_utils.postgres_saver import CustomSyncPostgresSaver, CustomAsyncPostgresSaver
from app.api.deps import SessionDep, CurrentUser
from app.models.users.user import AgentRequest, ListMessages, ListThread

from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/sample")
async def sample_agent_v1():
    return {"message": "Hello, World!"}


@router.get("/get/agent/threads/")
async def get_agent_threads(
        session: SessionDep, current_user: CurrentUser
) -> List[ListThread]:
    user_id = current_user.id
    threads = []
    data = []
    with CustomSyncPostgresSaver.from_conn_string() as checkpointer:
        # checkpointer.list({})
        for v in checkpointer.user_list({}, user_id=user_id):
            if (
                    v.config.get("configurable").get("thread_id") not in threads
                    and v.checkpoint.get("channel_values", {}).get("messages", [None])[0]
            ):
                print(v.config.get("configurable").get("thread_id"), '-=-=-=--=-==--=-=--=-=-=')
                threads.append(v.config.get("configurable").get("thread_id"))
                data.append(
                    {
                        "thread_id": v.config.get("configurable").get("thread_id"),
                        "title": v.checkpoint.get("channel_values")
                        .get("messages")[0]
                        .content,
                    }
                )
    print('======================')
    return data  # get_threads(user_id=user_id, session=session)


@router.post("/get/agent/messages/")
async def get_agent_messages(
        request: AgentRequest, session: SessionDep, current_user: CurrentUser
) -> List[ListMessages]:
    data = []
    with CustomSyncPostgresSaver.from_conn_string() as checkpointer:
        checkpointer.list({})
        checkpoint = checkpointer.get_thread_data(
            {"configurable": {"thread_id": request.thread_id}}, user_id=current_user.id
        )
        if not checkpoint:
            return []
        for v in checkpoint.checkpoint.get("channel_values").get("messages"):
            if isinstance(v, HumanMessage):
                data.append({"type": "USER", "message": v.content})
            if isinstance(v, AIMessage) and len(v.content) > 0:
                data.append({"type": "AI", "message": v.content})
    return data


@router.post("/invoke/agent/")
async def invoke_agent(user: CurrentUser,
                                      thread_id: str = Form(...),
                                      message: str = Form(...)
                                      ):
    config = {"configurable": {"thread_id": thread_id, "user_id": user.id}}

    graph = get_agent_graph()

    input_message = {"messages": [{"role": "user", "content": message}]}

    async def stream_response():
        try:
            async with CustomAsyncPostgresSaver.from_conn_string() as checkpointer:
                agent = graph.compile(checkpointer=checkpointer)

                async for event in agent.astream_events(
                        input_message, version="v2", stream_mode="values", config=config
                ):
                    if event["event"] == "on_chat_model_stream":
                        content = event["data"]["chunk"].content
                        if content:
                            if isinstance(event["data"]["chunk"], (ToolMessage, FunctionMessage)):
                                continue
                            if isinstance(content, list) and content[0].get("text", None):
                                val = {"value": f'{content[0].get("text")}'}
                                await asyncio.sleep(0.5)
                                yield f"event: locationUpdate\ndata:{json.dumps(val)}\n\n"
                            elif isinstance(content, str):
                                val = {"value": f"{content}"}
                                await asyncio.sleep(0.5)
                                yield f"event: locationUpdate\ndata:{json.dumps(val)}\n\n"

        except Exception as ex:
            error_message = {"type": "error", "value": str(ex)}
            yield f"event: message\ndata: {json.dumps(error_message)}\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")

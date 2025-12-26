from datetime import datetime
from typing import TypedDict, Annotated, Dict

from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableConfig
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.errors import GraphInterrupt
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt.tool_node import ToolNode, tools_condition
from pydantic_core import ValidationError
from app.agent_utils.prompts import get_system_prompt
from app.agent_utils.tool_models import GetWeatherConfig, WeatherConfig
from app.core.config import settings



def create_tool_node_with_fallback(tools: list):
    def handle_error_robustly(state: dict):
        error = state.get("error")

        if isinstance(error, GraphInterrupt):
            raise error

        # Handle other tool failures
        content = ""
        if isinstance(error, ValidationError):
            for err in error.errors():
                content += err.get("msg")
        else:
            content = f"Tool execution failed: {repr(error)}"

        tool_calls = state["messages"][-1].tool_calls
        return {
            "messages": [
                ToolMessage(content=content, tool_call_id=tc["id"])
                for tc in tool_calls
            ]
        }

    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_error_robustly)],
        exception_key="error"
    )


# --- Tool 1: Weather (static city data) ---------------------------------------
CITY_WEATHER: Dict[str, str] = {
    "san_francisco": "18°C, foggy morning, sunny afternoon",
    "new_york": "22°C, partly cloudy",
    "london": "16°C, light rain",
    "mumbai": "29°C, humid with scattered showers",
    "tokyo": "24°C, clear skies",
    "ahmedabad": "14°C, thunder storm",
}


@tool(args_schema=GetWeatherConfig)
def get_weather(weather_config: WeatherConfig, config: RunnableConfig) -> str:
    """
    Return simple weather info for a city using a static lookup.

    Args:

        :param config:
        :param weather_config:
    """
    key = weather_config.city.strip().lower().replace(" ", "_")
    if key in CITY_WEATHER:
        return f"Weather in {weather_config.city}: {CITY_WEATHER[key]}"
    return f"Sorry, no weather data for '{weather_config.city}'. Try one of: {', '.join(sorted(CITY_WEATHER.keys()))}"


@tool
def sum_numbers(a: float, b: float, config: RunnableConfig = None, ) -> float:
    """
    Add two numbers and return the result.

    Args:
        :param a:
        :param b:
        :param config:
    """
    return a + b


class State(TypedDict):
    messages: Annotated[list, add_messages]


def get_tools():
    tools = [sum_numbers, get_weather]
    return tools


def get_llm(config: RunnableConfig):
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001", api_key=settings.GOOGLE_API_KEY)
    tools = get_tools()
    llm_with_tools = llm.bind_tools(tools)
    system_prompt = get_system_prompt()
    system_prompt += f"\nToday's date is {datetime.now().date()}"

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ('placeholder', '{messages}'),
        ]
    )

    return prompt | llm_with_tools


async def chatbot(state: State, config: RunnableConfig):
    messages = state.get("messages", [])

    # Ensure we have at least one message with user content
    if not messages:
        return {"messages": []}

    response = await get_llm(config).ainvoke({"messages": messages})
    return {"messages": [response]}


def get_agent_graph():
    graph_builder = StateGraph(State)
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", create_tool_node_with_fallback(get_tools()))
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.set_entry_point("chatbot")
    return graph_builder

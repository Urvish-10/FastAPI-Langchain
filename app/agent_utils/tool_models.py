from pydantic import BaseModel, Field


class WeatherConfig(BaseModel):
    """Configuration details for creating a new Jira Story."""

    city: str = Field(
        description="The name of the city where the weather will be requested."
    )



class GetWeatherConfig(BaseModel):
    """Argument schema for the create_jira_story tool."""

    weather_config: WeatherConfig = Field(
        description="The detailed configuration for the weather request."
    )

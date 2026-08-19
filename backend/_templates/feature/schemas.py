from pydantic import BaseModel


class ExampleRequest(BaseModel):
    name: str


class ExampleResponse(BaseModel):
    id: str
    name: str

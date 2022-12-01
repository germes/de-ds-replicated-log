import uvicorn
from fastapi import FastAPI, Response
from typing import Union
from pydantic import BaseModel
from starlette.responses import JSONResponse
from distributed_log.data_manager import get_data_manager_instance
import time


class DelayValue(BaseModel):
    value: int


class NewValue(BaseModel):
    value: str
    write_concern: Union[int, None] = None


class SyncValue(BaseModel):
    key: int
    value: str


app = FastAPI()
app.delay = 0  # for imitating delay during the testing


@app.post("/message", status_code=201)
def add_value(inpt: NewValue, response: Response):
    try:
        get_data_manager_instance().add_value(inpt.value, inpt.write_concern)
    except BaseException as err:
        return JSONResponse(str(err), status_code=405)

    return True


@app.put("/message", status_code=204)
def set_value(inpt: SyncValue, response: Response):
    # sleep for `delay` seconds and reset delay
    if app.delay > 0:
        delay = app.delay
        app.delay = 0
        time.sleep(delay)

    try:
        get_data_manager_instance().set_value(inpt.key, inpt.value)
    except BaseException as err:
        return JSONResponse(err, status_code=405)

    return None


@app.get("/messages", status_code=200)
def get_data(response: Response):
    return get_data_manager_instance().get_values()


@app.post("/delay")
def set_delay(inpt: DelayValue):
    """Technical endpoint to imitate replication delay"""
    app.delay = inpt.value

    return {'delay': app.delay}


@app.get("/delay")
def get_delay():
    """Technical endpoint to imitate delay on secondary instance"""
    return {'delay': app.delay}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

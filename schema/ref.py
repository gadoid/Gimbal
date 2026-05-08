from pydantic import BaseModel, Field, model_validator, ConfigDict

class RefBase(BaseModel) :
    ref : str 
